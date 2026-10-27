"""Offline behavioural checks for the Step 16 MFA security helpers."""

import ast
import copy
import hashlib
import os
import secrets
import types
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from cryptography.fernet import Fernet
from fastapi import HTTPException
from jose import jwt
import pyotp


SOURCE = Path(__file__).resolve().parents[1] / "app" / "core" / "security.py"
ROUTER_SOURCE = Path(__file__).resolve().parents[1] / "app" / "routers" / "auth.py"
DEPENDENCIES_SOURCE = Path(__file__).resolve().parents[1] / "app" / "core" / "dependencies.py"


def load_security_module() -> types.ModuleType:
    """Execute security helpers with synthetic settings and no dotenv file."""
    module = types.ModuleType("mfa_security_under_test")
    # A shallow synthetic path leaves _HOST_ENV_FILE unset in the module.
    module.__file__ = "security.py"
    key = Fernet.generate_key().decode("ascii")
    with patch.dict(
        os.environ,
        {
            "JWT_SECRET_KEY": secrets.token_urlsafe(32),
            "MFA_ENCRYPTION_KEY": key,
            "MFA_ISSUER": "OfflineTestIssuer",
        },
        clear=True,
    ):
        exec(compile(SOURCE.read_text(encoding="utf-8"), str(SOURCE), "exec"), module.__dict__)
    return module


def load_function(source_path: Path, name: str, namespace: dict[str, object]):
    source = ast.parse(source_path.read_text(encoding="utf-8"))
    function = copy.deepcopy(
        next(
            node
            for node in source.body
            if isinstance(node, ast.FunctionDef) and node.name == name
        )
    )
    function.decorator_list = []
    function.returns = None
    function.args.defaults = []
    function.args.kw_defaults = []
    for argument in (*function.args.posonlyargs, *function.args.args, *function.args.kwonlyargs):
        argument.annotation = None
    exec(
        compile(ast.Module(body=[function], type_ignores=[]), str(source_path), "exec"),
        namespace,
    )
    return namespace[name]


class MfaSecurityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.security = load_security_module()

    def test_access_and_mfa_tokens_have_strictly_separated_scopes(self) -> None:
        access_token = self.security.create_access_token("user-id", "candidate")
        mfa_token = self.security.create_mfa_token("user-id", "candidate")

        self.assertEqual(self.security.decode_access_token(access_token)["scope"], "access")
        self.assertEqual(self.security.decode_mfa_token(mfa_token)["scope"], "mfa")
        expires_at = jwt.get_unverified_claims(mfa_token)["exp"]
        remaining_seconds = expires_at - datetime.now(timezone.utc).timestamp()
        self.assertGreater(remaining_seconds, 270)
        self.assertLessEqual(remaining_seconds, 300)
        with self.assertRaises(HTTPException) as access_error:
            self.security.decode_access_token(mfa_token)
        self.assertEqual(access_error.exception.status_code, 401)
        with self.assertRaises(HTTPException) as mfa_error:
            self.security.decode_mfa_token(access_token)
        self.assertEqual(mfa_error.exception.status_code, 401)

    def test_tokens_without_scope_are_rejected(self) -> None:
        token = jwt.encode(
            {"sub": "user-id", "role": "candidate"},
            self.security.settings.jwt_secret_key,
            algorithm=self.security.settings.jwt_algorithm,
        )
        with self.assertRaises(HTTPException) as error:
            self.security.decode_access_token(token)
        self.assertEqual(error.exception.status_code, 401)

    def test_current_user_dependency_rejects_every_non_access_scope(self) -> None:
        class Field:
            def __eq__(self, value):
                return value

        class User:
            id = Field()

        class Session:
            def __enter__(self):
                return self

            def __exit__(self, *_):
                return None

            def scalar(self, _statement):
                return SimpleNamespace(id="user-id", role="candidate")

        namespace: dict[str, object] = {
            "SessionLocal": Session,
            "_trace_event": lambda *_args, **_kwargs: None,
            "decode_access_token": self.security.decode_access_token,
            "User": User,
            "select": lambda _: SimpleNamespace(where=lambda condition: condition),
        }
        get_current_user = load_function(DEPENDENCIES_SOURCE, "get_current_user", namespace)
        access_token = self.security.create_access_token("user-id", "candidate")
        self.assertEqual(
            get_current_user(SimpleNamespace(credentials=access_token)).id,
            "user-id",
        )
        missing_scope = jwt.encode(
            {"sub": "user-id", "role": "candidate"},
            self.security.settings.jwt_secret_key,
            algorithm=self.security.settings.jwt_algorithm,
        )
        unexpected_scope = self.security._create_scoped_token(
            "user-id", "candidate", "unexpected", 5
        )
        expired_access = self.security._create_scoped_token(
            "user-id", "candidate", "access", -1
        )
        invalid_signature = access_token[:-1] + ("a" if access_token[-1] != "a" else "b")
        for token in (
            self.security.create_mfa_token("user-id", "candidate"),
            missing_scope,
            unexpected_scope,
            expired_access,
            invalid_signature,
        ):
            with self.subTest(token_kind="non-access"):
                with self.assertRaises(HTTPException) as error:
                    get_current_user(SimpleNamespace(credentials=token))
                self.assertEqual(error.exception.status_code, 401)

    def test_totp_secret_is_encrypted_at_rest_and_decrypts(self) -> None:
        encrypted_secret = self.security.encrypt_totp_secret("synthetic-totp-secret")
        self.assertNotEqual(encrypted_secret, "synthetic-totp-secret")
        self.assertEqual(
            self.security.decrypt_totp_secret(encrypted_secret),
            "synthetic-totp-secret",
        )

    def test_router_declares_the_locked_totp_parameters(self) -> None:
        source = ast.parse(ROUTER_SOURCE.read_text(encoding="utf-8"))
        function = next(
            node
            for node in source.body
            if isinstance(node, ast.FunctionDef) and node.name == "_totp"
        )
        call = next(
            node
            for node in ast.walk(function)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "TOTP"
        )
        keywords = {keyword.arg: keyword.value for keyword in call.keywords}
        self.assertEqual(getattr(keywords["digits"], "value", None), 6)
        self.assertEqual(getattr(keywords["interval"], "value", None), 30)
        self.assertEqual(
            getattr(keywords["digest"], "attr", None),
            "sha1",
        )

    def test_totp_accepts_valid_code_and_rejects_invalid_code_offline(self) -> None:
        totp_factory = load_function(
            ROUTER_SOURCE,
            "_totp",
            {"pyotp": pyotp, "hashlib": hashlib},
        )
        totp = totp_factory("JBSWY3DPEHPK3PXP")
        valid_code = totp.at(30)
        invalid_code = ("0" if valid_code[0] != "0" else "1") + valid_code[1:]
        self.assertTrue(totp.verify(valid_code, for_time=30, valid_window=1))
        self.assertFalse(totp.verify(invalid_code, for_time=30, valid_window=1))

    def test_login_returns_a_challenge_only_for_mfa_enabled_users(self) -> None:
        class Field:
            def __eq__(self, value):
                return value

        class User:
            email = Field()

        login = load_function(
            ROUTER_SOURCE,
            "login",
            {
                "verify_password": lambda *_: True,
                "create_access_token": lambda **_: "access-token",
                "create_mfa_token": lambda **_: "mfa-token",
                "TokenResponse": lambda **kwargs: kwargs,
                "MFAChallengeResponse": lambda **kwargs: {"mfa_required": True, **kwargs},
                "HTTPException": HTTPException,
                "status": SimpleNamespace(HTTP_401_UNAUTHORIZED=401),
                "User": User,
                "select": lambda _: SimpleNamespace(where=lambda condition: condition),
            },
        )

        class Database:
            def __init__(self, user):
                self.user = user

            def scalar(self, _statement):
                return self.user

        request = SimpleNamespace(email="synthetic@example.test", password="synthetic")
        enabled = SimpleNamespace(
            id="user-id",
            role="candidate",
            password_hash="hash",
            mfa_enabled=True,
        )
        challenge = login(request, Database(enabled))
        self.assertEqual(challenge["mfa_token"], "mfa-token")
        self.assertTrue(challenge["mfa_required"])
        self.assertNotIn("access_token", challenge)

        disabled = SimpleNamespace(
            id="user-id",
            role="candidate",
            password_hash="hash",
            mfa_enabled=False,
        )
        access = login(request, Database(disabled))
        self.assertEqual(access["access_token"], "access-token")
        self.assertNotIn("mfa_token", access)

    def test_confirmation_enables_mfa_only_after_a_valid_code(self) -> None:
        class Database:
            def __init__(self, user):
                self.user = user
                self.commits = 0

            def get(self, _model, _user_id):
                return self.user

            def commit(self):
                self.commits += 1

        class Totp:
            def __init__(self, accepted: bool):
                self.accepted = accepted

            def verify(self, _code, valid_window):
                self.valid_window = valid_window
                return self.accepted

        def confirm(accepted: bool):
            user = SimpleNamespace(id="user-id", role="candidate", mfa_enabled=False, totp_secret_encrypted="ciphertext")
            database = Database(user)
            handler = load_function(
                ROUTER_SOURCE,
                "confirm_mfa",
                {
                    "User": object,
                    "decrypt_totp_secret": lambda _: "synthetic-secret",
                    "_totp": lambda _: Totp(accepted),
                    "MFAConfigurationError": RuntimeError,
                    "_mfa_configuration_error": lambda: HTTPException(503, "unavailable"),
                    "HTTPException": HTTPException,
                    "status": SimpleNamespace(
                        HTTP_400_BAD_REQUEST=400,
                        HTTP_401_UNAUTHORIZED=401,
                    ),
                    "TokenResponse": lambda **kwargs: kwargs,
                    "create_access_token": lambda *_: "access-token",
                },
            )
            return handler, user, database

        handler, user, database = confirm(True)
        result = handler(SimpleNamespace(code="123456"), user, database)
        self.assertTrue(user.mfa_enabled)
        self.assertEqual(database.commits, 1)
        self.assertEqual(result["access_token"], "access-token")

        handler, user, database = confirm(False)
        with self.assertRaises(HTTPException) as error:
            handler(SimpleNamespace(code="123456"), user, database)
        self.assertEqual(error.exception.status_code, 400)
        self.assertFalse(user.mfa_enabled)
        self.assertEqual(database.commits, 0)

    def test_setup_persists_only_ciphertext_and_keeps_mfa_disabled(self) -> None:
        class Database:
            def __init__(self, user):
                self.user = user
                self.commits = 0

            def get(self, _model, _user_id):
                return self.user

            def commit(self):
                self.commits += 1

        class Totp:
            def provisioning_uri(self, *, name, issuer_name):
                return f"otpauth://totp/{issuer_name}:{name}?issuer={issuer_name}"

        user = SimpleNamespace(
            id="user-id",
            email="synthetic@example.test",
            mfa_enabled=False,
            totp_secret_encrypted=None,
        )
        database = Database(user)
        setup = load_function(
            ROUTER_SOURCE,
            "setup_mfa",
            {
                "User": object,
                "pyotp": SimpleNamespace(random_base32=lambda: "synthetic-totp-secret"),
                "encrypt_totp_secret": lambda _: "ciphertext-only",
                "_totp": lambda _: Totp(),
                "settings": SimpleNamespace(mfa_issuer="OfflineTestIssuer"),
                "MFAConfigurationError": RuntimeError,
                "_mfa_configuration_error": lambda: HTTPException(503, "unavailable"),
                "HTTPException": HTTPException,
                "status": SimpleNamespace(
                    HTTP_401_UNAUTHORIZED=401,
                    HTTP_409_CONFLICT=409,
                ),
                "MFASetupResponse": lambda **kwargs: kwargs,
            },
        )
        result = setup(user, database)
        self.assertEqual(user.totp_secret_encrypted, "ciphertext-only")
        self.assertFalse(user.mfa_enabled)
        self.assertEqual(database.commits, 1)
        self.assertIn("OfflineTestIssuer", result["provisioning_uri"])


if __name__ == "__main__":
    unittest.main()

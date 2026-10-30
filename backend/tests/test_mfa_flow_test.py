"""Offline safety checks for the owner-run Step 16 MFA flow harness."""

import importlib.util
import sys
import tempfile
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[2] / "docs" / "da3" / "scripts" / "mfa_flow_test.py"
SPEC = importlib.util.spec_from_file_location("mfa_flow_harness", SCRIPT)
if SPEC is None or SPEC.loader is None:  # pragma: no cover - import-time guard
    raise RuntimeError("Unable to load MFA flow harness")
HARNESS = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = HARNESS
SPEC.loader.exec_module(HARNESS)


class MfaFlowHarnessTests(unittest.TestCase):
    def test_result_path_is_confined_and_requested_collisions_fail_closed(self) -> None:
        self.assertEqual(HARNESS.DEFAULT_RESULT_PATH.name, "16-mfa-flow.md")
        with tempfile.TemporaryDirectory(dir=HARNESS.RESULTS_DIRECTORY) as temporary:
            result_path = Path(temporary) / "20-mfa-hardened-regression.md"
            parsed = HARNESS.parse_result_path(str(result_path))
            self.assertEqual(parsed, result_path.resolve())
            HARNESS.ensure_requested_result_path_is_unused(parsed)
            parsed.write_text("preserved", encoding="utf-8")
            with self.assertRaises(RuntimeError):
                HARNESS.ensure_requested_result_path_is_unused(parsed)
        for value in ("../outside.md", "docs/da3/results/../outside.md", "docs/da3/results/result.txt"):
            with self.subTest(value=value):
                with self.assertRaises(Exception):
                    HARNESS.parse_result_path(value)

    def test_response_parser_rejects_malformed_or_non_object_json(self) -> None:
        class Response:
            def __init__(self, value):
                self.value = value

            def json(self):
                if isinstance(self.value, Exception):
                    raise self.value
                return self.value

        self.assertIsNone(HARNESS.FlowRunner.json_object(Response(ValueError())))
        self.assertIsNone(HARNESS.FlowRunner.json_object(Response([])))
        self.assertIsNone(HARNESS.FlowRunner.json_value(Response({"token": None}), "token"))
        self.assertEqual(
            HARNESS.FlowRunner.json_value(Response({"token": "synthetic"}), "token"),
            "synthetic",
        )
        self.assertEqual(
            HARNESS.FlowRunner.mfa_challenge_token(
                Response({"mfa_required": True, "mfa_token": "synthetic"})
            ),
            "synthetic",
        )
        self.assertIsNone(
            HARNESS.FlowRunner.mfa_challenge_token(
                Response(
                    {
                        "mfa_required": True,
                        "mfa_token": "synthetic",
                        "access_token": None,
                    }
                )
            )
        )

    def test_token_tampering_changes_only_the_signature_segment(self) -> None:
        original = "header.payload.signature"
        tampered = HARNESS.FlowRunner.tamper_signed_token(original)
        self.assertIsNotNone(tampered)
        self.assertEqual(tampered.split(".")[:2], original.split(".")[:2])
        self.assertNotEqual(tampered.split(".")[2], original.split(".")[2])
        self.assertIsNone(HARNESS.FlowRunner.tamper_signed_token("not-a-jwt"))

    def test_cleanup_falls_back_to_exact_email_and_is_idempotent(self) -> None:
        class Field:
            def __eq__(self, value):
                return value

        class User:
            id = Field()
            email = Field()

        class Session:
            def __enter__(self):
                return self

            def __exit__(self, *_):
                return None

            def scalar(self, _statement):
                return "derived-user-id"

            def execute(self, _statement):
                return SimpleNamespace(rowcount=1)

            def commit(self):
                return None

        database_module = types.ModuleType("app.database")
        database_module.SessionLocal = Session
        user_module = types.ModuleType("app.models.user")
        user_module.User = User
        app_module = types.ModuleType("app")
        models_module = types.ModuleType("app.models")

        runner = HARNESS.FlowRunner("http://localhost:8080", {})
        runner.signup_attempted = True
        runner.created_email = "da3-mfa-synthetic@example.test"

        with patch.dict(
            sys.modules,
            {
                "app": app_module,
                "app.database": database_module,
                "app.models": models_module,
                "app.models.user": user_module,
            },
        ), patch.object(
            HARNESS,
            "select",
            lambda _: SimpleNamespace(where=lambda condition: condition),
        ), patch.object(
            HARNESS,
            "delete",
            lambda _: SimpleNamespace(where=lambda *conditions: conditions),
        ):
            runner.cleanup()
            runner.cleanup()

        cleanup_results = [item for item in runner.results if item.step == "Clean up synthetic MFA user"]
        self.assertEqual(len(cleanup_results), 1)
        self.assertTrue(cleanup_results[0].passed)


if __name__ == "__main__":
    unittest.main()

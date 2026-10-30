from datetime import datetime, timedelta, timezone
from pathlib import Path

from argon2 import PasswordHasher
from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException, status
from jose import JWTError, jwt
from pydantic_settings import BaseSettings, SettingsConfigDict


_MODULE_PARENTS = Path(__file__).resolve().parents
# Local development retains the owner-managed external dotenv path.  The
# container image has fewer path parents, so Compose supplies its settings
# through process environment variables instead of attempting this lookup.
_HOST_ENV_FILE = (
    _MODULE_PARENTS[4] / ".env" if len(_MODULE_PARENTS) > 4 else None
)


class SecuritySettings(BaseSettings):
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    mfa_encryption_key: str | None = None
    mfa_issuer: str = "ResumePortal"

    model_config = SettingsConfigDict(
        env_file = _HOST_ENV_FILE,
        extra="ignore",
    )


settings = SecuritySettings()

password_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return password_hasher.verify(password_hash, password)
    except Exception:
        return False


def _create_scoped_token(
    user_id: str,
    role: str,
    scope: str,
    expires_in_minutes: int,
    mfa_enabled: bool | None = None,
) -> str:
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=expires_in_minutes)

    payload = {
        "sub": user_id,
        "role": role,
        "scope": scope,
        "exp": expires_at,
    }
    if mfa_enabled is not None:
        payload["mfa_enabled"] = mfa_enabled

    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def create_access_token(user_id: str, role: str, *, mfa_enabled: bool) -> str:
    return _create_scoped_token(
        user_id,
        role,
        scope="access",
        expires_in_minutes=settings.access_token_expire_minutes,
        mfa_enabled=mfa_enabled,
    )


def create_mfa_token(user_id: str, role: str) -> str:
    return _create_scoped_token(user_id, role, scope="mfa", expires_in_minutes=5)


def _decode_scoped_token(token: str, expected_scope: str) -> dict:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )

        user_id = payload.get("sub")
        role = payload.get("role")

        if not user_id or not role or payload.get("scope") != expected_scope:
            raise credentials_exception

        return payload

    except JWTError as exc:
        raise credentials_exception from exc


def decode_access_token(token: str) -> dict:
    return _decode_scoped_token(token, expected_scope="access")


def decode_mfa_token(token: str) -> dict:
    return _decode_scoped_token(token, expected_scope="mfa")


class MFAConfigurationError(RuntimeError):
    pass


def _mfa_fernet() -> Fernet:
    if not settings.mfa_encryption_key:
        raise MFAConfigurationError("MFA encryption is not configured")
    try:
        return Fernet(settings.mfa_encryption_key.encode("utf-8"))
    except (TypeError, ValueError) as exc:
        raise MFAConfigurationError("MFA encryption is not configured") from exc


def encrypt_totp_secret(secret: str) -> str:
    return _mfa_fernet().encrypt(secret.encode("utf-8")).decode("utf-8")


def decrypt_totp_secret(encrypted_secret: str) -> str:
    try:
        return _mfa_fernet().decrypt(encrypted_secret.encode("utf-8")).decode("utf-8")
    except (InvalidToken, UnicodeDecodeError) as exc:
        raise MFAConfigurationError("Stored MFA secret is invalid") from exc

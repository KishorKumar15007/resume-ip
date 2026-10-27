"""Read-only DA3 Q2(a) verification for the two synthetic Argon2 users."""

from __future__ import annotations

import base64
import getpass
import os
import sys
from dataclasses import dataclass
from pathlib import Path

from argon2 import extract_parameters
from dotenv import dotenv_values
from sqlalchemy.engine import make_url


TARGET_EMAILS = (
    "da3-salt-a@example.com",
    "da3-salt-b@example.com",
)
RESULT_PATH = Path(__file__).resolve().parents[1] / "results" / "15-argon2-check.md"
LOADTEST_ENV_VARIABLE = "DA3_LOADTEST_ENV_FILE"
LOADTEST_BRANCH_SENTINEL = "DA3_LOADTEST_BRANCH"
LOADTEST_BRANCH_NAME = "da3-loadtest"
REQUIRED_CONFIGURATION = {
    "DATABASE_URL",
    "GCS_BUCKET_NAME",
    "GCP_PROJECT_ID",
    "PUBSUB_RESUME_UPLOADED_TOPIC",
    "JWT_SECRET_KEY",
}


@dataclass(frozen=True)
class HashEvidence:
    user_id: str
    email: str
    algorithm: str
    version: int
    memory_cost_kib: int
    time_cost: int
    parallelism: int
    hash_len: int
    salt_len_bytes: int
    encoded_salt: str
    encoded_hash: str


def _backend_root() -> Path:
    return Path(__file__).resolve().parents[3] / "backend"


def load_loadtest_configuration() -> dict[str, str]:
    """Load the owner-supplied DA3 configuration without disclosing its values."""
    configured_path = os.environ.get(LOADTEST_ENV_VARIABLE)
    if not configured_path:
        raise RuntimeError("load-test configuration file is unavailable")

    loadtest_env_path = Path(configured_path)
    if not loadtest_env_path.is_absolute() or not loadtest_env_path.is_file():
        raise RuntimeError("load-test configuration file is unavailable")

    values = {key: value for key, value in dotenv_values(loadtest_env_path).items() if value}
    missing = REQUIRED_CONFIGURATION - values.keys()
    if missing:
        raise RuntimeError("load-test configuration is incomplete")
    if values.get(LOADTEST_BRANCH_SENTINEL) != LOADTEST_BRANCH_NAME:
        raise RuntimeError("load-test branch sentinel is invalid")

    try:
        database_url = make_url(values["DATABASE_URL"])
    except Exception as exc:
        raise RuntimeError("load-test database URL is invalid") from exc
    if database_url.get_backend_name() != "postgresql" or not database_url.host:
        raise RuntimeError("load-test database must be a PostgreSQL host")
    if "-pooler" not in database_url.host:
        raise RuntimeError("load-test database URL must use the pooled endpoint")
    if database_url.query.get("sslmode") != "require":
        raise RuntimeError("load-test database URL must require TLS")

    return values


def _decode_phc_segment(segment: str) -> bytes:
    """Decode a padding-free PHC base64 segment without exposing the hash."""
    return base64.b64decode(segment + "=" * (-len(segment) % 4), validate=True)


def parse_hash_evidence(user_id: str, email: str, encoded_hash: str) -> HashEvidence:
    """Validate an Argon2 PHC string and retain only safe comparison evidence."""
    parameters = extract_parameters(encoded_hash)
    parts = encoded_hash.split("$")
    if len(parts) != 6 or parts[0] != "" or not parts[1].startswith("argon2"):
        raise ValueError("stored value is not a complete Argon2 PHC string")

    salt = _decode_phc_segment(parts[4])
    digest = _decode_phc_segment(parts[5])
    if not salt or not digest:
        raise ValueError("stored value has an empty Argon2 salt or digest")

    return HashEvidence(
        user_id=user_id,
        email=email,
        algorithm=parts[1],
        version=parameters.version,
        memory_cost_kib=parameters.memory_cost,
        time_cost=parameters.time_cost,
        parallelism=parameters.parallelism,
        hash_len=parameters.hash_len,
        salt_len_bytes=len(salt),
        encoded_salt=parts[4],
        encoded_hash=encoded_hash,
    )


def write_report(lines: list[str]) -> None:
    RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def failure_report(reason: str) -> None:
    write_report(
        [
            "# DA3 Q2(a) Argon2 verification",
            "",
            "Status: NOT VERIFIED",
            "",
            f"Reason: {reason}",
            "",
            "No password, encoded hash, database URL, or credential value was written.",
        ]
    )


def main() -> int:
    try:
        configuration = load_loadtest_configuration()
    except RuntimeError:
        failure_report(
            "The DA3 load-test configuration is unavailable, incomplete, or is not marked "
            "for the da3-loadtest branch."
        )
        return 1

    # This occurs before application imports, so Pydantic Settings resolves the
    # validated load-test values from the process environment instead of the host default.
    os.environ.update(configuration)
    backend_root = _backend_root()
    if str(backend_root) not in sys.path:
        sys.path.insert(0, str(backend_root))

    try:
        from sqlalchemy import select

        from app.core.security import verify_password
        from app.database import SessionLocal
        from app.models.user import User
    except Exception:
        failure_report(
            "The application hashing/database configuration could not be initialized. "
            "Confirm the owner-managed runtime configuration privately."
        )
        return 1

    try:
        with SessionLocal() as session:
            users = list(
                session.scalars(
                    select(User)
                    .where(User.email.in_(TARGET_EMAILS))
                    .order_by(User.email)
                )
            )
    except Exception:
        failure_report(
            "The read-only lookup could not reach the configured database. "
            "Confirm database connectivity and the selected Neon branch privately."
        )
        return 1

    found_by_email = {user.email: user for user in users}
    missing = [email for email in TARGET_EMAILS if email not in found_by_email]
    if missing:
        failure_report(
            "The required synthetic account set is incomplete: " + ", ".join(missing)
        )
        return 1

    try:
        evidence = [
            parse_hash_evidence(
                str(found_by_email[email].id),
                email,
                found_by_email[email].password_hash,
            )
            for email in TARGET_EMAILS
        ]
    except (TypeError, ValueError):
        failure_report("At least one stored password value is not a valid encoded Argon2 hash.")
        return 1

    try:
        password = getpass.getpass(
            "Shared password for the two synthetic DA3 salt accounts (not echoed): "
        )
    except (EOFError, KeyboardInterrupt):
        failure_report("Password entry was cancelled; stored hashes were not password-verified.")
        return 1

    verification = [verify_password(password, item.encoded_hash) for item in evidence]
    salts_differ = evidence[0].encoded_salt != evidence[1].encoded_salt
    hashes_differ = evidence[0].encoded_hash != evidence[1].encoded_hash
    all_verified = all(verification)

    lines = [
        "# DA3 Q2(a) Argon2 verification",
        "",
        "Status: PASS" if all_verified else "Status: FAIL",
        "",
        "The two existing synthetic users were read through the application's configured "
        "SQLAlchemy session. Password verification used `app.core.security.verify_password`; "
        "the prompted password was not saved or echoed.",
        "",
        "| Email | User ID | Algorithm | Version | Memory (KiB) | Time cost | Parallelism | Hash length (bytes) | Salt (PHC base64) | Salt length (bytes) | Password verification |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- | ---: | --- |",
    ]
    for item, verified in zip(evidence, verification, strict=True):
        lines.append(
            "| {email} | {user_id} | {algorithm} | {version} | {memory} | {time} | "
            "{parallelism} | {hash_len} | `{salt}` | {salt_len} | {verified} |".format(
                email=item.email,
                user_id=item.user_id,
                algorithm=item.algorithm,
                version=item.version,
                memory=item.memory_cost_kib,
                time=item.time_cost,
                parallelism=item.parallelism,
                hash_len=item.hash_len,
                salt=item.encoded_salt,
                salt_len=item.salt_len_bytes,
                verified="PASS" if verified else "FAIL",
            )
        )
    lines.extend(
        [
            "",
            f"Salt-distinctness verdict: {'PASS — salts differ' if salts_differ else 'FAIL — salts match'}.",
            f"Hash-distinctness verdict: {'PASS — hashes differ' if hashes_differ else 'FAIL — hashes match'}.",
            "",
            "Complete encoded hashes, plaintext passwords, database URLs, and other credentials "
            "are intentionally omitted.",
        ]
    )
    write_report(lines)
    return 0 if all_verified and salts_differ and hashes_differ else 1


if __name__ == "__main__":
    raise SystemExit(main())

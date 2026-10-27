"""Owner-run DA3 Step 16 MFA flow test for the local load-test stack."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit

import pyotp
import requests
from dotenv import dotenv_values
from jose import jwt
from sqlalchemy import delete, select
from sqlalchemy.engine import make_url


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
BACKEND_DIRECTORY = REPOSITORY_ROOT / "backend"
RESULT_PATH = REPOSITORY_ROOT / "docs" / "da3" / "results" / "16-mfa-flow.md"
LOADTEST_ENV_VARIABLE = "DA3_LOADTEST_ENV_FILE"
REQUIRED_CONFIGURATION = {
    "DATABASE_URL",
    "GCS_BUCKET_NAME",
    "GCP_PROJECT_ID",
    "PUBSUB_RESUME_UPLOADED_TOPIC",
    "JWT_SECRET_KEY",
    "MFA_ENCRYPTION_KEY",
}
LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1"}
REQUEST_TIMEOUT_SECONDS = 10
CLOCK_COMMAND_TIMEOUT_SECONDS = 10
CLOCK_SKEW_LIMIT_SECONDS = 5


@dataclass
class Result:
    step: str
    expected: str
    actual: str
    passed: bool


class FlowRunner:
    def __init__(self, base_url: str, configuration: dict[str, str]) -> None:
        self.base_url = base_url.rstrip("/")
        self.configuration = configuration
        self.results: list[Result] = []
        self.created_email: str | None = None
        self.created_user_id: str | None = None
        self.signup_attempted = False
        self.signup_succeeded = False
        self.cleanup_attempted = False

    def record(self, step: str, expected: str, actual: str, passed: bool) -> bool:
        self.results.append(Result(step, expected, actual, passed))
        return passed

    def request(self, step: str, expected: str, method: str, path: str, status_code: int, **kwargs) -> requests.Response | None:
        try:
            response = requests.request(
                method,
                f"{self.base_url}{path}",
                timeout=REQUEST_TIMEOUT_SECONDS,
                **kwargs,
            )
        except requests.RequestException as exc:
            self.record(step, expected, f"request error: {type(exc).__name__}", False)
            return None
        self.record(step, expected, f"HTTP {response.status_code}", response.status_code == status_code)
        return response

    @staticmethod
    def json_object(response: requests.Response | None) -> dict[str, object] | None:
        try:
            value = response.json() if response is not None else None
        except (AttributeError, ValueError):
            return None
        return value if isinstance(value, dict) else None

    @classmethod
    def json_value(cls, response: requests.Response | None, key: str) -> str | None:
        payload = cls.json_object(response)
        value = payload.get(key) if payload is not None else None
        return value if isinstance(value, str) and value else None

    @classmethod
    def mfa_challenge_token(cls, response: requests.Response | None) -> str | None:
        payload = cls.json_object(response)
        token = payload.get("mfa_token") if payload is not None else None
        if (
            payload is None
            or payload.get("mfa_required") is not True
            or "access_token" in payload
            or not isinstance(token, str)
            or not token
        ):
            return None
        return token

    @staticmethod
    def tamper_signed_token(token: str) -> str | None:
        parts = token.split(".")
        if len(parts) != 3 or not parts[2]:
            return None
        header, payload, signature = parts
        tampered_signature = ("A" if signature[0] != "A" else "B") + signature[1:]
        return ".".join((header, payload, tampered_signature))

    def cleanup(self) -> None:
        if self.cleanup_attempted or not self.signup_attempted:
            return
        self.cleanup_attempted = True
        if not self.created_email:
            self.record(
                "Clean up synthetic MFA user",
                "exactly one created user removed",
                "cleanup skipped because the generated identity was unavailable",
                False,
            )
            return
        try:
            os.environ.update(self.configuration)
            if str(BACKEND_DIRECTORY) not in sys.path:
                sys.path.insert(0, str(BACKEND_DIRECTORY))
            from app.database import SessionLocal
            from app.models.user import User

            with SessionLocal() as session:
                user_id = self.created_user_id
                if user_id is None:
                    user_id = session.scalar(
                        select(User.id).where(User.email == self.created_email)
                    )
                if user_id is None:
                    self.record(
                        "Clean up synthetic MFA user",
                        "exactly one created user removed when signup succeeded",
                        "no matching synthetic user found",
                        not self.signup_succeeded,
                    )
                    return
                deleted = session.execute(
                    delete(User).where(
                        User.id == user_id,
                        User.email == self.created_email,
                    )
                )
                session.commit()
            self.record("Clean up synthetic MFA user", "exactly one created user removed", f"rows deleted: {deleted.rowcount}", deleted.rowcount == 1)
        except Exception:
            self.record("Clean up synthetic MFA user", "exactly one created user removed", "cleanup failed without internal details", False)

    def verify_clocks(self) -> bool:
        self.record("Validate host clock", "UTC clock available", "UTC clock available", True)
        passed = True
        for service in ("backend-1", "backend-2", "backend-3"):
            started_at = datetime.now(timezone.utc)
            try:
                completed = subprocess.run(
                    [
                        "docker",
                        "compose",
                        "-f",
                        str(REPOSITORY_ROOT / "compose.da3.yml"),
                        "exec",
                        "-T",
                        service,
                        "python",
                        "-c",
                        "from datetime import datetime, timezone; print(datetime.now(timezone.utc).isoformat())",
                    ],
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=CLOCK_COMMAND_TIMEOUT_SECONDS,
                )
                finished_at = datetime.now(timezone.utc)
                container_time = datetime.fromisoformat(completed.stdout.strip())
                if container_time.tzinfo is None:
                    raise ValueError("container time has no timezone")
                midpoint = started_at + (finished_at - started_at) / 2
                skew_seconds = abs((container_time.astimezone(timezone.utc) - midpoint).total_seconds())
                clock_ok = completed.returncode == 0 and skew_seconds <= CLOCK_SKEW_LIMIT_SECONDS
            except (OSError, subprocess.TimeoutExpired, ValueError):
                clock_ok = False
            self.record(
                f"Validate {service} clock",
                f"within {CLOCK_SKEW_LIMIT_SECONDS} seconds of the host clock",
                "clock aligned" if clock_ok else "clock unavailable or outside tolerance",
                clock_ok,
            )
            passed = passed and clock_ok
        return passed

    def run(self) -> bool:
        health = self.request("Preflight local DA3 API", "HTTP 200 from a DA3 backend", "GET", "/health", 200)
        health_payload = self.json_object(health)
        instance = health_payload.get("instance") if health_payload is not None else None
        if not self.record("Validate local DA3 target", "backend instance identity", "backend identity present" if isinstance(instance, str) and instance else "backend identity missing", isinstance(instance, str) and instance.startswith("backend-")):
            return False
        if not self.verify_clocks():
            return False

        run_id = time.time_ns()
        self.created_email = f"da3-mfa-{run_id}@example.com"
        password = f"Da3Mfa-{run_id}!"
        try:
            self.signup_attempted = True
            signup = self.request("Register synthetic MFA user", "HTTP 201", "POST", "/auth/signup", 201, json={"email": self.created_email, "password": password, "role": "candidate"})
            self.signup_succeeded = bool(signup and signup.status_code == 201)
            initial_token = self.json_value(signup, "access_token")
            if not initial_token:
                self.record("Read synthetic user identity", "signed signup token", "token missing", False)
                return False
            try:
                self.created_user_id = jwt.get_unverified_claims(initial_token).get("sub")
            except Exception:
                self.created_user_id = None
            if not isinstance(self.created_user_id, str):
                self.record("Read synthetic user identity", "signed signup token", "subject missing", False)
                return False

            login_before = self.request("Login before MFA enrolment", "HTTP 200 with access token", "POST", "/auth/login", 200, json={"email": self.created_email, "password": password})
            access_token = self.json_value(login_before, "access_token")
            if not access_token:
                self.record("Validate pre-MFA login", "access token", "access token missing", False)
                return False
            headers = {"Authorization": f"Bearer {access_token}"}

            setup = self.request("Set up MFA", "HTTP 200 with in-memory provisioning URI", "POST", "/auth/mfa/setup", 200, headers=headers)
            provisioning_uri = self.json_value(setup, "provisioning_uri")
            if not provisioning_uri:
                self.record("Validate MFA setup", "provisioning URI", "provisioning URI missing", False)
                return False
            try:
                totp = pyotp.parse_uri(provisioning_uri)
            except (TypeError, ValueError):
                self.record("Validate MFA setup", "parseable provisioning URI", "provisioning URI invalid", False)
                return False
            code = totp.now()

            confirmed = self.request("Confirm MFA", "HTTP 200", "POST", "/auth/mfa/confirm", 200, headers=headers, json={"code": code})
            if confirmed is None or confirmed.status_code != 200:
                return False
            login_after = self.request("Login after MFA enrolment", "HTTP 200 with MFA challenge", "POST", "/auth/login", 200, json={"email": self.created_email, "password": password})
            mfa_token = self.mfa_challenge_token(login_after)
            valid_challenge = mfa_token is not None
            self.record("Validate MFA login challenge", "MFA token only", "MFA challenge fields present" if valid_challenge else "MFA challenge fields missing", valid_challenge)
            if not valid_challenge:
                return False

            self.request("Reject MFA token on protected route", "HTTP 401", "GET", "/postings", 401, headers={"Authorization": f"Bearer {mfa_token}"})
            verified = self.request("Verify MFA token and code", "HTTP 200 with access token", "POST", "/auth/mfa/verify", 200, json={"mfa_token": mfa_token, "code": code})
            verified_token = self.json_value(verified, "access_token")
            if not verified_token:
                self.record("Validate verified access token", "access token", "access token missing", False)
                return False
            self.request("Use verified access token", "HTTP 200", "GET", "/postings", 200, headers={"Authorization": f"Bearer {verified_token}"})

            invalid_code = ("0" if code[0] != "0" else "1") + code[1:]
            self.request("Reject invalid MFA code", "HTTP 401", "POST", "/auth/mfa/verify", 401, json={"mfa_token": mfa_token, "code": invalid_code})
            self.request("Reject wrong-scope access token", "HTTP 401", "POST", "/auth/mfa/verify", 401, json={"mfa_token": verified_token, "code": code})
            self.request("Reject malformed MFA token", "HTTP 401", "POST", "/auth/mfa/verify", 401, json={"mfa_token": "malformed", "code": code})
            tampered_token = self.tamper_signed_token(mfa_token)
            if tampered_token is None:
                self.record("Build invalidly signed MFA token", "valid JWT structure", "MFA token structure invalid", False)
            else:
                self.request("Reject invalidly signed MFA token", "HTTP 401", "POST", "/auth/mfa/verify", 401, json={"mfa_token": tampered_token, "code": code})
            expired_token = jwt.encode(
                {
                    "sub": self.created_user_id,
                    "role": "candidate",
                    "scope": "mfa",
                    "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
                },
                self.configuration["JWT_SECRET_KEY"],
                algorithm=self.configuration.get("JWT_ALGORITHM", "HS256"),
            )
            self.request("Reject expired MFA token", "HTTP 401", "POST", "/auth/mfa/verify", 401, json={"mfa_token": expired_token, "code": code})
        finally:
            self.cleanup()
        return bool(self.results) and all(result.passed for result in self.results)


def parse_base_url(value: str) -> str:
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or parsed.hostname not in LOOPBACK_HOSTS or parsed.username or parsed.password or parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        raise argparse.ArgumentTypeError("--base-url must be a loopback HTTP(S) origin")
    return value.rstrip("/")


def load_configuration() -> dict[str, str]:
    configured_path = os.environ.get(LOADTEST_ENV_VARIABLE)
    if not configured_path:
        raise RuntimeError("load-test configuration file is unavailable")
    env_path = Path(configured_path)
    if not env_path.is_absolute() or not env_path.is_file():
        raise RuntimeError("load-test configuration file is unavailable")
    values = {key: value for key, value in dotenv_values(env_path).items() if value}
    if REQUIRED_CONFIGURATION - values.keys() or values.get("DA3_LOADTEST_BRANCH") != "da3-loadtest":
        raise RuntimeError("load-test configuration is incomplete or targets the wrong branch")
    database_url = make_url(values["DATABASE_URL"])
    if database_url.get_backend_name() != "postgresql" or "-pooler" not in (database_url.host or "") or database_url.query.get("sslmode") != "require":
        raise RuntimeError("load-test database configuration is invalid")
    return values


def write_results(results: list[Result]) -> None:
    RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    overall = "PASS" if results and all(result.passed for result in results) else "FAIL"
    rows = ["# DA3 Step 16 MFA Flow Test", "", f"Overall: **{overall}**", "", "| Step | Expected | Actual |", "| --- | --- | --- |"]
    rows.extend(f"| {result.step} | {result.expected} | {result.actual} |" for result in results)
    rows.append("")
    rows.append("Tokens, provisioning URIs, TOTP secrets, Fernet keys, and connection details are intentionally omitted.")
    RESULT_PATH.write_text("\n".join(rows) + "\n", encoding="utf-8")
    print("\n".join(rows))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True, type=parse_base_url, help="explicit local DA3 API origin")
    args = parser.parse_args()
    try:
        configuration = load_configuration()
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        write_results(
            [
                Result(
                    "Validate load-test configuration",
                    "validated local da3-loadtest configuration",
                    "configuration unavailable or invalid",
                    False,
                )
            ]
        )
        return 1
    runner = FlowRunner(args.base_url, configuration)
    try:
        runner.run()
    except Exception as exc:
        runner.record("MFA flow execution", "no unexpected exception", f"unexpected error: {type(exc).__name__}", False)
        runner.cleanup()
    finally:
        write_results(runner.results)
    return 0 if runner.results and all(result.passed for result in runner.results) else 1


if __name__ == "__main__":
    raise SystemExit(main())

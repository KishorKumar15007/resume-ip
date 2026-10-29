"""Owner-run DA3 Step 18 authorization matrix for the local Nginx stack.

This harness writes only synthetic, run-scoped database fixtures. It never
serializes credentials, tokens, response bodies, or connection strings.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import traceback
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import requests
from dotenv import dotenv_values
from jose import jwt
from sqlalchemy import delete, select
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
BACKEND_DIRECTORY = REPOSITORY_ROOT / "backend"
RESULTS_DIRECTORY = REPOSITORY_ROOT / "docs" / "da3" / "results"
EVIDENCE_DIRECTORY = REPOSITORY_ROOT / "docs" / "da3" / "evidence"
LOADTEST_ENV_VARIABLE = "DA3_LOADTEST_ENV_FILE"
LOADTEST_BRANCH_NAME = "da3-loadtest"
LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1"}
REQUEST_TIMEOUT_SECONDS = 10
RUN_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{2,63}$")
FIXTURE_NAMESPACE = uuid.UUID("9f568ad1-e645-4c4e-b1d0-7ec8d0e7c50b")
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
CAPTURE_FILENAMES = ("2b-no-token-rejected.png", "2b-swagger-401.png", "2b-candidate-403.png", "2b-authz-matrix.png")
PRE_DELETE_CAPTURE_FILENAMES = CAPTURE_FILENAMES[:3]
REQUIRED_CONFIGURATION = {"DATABASE_URL", "JWT_SECRET_KEY", "DA3_SEED_PASSWORD", "DA3_LOADTEST_BRANCH", "GCS_BUCKET_NAME", "GCP_PROJECT_ID", "PUBSUB_RESUME_UPLOADED_TOPIC"}


class MatrixError(RuntimeError):
    """A safe-to-display fixture, matrix, or evidence-gate failure."""


class DatabaseDiagnosticError(MatrixError):
    """A database failure annotated with a safe operation label and cause."""

    def __init__(self, operation: str, cause: BaseException) -> None:
        super().__init__(f"database operation failed during {operation}: {type(cause).__name__}")
        self.operation = operation
        self.cause = cause


@dataclass(frozen=True)
class MatrixResult:
    request: str
    token_type: str
    expected: str
    actual: str
    passed: bool


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def redact_diagnostic(value: str) -> str:
    """Keep local error diagnostics useful without emitting secret-bearing text."""
    value = re.sub(r"postgresql(?:\+[a-z0-9_]+)?://[^\s'\"]+", "[database-url-redacted]", value, flags=re.IGNORECASE)
    return re.sub(r"(?i)\b(password|secret|token|authorization|api[_-]?key)\s*=\s*[^\s,;]+", r"\1=[redacted]", value)


def diagnostic_text(context: str, cause: BaseException) -> str:
    """Render exception type, safe DBAPI message, and frames without SQL parameters."""
    original = getattr(cause, "orig", cause)
    message = redact_diagnostic(str(original)).replace("\r", " ").replace("\n", " ")
    frames = traceback.extract_tb(cause.__traceback__)
    lines = [f"{context}: {type(cause).__name__}: {message or 'no safe exception message'}", "Sanitized traceback frames:"]
    lines.extend(f"  {frame.filename}:{frame.lineno} in {frame.name}" for frame in frames)
    return "\n".join(lines)


def rollback_after_failure(session: Any) -> None:
    try:
        session.rollback()
    except SQLAlchemyError:
        # Preserve the original failed operation as the diagnostic cause.
        pass


def parse_base_url(value: str) -> str:
    parsed = urlsplit(value)
    if (parsed.scheme not in {"http", "https"} or parsed.hostname not in LOOPBACK_HOSTS or parsed.username or parsed.password or parsed.path not in {"", "/"} or parsed.query or parsed.fragment or parsed.port != 8080):
        raise argparse.ArgumentTypeError("--base-url must be the local Nginx origin on port 8080")
    return value.rstrip("/")


def parse_run_id(value: str) -> str:
    if not RUN_ID_PATTERN.fullmatch(value):
        raise argparse.ArgumentTypeError("--run-id must contain only lowercase letters, digits, and hyphens")
    return value


def manifest_path(run_id: str) -> Path:
    return RESULTS_DIRECTORY / f"18-authz-fixture-{run_id}.json"


def attempt_json_path(run_id: str, attempt: int, phase: str) -> Path:
    return RESULTS_DIRECTORY / f"18-authz-matrix-{run_id}-attempt-{attempt}-{phase}.json"


def attempt_markdown_path(run_id: str, attempt: int, phase: str) -> Path:
    return RESULTS_DIRECTORY / f"18-authz-matrix-{run_id}-attempt-{attempt}-{phase}.md"


def canonical_json_path() -> Path:
    return RESULTS_DIRECTORY / "18-authz-matrix.json"


def canonical_markdown_path() -> Path:
    return RESULTS_DIRECTORY / "18-authz-matrix.md"


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)


def atomic_write_pair(first: Path, first_content: str, second: Path, second_content: str) -> None:
    """Replace a paired report, rolling back a partial replacement if possible."""
    first.parent.mkdir(parents=True, exist_ok=True)
    second.parent.mkdir(parents=True, exist_ok=True)
    first_tmp, second_tmp = first.with_suffix(first.suffix + ".tmp"), second.with_suffix(second.suffix + ".tmp")
    originals = {first: first.read_text(encoding="utf-8") if first.exists() else None, second: second.read_text(encoding="utf-8") if second.exists() else None}
    first_tmp.write_text(first_content, encoding="utf-8")
    second_tmp.write_text(second_content, encoding="utf-8")
    replaced: list[Path] = []
    try:
        first_tmp.replace(first); replaced.append(first)
        second_tmp.replace(second); replaced.append(second)
    except OSError as exc:
        for path in reversed(replaced):
            old = originals[path]
            if old is None:
                path.unlink(missing_ok=True)
            else:
                atomic_write(path, old)
        raise MatrixError("result-pair promotion could not be completed safely") from exc
    finally:
        first_tmp.unlink(missing_ok=True)
        second_tmp.unlink(missing_ok=True)


def load_configuration() -> dict[str, str]:
    """Apply the established private DA3 file contract without disclosing values.

    Repository scripts validate the explicit branch sentinel plus pooled
    PostgreSQL/TLS shape. PostgreSQL supplies no independent Neon-branch value,
    so this validation is intentionally not reported as proof of branch identity.
    """
    configured_path = os.environ.get(LOADTEST_ENV_VARIABLE)
    if not configured_path:
        raise MatrixError("load-test configuration file is unavailable")
    path = Path(configured_path)
    if not path.is_absolute() or not path.is_file():
        raise MatrixError("load-test configuration file is unavailable")
    values = {key: value for key, value in dotenv_values(path).items() if value}
    if REQUIRED_CONFIGURATION - values.keys() or values.get("DA3_LOADTEST_BRANCH") != LOADTEST_BRANCH_NAME:
        raise MatrixError("load-test configuration is incomplete or targets the wrong branch")
    try:
        database_url = make_url(values["DATABASE_URL"])
    except Exception as exc:
        raise MatrixError("load-test database URL is invalid") from exc
    if database_url.get_backend_name() != "postgresql" or "-pooler" not in (database_url.host or "") or database_url.query.get("sslmode") != "require":
        raise MatrixError("load-test database configuration is invalid")
    return values


def application_modules(configuration: dict[str, str]):
    os.environ.update(configuration)
    if str(BACKEND_DIRECTORY) not in sys.path:
        sys.path.insert(0, str(BACKEND_DIRECTORY))
    from app.core.security import hash_password
    from app.database import SessionLocal
    from app.models import JobPosting, Submission, User
    return SessionLocal, User, JobPosting, Submission, hash_password


def preflight_api(base_url: str) -> None:
    try:
        health = requests.get(f"{base_url}/health", timeout=REQUEST_TIMEOUT_SECONDS)
        docs = requests.get(f"{base_url}/docs", timeout=REQUEST_TIMEOUT_SECONDS)
        payload = health.json()
    except (requests.RequestException, ValueError) as exc:
        raise MatrixError("local Nginx API preflight failed") from exc
    instance = payload.get("instance") if isinstance(payload, dict) else None
    if health.status_code != 200 or not isinstance(instance, str) or not instance.startswith("backend-"):
        raise MatrixError("local Nginx API preflight did not identify a DA3 backend")
    if docs.status_code != 200:
        raise MatrixError("local Swagger UI preflight failed")


def fixture_ids(run_id: str) -> dict[str, str]:
    return {name: str(uuid.uuid5(FIXTURE_NAMESPACE, f"{run_id}:{name}")) for name in ("recruiter_a", "recruiter_b", "candidate_a", "candidate_b", "posting", "submission")}


def database_id(ids: dict[str, str], name: str) -> uuid.UUID:
    return uuid.UUID(ids[name])


def fixture_values(run_id: str) -> dict[str, str]:
    prefix = f"da3-authz-{run_id}"
    return {"recruiter_a_email": f"{prefix}-recruiter-a@example.com", "recruiter_b_email": f"{prefix}-recruiter-b@example.com", "candidate_a_email": f"{prefix}-candidate-a@example.com", "candidate_b_email": f"{prefix}-candidate-b@example.com", "posting_title": f"DA3 authorization fixture {run_id}", "posting_description": "Synthetic authorization fixture only."}


def build_manifest(run_id: str) -> dict[str, Any]:
    return {"run_id": run_id, "attempt": 1, "created_at": now_iso(), "phase": "preparing", "ids": fixture_ids(run_id), "fixture": fixture_values(run_id), "results": [], "events": [{"at": now_iso(), "event": "manifest-reserved"}]}


def read_manifest(run_id: str) -> dict[str, Any]:
    path = manifest_path(run_id)
    if not path.is_file():
        raise MatrixError("fixture manifest is unavailable")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise MatrixError("fixture manifest is invalid") from exc
    if not isinstance(value, dict) or value.get("run_id") != run_id or value.get("attempt") != 1 or value.get("ids") != fixture_ids(run_id) or value.get("fixture") != fixture_values(run_id) or not isinstance(value.get("events"), list) or not isinstance(value.get("results"), list):
        raise MatrixError("fixture manifest fails run-scoped ownership validation")
    return value


def save_manifest(run_id: str, manifest: dict[str, Any]) -> None:
    atomic_write(manifest_path(run_id), json.dumps(manifest, indent=2) + "\n")


def record_event(manifest: dict[str, Any], event: str) -> None:
    manifest["events"].append({"at": now_iso(), "event": event})


def assert_unused_run(run_id: str) -> None:
    paths = [manifest_path(run_id), RESULTS_DIRECTORY / f"18-authz-matrix-{run_id}.json", RESULTS_DIRECTORY / f"18-authz-matrix-{run_id}.md"]
    paths += list(RESULTS_DIRECTORY.glob(f"18-authz-matrix-{run_id}-attempt-*.json")) + list(RESULTS_DIRECTORY.glob(f"18-authz-matrix-{run_id}-attempt-*.md"))
    if any(path.exists() for path in paths):
        raise MatrixError("run ID already has preserved fixture or result artifacts; choose a new run ID")


def capture_paths(*, include_final: bool = True) -> tuple[Path, ...]:
    names = CAPTURE_FILENAMES if include_final else PRE_DELETE_CAPTURE_FILENAMES
    return tuple(EVIDENCE_DIRECTORY / name for name in names)


def assert_capture_slots_unused() -> None:
    if any(path.exists() for path in capture_paths()):
        raise MatrixError("required capture filename already exists; do not overwrite existing evidence")


def verify_capture_files(*, include_final: bool = True) -> None:
    for path in capture_paths(include_final=include_final):
        try:
            valid = path.is_file() and path.stat().st_size > len(PNG_SIGNATURE) and path.read_bytes()[:8] == PNG_SIGNATURE
        except OSError:
            valid = False
        if not valid:
            raise MatrixError("all required owner-captured PNG evidence must exist and be readable before final owner DELETE")


def verify_fixture(manifest: dict[str, Any], configuration: dict[str, str], *, require_submission: bool = True) -> None:
    ids, fixture = manifest["ids"], manifest["fixture"]
    SessionLocal, User, JobPosting, Submission, _hash = application_modules(configuration)
    database_step = "loading synthetic fixture users"
    try:
        with SessionLocal() as session:
            users = {name: session.get(User, database_id(ids, name)) for name in ("recruiter_a", "recruiter_b", "candidate_a", "candidate_b")}
            for name, role in (("recruiter_a", "recruiter"), ("recruiter_b", "recruiter"), ("candidate_a", "candidate"), ("candidate_b", "candidate")):
                user = users[name]
                if user is None or user.email != fixture[f"{name}_email"] or user.role != role:
                    raise MatrixError("fixture users do not match the requested run")
            database_step = "loading the synthetic fixture posting"
            posting = session.get(JobPosting, database_id(ids, "posting"))
            if posting is None or posting.recruiter_id != users["recruiter_a"].id or posting.title != fixture["posting_title"]:
                raise MatrixError("fixture posting does not match the requested run")
            database_step = "loading the synthetic fixture submission"
            submission = session.get(Submission, database_id(ids, "submission"))
            if require_submission and (submission is None or submission.posting_id != posting.id or submission.candidate_id != users["candidate_a"].id):
                raise MatrixError("fixture submission does not match the requested run")
    except SQLAlchemyError as exc:
        raise DatabaseDiagnosticError(database_step, exc) from exc


def prepare_fixture(run_id: str, configuration: dict[str, str]) -> None:
    assert_unused_run(run_id)
    assert_capture_slots_unused()
    manifest = build_manifest(run_id)
    save_manifest(run_id, manifest)  # Persist exact IDs before any database write.
    ids, fixture = manifest["ids"], manifest["fixture"]
    SessionLocal, User, JobPosting, Submission, hash_password = application_modules(configuration)
    session = SessionLocal()
    database_step = "checking reserved fixture IDs"
    try:
        for identifier in ids.values():
            value = uuid.UUID(identifier)
            if session.get(User, value) is not None or session.get(JobPosting, value) is not None or session.get(Submission, value) is not None:
                raise MatrixError("run-scoped fixture IDs are already in use")
        database_step = "checking synthetic fixture emails"
        emails = tuple(value for key, value in fixture.items() if key.endswith("_email"))
        if session.scalar(select(User.id).where(User.email.in_(emails))) is not None:
            raise MatrixError("run-scoped fixture email collides with an existing account")
        session.add_all([User(id=database_id(ids, name), email=fixture[f"{name}_email"], password_hash=hash_password(configuration["DA3_SEED_PASSWORD"]), role=role) for name, role in (("recruiter_a", "recruiter"), ("recruiter_b", "recruiter"), ("candidate_a", "candidate"), ("candidate_b", "candidate"))])
        database_step = "flushing synthetic fixture users"
        session.flush()
        session.add(JobPosting(id=database_id(ids, "posting"), recruiter_id=database_id(ids, "recruiter_a"), title=fixture["posting_title"], description=fixture["posting_description"], required_skills=["Authorization", "Testing"]))
        database_step = "flushing the synthetic fixture posting"
        session.flush()
        session.add(Submission(id=database_id(ids, "submission"), posting_id=database_id(ids, "posting"), candidate_id=database_id(ids, "candidate_a"), storage_path=f"synthetic://da3-authz/{run_id}/resume.pdf", status="QUEUED", score=None, matched_skills=None))
        database_step = "committing the synthetic fixture"
        session.commit()
    except SQLAlchemyError as exc:
        rollback_after_failure(session)
        manifest["phase"] = "prepare-failed"; record_event(manifest, "prepare-failed"); save_manifest(run_id, manifest)
        raise DatabaseDiagnosticError(database_step, exc) from exc
    except Exception:
        rollback_after_failure(session)
        manifest["phase"] = "prepare-failed"; record_event(manifest, "prepare-failed"); save_manifest(run_id, manifest)
        raise
    finally:
        session.close()
    manifest["phase"] = "prepared"; record_event(manifest, "fixture-committed")
    try:
        save_manifest(run_id, manifest)
    except OSError as exc:
        raise MatrixError("fixture may be committed; use --recover with this exact run ID") from exc


def recover_fixture(run_id: str, configuration: dict[str, str]) -> None:
    manifest = read_manifest(run_id)
    if manifest.get("phase") not in {"preparing", "prepare-failed"}:
        raise MatrixError("only an interrupted preparation can be recovered")
    verify_fixture(manifest, configuration)
    manifest["phase"] = "prepared"; record_event(manifest, "fixture-recovered"); save_manifest(run_id, manifest)


def login(base_url: str, email: str, password: str) -> str:
    try:
        response = requests.post(f"{base_url}/auth/login", json={"email": email, "password": password}, timeout=REQUEST_TIMEOUT_SECONDS)
    except requests.RequestException as exc:
        raise MatrixError(f"login request failed: {type(exc).__name__}") from exc
    try:
        token = response.json().get("access_token") if response.status_code == 200 else None
    except (ValueError, AttributeError):
        token = None
    if not isinstance(token, str) or not token:
        raise MatrixError("synthetic fixture login was rejected")
    return token


def tamper_token(token: str) -> str:
    parts = token.split(".")
    if len(parts) != 3 or not parts[2]:
        raise MatrixError("owner token has an unexpected structure")
    return ".".join((parts[0], parts[1], ("A" if parts[2][0] != "A" else "B") + parts[2][1:]))


def response_actual(response: requests.Response | None, require_bearer_header: bool) -> str:
    if response is None:
        return "request error"
    actual = f"HTTP {response.status_code}"
    if require_bearer_header:
        actual += "; WWW-Authenticate: " + ("Bearer" if response.headers.get("WWW-Authenticate", "").lower() == "bearer" else "missing")
    return actual


def request_case(results: list[MatrixResult], *, base_url: str, method: str, path: str, token_type: str, token: str | None, expected_status: int, payload: dict[str, Any] | None = None, require_bearer_header: bool = False) -> None:
    headers = {"Authorization": f"Bearer {token}"} if token is not None else {}
    try:
        response = requests.request(method, f"{base_url}{path}", headers=headers, json=payload, timeout=REQUEST_TIMEOUT_SECONDS)
    except requests.RequestException as exc:
        response, actual = None, f"request error: {type(exc).__name__}"
    else:
        actual = response_actual(response, require_bearer_header)
    header_ok = not require_bearer_header or (response is not None and response.headers.get("WWW-Authenticate", "").lower() == "bearer")
    results.append(MatrixResult(f"{method} {path}", token_type, f"HTTP {expected_status}" + ("; WWW-Authenticate: Bearer" if require_bearer_header else ""), actual, response is not None and response.status_code == expected_status and header_ok))


def is_final_owner_delete(item: MatrixResult) -> bool:
    return item.token_type == "Recruiter A owner access token" and item.request.startswith("DELETE /postings/") and item.expected == "HTTP 204"


def overall_for(results: list[MatrixResult], phase: str) -> str:
    return "PASS" if phase == "complete" and results and all(item.passed for item in results) else "FAIL" if "failed" in phase or phase == "complete" else "INCOMPLETE"


def result_documents(run_id: str, attempt: int, results: list[MatrixResult], phase: str) -> tuple[str, str]:
    payload = {"script": "docs/da3/scripts/authz_matrix.py", "run_id": run_id, "attempt": attempt, "phase": phase, "overall": overall_for(results, phase), "steps": [asdict(item) for item in results]}
    rows = ["# DA3 Step 18 Authorization Matrix", "", f"Run: `{run_id}`", f"Attempt: `{attempt}`", f"Phase: **{phase}**", f"Overall: **{payload['overall']}**", "", "| Request | Token type | Expected | Actual | PASS/FAIL |", "| --- | --- | --- | --- | --- |"]
    rows.extend(f"| {item.request} | {item.token_type} | {item.expected} | {item.actual} | {'PASS' if item.passed else 'FAIL'} |" for item in results)
    rows.extend(["", "Tokens, passwords, connection strings, and response bodies are intentionally omitted."])
    return json.dumps(payload, indent=2) + "\n", "\n".join(rows) + "\n"


def write_attempt_results(run_id: str, attempt: int, results: list[MatrixResult], phase: str) -> None:
    json_path, markdown_path = attempt_json_path(run_id, attempt, phase), attempt_markdown_path(run_id, attempt, phase)
    if json_path.exists() or markdown_path.exists():
        raise MatrixError("attempt result artifact already exists; refusing to overwrite preserved evidence")
    json_text, markdown_text = result_documents(run_id, attempt, results, phase)
    atomic_write_pair(json_path, json_text, markdown_path, markdown_text)


def promote_canonical(run_id: str, attempt: int, results: list[MatrixResult]) -> None:
    if not results or not all(item.passed for item in results) or not any(is_final_owner_delete(item) and item.passed for item in results):
        raise MatrixError("canonical promotion requires a fully passing matrix with the recorded final owner DELETE")
    json_text, markdown_text = result_documents(run_id, attempt, results, "complete")
    atomic_write_pair(canonical_json_path(), json_text, canonical_markdown_path(), markdown_text)


def run_matrix(run_id: str, base_url: str, configuration: dict[str, str]) -> None:
    manifest = read_manifest(run_id)
    if manifest.get("phase") != "prepared":
        raise MatrixError("fixture run is not ready for a new pre-delete matrix")
    verify_fixture(manifest, configuration)
    fixture, ids, password = manifest["fixture"], manifest["ids"], configuration["DA3_SEED_PASSWORD"]
    tokens = {label: login(base_url, fixture[email_key], password) for label, email_key in (("Candidate A access token", "candidate_a_email"), ("Candidate B access token", "candidate_b_email"), ("Recruiter B non-owner access token", "recruiter_b_email"), ("Recruiter A owner access token", "recruiter_a_email"))}
    now = datetime.now(timezone.utc)
    expired = jwt.encode({"sub": ids["recruiter_a"], "role": "recruiter", "scope": "access", "exp": now - timedelta(minutes=1)}, configuration["JWT_SECRET_KEY"], algorithm=configuration.get("JWT_ALGORITHM", "HS256"))
    mfa_token = jwt.encode({"sub": ids["candidate_a"], "role": "candidate", "scope": "mfa", "exp": now + timedelta(minutes=5)}, configuration["JWT_SECRET_KEY"], algorithm=configuration.get("JWT_ALGORITHM", "HS256"))
    results: list[MatrixResult] = []
    posting, submission, ranked, update = f"/postings/{ids['posting']}", f"/submissions/{ids['submission']}", f"/postings/{ids['posting']}/submissions", {"description": "Synthetic authorization fixture updated by its owner."}
    for method in ("PUT", "DELETE"):
        for label, token in (("No token", None), ("Malformed token", "abc"), ("Expired token", expired), ("Signature-tampered token", tamper_token(tokens["Recruiter A owner access token"])), ("MFA-scope token", mfa_token)):
            request_case(results, base_url=base_url, method=method, path=posting, token_type=label, token=token, expected_status=401, payload=update if method == "PUT" else None, require_bearer_header=True)
    for method in ("PUT", "DELETE"):
        for label in ("Candidate A access token", "Recruiter B non-owner access token"):
            request_case(results, base_url=base_url, method=method, path=posting, token_type=label, token=tokens[label], expected_status=403, payload=update if method == "PUT" else None)
    request_case(results, base_url=base_url, method="PUT", path=posting, token_type="Recruiter A owner access token", token=tokens["Recruiter A owner access token"], expected_status=200, payload=update)
    for label, expected in (("Candidate A access token", 200), ("Candidate B access token", 403), ("Recruiter A owner access token", 200), ("Recruiter B non-owner access token", 403)):
        request_case(results, base_url=base_url, method="GET", path=submission, token_type=label, token=tokens[label], expected_status=expected)
    for label, expected in (("Recruiter A owner access token", 200), ("Recruiter B non-owner access token", 403)):
        request_case(results, base_url=base_url, method="GET", path=ranked, token_type=label, token=tokens[label], expected_status=expected)
    manifest["results"] = [asdict(item) for item in results]
    manifest["phase"] = "matrix-predelete" if all(item.passed for item in results) else "matrix-failed"; record_event(manifest, manifest["phase"]); save_manifest(run_id, manifest)
    write_attempt_results(run_id, manifest["attempt"], results, manifest["phase"])
    if manifest["phase"] != "matrix-predelete":
        raise MatrixError("authorization matrix contains failed cases; preserve this attempt and clean up")
    print("Pre-delete matrix passed. The synthetic posting remains available for owner captures.")


def final_delete(run_id: str, base_url: str, configuration: dict[str, str]) -> None:
    manifest = read_manifest(run_id)
    if manifest.get("phase") != "matrix-predelete":
        raise MatrixError("final owner DELETE requires a passing pre-delete matrix")
    verify_fixture(manifest, configuration); verify_capture_files(include_final=False); record_event(manifest, "pre-delete-captures-verified")
    ids, fixture = manifest["ids"], manifest["fixture"]
    owner_token = login(base_url, fixture["recruiter_a_email"], configuration["DA3_SEED_PASSWORD"])
    SessionLocal, _User, _Posting, Submission, _hash = application_modules(configuration)
    with SessionLocal() as session:
        deleted = session.execute(delete(Submission).where(Submission.id == database_id(ids, "submission"), Submission.posting_id == database_id(ids, "posting"), Submission.candidate_id == database_id(ids, "candidate_a")))
        if deleted.rowcount != 1:
            session.rollback(); raise MatrixError("fixture submission could not be removed before final owner deletion")
        session.commit()
    results = [MatrixResult(**item) for item in manifest["results"]]
    request_case(results, base_url=base_url, method="DELETE", path=f"/postings/{ids['posting']}", token_type="Recruiter A owner access token", token=owner_token, expected_status=204)
    success = all(item.passed for item in results)
    manifest["results"], manifest["phase"] = [asdict(item) for item in results], "complete" if success else "final-delete-failed"; record_event(manifest, manifest["phase"]); save_manifest(run_id, manifest)
    write_attempt_results(run_id, manifest["attempt"], results, manifest["phase"])
    if not success:
        raise MatrixError("final owner DELETE failed; preserved this attempt and left canonical output unchanged")
    promote_canonical(run_id, manifest["attempt"], results)


def capture_no_token(run_id: str, base_url: str, configuration: dict[str, str]) -> None:
    manifest = read_manifest(run_id)
    if manifest.get("phase") != "matrix-predelete":
        raise MatrixError("fixture run is not available for the requested capture")
    verify_fixture(manifest, configuration)
    posting_id = manifest["ids"]["posting"]
    try:
        response = requests.delete(f"{base_url}/postings/{posting_id}", timeout=REQUEST_TIMEOUT_SECONDS)
    except requests.RequestException as exc:
        raise MatrixError("no-token capture request failed") from exc
    header = response.headers.get("WWW-Authenticate", "missing")
    print(f"DELETE /postings/{posting_id} with no Authorization header"); print(f"HTTP {response.status_code}; WWW-Authenticate: {header}")
    if response.status_code != 401 or header.lower() != "bearer":
        raise MatrixError("no-token capture did not return the expected 401 Bearer response")


def capture_candidate_denial(run_id: str, base_url: str, configuration: dict[str, str]) -> None:
    manifest = read_manifest(run_id)
    if manifest.get("phase") != "matrix-predelete":
        raise MatrixError("fixture run is not available for the requested capture")
    verify_fixture(manifest, configuration)
    posting_id = manifest["ids"]["posting"]
    token = login(base_url, manifest["fixture"]["candidate_a_email"], configuration["DA3_SEED_PASSWORD"])
    try:
        response = requests.put(f"{base_url}/postings/{posting_id}", headers={"Authorization": f"Bearer {token}"}, json={"description": "Synthetic candidate denial capture."}, timeout=REQUEST_TIMEOUT_SECONDS)
    except requests.RequestException as exc:
        raise MatrixError("candidate-denial capture request failed") from exc
    print(f"PUT /postings/{posting_id} with synthetic Candidate A access token (token withheld)"); print(f"HTTP {response.status_code}")
    if response.status_code != 403:
        raise MatrixError("candidate-denial capture did not return the expected 403 response")


def cleanup_fixture(run_id: str, configuration: dict[str, str]) -> None:
    manifest = read_manifest(run_id)
    ids, fixture = manifest["ids"], manifest["fixture"]
    SessionLocal, User, JobPosting, Submission, _hash = application_modules(configuration)
    with SessionLocal() as session:
        submission = session.get(Submission, database_id(ids, "submission"))
        if submission is not None:
            if submission.posting_id != database_id(ids, "posting") or submission.candidate_id != database_id(ids, "candidate_a"):
                raise MatrixError("fixture cleanup ownership validation failed for submission")
            session.delete(submission)
        posting = session.get(JobPosting, database_id(ids, "posting"))
        if posting is not None:
            if posting.recruiter_id != database_id(ids, "recruiter_a") or posting.title != fixture["posting_title"]:
                raise MatrixError("fixture cleanup ownership validation failed for posting")
            session.delete(posting)
        for name, role in (("recruiter_a", "recruiter"), ("recruiter_b", "recruiter"), ("candidate_a", "candidate"), ("candidate_b", "candidate")):
            user = session.get(User, database_id(ids, name))
            if user is not None:
                if user.email != fixture[f"{name}_email"] or user.role != role:
                    raise MatrixError("fixture cleanup ownership validation failed for user")
                session.delete(user)
        session.commit()
    manifest["phase"] = "cleaned"; record_event(manifest, "cleanup-complete"); save_manifest(run_id, manifest)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True, type=parse_run_id)
    parser.add_argument("--base-url", type=parse_base_url, default="http://localhost:8080")
    action = parser.add_mutually_exclusive_group(required=True)
    for flag in ("prepare", "recover", "run-matrix", "verify-captures", "verify-complete-captures", "finalize-delete", "cleanup", "capture-no-token", "capture-candidate-denial"):
        action.add_argument(f"--{flag}", action="store_true")
    args = parser.parse_args()
    try:
        configuration = load_configuration()
        if args.prepare:
            preflight_api(args.base_url); prepare_fixture(args.run_id, configuration); print("Synthetic authorization fixture prepared.")
        elif args.recover:
            preflight_api(args.base_url); recover_fixture(args.run_id, configuration); print("Interrupted fixture preparation recovered.")
        elif args.run_matrix:
            preflight_api(args.base_url); run_matrix(args.run_id, args.base_url, configuration)
        elif args.verify_captures:
            verify_capture_files(include_final=False); print("Required pre-delete owner-captured PNG files are readable.")
        elif args.verify_complete_captures:
            verify_capture_files(); print("All required owner-captured PNG files are readable.")
        elif args.finalize_delete:
            preflight_api(args.base_url); final_delete(args.run_id, args.base_url, configuration); print("Final owner DELETE recorded and canonical matrix promoted.")
        elif args.capture_no_token:
            preflight_api(args.base_url); capture_no_token(args.run_id, args.base_url, configuration)
        elif args.capture_candidate_denial:
            preflight_api(args.base_url); capture_candidate_denial(args.run_id, args.base_url, configuration)
        else:
            cleanup_fixture(args.run_id, configuration); print("Synthetic authorization fixture cleanup completed.")
    except DatabaseDiagnosticError as exc:
        print(str(exc), file=sys.stderr)
        print(diagnostic_text("underlying database error", exc.cause), file=sys.stderr)
        return 1
    except MatrixError as exc:
        print(str(exc), file=sys.stderr); return 1
    except Exception as exc:
        print(diagnostic_text("authorization matrix stopped", exc), file=sys.stderr); return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Create deterministic, idempotent fixtures for the DA3 load-test database."""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

from dotenv import dotenv_values
from sqlalchemy.engine import make_url


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
BACKEND_DIRECTORY = REPOSITORY_ROOT / "backend"
LOADTEST_ENV_PATH = REPOSITORY_ROOT / "backend" / ".env.loadtest"
RESULTS_DIRECTORY = REPOSITORY_ROOT / "docs" / "da3" / "results"
SUMMARY_JSON_PATH = RESULTS_DIRECTORY / "07-seed-summary.json"
SUMMARY_MARKDOWN_PATH = RESULTS_DIRECTORY / "07-seed-summary.md"

REQUIRED_CONFIGURATION = {
    "DATABASE_URL",
    "GCS_BUCKET_NAME",
    "GCP_PROJECT_ID",
    "PUBSUB_RESUME_UPLOADED_TOPIC",
    "JWT_SECRET_KEY",
    "DA3_SEED_PASSWORD",
}
LOADTEST_BRANCH_SENTINEL = "DA3_LOADTEST_BRANCH"
LOADTEST_BRANCH_NAME = "da3-loadtest"

RECRUITER_EMAILS = tuple(
    f"da3-seed-recruiter-{index}@example.com" for index in range(1, 4)
)
CANDIDATE_EMAILS = tuple(
    f"da3-seed-candidate-{index}@example.com" for index in range(1, 3)
)
SKILL_VARIANTS = (
    ["Python", "FastAPI", "PostgreSQL"],
    ["JavaScript", "React", "CSS"],
    ["Docker", "Nginx", "Linux"],
    ["SQL", "Data Analysis", "Excel"],
    ["Java", "Spring", "REST"],
    ["Cloud Run", "Google Cloud", "Pub/Sub"],
    ["Security", "OAuth", "JWT"],
    ["TypeScript", "Node.js", "Testing"],
    ["Machine Learning", "Python", "Pandas"],
    ["Git", "CI/CD", "Documentation"],
)


class SeedConfigurationError(RuntimeError):
    pass


class FixtureValidationError(RuntimeError):
    pass


@dataclass
class FixtureCount:
    created: int = 0
    already_present: int = 0


@dataclass
class SeedSummary:
    outcome: str
    recruiters: FixtureCount
    candidates: FixtureCount
    postings: FixtureCount
    message: str


def load_loadtest_configuration() -> tuple[dict[str, str], str]:
    if not LOADTEST_ENV_PATH.is_file():
        raise SeedConfigurationError("load-test configuration file is unavailable")

    values = {key: value for key, value in dotenv_values(LOADTEST_ENV_PATH).items() if value}
    missing = sorted(REQUIRED_CONFIGURATION - values.keys())
    if missing:
        raise SeedConfigurationError("load-test configuration is incomplete")
    if values.get(LOADTEST_BRANCH_SENTINEL) != LOADTEST_BRANCH_NAME:
        raise SeedConfigurationError("load-test branch sentinel is invalid")

    try:
        database_url = make_url(values["DATABASE_URL"])
    except Exception as exc:
        raise SeedConfigurationError("load-test database URL is invalid") from exc

    if database_url.get_backend_name() != "postgresql" or not database_url.host:
        raise SeedConfigurationError("load-test database must be a PostgreSQL host")
    if "-pooler" not in database_url.host:
        raise SeedConfigurationError("load-test database URL must use the pooled endpoint")
    if database_url.query.get("sslmode") != "require":
        raise SeedConfigurationError("load-test database URL must require TLS")

    return values, database_url.host


def write_summary(summary: SeedSummary) -> None:
    RESULTS_DIRECTORY.mkdir(parents=True, exist_ok=True)
    SUMMARY_JSON_PATH.write_text(
        json.dumps(asdict(summary), indent=2) + "\n",
        encoding="utf-8",
    )
    SUMMARY_MARKDOWN_PATH.write_text(
        "\n".join(
            [
                "# DA3 Step 7 Load-test Seeding Summary",
                "",
                f"Outcome: **{summary.outcome}**",
                "",
                "| Fixture type | Created | Already present |",
                "| --- | ---: | ---: |",
                f"| Recruiters | {summary.recruiters.created} | {summary.recruiters.already_present} |",
                f"| Candidates | {summary.candidates.created} | {summary.candidates.already_present} |",
                f"| Postings | {summary.postings.created} | {summary.postings.already_present} |",
                "",
                f"Summary: {summary.message}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def expected_postings() -> tuple[tuple[int, str, str, list[str]], ...]:
    postings = []
    for index in range(1, 51):
        recruiter_index = (index - 1) % len(RECRUITER_EMAILS)
        required_skills = SKILL_VARIANTS[(index - 1) % len(SKILL_VARIANTS)]
        postings.append(
            (
                recruiter_index,
                f"da3-seed-posting-{index:02d}",
                f"Synthetic DA3 load-test posting {index:02d}.",
                required_skills,
            )
        )
    return tuple(postings)


def validate_existing_user(user, email: str, role: str, password: str, verify_password) -> None:
    if user.role != role:
        raise FixtureValidationError(f"fixture identity has an unexpected role: {email}")
    if not verify_password(password, user.password_hash):
        raise FixtureValidationError(f"fixture credential check failed: {email}")


def seed_database(configuration: dict[str, str]) -> SeedSummary:
    os.environ.update(configuration)

    backend_directory = str(BACKEND_DIRECTORY)
    if backend_directory not in sys.path:
        sys.path.insert(0, backend_directory)

    from sqlalchemy import select
    from sqlalchemy.exc import SQLAlchemyError

    from app.core.security import hash_password, verify_password
    from app.database import SessionLocal
    from app.models import JobPosting, User

    password = configuration["DA3_SEED_PASSWORD"]
    recruiter_count = FixtureCount()
    candidate_count = FixtureCount()
    posting_count = FixtureCount()
    session = SessionLocal()

    try:
        users: dict[str, User] = {}
        expected_users = [
            *((email, "recruiter") for email in RECRUITER_EMAILS),
            *((email, "candidate") for email in CANDIDATE_EMAILS),
        ]
        for email, role in expected_users:
            user = session.scalar(select(User).where(User.email == email))
            if user is not None:
                validate_existing_user(user, email, role, password, verify_password)
                users[email] = user
                target_count = recruiter_count if role == "recruiter" else candidate_count
                target_count.already_present += 1

        for recruiter_index, title, description, required_skills in expected_postings():
            recruiter = users.get(RECRUITER_EMAILS[recruiter_index])
            matches = list(
                session.scalars(
                    select(JobPosting).where(JobPosting.title == title)
                )
            )
            if len(matches) > 1:
                raise FixtureValidationError(f"duplicate fixture postings found: {title}")
            if matches:
                posting = matches[0]
                if (
                    recruiter is None
                    or posting.recruiter_id != recruiter.id
                    or posting.description != description
                    or posting.required_skills != required_skills
                ):
                    raise FixtureValidationError(f"fixture posting differs from expected data: {title}")
                posting_count.already_present += 1

        for email, role in expected_users:
            if email in users:
                continue
            user = User(email=email, password_hash=hash_password(password), role=role)
            session.add(user)
            session.flush()
            users[email] = user
            target_count = recruiter_count if role == "recruiter" else candidate_count
            target_count.created += 1

        for recruiter_index, title, description, required_skills in expected_postings():
            recruiter = users[RECRUITER_EMAILS[recruiter_index]]
            existing = session.scalar(
                select(JobPosting).where(
                    JobPosting.recruiter_id == recruiter.id,
                    JobPosting.title == title,
                )
            )
            if existing is None:
                session.add(
                    JobPosting(
                        recruiter_id=recruiter.id,
                        title=title,
                        description=description,
                        required_skills=required_skills,
                    )
                )
                posting_count.created += 1

        session.commit()
    except SQLAlchemyError as exc:
        session.rollback()
        raise RuntimeError("database operation failed") from exc
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    return SeedSummary(
        outcome="success",
        recruiters=recruiter_count,
        candidates=candidate_count,
        postings=posting_count,
        message="Synthetic DA3 fixtures are present; no credentials or URLs were recorded.",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--yes",
        action="store_true",
        help="permit fixture creation in the explicitly configured load-test database",
    )
    args = parser.parse_args()

    try:
        configuration, database_host = load_loadtest_configuration()
    except SeedConfigurationError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(f"database_host: {database_host}")
    if not args.yes:
        print("refusing to seed without --yes")
        return 2

    try:
        summary = seed_database(configuration)
    except FixtureValidationError as exc:
        summary = SeedSummary(
            outcome="stopped",
            recruiters=FixtureCount(),
            candidates=FixtureCount(),
            postings=FixtureCount(),
            message=str(exc),
        )
        write_summary(summary)
        print("fixture validation stopped seeding", file=sys.stderr)
        return 1
    except RuntimeError:
        summary = SeedSummary(
            outcome="failed",
            recruiters=FixtureCount(),
            candidates=FixtureCount(),
            postings=FixtureCount(),
            message="Database operation failed without recording internal details.",
        )
        write_summary(summary)
        print("database operation failed", file=sys.stderr)
        return 1

    write_summary(summary)
    print(
        "recruiters: created={0.created} already_present={0.already_present}".format(
            summary.recruiters
        )
    )
    print(
        "candidates: created={0.created} already_present={0.already_present}".format(
            summary.candidates
        )
    )
    print(
        "postings: created={0.created} already_present={0.already_present}".format(
            summary.postings
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

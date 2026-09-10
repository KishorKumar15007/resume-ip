from decimal import Decimal
from pathlib import Path
from typing import Literal
from uuid import UUID

from pypdf import PdfReader
from pypdf.errors import PdfReadError
from sqlalchemy import update
from sqlalchemy.exc import SQLAlchemyError

from app.database import SessionLocal
from app.models import JobPosting, Submission


ProcessingOutcome = Literal[
    "DONE",
    "ALREADY_DONE",
    "ALREADY_PROCESSING",
    "ALREADY_FAILED",
    "NOT_FOUND",
    "INVALID_STATE",
    "FAILED",
    "DATABASE_ERROR",
    "STATE_CHANGED",
]

UPLOADS_DIRECTORY = Path(__file__).resolve().parents[2] / "uploads"


class ProcessingInputError(Exception):
    pass


def process_submission(submission_id: UUID) -> ProcessingOutcome:
    db = SessionLocal()
    claimed = False

    try:
        claim = db.execute(
            update(Submission)
            .where(
                Submission.id == submission_id,
                Submission.status == "QUEUED",
            )
            .values(
                status="PROCESSING",
                score=None,
                matched_skills=None,
            )
        )

        if claim.rowcount != 1:
            db.rollback()
            return _existing_submission_outcome(db, submission_id)

        db.commit()
        claimed = True

        submission = db.get(Submission, submission_id)

        if submission is None:
            return "NOT_FOUND"

        try:
            posting = db.get(JobPosting, submission.posting_id)

            if posting is None:
                raise ProcessingInputError

            if not posting.required_skills:
                raise ProcessingInputError

            resume_text = _extract_resume_text(submission.storage_path)
            matched_skills = _matched_skills(
                posting.required_skills,
                resume_text,
            )
            score = (
                Decimal(len(matched_skills))
                / Decimal(len(posting.required_skills))
                * Decimal("100")
            )
        except (OSError, PdfReadError, ProcessingInputError):
            return _failed_outcome(submission_id)

        try:
            completed = db.execute(
                update(Submission)
                .where(
                    Submission.id == submission_id,
                    Submission.status == "PROCESSING",
                )
                .values(
                    status="DONE",
                    score=score,
                    matched_skills=matched_skills,
                )
            )

            if completed.rowcount != 1:
                db.rollback()
                return "STATE_CHANGED"

            db.commit()
            return "DONE"
        except SQLAlchemyError:
            db.rollback()
            return _failed_outcome(submission_id)
    except SQLAlchemyError:
        db.rollback()

        if claimed:
            return _failed_outcome(submission_id)

        return "DATABASE_ERROR"
    finally:
        db.close()


def _existing_submission_outcome(
    db,
    submission_id: UUID,
) -> ProcessingOutcome:
    submission = db.get(Submission, submission_id)

    if submission is None:
        return "NOT_FOUND"

    if submission.status == "DONE":
        return "ALREADY_DONE"

    if submission.status == "PROCESSING":
        return "ALREADY_PROCESSING"

    if submission.status == "FAILED":
        return "ALREADY_FAILED"

    return "INVALID_STATE"


def _extract_resume_text(storage_path: str) -> str:
    uploads_directory = UPLOADS_DIRECTORY.resolve()
    resume_path = Path(storage_path).resolve()

    if not resume_path.is_relative_to(uploads_directory):
        raise ProcessingInputError

    if not resume_path.is_file():
        raise ProcessingInputError

    reader = PdfReader(resume_path)

    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _matched_skills(
    required_skills: list[str],
    resume_text: str,
) -> list[str]:
    resume_text_lower = resume_text.lower()

    return [
        skill
        for skill in required_skills
        if skill.lower() in resume_text_lower
    ]


def _failed_outcome(submission_id: UUID) -> ProcessingOutcome:
    db = SessionLocal()

    try:
        failed = db.execute(
            update(Submission)
            .where(
                Submission.id == submission_id,
                Submission.status == "PROCESSING",
            )
            .values(
                status="FAILED",
                score=None,
                matched_skills=None,
            )
        )
        db.commit()

        if failed.rowcount == 1:
            return "FAILED"

        return _existing_submission_outcome(db, submission_id)
    except SQLAlchemyError:
        db.rollback()
        return "DATABASE_ERROR"
    finally:
        db.close()

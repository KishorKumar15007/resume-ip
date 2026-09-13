from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class SubmissionUploadResponse(BaseModel):
    id: UUID
    status: Literal["QUEUED"]


class SubmissionStatusResponse(BaseModel):
    id: UUID
    status: Literal["QUEUED", "PROCESSING", "DONE", "FAILED"]
    score: Decimal | None
    matched_skills: list[str] | None


class RankedSubmissionResponse(SubmissionStatusResponse):
    candidate_id: UUID
    candidate_email: str

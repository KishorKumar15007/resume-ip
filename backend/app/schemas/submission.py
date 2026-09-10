from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class SubmissionUploadResponse(BaseModel):
    id: UUID
    status: Literal["QUEUED"]

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PostingCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1)
    required_skills: list[str] = Field(min_length=1)


class PostingUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, min_length=1)
    required_skills: list[str] | None = Field(default=None, min_length=1)


class PostingResponse(BaseModel):
    id: UUID
    recruiter_id: UUID
    title: str
    description: str
    required_skills: list[str]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

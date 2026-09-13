from uuid import UUID

from pydantic import BaseModel, Field


class PubSubPushMessage(BaseModel):
    data: str | None = None
    message_id: str | None = None
    attributes: dict[str, str] = Field(default_factory=dict)


class PubSubPushEnvelope(BaseModel):
    message: PubSubPushMessage | None = None
    subscription: str | None = None


class ResumeUploadedEvent(BaseModel):
    submission_id: UUID
    posting_id: UUID
    storage_path: str
    required_skills: list[str]

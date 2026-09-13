import json
from uuid import UUID

from google.api_core.exceptions import GoogleAPIError
from google.auth.exceptions import GoogleAuthError
from google.cloud import pubsub_v1

from app.database import settings


class ResumeEventPublishError(Exception):
    pass


class ResumeEventPublisher:
    def __init__(
        self,
        project_id: str | None = None,
        topic_id: str | None = None,
    ) -> None:
        self.project_id = project_id or settings.gcp_project_id
        self.topic_id = topic_id or settings.pubsub_resume_uploaded_topic
        self._client: pubsub_v1.PublisherClient | None = None

    def publish_resume_uploaded(
        self,
        *,
        submission_id: UUID,
        posting_id: UUID,
        storage_path: str,
        required_skills: list[str],
    ) -> str:
        event = {
            "posting_id": str(posting_id),
            "required_skills": required_skills,
            "storage_path": storage_path,
            "submission_id": str(submission_id),
        }

        try:
            future = self._publisher().publish(
                self._topic_path(),
                json.dumps(
                    event,
                    separators=(",", ":"),
                    sort_keys=True,
                ).encode("utf-8"),
            )
            return future.result(timeout=10)
        except (GoogleAPIError, GoogleAuthError, OSError, TimeoutError, ValueError) as exc:
            raise ResumeEventPublishError from exc

    def _publisher(self) -> pubsub_v1.PublisherClient:
        if self._client is None:
            self._client = pubsub_v1.PublisherClient()

        return self._client

    def _topic_path(self) -> str:
        return pubsub_v1.PublisherClient.topic_path(
            self.project_id,
            self.topic_id,
        )

from typing import BinaryIO
from uuid import UUID

from google.api_core.exceptions import GoogleAPIError, NotFound
from google.auth.exceptions import GoogleAuthError
from google.cloud import storage

from app.database import settings


class ResumeStorageError(Exception):
    pass


class GCSResumeStorage:
    def __init__(self, bucket_name: str | None = None) -> None:
        self.bucket_name = bucket_name or settings.gcs_bucket_name

    def upload_pdf(self, submission_id: UUID, source: BinaryIO) -> str:
        object_name = f"submissions/{submission_id}.pdf"

        try:
            source.seek(0)
            self._bucket().blob(object_name).upload_from_file(
                source,
                content_type="application/pdf",
                if_generation_match=0,
            )
        except (GoogleAPIError, GoogleAuthError, OSError, ValueError) as exc:
            raise ResumeStorageError from exc

        return self._storage_path(object_name)

    def download_pdf(self, storage_path: str) -> bytes:
        try:
            return self._blob_for(storage_path).download_as_bytes()
        except (GoogleAPIError, GoogleAuthError) as exc:
            raise ResumeStorageError from exc

    def delete_pdf(self, storage_path: str) -> None:
        try:
            self._blob_for(storage_path).delete()
        except NotFound:
            return
        except (GoogleAPIError, GoogleAuthError) as exc:
            raise ResumeStorageError from exc

    def _bucket(self) -> storage.Bucket:
        return storage.Client().bucket(self.bucket_name)

    def _blob_for(self, storage_path: str) -> storage.Blob:
        expected_prefix = f"gs://{self.bucket_name}/"

        if not storage_path.startswith(expected_prefix):
            raise ResumeStorageError

        object_name = storage_path.removeprefix(expected_prefix)

        if not self._is_submission_object_name(object_name):
            raise ResumeStorageError

        return self._bucket().blob(object_name)

    def _storage_path(self, object_name: str) -> str:
        return f"gs://{self.bucket_name}/{object_name}"

    @staticmethod
    def _is_submission_object_name(object_name: str) -> bool:
        prefix = "submissions/"

        if not object_name.startswith(prefix):
            return False

        filename = object_name.removeprefix(prefix)

        if "/" in filename or not filename.endswith(".pdf"):
            return False

        try:
            submission_id = UUID(filename.removesuffix(".pdf"))
        except ValueError:
            return False

        return object_name == f"submissions/{submission_id}.pdf"

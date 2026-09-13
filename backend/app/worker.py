import argparse
import base64
import binascii
from uuid import UUID

from fastapi import FastAPI, Response, status
from pydantic import ValidationError

from app.schemas.pubsub import PubSubPushEnvelope, ResumeUploadedEvent
from app.services.submission_processor import process_submission


SUCCESSFUL_OUTCOMES = {
    "DONE",
    "ALREADY_DONE",
    "ALREADY_PROCESSING",
}

ACKNOWLEDGED_OUTCOMES = SUCCESSFUL_OUTCOMES | {
    "ALREADY_FAILED",
    "FAILED",
    "INVALID_STATE",
    "NOT_FOUND",
}

app = FastAPI(
    title="Resume Processing Worker",
)


@app.post(
    "/internal/pubsub/resume-uploaded",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_400_BAD_REQUEST: {"description": "Invalid Pub/Sub envelope"},
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "description": "Processing will be retried",
        },
    },
)
def handle_resume_uploaded(
    envelope: PubSubPushEnvelope,
) -> Response:
    event = _decode_resume_uploaded_event(envelope)

    if event is None:
        return Response(status_code=status.HTTP_400_BAD_REQUEST)

    outcome = process_submission(event.submission_id)

    if outcome in ACKNOWLEDGED_OUTCOMES:
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    return Response(status_code=status.HTTP_503_SERVICE_UNAVAILABLE)


def _decode_resume_uploaded_event(
    envelope: PubSubPushEnvelope,
) -> ResumeUploadedEvent | None:
    if envelope.message is None or not envelope.message.data:
        return None

    try:
        payload = base64.b64decode(envelope.message.data, validate=True)
        return ResumeUploadedEvent.model_validate_json(payload)
    except (binascii.Error, UnicodeDecodeError, ValidationError, ValueError):
        return None


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Process one queued resume submission locally.",
    )
    parser.add_argument(
        "submission_id",
        type=UUID,
    )
    arguments = parser.parse_args()

    outcome = process_submission(arguments.submission_id)
    print(f"{arguments.submission_id}: {outcome}")

    return 0 if outcome in SUCCESSFUL_OUTCOMES else 1


if __name__ == "__main__":
    raise SystemExit(main())

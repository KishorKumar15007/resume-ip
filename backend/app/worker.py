import argparse
from uuid import UUID

from app.services.submission_processor import process_submission


SUCCESSFUL_OUTCOMES = {
    "DONE",
    "ALREADY_DONE",
    "ALREADY_PROCESSING",
}


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

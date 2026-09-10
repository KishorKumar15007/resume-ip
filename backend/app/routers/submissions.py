from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.database import get_db
from app.models import JobPosting, Submission, User
from app.schemas.submission import SubmissionStatusResponse


router = APIRouter(
    prefix="/submissions",
    tags=["Submissions"],
)


@router.get(
    "/{submission_id}",
    response_model=SubmissionStatusResponse,
)
def get_submission(
    submission_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SubmissionStatusResponse:
    submission = db.get(Submission, submission_id)

    if submission is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Submission not found",
        )

    if current_user.role == "candidate":
        if submission.candidate_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only view your own submissions",
            )
    elif current_user.role == "recruiter":
        posting = db.get(JobPosting, submission.posting_id)

        if posting is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Job posting not found",
            )

        if posting.recruiter_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only view submissions for your own postings",
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )

    return SubmissionStatusResponse(
        id=submission.id,
        status=submission.status,
        score=submission.score if submission.status == "DONE" else None,
        matched_skills=(
            submission.matched_skills if submission.status == "DONE" else None
        ),
    )

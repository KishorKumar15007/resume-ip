from pathlib import Path
from shutil import copyfileobj
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_role
from app.database import get_db
from app.models import JobPosting, Submission, User
from app.schemas.posting import PostingCreate, PostingResponse, PostingUpdate
from app.schemas.submission import SubmissionUploadResponse


router = APIRouter(
    prefix="/postings",
    tags=["Job Postings"],
)

UPLOADS_DIRECTORY = Path(__file__).resolve().parents[2] / "uploads"


def get_posting_or_404(posting_id: UUID, db: Session) -> JobPosting:
    posting = db.get(JobPosting, posting_id)

    if posting is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job posting not found",
        )

    return posting


@router.post(
    "",
    response_model=PostingResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_posting(
    request: PostingCreate,
    current_user: User = Depends(require_role("recruiter")),
    db: Session = Depends(get_db),
) -> JobPosting:
    posting = JobPosting(
        recruiter_id=current_user.id,
        **request.model_dump(),
    )

    db.add(posting)
    db.commit()
    db.refresh(posting)

    return posting


@router.get(
    "",
    response_model=list[PostingResponse],
)
def list_postings(
    _current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[JobPosting]:
    return list(
        db.scalars(
            select(JobPosting).order_by(JobPosting.created_at.desc())
        ).all()
    )


@router.get(
    "/{posting_id}",
    response_model=PostingResponse,
)
def get_posting(
    posting_id: UUID,
    _current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> JobPosting:
    return get_posting_or_404(posting_id, db)


@router.put(
    "/{posting_id}",
    response_model=PostingResponse,
)
def update_posting(
    posting_id: UUID,
    request: PostingUpdate,
    current_user: User = Depends(require_role("recruiter")),
    db: Session = Depends(get_db),
) -> JobPosting:
    posting = get_posting_or_404(posting_id, db)

    if posting.recruiter_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only modify your own postings",
        )

    for field, value in request.model_dump(exclude_unset=True).items():
        setattr(posting, field, value)

    db.commit()
    db.refresh(posting)

    return posting


@router.delete(
    "/{posting_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_posting(
    posting_id: UUID,
    current_user: User = Depends(require_role("recruiter")),
    db: Session = Depends(get_db),
) -> Response:
    posting = get_posting_or_404(posting_id, db)

    if posting.recruiter_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only modify your own postings",
        )

    db.delete(posting)
    db.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{posting_id}/submissions",
    response_model=SubmissionUploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def create_submission(
    posting_id: UUID,
    resume: UploadFile = File(...),
    current_user: User = Depends(require_role("candidate")),
    db: Session = Depends(get_db),
) -> SubmissionUploadResponse:
    get_posting_or_404(posting_id, db)

    existing_submission = db.scalar(
        select(Submission.id).where(
            Submission.posting_id == posting_id,
            Submission.candidate_id == current_user.id,
        )
    )

    if existing_submission is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You have already submitted to this posting",
        )

    if resume.content_type != "application/pdf":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Resume must be a PDF",
        )

    file_header = resume.file.read(5)

    if file_header != b"%PDF-":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Resume must be a valid PDF",
        )

    submission_id = uuid4()
    upload_path = UPLOADS_DIRECTORY / f"{submission_id}.pdf"

    try:
        UPLOADS_DIRECTORY.mkdir(parents=True, exist_ok=True)
        with upload_path.open("xb") as destination:
            destination.write(file_header)
            copyfileobj(resume.file, destination)
    except OSError as exc:
        try:
            upload_path.unlink(missing_ok=True)
        except OSError:
            pass

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to store resume",
        ) from exc
    finally:
        resume.file.close()

    submission = Submission(
        id=submission_id,
        posting_id=posting_id,
        candidate_id=current_user.id,
        storage_path=str(upload_path),
        status="QUEUED",
        score=None,
        matched_skills=None,
    )

    db.add(submission)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()

        try:
            upload_path.unlink(missing_ok=True)
        except OSError:
            pass

        duplicate_submission = db.scalar(
            select(Submission.id).where(
                Submission.posting_id == posting_id,
                Submission.candidate_id == current_user.id,
            )
        )

        if duplicate_submission is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="You have already submitted to this posting",
            ) from exc

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to create submission",
        ) from exc

    db.refresh(submission)

    return SubmissionUploadResponse(
        id=submission.id,
        status="QUEUED",
    )

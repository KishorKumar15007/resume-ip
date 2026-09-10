from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_role
from app.database import get_db
from app.models import JobPosting, User
from app.schemas.posting import PostingCreate, PostingResponse, PostingUpdate


router = APIRouter(
    prefix="/postings",
    tags=["Job Postings"],
)


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

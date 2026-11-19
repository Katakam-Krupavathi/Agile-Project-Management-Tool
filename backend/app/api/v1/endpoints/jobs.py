from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_csrf
from app.db.session import get_db
from app.models.user import User
from app.schemas.job import JobResponse
from app.services import job_service

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/{job_id}", response_model=JobResponse)
def get_job(
    job_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> JobResponse:
    return job_service.get_job_for_user(db, job_id, current_user)


@router.post(
    "/{job_id}/retry",
    response_model=JobResponse,
    dependencies=[Depends(require_csrf)],
)
def retry_job(
    job_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> JobResponse:
    return job_service.retry_dead_job(db, job_id, current_user)

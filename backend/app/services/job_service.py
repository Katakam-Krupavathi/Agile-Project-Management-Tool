import json
from typing import Any

from sqlalchemy.orm import Session

from app.core.errors import ConflictError, ForbiddenError, NotFoundError
from app.jobs.queue import get_job_by_id
from app.models.enums import JobStatus, ProjectRole
from app.models.job import Job
from app.models.user import User, utc_now
from app.schemas.job import JobResponse
from app.services.permissions import assert_project_role


def to_job_response(job: Job) -> JobResponse:
    parsed_result: dict[str, Any] | None = None
    if job.result:
        try:
            loaded = json.loads(job.result)
            parsed_result = loaded if isinstance(loaded, dict) else {"value": loaded}
        except ValueError:
            parsed_result = {"raw": job.result}

    return JobResponse(
        id=job.id,
        job_type=job.job_type,
        status=JobStatus(job.status),
        attempts=job.attempts,
        max_attempts=job.max_attempts,
        run_at=job.run_at,
        last_error=job.last_error,
        result=parsed_result,
        project_id=job.project_id,
        created_by=job.created_by,
        created_at=job.created_at,
        updated_at=job.updated_at,
        completed_at=job.completed_at,
    )


def get_job_for_user(db: Session, job_id: str, user: User) -> JobResponse:
    job = get_job_by_id(db, job_id)
    if job is None:
        raise NotFoundError("Job not found.", code="JOB_NOT_FOUND")

    if job.created_by == user.id:
        return to_job_response(job)

    if job.project_id is not None:
        assert_project_role(db, job.project_id, user, ProjectRole.VIEWER)
        return to_job_response(job)

    raise NotFoundError("Job not found.", code="JOB_NOT_FOUND")


def retry_dead_job(db: Session, job_id: str, user: User) -> JobResponse:
    job = get_job_by_id(db, job_id)
    if job is None:
        raise NotFoundError("Job not found.", code="JOB_NOT_FOUND")

    if job.project_id is None:
        raise ForbiddenError(
            "Only project owners can retry project-scoped dead jobs.",
            code="INSUFFICIENT_ROLE",
        )

    assert_project_role(db, job.project_id, user, ProjectRole.OWNER)

    if job.status != JobStatus.DEAD.value:
        raise ConflictError("Only dead jobs can be retried.", code="JOB_NOT_DEAD")

    now = utc_now()
    job.status = JobStatus.QUEUED.value
    job.attempts = 0
    job.run_at = now
    job.locked_by = None
    job.locked_at = None
    job.last_error = None
    job.completed_at = None
    job.updated_at = now
    db.commit()
    db.refresh(job)
    return to_job_response(job)

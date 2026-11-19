import json
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.enums import JobStatus
from app.models.job import Job
from app.models.user import utc_now


def enqueue_job(
    db: Session,
    job_type: str,
    payload: dict[str, Any] | None = None,
    *,
    project_id: str | None = None,
    created_by: str | None = None,
    idempotency_key: str | None = None,
    run_at: datetime | None = None,
    max_attempts: int = 3,
) -> Job:
    """Enqueue a durable job inside the caller's active DB transaction.

    If ``idempotency_key`` is supplied and a job with that key already exists,
    the existing job is returned without inserting a duplicate row.
    """
    if idempotency_key:
        existing = db.scalar(select(Job).where(Job.idempotency_key == idempotency_key))
        if existing is not None:
            return existing

    job = Job(
        job_type=job_type,
        payload=json.dumps(payload or {}, default=str),
        status=JobStatus.QUEUED.value,
        run_at=run_at or utc_now(),
        attempts=0,
        max_attempts=max_attempts,
        idempotency_key=idempotency_key,
        project_id=project_id,
        created_by=created_by,
    )

    try:
        with db.begin_nested():
            db.add(job)
            db.flush()
    except IntegrityError:
        if idempotency_key:
            existing = db.scalar(select(Job).where(Job.idempotency_key == idempotency_key))
            if existing is not None:
                return existing
        raise

    return job


def get_job_by_id(db: Session, job_id: str) -> Job | None:
    return db.scalar(select(Job).where(Job.id == job_id))

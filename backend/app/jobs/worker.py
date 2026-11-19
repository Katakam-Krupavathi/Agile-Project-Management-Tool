import json
import logging
import os
import random
import signal
import socket
import threading
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session, sessionmaker

from app.db.session import SessionLocal
from app.jobs.registry import get_handler
from app.models.enums import JobStatus
from app.models.job import Job
from app.models.user import utc_now

logger = logging.getLogger("app.jobs.worker")

BASE_BACKOFF_SECONDS: float = 10.0
BACKOFF_FACTOR: float = 4.0
JITTER_RATIO: float = 0.1


def compute_backoff_seconds(
    attempt: int,
    rng: Callable[[], float] | None = None,
) -> float:
    """Compute exponential backoff (10s, 40s, 160s, ...) plus bounded jitter."""
    base = BASE_BACKOFF_SECONDS * (BACKOFF_FACTOR ** max(attempt - 1, 0))
    jitter_fn = rng or random.random
    return base + (base * JITTER_RATIO * jitter_fn())


def _log_event(level: int, event: str, **fields: Any) -> None:
    logger.log(level, json.dumps({"event": event, **fields}, default=str))


def default_worker_id() -> str:
    return f"{socket.gethostname()}:{os.getpid()}"


def claim_next_job(
    db: Session,
    worker_id: str,
    *,
    now: datetime | None = None,
) -> Job | None:
    """Atomically claim the next due queued job using a conditional UPDATE."""
    reference_now = now or utc_now()
    next_id_subq = (
        select(Job.id)
        .where(Job.status == JobStatus.QUEUED.value, Job.run_at <= reference_now)
        .order_by(Job.run_at.asc(), Job.created_at.asc())
        .limit(1)
        .scalar_subquery()
    )

    stmt = (
        update(Job)
        .where(
            Job.id == next_id_subq,
            Job.status == JobStatus.QUEUED.value,
            Job.run_at <= reference_now,
        )
        .values(
            status=JobStatus.RUNNING.value,
            locked_by=worker_id,
            locked_at=reference_now,
            attempts=Job.attempts + 1,
            updated_at=reference_now,
        )
        .returning(Job.id)
    )

    claimed_id = db.execute(stmt).scalar_one_or_none()
    db.commit()
    if claimed_id is None:
        return None

    job = db.scalar(select(Job).where(Job.id == claimed_id))
    if job is not None:
        _log_event(
            logging.INFO,
            "job.claimed",
            job_id=job.id,
            job_type=job.job_type,
            worker_id=worker_id,
            attempts=job.attempts,
        )
    return job


def _handle_job_failure(
    db: Session,
    job_id: str,
    *,
    error_msg: str,
    worker_id: str,
    now: datetime,
    rng: Callable[[], float] | None = None,
    force_dead: bool = False,
) -> Job | None:
    failed_job = db.scalar(select(Job).where(Job.id == job_id))
    if failed_job is None:
        return None

    failed_job.last_error = error_msg[:2000]
    failed_job.locked_by = None
    failed_job.locked_at = None
    failed_job.updated_at = now

    if force_dead or failed_job.attempts >= failed_job.max_attempts:
        failed_job.status = JobStatus.DEAD.value
        db.commit()
        _log_event(
            logging.ERROR,
            "job.dead",
            job_id=failed_job.id,
            job_type=failed_job.job_type,
            worker_id=worker_id,
            attempts=failed_job.attempts,
            max_attempts=failed_job.max_attempts,
            error=failed_job.last_error,
        )
    else:
        delay_seconds = compute_backoff_seconds(failed_job.attempts, rng=rng)
        failed_job.status = JobStatus.QUEUED.value
        failed_job.run_at = now + timedelta(seconds=delay_seconds)
        db.commit()
        _log_event(
            logging.WARNING,
            "job.retry_scheduled",
            job_id=failed_job.id,
            job_type=failed_job.job_type,
            worker_id=worker_id,
            attempts=failed_job.attempts,
            max_attempts=failed_job.max_attempts,
            retry_in_seconds=round(delay_seconds, 2),
            next_run_at=failed_job.run_at.isoformat(),
            error=failed_job.last_error,
        )
    return failed_job


def process_next_job(
    db: Session,
    worker_id: str,
    *,
    now: datetime | None = None,
    rng: Callable[[], float] | None = None,
) -> Job | None:
    reference_now = now or utc_now()
    job = claim_next_job(db, worker_id, now=reference_now)
    if job is None:
        return None

    handler = get_handler(job.job_type)
    if handler is None:
        error_msg = f"No handler registered for job_type '{job.job_type}'."
        return _handle_job_failure(
            db,
            job.id,
            error_msg=error_msg,
            worker_id=worker_id,
            now=reference_now,
            rng=rng,
            force_dead=True,
        )

    payload = json.loads(job.payload) if job.payload else {}
    try:
        result = handler(db, payload)
        finished_at = now or utc_now()
        job.status = JobStatus.SUCCEEDED.value
        job.result = json.dumps(result, default=str) if result is not None else None
        job.last_error = None
        job.locked_by = None
        job.locked_at = None
        job.completed_at = finished_at
        job.updated_at = finished_at
        db.commit()
        _log_event(
            logging.INFO,
            "job.succeeded",
            job_id=job.id,
            job_type=job.job_type,
            worker_id=worker_id,
            attempts=job.attempts,
        )
        return job
    except Exception as exc:
        db.rollback()
        return _handle_job_failure(
            db,
            job.id,
            error_msg=f"{type(exc).__name__}: {exc}",
            worker_id=worker_id,
            now=now or utc_now(),
            rng=rng,
        )


class Worker:
    def __init__(
        self,
        session_factory: sessionmaker[Session] = SessionLocal,
        *,
        worker_id: str | None = None,
        poll_interval_seconds: float = 1.0,
    ) -> None:
        self.session_factory = session_factory
        self.worker_id = worker_id or default_worker_id()
        self.poll_interval_seconds = poll_interval_seconds
        self._stop_event = threading.Event()

    def stop(self) -> None:
        self._stop_event.set()

    def run_once(self) -> Job | None:
        with self.session_factory() as db:
            return process_next_job(db, self.worker_id)

    def run_forever(self) -> None:
        _log_event(logging.INFO, "worker.started", worker_id=self.worker_id)
        while not self._stop_event.is_set():
            processed = self.run_once()
            if processed is None:
                self._stop_event.wait(self.poll_interval_seconds)
        _log_event(logging.INFO, "worker.stopped", worker_id=self.worker_id)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    worker = Worker()

    def _handle_signal(_signum: int, _frame: Any) -> None:
        worker.stop()

    signal.signal(signal.SIGINT, _handle_signal)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _handle_signal)

    worker.run_forever()


if __name__ == "__main__":
    main()

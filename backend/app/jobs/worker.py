import json
import logging
import os
import signal
import socket
import threading
from datetime import datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session, sessionmaker

from app.db.session import SessionLocal
from app.jobs.registry import get_handler
from app.models.enums import JobStatus
from app.models.job import Job
from app.models.user import utc_now

logger = logging.getLogger("app.jobs.worker")


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


def process_next_job(
    db: Session,
    worker_id: str,
    *,
    now: datetime | None = None,
) -> Job | None:
    job = claim_next_job(db, worker_id, now=now)
    if job is None:
        return None

    handler = get_handler(job.job_type)
    if handler is None:
        error_msg = f"No handler registered for job_type '{job.job_type}'."
        job.status = JobStatus.FAILED.value
        job.last_error = error_msg
        job.locked_by = None
        job.locked_at = None
        job.updated_at = now or utc_now()
        db.commit()
        _log_event(
            logging.ERROR,
            "job.handler_missing",
            job_id=job.id,
            job_type=job.job_type,
            worker_id=worker_id,
            error=error_msg,
        )
        return job

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
    except Exception as exc:
        db.rollback()
        failed_job = db.scalar(select(Job).where(Job.id == job.id))
        if failed_job is not None:
            failed_job.status = JobStatus.FAILED.value
            failed_job.last_error = f"{type(exc).__name__}: {exc}"[:2000]
            failed_job.locked_by = None
            failed_job.locked_at = None
            failed_job.updated_at = now or utc_now()
            db.commit()
            job = failed_job
        _log_event(
            logging.ERROR,
            "job.failed",
            job_id=job.id,
            job_type=job.job_type,
            worker_id=worker_id,
            attempts=job.attempts,
            error=f"{type(exc).__name__}: {exc}",
        )

    return job


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

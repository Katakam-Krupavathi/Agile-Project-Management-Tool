import json
import logging
import os
import random
import signal
import socket
import threading
import time
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.jobs import handlers as _handlers  # noqa: F401
from app.jobs.queue import enqueue_job
from app.jobs.registry import get_handler
from app.models.enums import JobStatus
from app.models.job import Job
from app.models.user import utc_now

logger = logging.getLogger("app.jobs.worker")

BASE_BACKOFF_SECONDS: float = 10.0
BACKOFF_FACTOR: float = 4.0
JITTER_RATIO: float = 0.1
DEFAULT_LOCK_TIMEOUT_SECONDS: int = 300


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


def refresh_job_lock(
    db: Session,
    job_id: str,
    worker_id: str,
    *,
    now: datetime | None = None,
) -> bool:
    """Refresh ``locked_at`` for an in-flight running job held by ``worker_id``."""
    reference_now = now or utc_now()
    result = db.execute(
        update(Job)
        .where(
            Job.id == job_id,
            Job.status == JobStatus.RUNNING.value,
            Job.locked_by == worker_id,
        )
        .values(locked_at=reference_now, updated_at=reference_now)
    )
    db.commit()
    return (result.rowcount or 0) == 1


def process_next_job(
    db: Session,
    worker_id: str,
    *,
    now: datetime | None = None,
    rng: Callable[[], float] | None = None,
    heartbeat_interval_seconds: float | None = None,
    heartbeat_session_factory: Callable[[], Session] | None = None,
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
    hb_stop = threading.Event()
    hb_thread: threading.Thread | None = None
    if heartbeat_interval_seconds is not None and heartbeat_interval_seconds > 0:
        session_maker = heartbeat_session_factory or sessionmaker(
            bind=db.get_bind(),
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,
        )
        claimed_job_id = job.id

        def _heartbeat_loop() -> None:
            while not hb_stop.wait(heartbeat_interval_seconds):
                try:
                    with session_maker() as hb_db:
                        refresh_job_lock(hb_db, claimed_job_id, worker_id)
                except Exception:
                    pass

        hb_thread = threading.Thread(target=_heartbeat_loop, daemon=True)
        hb_thread.start()

    try:
        try:
            result = handler(db, payload)
        finally:
            hb_stop.set()
            if hb_thread is not None:
                hb_thread.join(timeout=2.0)

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


def recover_stuck_jobs(
    db: Session,
    *,
    lock_timeout_seconds: float = DEFAULT_LOCK_TIMEOUT_SECONDS,
    now: datetime | None = None,
) -> int:
    """Recover jobs stuck in 'running' past ``lock_timeout_seconds``."""
    reference_now = now or utc_now()
    cutoff = reference_now - timedelta(seconds=lock_timeout_seconds)

    stuck_jobs = list(
        db.scalars(
            select(Job).where(
                Job.status == JobStatus.RUNNING.value,
                Job.locked_at.is_not(None),
                Job.locked_at < cutoff,
            )
        ).all()
    )
    if not stuck_jobs:
        return 0

    for job in stuck_jobs:
        previous_owner = job.locked_by
        job.locked_by = None
        job.locked_at = None
        job.updated_at = reference_now
        if job.attempts >= job.max_attempts:
            job.status = JobStatus.DEAD.value
            job.last_error = "Job lock timed out after reaching max_attempts."
            event_name = "job.stuck_marked_dead"
        else:
            job.status = JobStatus.QUEUED.value
            job.run_at = reference_now
            job.last_error = "Recovered from stale worker lock."
            event_name = "job.stuck_recovered"

        _log_event(
            logging.WARNING,
            event_name,
            job_id=job.id,
            job_type=job.job_type,
            previous_worker_id=previous_owner,
            attempts=job.attempts,
            max_attempts=job.max_attempts,
        )

    db.commit()
    return len(stuck_jobs)


def schedule_due_soon_reminders(
    db: Session,
    *,
    now: datetime | None = None,
) -> Job:
    """Schedule the hourly due_soon_reminder scan idempotently."""
    reference_now = now or utc_now()
    hour_bucket = reference_now.strftime("%Y-%m-%dT%H")
    job = enqueue_job(
        db,
        "due_soon_reminder",
        {"reference_date": reference_now.date().isoformat()},
        idempotency_key=f"schedule:due_soon_reminder:{hour_bucket}",
        run_at=reference_now,
    )
    db.commit()
    return job


def cleanup_old_succeeded_jobs(
    db: Session,
    *,
    retention_days: int | None = None,
    now: datetime | None = None,
) -> int:
    """Delete succeeded jobs older than ``retention_days``."""
    days = (
        retention_days
        if retention_days is not None
        else get_settings().job_cleanup_retention_days
    )
    reference_now = now or utc_now()
    cutoff = reference_now - timedelta(days=days)
    result = db.execute(
        delete(Job).where(
            Job.status == JobStatus.SUCCEEDED.value,
            func.coalesce(Job.completed_at, Job.updated_at) < cutoff,
        )
    )
    db.commit()
    return int(result.rowcount or 0)


def schedule_daily_job_cleanup(
    db: Session,
    *,
    now: datetime | None = None,
) -> Job:
    """Schedule the daily cleanup_succeeded_jobs job idempotently."""
    reference_now = now or utc_now()
    day_bucket = reference_now.strftime("%Y-%m-%d")
    job = enqueue_job(
        db,
        "cleanup_succeeded_jobs",
        {"retention_days": get_settings().job_cleanup_retention_days},
        idempotency_key=f"schedule:cleanup_succeeded_jobs:{day_bucket}",
        run_at=reference_now,
    )
    db.commit()
    return job


class Worker:
    def __init__(
        self,
        session_factory: sessionmaker[Session] = SessionLocal,
        *,
        worker_id: str | None = None,
        poll_interval_seconds: float = 1.0,
        lock_timeout_seconds: int = DEFAULT_LOCK_TIMEOUT_SECONDS,
        maintenance_interval_seconds: float | None = None,
        heartbeat_interval_seconds: float | None = None,
    ) -> None:
        settings = get_settings()
        self.session_factory = session_factory
        self.worker_id = worker_id or default_worker_id()
        self.poll_interval_seconds = poll_interval_seconds
        self.lock_timeout_seconds = lock_timeout_seconds
        self.maintenance_interval_seconds = (
            maintenance_interval_seconds
            if maintenance_interval_seconds is not None
            else settings.worker_maintenance_interval_seconds
        )
        self.heartbeat_interval_seconds = (
            heartbeat_interval_seconds
            if heartbeat_interval_seconds is not None
            else settings.worker_lock_heartbeat_interval_seconds
        )
        self._last_maintenance_at: float | None = None
        self._stop_event = threading.Event()

    def stop(self) -> None:
        self._stop_event.set()

    def recover_once(self) -> int:
        with self.session_factory() as db:
            return recover_stuck_jobs(db, lock_timeout_seconds=self.lock_timeout_seconds)

    def schedule_once(self) -> Job:
        with self.session_factory() as db:
            return schedule_due_soon_reminders(db)

    def schedule_cleanup_once(self) -> Job:
        with self.session_factory() as db:
            return schedule_daily_job_cleanup(db)

    def run_maintenance_if_due(self, *, now_monotonic: float | None = None) -> bool:
        current = now_monotonic if now_monotonic is not None else time.monotonic()
        if (
            self._last_maintenance_at is not None
            and (current - self._last_maintenance_at) < self.maintenance_interval_seconds
        ):
            return False
        self.recover_once()
        self.schedule_once()
        self.schedule_cleanup_once()
        self._last_maintenance_at = current
        return True

    def run_once(self) -> Job | None:
        with self.session_factory() as db:
            return process_next_job(
                db,
                self.worker_id,
                heartbeat_interval_seconds=self.heartbeat_interval_seconds,
                heartbeat_session_factory=self.session_factory,
            )

    def run_forever(self) -> None:
        _log_event(logging.INFO, "worker.started", worker_id=self.worker_id)
        while not self._stop_event.is_set():
            self.run_maintenance_if_due()
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

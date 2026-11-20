import json
import threading
from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.rate_limit import login_rate_limiter
from app.db.session import get_db
from app.jobs.queue import enqueue_job, get_job_by_id
from app.jobs.registry import register, unregister
from app.jobs.worker import (
    claim_next_job,
    compute_backoff_seconds,
    process_next_job,
    recover_stuck_jobs,
)
from app.main import create_app
from app.models.enums import JobStatus
from app.models.job import Job


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def test_handler_fails_twice_then_succeeds_with_backoff_times_asserted(
    db_session_factory: sessionmaker[Session],
) -> None:
    assert compute_backoff_seconds(1, rng=lambda: 0.0) == 10.0
    assert compute_backoff_seconds(2, rng=lambda: 0.0) == 40.0
    assert compute_backoff_seconds(3, rng=lambda: 0.0) == 160.0
    assert 10.0 <= compute_backoff_seconds(1, rng=lambda: 1.0) <= 11.0

    calls = {"count": 0}
    job_type = "test.flaky_twice"

    @register(job_type)
    def flaky_handler(_db: Session, payload: dict[str, Any]) -> dict[str, Any]:
        calls["count"] += 1
        if calls["count"] <= 2:
            raise RuntimeError(f"transient failure #{calls['count']}")
        return {"processed": payload["item"], "attempts_seen": calls["count"]}

    t0 = datetime(2026, 11, 20, 12, 0, 0, tzinfo=UTC)
    try:
        with db_session_factory() as db:
            job = enqueue_job(db, job_type, {"item": "story-1"}, run_at=t0, max_attempts=3)
            db.commit()
            job_id = job.id

        # Attempt 1 fails -> backoff 10s
        with db_session_factory() as db:
            j1 = process_next_job(db, "worker-a", now=t0, rng=lambda: 0.0)
            assert j1 is not None
            assert j1.status == JobStatus.QUEUED.value
            assert j1.attempts == 1
            assert _as_utc(j1.run_at) == t0 + timedelta(seconds=10)
            assert "transient failure #1" in (j1.last_error or "")

        # Too early (t0 + 5s) -> cannot claim
        with db_session_factory() as db:
            assert process_next_job(db, "worker-a", now=t0 + timedelta(seconds=5)) is None

        # Attempt 2 at t0 + 10s fails -> backoff 40s (next run at t0 + 50s)
        t1 = t0 + timedelta(seconds=10)
        with db_session_factory() as db:
            j2 = process_next_job(db, "worker-a", now=t1, rng=lambda: 0.0)
            assert j2 is not None
            assert j2.status == JobStatus.QUEUED.value
            assert j2.attempts == 2
            assert _as_utc(j2.run_at) == t1 + timedelta(seconds=40)

        # Too early (t0 + 49s) -> cannot claim
        with db_session_factory() as db:
            assert process_next_job(db, "worker-a", now=t0 + timedelta(seconds=49)) is None

        # Attempt 3 at t0 + 50s succeeds
        t2 = t0 + timedelta(seconds=50)
        with db_session_factory() as db:
            j3 = process_next_job(db, "worker-a", now=t2, rng=lambda: 0.0)
            assert j3 is not None
            assert j3.id == job_id
            assert j3.status == JobStatus.SUCCEEDED.value
            assert j3.attempts == 3
            assert j3.last_error is None
            assert json.loads(j3.result or "{}") == {
                "processed": "story-1",
                "attempts_seen": 3,
            }
    finally:
        unregister(job_type)


def test_job_becomes_dead_after_max_attempts(
    db_session_factory: sessionmaker[Session],
) -> None:
    job_type = "test.always_fail"

    @register(job_type)
    def always_fail(_db: Session, _payload: dict[str, Any]) -> None:
        raise ValueError("permanent failure")

    t = datetime(2026, 11, 20, 12, 0, 0, tzinfo=UTC)
    try:
        with db_session_factory() as db:
            job = enqueue_job(db, job_type, {}, run_at=t, max_attempts=3)
            db.commit()
            job_id = job.id

        for step_offset in (0, 10, 50):
            with db_session_factory() as db:
                res = process_next_job(
                    db,
                    "worker-dead",
                    now=t + timedelta(seconds=step_offset),
                    rng=lambda: 0.0,
                )
                assert res is not None

        with db_session_factory() as db:
            final_job = get_job_by_id(db, job_id)
            assert final_job is not None
            assert final_job.status == JobStatus.DEAD.value
            assert final_job.attempts == 3
            assert "ValueError: permanent failure" in (final_job.last_error or "")
            assert process_next_job(db, "worker-dead", now=t + timedelta(seconds=500)) is None
    finally:
        unregister(job_type)


def test_stuck_running_job_is_recovered(
    db_session_factory: sessionmaker[Session],
) -> None:
    job_type = "test.recover_ok"

    @register(job_type)
    def ok_handler(_db: Session, payload: dict[str, Any]) -> dict[str, Any]:
        return {"recovered": True, "value": payload.get("v")}

    t0 = datetime(2026, 11, 20, 12, 0, 0, tzinfo=UTC)
    try:
        with db_session_factory() as db:
            j1 = enqueue_job(db, job_type, {"v": 42}, run_at=t0, max_attempts=3)
            j2 = enqueue_job(db, job_type, {"v": 99}, run_at=t0, max_attempts=1)
            db.commit()
            j1_id, j2_id = j1.id, j2.id

        # Simulate crashed worker holding locks on both jobs
        with db_session_factory() as db:
            c1 = claim_next_job(db, "crashed-worker", now=t0)
            c2 = claim_next_job(db, "crashed-worker", now=t0)
            assert c1 is not None and c2 is not None

        # Before timeout (t0 + 60s): nothing recovered
        with db_session_factory() as db:
            assert (
                recover_stuck_jobs(db, lock_timeout_seconds=300, now=t0 + timedelta(seconds=60))
                == 0
            )

        # Past timeout (t0 + 301s): j1 re-queued, j2 marked dead (attempts == max_attempts == 1)
        t_recover = t0 + timedelta(seconds=301)
        with db_session_factory() as db:
            recovered = recover_stuck_jobs(db, lock_timeout_seconds=300, now=t_recover)
            assert recovered == 2

            reloaded_1 = get_job_by_id(db, j1_id)
            reloaded_2 = get_job_by_id(db, j2_id)
            assert reloaded_1 is not None and reloaded_1.status == JobStatus.QUEUED.value
            assert reloaded_1.locked_by is None and reloaded_1.locked_at is None
            assert reloaded_2 is not None and reloaded_2.status == JobStatus.DEAD.value

        # Healthy worker picks up recovered j1 and succeeds
        with db_session_factory() as db:
            done = process_next_job(db, "healthy-worker", now=t_recover)
            assert done is not None
            assert done.id == j1_id
            assert done.status == JobStatus.SUCCEEDED.value
    finally:
        unregister(job_type)


def test_duplicate_idempotency_key_does_not_create_second_job(
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as db:
        first = enqueue_job(
            db,
            "test.idempotent",
            {"x": 1},
            idempotency_key="dedupe-key-123",
        )
        second = enqueue_job(
            db,
            "test.idempotent",
            {"x": 2},
            idempotency_key="dedupe-key-123",
        )
        db.commit()
        assert first.id == second.id

    with db_session_factory() as db:
        third = enqueue_job(
            db,
            "test.idempotent",
            {"x": 3},
            idempotency_key="dedupe-key-123",
        )
        db.commit()
        assert third.id == first.id

        total = db.scalar(
            select(func.count(Job.id)).where(Job.idempotency_key == "dedupe-key-123")
        )
        assert total == 1


def test_two_workers_cannot_claim_the_same_job(
    db_session_factory: sessionmaker[Session],
) -> None:
    t0 = datetime(2026, 11, 20, 12, 0, 0, tzinfo=UTC)
    with db_session_factory() as db:
        job = enqueue_job(db, "test.concurrent", {"n": 1}, run_at=t0)
        db.commit()
        expected_id = job.id

    barrier = threading.Barrier(2)
    claimed_ids: list[str | None] = []
    lock = threading.Lock()

    def worker_claim(worker_name: str) -> None:
        barrier.wait()
        with db_session_factory() as db:
            claimed = claim_next_job(db, worker_name, now=t0)
            with lock:
                claimed_ids.append(claimed.id if claimed is not None else None)

    t1 = threading.Thread(target=worker_claim, args=("worker-1",))
    t2 = threading.Thread(target=worker_claim, args=("worker-2",))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    non_null = [cid for cid in claimed_ids if cid is not None]
    assert non_null == [expected_id]
    assert claimed_ids.count(None) == 1


@contextmanager
def _user_client(
    db_session_factory: sessionmaker[Session],
    email: str,
    name: str,
) -> Generator[tuple[TestClient, dict, dict[str, str]], None, None]:
    login_rate_limiter.reset()
    app = create_app()

    def override_get_db() -> Generator[Session, None, None]:
        db = db_session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        reg = client.post(
            "/api/v1/auth/register",
            json={"email": email, "name": name, "password": "StrongPassword123"},
        )
        assert reg.status_code == 201
        login = client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "StrongPassword123"},
        )
        assert login.status_code == 200
        yield client, reg.json(), {"X-CSRF-Token": login.json()["csrf_token"]}


def test_job_status_and_retry_endpoints_enforce_visibility_and_owner_rbac(
    db_session_factory: sessionmaker[Session],
) -> None:
    with (
        _user_client(db_session_factory, "jowner@example.com", "Job Owner") as (
            owner_client,
            owner_user,
            owner_headers,
        ),
        _user_client(db_session_factory, "jmember@example.com", "Job Member") as (
            member_client,
            member_user,
            member_headers,
        ),
        _user_client(db_session_factory, "joutsider@example.com", "Job Outsider") as (
            outsider_client,
            _outsider_user,
            outsider_headers,
        ),
    ):
        project_id = owner_client.post(
            "/api/v1/projects",
            json={"key": "JOB", "name": "Jobs Project"},
            headers=owner_headers,
        ).json()["id"]
        owner_client.post(
            f"/api/v1/projects/{project_id}/members",
            json={"email": "jmember@example.com", "role": "member"},
            headers=owner_headers,
        )

        with db_session_factory() as db:
            job = enqueue_job(
                db,
                "test.api_job",
                {"a": 1},
                project_id=project_id,
                created_by=owner_user["id"],
            )
            job.status = JobStatus.DEAD.value
            job.attempts = 3
            job.last_error = "Simulated crash"
            db.commit()
            job_id = job.id

        # Visibility: owner & project member -> 200; outsider -> 404
        owner_get = owner_client.get(f"/api/v1/jobs/{job_id}")
        assert owner_get.status_code == 200
        assert owner_get.json()["status"] == "dead"
        assert owner_get.json()["last_error"] == "Simulated crash"

        assert member_client.get(f"/api/v1/jobs/{job_id}").status_code == 200
        assert outsider_client.get(f"/api/v1/jobs/{job_id}").status_code == 404

        # Retry: member -> 403; outsider -> 404; owner -> 200
        assert (
            member_client.post(
                f"/api/v1/jobs/{job_id}/retry",
                headers=member_headers,
            ).status_code
            == 403
        )
        assert (
            outsider_client.post(
                f"/api/v1/jobs/{job_id}/retry",
                headers=outsider_headers,
            ).status_code
            == 404
        )

        retry_ok = owner_client.post(f"/api/v1/jobs/{job_id}/retry", headers=owner_headers)
        assert retry_ok.status_code == 200
        assert retry_ok.json()["status"] == "queued"
        assert retry_ok.json()["attempts"] == 0
        assert retry_ok.json()["last_error"] is None

        # Retrying a non-dead job returns 409
        retry_again = owner_client.post(f"/api/v1/jobs/{job_id}/retry", headers=owner_headers)
        assert retry_again.status_code == 409
        assert retry_again.json()["code"] == "JOB_NOT_DEAD"

        # Project-scoped job created by member requires CURRENT project membership
        with db_session_factory() as db:
            member_proj_job = enqueue_job(
                db,
                "test.member_project_job",
                {"b": 2},
                project_id=project_id,
                created_by=member_user["id"],
            )
            member_global_job = enqueue_job(
                db,
                "test.member_global_job",
                {"c": 3},
                project_id=None,
                created_by=member_user["id"],
            )
            db.commit()
            member_proj_job_id = member_proj_job.id
            member_global_job_id = member_global_job.id

        assert member_client.get(f"/api/v1/jobs/{member_proj_job_id}").status_code == 200
        assert member_client.get(f"/api/v1/jobs/{member_global_job_id}").status_code == 200

        # Remove member from project -> member loses access to project-scoped job they created,
        # while retaining creator access to non-project job.
        rm = owner_client.delete(
            f"/api/v1/projects/{project_id}/members/{member_user['id']}",
            headers=owner_headers,
        )
        assert rm.status_code == 204
        assert member_client.get(f"/api/v1/jobs/{member_proj_job_id}").status_code == 404
        assert member_client.get(f"/api/v1/jobs/{member_global_job_id}").status_code == 200

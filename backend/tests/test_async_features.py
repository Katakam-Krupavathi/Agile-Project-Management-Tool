import asyncio
import time
from contextlib import AsyncExitStack, asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.core.security import create_session_token, hash_password
from app.db.session import get_db
from app.jobs.worker import process_next_job, schedule_due_soon_reminders
from app.main import create_app
from app.models.enums import JobStatus
from app.models.user import User
from app.services.mailer import ConsoleMailer, set_mailer
from app.services.notification_service import reset_user_stream_slots
from app.services.report_service import set_report_failure_hook


class _RecordingMailer:
    def __init__(self) -> None:
        self.sent: list[dict[str, str]] = []

    def send(self, *, to_email: str, subject: str, body: str) -> None:
        self.sent.append({"to": to_email, "subject": subject, "body": body})


def _auth(client: TestClient, email: str, name: str) -> tuple[dict, dict[str, str]]:
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
    return reg.json(), {"X-CSRF-Token": login.json()["csrf_token"]}


def _drain_worker(db_session_factory: sessionmaker[Session], now: datetime | None = None) -> int:
    processed = 0
    while True:
        with db_session_factory() as db:
            job = process_next_job(db, "test-worker", now=now, rng=lambda: 0.0)
            if job is None:
                break
            if job.job_type != "send_email":
                processed += 1
    return processed


def test_assign_and_status_change_enqueue_notifications_and_mailer(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    mailer = _RecordingMailer()
    set_mailer(mailer)
    try:
        user, headers = _auth(client, "notify@example.com", "Notify User")
        project_id = client.post(
            "/api/v1/projects",
            json={"key": "NTF", "name": "Notify Project"},
            headers=headers,
        ).json()["id"]
        story_id = client.post(
            f"/api/v1/projects/{project_id}/stories",
            json={"title": "Notification Story"},
            headers=headers,
        ).json()["id"]

        task = client.post(
            f"/api/v1/stories/{story_id}/tasks",
            json={"title": "Wire SSE", "assignee_id": user["id"]},
            headers=headers,
        ).json()
        client.patch(
            f"/api/v1/tasks/{task['id']}",
            json={"status": "doing", "version": 1},
            headers=headers,
        )

        assert _drain_worker(db_session_factory) == 2
        assert len(mailer.sent) == 2
        assert mailer.sent[0]["to"] == "notify@example.com"

        listing = client.get("/api/v1/notifications").json()
        assert listing["unread_count"] == 2
        assert len(listing["items"]) == 2
        types = {item["type"] for item in listing["items"]}
        assert types == {"task.assigned", "task.status_changed"}

        first_id = listing["items"][0]["id"]
        mark_one = client.patch(f"/api/v1/notifications/{first_id}/read", headers=headers)
        assert mark_one.status_code == 200
        assert mark_one.json()["read_at"] is not None

        assert client.get("/api/v1/notifications").json()["unread_count"] == 1

        mark_all = client.post("/api/v1/notifications/read-all", headers=headers)
        assert mark_all.status_code == 200
        assert mark_all.json()["updated"] == 1
        assert client.get("/api/v1/notifications").json()["unread_count"] == 0
    finally:
        set_mailer(ConsoleMailer())


def test_sse_stream_requires_auth_and_supports_reconnect_last_event_id(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    # Unauthenticated SSE rejected with 401
    unauth = client.get("/api/v1/notifications/stream?once=true")
    assert unauth.status_code == 401

    user, headers = _auth(client, "sse@example.com", "SSE User")
    project_id = client.post(
        "/api/v1/projects",
        json={"key": "SSE", "name": "SSE Project"},
        headers=headers,
    ).json()["id"]
    story_id = client.post(
        f"/api/v1/projects/{project_id}/stories",
        json={"title": "Stream Story"},
        headers=headers,
    ).json()["id"]

    # Trigger first notification
    t1 = client.post(
        f"/api/v1/stories/{story_id}/tasks",
        json={"title": "First Task", "assignee_id": user["id"]},
        headers=headers,
    ).json()
    assert _drain_worker(db_session_factory) == 1

    stream1 = client.get("/api/v1/notifications/stream?once=true")
    assert stream1.status_code == 200
    assert stream1.headers["content-type"].startswith("text/event-stream")
    body1 = stream1.text
    assert "event: notification" in body1
    assert "First Task" in body1
    assert ": heartbeat" in body1

    first_event_id = next(
        line.removeprefix("id: ").strip()
        for line in body1.splitlines()
        if line.startswith("id: ")
    )

    # Trigger second notification and reconnect with Last-Event-ID
    client.patch(
        f"/api/v1/tasks/{t1['id']}",
        json={"status": "done", "version": 1},
        headers=headers,
    )
    assert _drain_worker(db_session_factory) == 1

    stream2 = client.get(
        "/api/v1/notifications/stream?once=true",
        headers={"Last-Event-ID": first_event_id},
    )
    assert stream2.status_code == 200
    body2 = stream2.text
    assert "is now done" in body2
    assert "Assigned task: First Task" not in body2

    # Mark first notification as read, keep second unread, then pass a missing Last-Event-ID anchor
    mark_first = client.patch(f"/api/v1/notifications/{first_event_id}/read", headers=headers)
    assert mark_first.status_code == 200

    stream_missing_anchor = client.get(
        "/api/v1/notifications/stream?once=true",
        headers={"Last-Event-ID": "00000000-0000-0000-0000-000000000000"},
    )
    assert stream_missing_anchor.status_code == 200
    missing_body = stream_missing_anchor.text
    assert "is now done" in missing_body
    assert "Assigned task: First Task" not in missing_body


def test_due_soon_reminder_scheduler_and_deduplication(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    user, headers = _auth(client, "due@example.com", "Due User")
    project_id = client.post(
        "/api/v1/projects",
        json={"key": "DUE", "name": "Due Soon Project"},
        headers=headers,
    ).json()["id"]
    story_id = client.post(
        f"/api/v1/projects/{project_id}/stories",
        json={"title": "Deadlines"},
        headers=headers,
    ).json()["id"]

    run_time = datetime.now(UTC).replace(hour=10, minute=0, second=0, microsecond=0) + timedelta(
        days=1
    )
    today = run_time.date()
    tomorrow = today + timedelta(days=1)
    later = today + timedelta(days=5)

    # Task due within 24h (should notify)
    client.post(
        f"/api/v1/stories/{story_id}/tasks",
        json={
            "title": "Submit PR",
            "assignee_id": user["id"],
            "due_date": tomorrow.isoformat(),
        },
        headers=headers,
    )
    # Done task due tomorrow (should NOT notify)
    client.post(
        f"/api/v1/stories/{story_id}/tasks",
        json={
            "title": "Already Finished",
            "status": "done",
            "assignee_id": user["id"],
            "due_date": tomorrow.isoformat(),
        },
        headers=headers,
    )
    # Task due in 5 days (should NOT notify)
    client.post(
        f"/api/v1/stories/{story_id}/tasks",
        json={
            "title": "Future Task",
            "assignee_id": user["id"],
            "due_date": later.isoformat(),
        },
        headers=headers,
    )
    # Drain the initial task.assigned notifications first
    _drain_worker(db_session_factory)

    with db_session_factory() as db:
        sched1 = schedule_due_soon_reminders(db, now=run_time)
        sched2 = schedule_due_soon_reminders(db, now=run_time + timedelta(minutes=15))
        assert sched1.id == sched2.id

    # Process due_soon_reminder + resulting send_notification
    assert _drain_worker(db_session_factory, now=run_time) == 2

    # Schedule in next hour on the same day -> reminder job runs, but task+day dedupe prevents dup
    next_hour = run_time + timedelta(hours=1)
    with db_session_factory() as db:
        sched3 = schedule_due_soon_reminders(db, now=next_hour)
        assert sched3.id != sched1.id

    # Only due_soon_reminder runs; send_notification is deduped by due_soon:<task_id>:<day>
    assert _drain_worker(db_session_factory, now=next_hour) == 1

    notifs = client.get("/api/v1/notifications").json()["items"]
    due_notifs = [n for n in notifs if n["type"] == "task.due_soon"]
    assert len(due_notifs) == 1
    assert "Submit PR" in due_notifs[0]["title"]


def test_report_generation_idempotency_injectable_failure_retry_and_download(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _user, headers = _auth(client, "rep@example.com", "Report User")
    project_id = client.post(
        "/api/v1/projects",
        json={"key": "REP", "name": "Reporting Project"},
        headers=headers,
    ).json()["id"]
    story_id = client.post(
        f"/api/v1/projects/{project_id}/stories",
        json={"title": "Release Prep", "status": "in_progress"},
        headers=headers,
    ).json()["id"]
    client.post(
        f"/api/v1/stories/{story_id}/tasks",
        json={"title": "Fix blocker", "status": "blocked", "due_date": "2020-01-01"},
        headers=headers,
    )
    client.post(
        f"/api/v1/stories/{story_id}/tasks",
        json={"title": "Ship docs", "status": "done"},
        headers=headers,
    )

    # Request report with Idempotency-Key -> 202
    req1 = client.post(
        f"/api/v1/projects/{project_id}/reports",
        headers={**headers, "Idempotency-Key": "sprint-review-1"},
    )
    assert req1.status_code == 202
    job_id = req1.json()["job_id"]
    assert req1.json()["status"] == "queued"

    # Duplicate Idempotency-Key returns same job_id
    req2 = client.post(
        f"/api/v1/projects/{project_id}/reports",
        headers={**headers, "Idempotency-Key": "sprint-review-1"},
    )
    assert req2.status_code == 202
    assert req2.json()["job_id"] == job_id

    # Inject a transient failure on first attempt to verify automatic retry
    attempts = {"count": 0}

    def fail_once(_payload: dict[str, Any]) -> None:
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise RuntimeError("transient report renderer error")

    set_report_failure_hook(fail_once)
    t0 = datetime.now(UTC) + timedelta(seconds=1)
    try:
        with db_session_factory() as db:
            j1 = process_next_job(db, "report-worker", now=t0, rng=lambda: 0.0)
            assert j1 is not None
            assert j1.id == job_id
            assert j1.status == JobStatus.QUEUED.value
            assert j1.attempts == 1

        with db_session_factory() as db:
            j2 = process_next_job(
                db,
                "report-worker",
                now=t0 + timedelta(seconds=10),
                rng=lambda: 0.0,
            )
            assert j2 is not None
            assert j2.id == job_id
            assert j2.status == JobStatus.SUCCEEDED.value
            assert j2.attempts == 2
    finally:
        set_report_failure_hook(None)

    # Job status endpoint exposes report_id in result
    job_status = client.get(f"/api/v1/jobs/{job_id}").json()
    assert job_status["status"] == "succeeded"
    report_id = job_status["result"]["report_id"]

    # List reports
    reports_list = client.get(f"/api/v1/projects/{project_id}/reports").json()
    assert len(reports_list["items"]) == 1
    assert reports_list["items"][0]["id"] == report_id

    # Download Markdown report
    download = client.get(f"/api/v1/reports/{report_id}")
    assert download.status_code == 200
    assert download.headers["content-type"].startswith("text/markdown")
    md = download.text
    assert "# REP Status Report" in md
    assert "Release Prep" in md
    assert "Fix blocker" in md
    assert "## Blocked Items" in md
    assert "## Overdue Tasks" in md
    assert "## Recent Activity" in md


@asynccontextmanager
async def _open_asgi_sse_stream(
    app: FastAPI,
    session_cookie: str,
    *,
    query_string: str = "",
) -> Any:
    settings = get_settings()
    receive_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    send_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    await receive_queue.put({"type": "http.request", "body": b"", "more_body": False})

    cookie_header = f"{settings.session_cookie_name}={session_cookie}".encode("latin-1")
    scope: dict[str, Any] = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/api/v1/notifications/stream",
        "raw_path": b"/api/v1/notifications/stream",
        "query_string": query_string.encode("latin-1"),
        "headers": [(b"cookie", cookie_header)],
        "client": ("127.0.0.1", 50000),
        "server": ("testserver", 80),
    }

    async def receive() -> dict[str, Any]:
        return await receive_queue.get()

    async def send(message: dict[str, Any]) -> None:
        await send_queue.put(message)

    task = asyncio.create_task(app(scope, receive, send))
    try:
        start_msg = await asyncio.wait_for(send_queue.get(), timeout=2.0)
        assert start_msg["type"] == "http.response.start"
        status_code = int(start_msg["status"])
        first_body = await asyncio.wait_for(send_queue.get(), timeout=2.0)
        assert first_body["type"] == "http.response.body"
        # Allow the generator to execute its first poll before pausing at sleep
        await asyncio.sleep(0.05)
        yield {
            "status": status_code,
            "first_chunk": first_body.get("body", b"").decode("utf-8", errors="replace"),
            "send_queue": send_queue,
            "task": task,
        }
    finally:
        await receive_queue.put({"type": "http.disconnect"})
        try:
            await asyncio.wait_for(task, timeout=2.0)
        except Exception:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)


def test_twenty_open_sse_streams_do_not_exhaust_db_pool(
    db_session_factory: sessionmaker[Session],
) -> None:
    engine = db_session_factory.kw["bind"]
    original_timeout = getattr(engine.pool, "_timeout", 30.0)
    engine.pool._timeout = 0.5

    app = create_app()

    def override_get_db() -> Any:
        db = db_session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    settings = get_settings()
    pw_hash = hash_password("StrongPassword123")
    cookies: list[str] = []
    with db_session_factory() as db:
        users = [
            User(
                email=f"stream_user_{idx}@example.com",
                name=f"Stream User {idx}",
                password_hash=pw_hash,
            )
            for idx in range(20)
        ]
        db.add_all(users)
        db.commit()
        for u in users:
            cookies.append(create_session_token(u.id, settings.secret_key))

    async def _run() -> None:
        async with AsyncExitStack() as stack:
            streams = []
            for cookie in cookies:
                stream = await stack.enter_async_context(_open_asgi_sse_stream(app, cookie))
                assert stream["status"] == 200
                assert "retry: 3000" in stream["first_chunk"]
                streams.append(stream)

            assert len(streams) == 20

            # Normal API request while all 20 streams are open must succeed quickly
            t0 = time.monotonic()
            with TestClient(app) as normal_client:
                normal_client.cookies.set(settings.session_cookie_name, cookies[0])
                resp = normal_client.get("/api/v1/notifications")
            elapsed = time.monotonic() - t0
            assert resp.status_code == 200, resp.text
            assert elapsed < 1.0

    try:
        asyncio.run(_run())
    finally:
        engine.pool._timeout = original_timeout
        reset_user_stream_slots()


def test_sse_per_user_stream_cap_and_max_lifetime(
    db_session_factory: sessionmaker[Session],
) -> None:
    reset_user_stream_slots()
    app = create_app()

    def override_get_db() -> Any:
        db = db_session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    base_settings = get_settings()
    with db_session_factory() as db:
        user = User(
            email="cap_user@example.com",
            name="Cap User",
            password_hash=hash_password("StrongPassword123"),
        )
        db.add(user)
        db.commit()
        cookie = create_session_token(user.id, base_settings.secret_key)

    async def _verify_cap() -> None:
        async with AsyncExitStack() as stack:
            # Open 3 concurrent streams for the same user (default cap = 3)
            s1 = await stack.enter_async_context(_open_asgi_sse_stream(app, cookie))
            s2 = await stack.enter_async_context(_open_asgi_sse_stream(app, cookie))
            s3 = await stack.enter_async_context(_open_asgi_sse_stream(app, cookie))
            assert s1["status"] == 200
            assert s2["status"] == 200
            assert s3["status"] == 200

            # 4th concurrent stream for the same user is rejected with 429
            with TestClient(app) as cap_client:
                cap_client.cookies.set(base_settings.session_cookie_name, cookie)
                over_cap = cap_client.get("/api/v1/notifications/stream?once=true")
                assert over_cap.status_code == 429
                assert over_cap.json()["code"] == "TOO_MANY_STREAMS"
                assert over_cap.headers.get("Retry-After") == "5"

        # After closing the 3 streams, user can open a stream again
        with TestClient(app) as after_client:
            after_client.cookies.set(base_settings.session_cookie_name, cookie)
            reopened = after_client.get("/api/v1/notifications/stream?once=true")
            assert reopened.status_code == 200

    asyncio.run(_verify_cap())

    # Configure short max_lifetime_seconds and verify stream ends automatically without once=true
    short_settings = base_settings.model_copy(
        update={
            "sse_max_lifetime_seconds": 0.12,
            "sse_poll_interval_seconds": 0.05,
        }
    )
    app.dependency_overrides[get_settings] = lambda: short_settings
    try:
        t0 = time.monotonic()
        with TestClient(app) as lifetime_client:
            lifetime_client.cookies.set(base_settings.session_cookie_name, cookie)
            resp = lifetime_client.get("/api/v1/notifications/stream")
        elapsed = time.monotonic() - t0
        assert resp.status_code == 200
        assert "retry: 3000" in resp.text
        assert 0.10 <= elapsed < 2.0
    finally:
        app.dependency_overrides.pop(get_settings, None)
        reset_user_stream_slots()


def test_notification_title_truncation_separate_email_job_and_masked_console_mailer(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
    caplog: Any,
) -> None:
    import logging

    from app.jobs.queue import enqueue_job

    mailer = _RecordingMailer()
    set_mailer(mailer)
    try:
        user, headers = _auth(client, "trunc@example.com", "Trunc User")
        project_id = client.post(
            "/api/v1/projects",
            json={"key": "TRN", "name": "Truncate Project"},
            headers=headers,
        ).json()["id"]
        story_id = client.post(
            f"/api/v1/projects/{project_id}/stories",
            json={"title": "Long Title Story"},
            headers=headers,
        ).json()["id"]

        long_task_title = "X" * 195
        client.post(
            f"/api/v1/stories/{story_id}/tasks",
            json={"title": long_task_title, "assignee_id": user["id"]},
            headers=headers,
        )

        # Step 1: process send_notification job -> creates notification with 200-char truncated
        # title and enqueues a separate send_email job (mailer is NOT called yet).
        with db_session_factory() as db:
            notif_job = process_next_job(db, "test-worker", rng=lambda: 0.0)
            assert notif_job is not None
            assert notif_job.job_type == "send_notification"
            assert notif_job.status == JobStatus.SUCCEEDED.value

        assert len(mailer.sent) == 0

        listing = client.get("/api/v1/notifications").json()["items"]
        assert len(listing) == 1
        notif = listing[0]
        assert len(notif["title"]) == 200
        assert notif["title"].endswith("…")

        # Re-enqueuing with the same per-notification idempotency key does not duplicate email job
        with db_session_factory() as db:
            dup_email_job = enqueue_job(
                db,
                "send_email",
                {
                    "notification_id": notif["id"],
                    "user_id": user["id"],
                    "subject": notif["title"],
                    "body": notif["body"],
                },
                project_id=project_id,
                idempotency_key=f"send_email:{notif['id']}",
            )
            db.commit()
            assert dup_email_job.job_type == "send_email"

        # Step 2: process send_email job -> sends exactly 1 email
        with db_session_factory() as db:
            email_job = process_next_job(db, "test-worker", rng=lambda: 0.0)
            assert email_job is not None
            assert email_job.job_type == "send_email"
            assert email_job.status == JobStatus.SUCCEEDED.value
            assert process_next_job(db, "test-worker", rng=lambda: 0.0) is None

        assert len(mailer.sent) == 1
        assert len(mailer.sent[0]["subject"]) == 200
    finally:
        set_mailer(ConsoleMailer())

    # ConsoleMailer logs only masked address and subject, never full body
    with caplog.at_level(logging.INFO, logger="app.services.mailer"):
        ConsoleMailer().send(
            to_email="sensitive.person@example.com",
            subject="Status update",
            body="TOP_SECRET_TASK_BODY_CONTENT",
        )
    logged_text = "\n".join(caplog.messages)
    assert "s***@example.com" in logged_text
    assert "sensitive.person@example.com" not in logged_text
    assert "Status update" in logged_text
    assert "TOP_SECRET_TASK_BODY_CONTENT" not in logged_text


def test_report_single_active_job_cooldown_retention_and_user_scoped_idempotency(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _user, headers = _auth(client, "rep_limit@example.com", "Report Limit User")
    project_id = client.post(
        "/api/v1/projects",
        json={"key": "RPL", "name": "Report Limits Project"},
        headers=headers,
    ).json()["id"]

    # 1. First report request creates a queued job
    r1 = client.post(
        f"/api/v1/projects/{project_id}/reports",
        headers={**headers, "Idempotency-Key": "k1"},
    )
    assert r1.status_code == 202
    job_1_id = r1.json()["job_id"]

    # 2. Second report request while one is still active returns the SAME job_id
    r2 = client.post(
        f"/api/v1/projects/{project_id}/reports",
        headers={**headers, "Idempotency-Key": "k2"},
    )
    assert r2.status_code == 202
    assert r2.json()["job_id"] == job_1_id

    # Drain worker so job_1 completes and generates report #1
    assert _drain_worker(db_session_factory) == 1

    # 3. Immediate request within cooldown (30s default) returns 429 REPORT_COOLDOWN_ACTIVE
    cooldown_res = client.post(
        f"/api/v1/projects/{project_id}/reports",
        headers=headers,
    )
    assert cooldown_res.status_code == 429
    assert cooldown_res.json()["code"] == "REPORT_COOLDOWN_ACTIVE"
    assert int(cooldown_res.headers["Retry-After"]) >= 1

    # Same user + project + Idempotency-Key "k1" still returns the original job idempotently
    idem_replay = client.post(
        f"/api/v1/projects/{project_id}/reports",
        headers={**headers, "Idempotency-Key": "k1"},
    )
    assert idem_replay.status_code == 202
    assert idem_replay.json()["job_id"] == job_1_id

    # 4. Retention rule: keep only the latest N reports per project (configure N=2, cooldown=0)
    base_settings = get_settings()
    custom_settings = base_settings.model_copy(
        update={
            "report_cooldown_seconds": 0,
            "report_retention_max_per_project": 2,
        }
    )
    client.app.dependency_overrides[get_settings] = lambda: custom_settings  # type: ignore[ union-attr ]
    try:
        for idx in (2, 3):
            enq = client.post(
                f"/api/v1/projects/{project_id}/reports",
                headers={**headers, "Idempotency-Key": f"ret-{idx}"},
            )
            assert enq.status_code == 202
            with db_session_factory() as db:
                j = process_next_job(db, "ret-worker", rng=lambda: 0.0)
                assert j is not None and j.status == JobStatus.SUCCEEDED.value

        reports = client.get(f"/api/v1/projects/{project_id}/reports").json()["items"]
        assert len(reports) == 2
    finally:
        client.app.dependency_overrides.pop(get_settings, None)  # type: ignore[ union-attr ]

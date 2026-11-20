import json
from collections.abc import Callable
from datetime import UTC, datetime
from math import ceil
from typing import Any

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import BadRequestError, NotFoundError, RateLimitError
from app.core.pagination import decode_cursor, encode_cursor
from app.jobs.queue import enqueue_job
from app.models.enums import JobStatus, ProjectRole, TaskStatus
from app.models.job import Job
from app.models.project import Project
from app.models.report import Report
from app.models.user import User, utc_now
from app.schemas.report import ReportSummaryResponse
from app.services import activity as activity_service
from app.services import tree_service
from app.services.permissions import assert_project_role

FailureHook = Callable[[dict[str, Any]], None]
_report_failure_hook: FailureHook | None = None


def set_report_failure_hook(hook: FailureHook | None) -> None:
    """Inject a failure callback for testing report retry behavior."""
    global _report_failure_hook
    _report_failure_hook = hook


def request_project_report(
    db: Session,
    project: Project,
    user: User,
    *,
    idempotency_key: str | None = None,
    cooldown_seconds: int | None = None,
    retention_max: int | None = None,
) -> Job:
    settings = get_settings()
    effective_cooldown = (
        cooldown_seconds if cooldown_seconds is not None else settings.report_cooldown_seconds
    )
    effective_retention = (
        retention_max
        if retention_max is not None
        else settings.report_retention_max_per_project
    )

    scoped_key = (
        f"report:{project.id}:{user.id}:{idempotency_key.strip()}"
        if idempotency_key and idempotency_key.strip()
        else None
    )
    if scoped_key:
        existing_idem = db.scalar(select(Job).where(Job.idempotency_key == scoped_key))
        if existing_idem is not None:
            return existing_idem

    active_job = db.scalar(
        select(Job)
        .where(
            Job.project_id == project.id,
            Job.job_type == "generate_project_report",
            Job.status.in_((JobStatus.QUEUED.value, JobStatus.RUNNING.value)),
        )
        .order_by(Job.created_at.desc())
        .limit(1)
    )
    if active_job is not None:
        return active_job

    if effective_cooldown > 0:
        latest_report = db.scalar(
            select(Report)
            .where(Report.project_id == project.id)
            .order_by(Report.created_at.desc())
            .limit(1)
        )
        if latest_report is not None:
            elapsed = (utc_now() - latest_report.created_at).total_seconds()
            if elapsed < effective_cooldown:
                retry_after = max(1, ceil(effective_cooldown - elapsed))
                raise RateLimitError(
                    "A report was recently generated for this project. Please wait before retry.",
                    code="REPORT_COOLDOWN_ACTIVE",
                    headers={"Retry-After": str(retry_after)},
                )

    job = enqueue_job(
        db,
        "generate_project_report",
        {
            "project_id": project.id,
            "requested_by": user.id,
            "retention_max": effective_retention,
        },
        project_id=project.id,
        created_by=user.id,
        idempotency_key=scoped_key,
    )
    # Persist job_id inside payload if newly created so the handler can link Report.job_id
    payload = json.loads(job.payload) if job.payload else {}
    if "job_id" not in payload:
        payload["job_id"] = job.id
        job.payload = json.dumps(payload, default=str)
    db.commit()
    db.refresh(job)
    return job


def build_project_report_markdown(db: Session, project: Project) -> tuple[str, str]:
    now = datetime.now(UTC)
    today = now.date()
    tree = tree_service.get_project_tree(db, project, ProjectRole.OWNER)
    recent_activity, _, _ = activity_service.list_project_activity(db, project.id, limit=15)

    title = f"{project.key} Status Report ({today.isoformat()})"
    lines: list[str] = [
        f"# {title}",
        "",
        f"**Project:** {project.name} (`{project.key}`)",
        f"**Generated:** {now.strftime('%Y-%m-%d %H:%M UTC')}",
        f"**Health:** `{tree.rollup.health.value}`",
        (
            f"**Summary:** {tree.rollup.done_stories}/{tree.rollup.total_stories} stories done, "
            f"{tree.rollup.done_tasks}/{tree.rollup.total_tasks} tasks done "
            f"({tree.rollup.progress_pct}%), "
            f"{tree.rollup.blocked_tasks} blocked, {tree.rollup.overdue_tasks} overdue."
        ),
        "",
        "## Story Progress",
        "",
    ]

    if not tree.stories:
        lines.append("_No active stories in this project._")
    else:
        lines.extend(
            [
                "| Key | Title | Status | Progress | Tasks | Blocked |",
                "| --- | --- | --- | --- | --- | --- |",
            ]
        )
        for node in tree.stories:
            blocked_label = "Yes" if node.rollup.is_blocked else "No"
            lines.append(
                f"| {node.story.key} | {node.story.title} | {node.story.status.value} "
                f"| {node.rollup.progress_pct}% "
                f"| {node.rollup.done_tasks}/{node.rollup.total_tasks} | {blocked_label} |"
            )

    blocked_items: list[str] = []
    overdue_items: list[str] = []
    for node in tree.stories:
        for task in node.tasks:
            if task.status == TaskStatus.BLOCKED:
                blocked_items.append(f"- **{node.story.key}** — {task.title}")
            if (
                task.due_date is not None
                and task.due_date < today
                and task.status != TaskStatus.DONE
            ):
                overdue_items.append(
                    f"- **{node.story.key}** — {task.title} (due {task.due_date.isoformat()})"
                )

    lines.extend(["", "## Blocked Items", ""])
    lines.extend(blocked_items if blocked_items else ["_None._"])

    lines.extend(["", "## Overdue Tasks", ""])
    lines.extend(overdue_items if overdue_items else ["_None._"])

    lines.extend(["", "## Recent Activity", ""])
    if not recent_activity:
        lines.append("_No recent activity._")
    else:
        for entry in recent_activity:
            actor = entry.actor_name or "System"
            lines.append(
                f"- `{entry.created_at.strftime('%Y-%m-%d %H:%M')}` **{actor}** — {entry.action}"
            )

    return title, "\n".join(lines) + "\n"


def prune_old_project_reports(
    db: Session,
    project_id: str,
    *,
    max_reports: int | None = None,
) -> int:
    keep = (
        max_reports
        if max_reports is not None
        else get_settings().report_retention_max_per_project
    )
    if keep <= 0:
        return 0
    all_reports = list(
        db.scalars(
            select(Report)
            .where(Report.project_id == project_id)
            .order_by(Report.created_at.desc(), Report.id.desc())
        ).all()
    )
    stale = all_reports[keep:]
    for old_report in stale:
        db.delete(old_report)
    if stale:
        db.flush()
    return len(stale)


def generate_report_for_job(db: Session, payload: dict[str, Any]) -> dict[str, Any]:
    if _report_failure_hook is not None:
        _report_failure_hook(payload)

    job_id = payload.get("job_id")
    if isinstance(job_id, str):
        existing = db.scalar(select(Report).where(Report.job_id == job_id))
        if existing is not None:
            return {"report_id": existing.id, "title": existing.title}

    project_id = str(payload["project_id"])
    project = db.scalar(
        select(Project).where(Project.id == project_id, Project.deleted_at.is_(None))
    )
    if project is None:
        raise ValueError(f"Project '{project_id}' not found or archived.")

    title, markdown = build_project_report_markdown(db, project)
    report = Report(
        project_id=project.id,
        job_id=job_id if isinstance(job_id, str) else None,
        created_by=payload.get("requested_by"),
        title=title,
        content_markdown=markdown,
    )
    db.add(report)
    db.flush()

    retention_raw = payload.get("retention_max")
    retention_max = int(retention_raw) if isinstance(retention_raw, int) else None
    prune_old_project_reports(db, project.id, max_reports=retention_max)

    return {"report_id": report.id, "title": report.title}


def list_project_reports(
    db: Session,
    project_id: str,
    *,
    cursor: str | None = None,
    limit: int = 20,
) -> tuple[list[ReportSummaryResponse], str | None, bool]:
    stmt = select(Report).where(Report.project_id == project_id)

    if cursor:
        cursor_data = decode_cursor(cursor)
        created_at_raw = cursor_data.get("created_at")
        cursor_id = cursor_data.get("id")
        if not isinstance(created_at_raw, str) or not isinstance(cursor_id, str):
            raise BadRequestError("Invalid pagination cursor.", code="INVALID_CURSOR")
        try:
            cursor_created_at = datetime.fromisoformat(created_at_raw)
        except ValueError as exc:
            raise BadRequestError("Invalid pagination cursor.", code="INVALID_CURSOR") from exc
        stmt = stmt.where(
            or_(
                Report.created_at < cursor_created_at,
                and_(Report.created_at == cursor_created_at, Report.id < cursor_id),
            )
        )

    stmt = stmt.order_by(Report.created_at.desc(), Report.id.desc()).limit(limit + 1)
    rows = list(db.scalars(stmt).all())

    has_more = len(rows) > limit
    page_rows = rows[:limit]
    items = [ReportSummaryResponse.model_validate(row) for row in page_rows]

    next_cursor: str | None = None
    if has_more and page_rows:
        last_item = page_rows[-1]
        next_cursor = encode_cursor(
            {"created_at": last_item.created_at.isoformat(), "id": last_item.id}
        )

    return items, next_cursor, has_more


def get_report_for_user(db: Session, report_id: str, user: User) -> Report:
    report = db.scalar(select(Report).where(Report.id == report_id))
    if report is None:
        raise NotFoundError("Report not found.", code="REPORT_NOT_FOUND")
    assert_project_role(db, report.project_id, user, ProjectRole.VIEWER)
    return report

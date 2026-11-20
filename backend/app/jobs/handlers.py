from datetime import date, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.jobs.queue import enqueue_job
from app.jobs.registry import register
from app.models.enums import ActivityEntityType, TaskStatus
from app.models.project import Project, ProjectMember
from app.models.story import Story
from app.models.task import Task
from app.models.user import User, utc_now
from app.services import notification_service, report_service
from app.services.mailer import get_mailer


@register("send_notification")
def handle_send_notification(db: Session, payload: dict[str, Any]) -> dict[str, Any]:
    user_id = str(payload["user_id"])
    project_id = payload.get("project_id")
    if isinstance(project_id, str) and project_id:
        is_member = db.scalar(
            select(ProjectMember.id).where(
                ProjectMember.project_id == project_id,
                ProjectMember.user_id == user_id,
            )
        )
        if is_member is None:
            return {"skipped": True, "reason": "not_project_member"}

    notification = notification_service.create_notification(
        db,
        user_id=user_id,
        project_id=project_id,
        notification_type=str(payload["type"]),
        title=str(payload["title"]),
        body=payload.get("body"),
        entity_type=payload.get("entity_type"),
        entity_id=payload.get("entity_id"),
        send_email=True,
    )
    return {"notification_id": notification.id}


@register("send_email")
def handle_send_email(db: Session, payload: dict[str, Any]) -> dict[str, Any]:
    to_email = payload.get("to_email")
    if not isinstance(to_email, str) or not to_email:
        user_id = str(payload.get("user_id", ""))
        user = db.scalar(select(User).where(User.id == user_id))
        if user is None:
            return {"skipped": True, "reason": "user_not_found"}
        to_email = user.email

    subject = notification_service.truncate_notification_title(str(payload.get("subject", "")))
    body = str(payload.get("body") or subject)
    get_mailer().send(
        to_email=to_email,
        subject=subject,
        body=body,
    )
    return {
        "sent": True,
        "notification_id": payload.get("notification_id"),
    }


@register("due_soon_reminder")
def handle_due_soon_reminder(db: Session, payload: dict[str, Any]) -> dict[str, Any]:
    ref_raw = payload.get("reference_date")
    reference_day = date.fromisoformat(ref_raw) if isinstance(ref_raw, str) else utc_now().date()
    horizon_day = reference_day + timedelta(days=1)

    rows = db.execute(
        select(Task, Story, Project)
        .join(Story, Story.id == Task.story_id)
        .join(Project, Project.id == Story.project_id)
        .where(
            Task.deleted_at.is_(None),
            Story.deleted_at.is_(None),
            Project.deleted_at.is_(None),
            Task.status != TaskStatus.DONE.value,
            Task.assignee_id.is_not(None),
            Task.due_date.is_not(None),
            Task.due_date >= reference_day,
            Task.due_date <= horizon_day,
        )
    ).all()

    enqueued_job_ids: list[str] = []
    for task, story, project in rows:
        if task.assignee_id is None or task.due_date is None:
            continue
        dedupe_key = f"due_soon:{task.id}:{reference_day.isoformat()}"
        job = enqueue_job(
            db,
            "send_notification",
            {
                "user_id": task.assignee_id,
                "project_id": project.id,
                "type": "task.due_soon",
                "title": f"Task due soon: {task.title}",
                "body": (
                    f"Task '{task.title}' in {project.key}-{story.number} "
                    f"is due on {task.due_date.isoformat()}."
                ),
                "entity_type": ActivityEntityType.TASK.value,
                "entity_id": task.id,
            },
            project_id=project.id,
            idempotency_key=dedupe_key,
        )
        enqueued_job_ids.append(job.id)

    return {
        "reference_date": reference_day.isoformat(),
        "matched_tasks": len(rows),
        "notification_job_ids": enqueued_job_ids,
    }


@register("generate_project_report")
def handle_generate_project_report(db: Session, payload: dict[str, Any]) -> dict[str, Any]:
    return report_service.generate_report_for_job(db, payload)

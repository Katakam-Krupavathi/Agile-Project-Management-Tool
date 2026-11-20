from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.orm import Session

from app.core.errors import BadRequestError, ConflictError
from app.core.pagination import decode_cursor, encode_cursor
from app.db.session import begin_immediate_if_sqlite
from app.jobs.queue import enqueue_job
from app.models.enums import ActivityEntityType, TaskStatus
from app.models.project import ProjectMember
from app.models.story import Story
from app.models.task import Task
from app.models.user import utc_now
from app.schemas.task import TaskCreateRequest, TaskMoveRequest, TaskResponse, TaskUpdateRequest
from app.services.activity import compute_diff, record_activity
from app.services.ranking import RANK_STEP, compute_insert_position, rebalance_positions


def to_task_response(task: Task) -> TaskResponse:
    return TaskResponse(
        id=task.id,
        story_id=task.story_id,
        title=task.title,
        description=task.description,
        status=TaskStatus(task.status),
        assignee_id=task.assignee_id,
        estimate_hours=task.estimate_hours,
        due_date=task.due_date,
        position=task.position,
        version=task.version,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


def _validate_assignee(db: Session, project_id: str, assignee_id: str | None) -> None:
    if assignee_id is None:
        return
    member = db.scalar(
        select(ProjectMember.id).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == assignee_id,
        )
    )
    if member is None:
        raise BadRequestError(
            "Assignee must be a member of this project.",
            code="INVALID_ASSIGNEE",
        )


def list_tasks(
    db: Session,
    story_id: str,
    *,
    cursor: str | None = None,
    limit: int = 50,
) -> tuple[list[TaskResponse], str | None, bool]:
    stmt = select(Task).where(Task.story_id == story_id, Task.deleted_at.is_(None))

    if cursor:
        cursor_data = decode_cursor(cursor)
        pos_raw = cursor_data.get("position")
        cursor_id = cursor_data.get("id")
        if not isinstance(pos_raw, (int, float)) or not isinstance(cursor_id, str):
            raise BadRequestError("Invalid pagination cursor.", code="INVALID_CURSOR")
        stmt = stmt.where(
            or_(
                Task.position > float(pos_raw),
                and_(Task.position == float(pos_raw), Task.id > cursor_id),
            )
        )

    stmt = stmt.order_by(Task.position.asc(), Task.id.asc()).limit(limit + 1)
    rows = list(db.scalars(stmt).all())

    has_more = len(rows) > limit
    page_rows = rows[:limit]
    items = [to_task_response(task) for task in page_rows]

    next_cursor: str | None = None
    if has_more and page_rows:
        last_task = page_rows[-1]
        next_cursor = encode_cursor({"position": last_task.position, "id": last_task.id})

    return items, next_cursor, has_more


def create_task(
    db: Session,
    story: Story,
    payload: TaskCreateRequest,
    actor_id: str,
) -> TaskResponse:
    _validate_assignee(db, story.project_id, payload.assignee_id)

    max_pos = db.scalar(
        select(func.max(Task.position)).where(
            Task.story_id == story.id,
            Task.deleted_at.is_(None),
        )
    )
    position = float(max_pos) + RANK_STEP if max_pos is not None else RANK_STEP

    task = Task(
        story_id=story.id,
        title=payload.title,
        description=payload.description,
        status=payload.status.value,
        assignee_id=payload.assignee_id,
        estimate_hours=payload.estimate_hours,
        due_date=payload.due_date,
        position=position,
    )
    db.add(task)
    db.flush()
    record_activity(
        db,
        project_id=story.project_id,
        actor_id=actor_id,
        entity_type=ActivityEntityType.TASK,
        entity_id=task.id,
        action="task.created",
        details={"story_id": story.id, "title": task.title, "status": task.status},
    )
    if task.assignee_id:
        enqueue_job(
            db,
            "send_notification",
            {
                "user_id": task.assignee_id,
                "project_id": story.project_id,
                "type": "task.assigned",
                "title": f"Assigned task: {task.title}",
                "body": f"You were assigned to task '{task.title}'.",
                "entity_type": ActivityEntityType.TASK.value,
                "entity_id": task.id,
            },
            project_id=story.project_id,
            created_by=actor_id,
        )
    db.commit()
    db.refresh(task)
    return to_task_response(task)


def update_task(
    db: Session,
    task: Task,
    project_id: str,
    payload: TaskUpdateRequest,
    actor_id: str,
) -> TaskResponse:
    task_id = task.id

    if "assignee_id" in payload.model_fields_set:
        _validate_assignee(db, project_id, payload.assignee_id)

    before = {
        "title": task.title,
        "description": task.description,
        "status": task.status,
        "assignee_id": task.assignee_id,
        "estimate_hours": task.estimate_hours,
        "due_date": task.due_date.isoformat() if task.due_date else None,
    }

    new_title = payload.title if payload.title is not None else task.title
    new_description = (
        payload.description if "description" in payload.model_fields_set else task.description
    )
    new_status = payload.status.value if payload.status is not None else task.status
    new_assignee = (
        payload.assignee_id if "assignee_id" in payload.model_fields_set else task.assignee_id
    )
    new_estimate = (
        payload.estimate_hours
        if "estimate_hours" in payload.model_fields_set
        else task.estimate_hours
    )
    new_due_date = payload.due_date if "due_date" in payload.model_fields_set else task.due_date

    after = {
        "title": new_title,
        "description": new_description,
        "status": new_status,
        "assignee_id": new_assignee,
        "estimate_hours": new_estimate,
        "due_date": new_due_date.isoformat() if new_due_date else None,
    }

    now = utc_now()
    begin_immediate_if_sqlite(db)
    result = db.execute(
        update(Task)
        .where(
            Task.id == task_id,
            Task.version == payload.version,
            Task.deleted_at.is_(None),
        )
        .values(
            title=new_title,
            description=new_description,
            status=new_status,
            assignee_id=new_assignee,
            estimate_hours=new_estimate,
            due_date=new_due_date,
            version=payload.version + 1,
            updated_at=now,
        )
    )
    if result.rowcount != 1:
        db.rollback()
        raise ConflictError(
            "Task has been modified by another request. Reload and retry.",
            code="VERSION_CONFLICT",
        )

    record_activity(
        db,
        project_id=project_id,
        actor_id=actor_id,
        entity_type=ActivityEntityType.TASK,
        entity_id=task_id,
        action="task.updated",
        details=compute_diff(before, after),
    )
    if new_assignee and new_assignee != before["assignee_id"]:
        enqueue_job(
            db,
            "send_notification",
            {
                "user_id": new_assignee,
                "project_id": project_id,
                "type": "task.assigned",
                "title": f"Assigned task: {new_title}",
                "body": f"You were assigned to task '{new_title}'.",
                "entity_type": ActivityEntityType.TASK.value,
                "entity_id": task_id,
            },
            project_id=project_id,
            created_by=actor_id,
        )
    if new_assignee and new_status != before["status"]:
        enqueue_job(
            db,
            "send_notification",
            {
                "user_id": new_assignee,
                "project_id": project_id,
                "type": "task.status_changed",
                "title": f"Task '{new_title}' is now {new_status}",
                "body": f"Task '{new_title}' changed from {before['status']} to {new_status}.",
                "entity_type": ActivityEntityType.TASK.value,
                "entity_id": task_id,
            },
            project_id=project_id,
            created_by=actor_id,
        )
    db.commit()
    updated = db.scalar(select(Task).where(Task.id == task_id))
    assert updated is not None
    return to_task_response(updated)


def move_task(
    db: Session,
    task: Task,
    project_id: str,
    payload: TaskMoveRequest,
    actor_id: str,
) -> TaskResponse:
    if payload.version is not None and task.version != payload.version:
        raise ConflictError(
            "Task has been modified by another request. Reload and retry.",
            code="VERSION_CONFLICT",
        )
    if payload.before_id == task.id or payload.after_id == task.id:
        raise BadRequestError("Cannot position a task relative to itself.", code="INVALID_MOVE")

    before = {"status": task.status, "position": task.position}
    siblings = list(
        db.scalars(
            select(Task)
            .where(
                Task.story_id == task.story_id,
                Task.deleted_at.is_(None),
                Task.id != task.id,
            )
            .order_by(Task.position.asc(), Task.id.asc())
        ).all()
    )
    sibling_by_id = {item.id: item for item in siblings}

    before_task = sibling_by_id.get(payload.before_id) if payload.before_id else None
    after_task = sibling_by_id.get(payload.after_id) if payload.after_id else None

    if payload.before_id and before_task is None:
        raise BadRequestError("Reference before_id not found in story.", code="INVALID_MOVE")
    if payload.after_id and after_task is None:
        raise BadRequestError("Reference after_id not found in story.", code="INVALID_MOVE")

    before_pos = before_task.position if before_task is not None else None
    after_pos = after_task.position if after_task is not None else None

    if before_pos is None and after_pos is None and siblings:
        before_pos = siblings[-1].position

    new_pos, needs_rebalance = compute_insert_position(before_pos, after_pos)
    if payload.status is not None:
        task.status = payload.status.value

    if needs_rebalance:
        ordered = list(siblings)
        if before_task is not None:
            insert_idx = ordered.index(before_task) + 1
        elif after_task is not None:
            insert_idx = ordered.index(after_task)
        else:
            insert_idx = len(ordered)
        ordered.insert(insert_idx, task)
        rebalance_positions(ordered, lambda item, pos: setattr(item, "position", pos))
    else:
        task.position = new_pos

    task.version += 1
    record_activity(
        db,
        project_id=project_id,
        actor_id=actor_id,
        entity_type=ActivityEntityType.TASK,
        entity_id=task.id,
        action="task.moved",
        details=compute_diff(before, {"status": task.status, "position": task.position}),
    )
    if task.assignee_id and task.status != before["status"]:
        enqueue_job(
            db,
            "send_notification",
            {
                "user_id": task.assignee_id,
                "project_id": project_id,
                "type": "task.status_changed",
                "title": f"Task '{task.title}' is now {task.status}",
                "body": f"Task '{task.title}' changed from {before['status']} to {task.status}.",
                "entity_type": ActivityEntityType.TASK.value,
                "entity_id": task.id,
            },
            project_id=project_id,
            created_by=actor_id,
        )
    db.commit()
    db.refresh(task)
    return to_task_response(task)


def soft_delete_task(db: Session, task: Task, project_id: str, actor_id: str) -> None:
    task_id = task.id
    task_title = task.title
    story_id = task.story_id
    expected_version = task.version
    now = utc_now()

    begin_immediate_if_sqlite(db)
    result = db.execute(
        update(Task)
        .where(
            Task.id == task_id,
            Task.version == expected_version,
            Task.deleted_at.is_(None),
        )
        .values(deleted_at=now, version=expected_version + 1, updated_at=now)
    )
    if result.rowcount != 1:
        db.rollback()
        raise ConflictError(
            "Task has been modified by another request. Reload and retry.",
            code="VERSION_CONFLICT",
        )

    record_activity(
        db,
        project_id=project_id,
        actor_id=actor_id,
        entity_type=ActivityEntityType.TASK,
        entity_id=task_id,
        action="task.deleted",
        details={"title": task_title, "story_id": story_id},
    )
    db.commit()

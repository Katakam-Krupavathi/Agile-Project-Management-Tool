from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.core.errors import BadRequestError
from app.core.pagination import decode_cursor, encode_cursor
from app.models.enums import TaskStatus
from app.models.project import ProjectMember
from app.models.story import Story
from app.models.task import Task
from app.models.user import utc_now
from app.schemas.task import TaskCreateRequest, TaskMoveRequest, TaskResponse, TaskUpdateRequest
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
    db.commit()
    db.refresh(task)
    return to_task_response(task)


def update_task(
    db: Session,
    task: Task,
    project_id: str,
    payload: TaskUpdateRequest,
) -> TaskResponse:
    if "assignee_id" in payload.model_fields_set:
        _validate_assignee(db, project_id, payload.assignee_id)
        task.assignee_id = payload.assignee_id

    if payload.title is not None:
        task.title = payload.title
    if "description" in payload.model_fields_set:
        task.description = payload.description
    if payload.status is not None:
        task.status = payload.status.value
    if "estimate_hours" in payload.model_fields_set:
        task.estimate_hours = payload.estimate_hours
    if "due_date" in payload.model_fields_set:
        task.due_date = payload.due_date

    task.version += 1
    db.commit()
    db.refresh(task)
    return to_task_response(task)


def move_task(
    db: Session,
    task: Task,
    payload: TaskMoveRequest,
) -> TaskResponse:
    if payload.before_id == task.id or payload.after_id == task.id:
        raise BadRequestError("Cannot position a task relative to itself.", code="INVALID_MOVE")

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
    db.commit()
    db.refresh(task)
    return to_task_response(task)


def soft_delete_task(db: Session, task: Task) -> None:
    task.deleted_at = utc_now()
    task.version += 1
    db.commit()

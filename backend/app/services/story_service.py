from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.orm import Session

from app.core.errors import BadRequestError, ConflictError
from app.core.pagination import decode_cursor, encode_cursor
from app.jobs.queue import enqueue_job
from app.models.enums import ActivityEntityType, StoryPriority, StoryStatus
from app.models.project import Project, ProjectMember
from app.models.story import Story
from app.models.task import Task
from app.models.user import utc_now
from app.schemas.story import (
    StoryCreateRequest,
    StoryMoveRequest,
    StoryResponse,
    StoryUpdateRequest,
)
from app.services.activity import compute_diff, record_activity
from app.services.ranking import RANK_STEP, compute_insert_position, rebalance_positions


def to_story_response(story: Story, project_key: str) -> StoryResponse:
    return StoryResponse(
        id=story.id,
        project_id=story.project_id,
        number=story.number,
        key=f"{project_key}-{story.number}",
        title=story.title,
        description=story.description,
        acceptance_criteria=story.acceptance_criteria,
        status=StoryStatus(story.status),
        priority=StoryPriority(story.priority),
        story_points=story.story_points,
        assignee_id=story.assignee_id,
        position=story.position,
        version=story.version,
        created_by=story.created_by,
        created_at=story.created_at,
        updated_at=story.updated_at,
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


def _allocate_story_number(db: Session, project_id: str) -> int:
    allocated = db.execute(
        update(Project)
        .where(Project.id == project_id)
        .values(next_story_number=Project.next_story_number + 1)
        .returning(Project.next_story_number)
    ).scalar_one()
    return int(allocated) - 1


def list_stories(
    db: Session,
    project: Project,
    *,
    status_filter: StoryStatus | None = None,
    assignee_id: str | None = None,
    q: str | None = None,
    cursor: str | None = None,
    limit: int = 20,
) -> tuple[list[StoryResponse], str | None, bool]:
    stmt = select(Story).where(
        Story.project_id == project.id,
        Story.deleted_at.is_(None),
    )

    if status_filter is not None:
        stmt = stmt.where(Story.status == status_filter.value)
    if assignee_id is not None:
        stmt = stmt.where(Story.assignee_id == assignee_id)
    if q:
        pattern = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                Story.title.ilike(pattern),
                Story.description.ilike(pattern),
            )
        )

    if cursor:
        cursor_data = decode_cursor(cursor)
        pos_raw = cursor_data.get("position")
        cursor_id = cursor_data.get("id")
        if not isinstance(pos_raw, (int, float)) or not isinstance(cursor_id, str):
            raise BadRequestError("Invalid pagination cursor.", code="INVALID_CURSOR")
        stmt = stmt.where(
            or_(
                Story.position > float(pos_raw),
                and_(Story.position == float(pos_raw), Story.id > cursor_id),
            )
        )

    stmt = stmt.order_by(Story.position.asc(), Story.id.asc()).limit(limit + 1)
    rows = list(db.scalars(stmt).all())

    has_more = len(rows) > limit
    page_rows = rows[:limit]
    items = [to_story_response(story, project.key) for story in page_rows]

    next_cursor: str | None = None
    if has_more and page_rows:
        last_story = page_rows[-1]
        next_cursor = encode_cursor({"position": last_story.position, "id": last_story.id})

    return items, next_cursor, has_more


def create_story(
    db: Session,
    project: Project,
    payload: StoryCreateRequest,
    actor_id: str,
) -> StoryResponse:
    _validate_assignee(db, project.id, payload.assignee_id)

    number = _allocate_story_number(db, project.id)
    max_pos = db.scalar(
        select(func.max(Story.position)).where(
            Story.project_id == project.id,
            Story.status == payload.status.value,
            Story.deleted_at.is_(None),
        )
    )
    position = float(max_pos) + RANK_STEP if max_pos is not None else RANK_STEP

    story = Story(
        project_id=project.id,
        number=number,
        title=payload.title,
        description=payload.description,
        acceptance_criteria=payload.acceptance_criteria,
        status=payload.status.value,
        priority=payload.priority.value,
        story_points=payload.story_points,
        assignee_id=payload.assignee_id,
        position=position,
        created_by=actor_id,
    )
    db.add(story)
    db.flush()
    record_activity(
        db,
        project_id=project.id,
        actor_id=actor_id,
        entity_type=ActivityEntityType.STORY,
        entity_id=story.id,
        action="story.created",
        details={
            "key": f"{project.key}-{story.number}",
            "title": story.title,
            "status": story.status,
            "priority": story.priority,
        },
    )
    if story.assignee_id:
        enqueue_job(
            db,
            "send_notification",
            {
                "user_id": story.assignee_id,
                "project_id": project.id,
                "type": "story.assigned",
                "title": f"Assigned to {project.key}-{story.number}: {story.title}",
                "body": f"You were assigned to story {project.key}-{story.number}.",
                "entity_type": ActivityEntityType.STORY.value,
                "entity_id": story.id,
            },
            project_id=project.id,
            created_by=actor_id,
        )
    db.commit()
    db.refresh(story)
    return to_story_response(story, project.key)


def update_story(
    db: Session,
    story: Story,
    project: Project,
    payload: StoryUpdateRequest,
    actor_id: str,
) -> StoryResponse:
    if story.version != payload.version:
        raise ConflictError(
            "Story has been modified by another request. Reload and retry.",
            code="VERSION_CONFLICT",
        )

    before = {
        "title": story.title,
        "description": story.description,
        "acceptance_criteria": story.acceptance_criteria,
        "status": story.status,
        "priority": story.priority,
        "story_points": story.story_points,
        "assignee_id": story.assignee_id,
    }

    if "assignee_id" in payload.model_fields_set:
        _validate_assignee(db, project.id, payload.assignee_id)
        story.assignee_id = payload.assignee_id

    if payload.title is not None:
        story.title = payload.title
    if "description" in payload.model_fields_set:
        story.description = payload.description
    if "acceptance_criteria" in payload.model_fields_set:
        story.acceptance_criteria = payload.acceptance_criteria
    if payload.status is not None:
        story.status = payload.status.value
    if payload.priority is not None:
        story.priority = payload.priority.value
    if "story_points" in payload.model_fields_set:
        story.story_points = payload.story_points

    after = {
        "title": story.title,
        "description": story.description,
        "acceptance_criteria": story.acceptance_criteria,
        "status": story.status,
        "priority": story.priority,
        "story_points": story.story_points,
        "assignee_id": story.assignee_id,
    }
    story.version += 1
    record_activity(
        db,
        project_id=project.id,
        actor_id=actor_id,
        entity_type=ActivityEntityType.STORY,
        entity_id=story.id,
        action="story.updated",
        details=compute_diff(before, after),
    )
    if story.assignee_id and story.assignee_id != before["assignee_id"]:
        enqueue_job(
            db,
            "send_notification",
            {
                "user_id": story.assignee_id,
                "project_id": project.id,
                "type": "story.assigned",
                "title": f"Assigned to {project.key}-{story.number}: {story.title}",
                "body": f"You were assigned to story {project.key}-{story.number}.",
                "entity_type": ActivityEntityType.STORY.value,
                "entity_id": story.id,
            },
            project_id=project.id,
            created_by=actor_id,
        )
    if story.assignee_id and story.status != before["status"]:
        enqueue_job(
            db,
            "send_notification",
            {
                "user_id": story.assignee_id,
                "project_id": project.id,
                "type": "story.status_changed",
                "title": f"{project.key}-{story.number} moved to {story.status}",
                "body": f"Story '{story.title}' changed from {before['status']} to {story.status}.",
                "entity_type": ActivityEntityType.STORY.value,
                "entity_id": story.id,
            },
            project_id=project.id,
            created_by=actor_id,
        )
    db.commit()
    db.refresh(story)
    return to_story_response(story, project.key)


def move_story(
    db: Session,
    story: Story,
    project: Project,
    payload: StoryMoveRequest,
    actor_id: str,
) -> StoryResponse:
    if payload.version is not None and story.version != payload.version:
        raise ConflictError(
            "Story has been modified by another request. Reload and retry.",
            code="VERSION_CONFLICT",
        )
    if payload.before_id == story.id or payload.after_id == story.id:
        raise BadRequestError("Cannot position a story relative to itself.", code="INVALID_MOVE")

    before = {"status": story.status, "position": story.position}
    target_status = payload.status.value
    siblings = list(
        db.scalars(
            select(Story)
            .where(
                Story.project_id == project.id,
                Story.status == target_status,
                Story.deleted_at.is_(None),
                Story.id != story.id,
            )
            .order_by(Story.position.asc(), Story.id.asc())
        ).all()
    )
    sibling_by_id = {item.id: item for item in siblings}

    before_story = sibling_by_id.get(payload.before_id) if payload.before_id else None
    after_story = sibling_by_id.get(payload.after_id) if payload.after_id else None

    if payload.before_id and before_story is None:
        raise BadRequestError(
            "Reference before_id not found in target column.", code="INVALID_MOVE"
        )
    if payload.after_id and after_story is None:
        raise BadRequestError(
            "Reference after_id not found in target column.", code="INVALID_MOVE"
        )

    before_pos = before_story.position if before_story is not None else None
    after_pos = after_story.position if after_story is not None else None

    if before_pos is None and after_pos is None and siblings:
        before_pos = siblings[-1].position

    new_pos, needs_rebalance = compute_insert_position(before_pos, after_pos)
    story.status = target_status

    if needs_rebalance:
        ordered = list(siblings)
        if before_story is not None:
            insert_idx = ordered.index(before_story) + 1
        elif after_story is not None:
            insert_idx = ordered.index(after_story)
        else:
            insert_idx = len(ordered)
        ordered.insert(insert_idx, story)
        rebalance_positions(ordered, lambda item, pos: setattr(item, "position", pos))
    else:
        story.position = new_pos

    story.version += 1
    record_activity(
        db,
        project_id=project.id,
        actor_id=actor_id,
        entity_type=ActivityEntityType.STORY,
        entity_id=story.id,
        action="story.moved",
        details=compute_diff(before, {"status": story.status, "position": story.position}),
    )
    if story.assignee_id and story.status != before["status"]:
        enqueue_job(
            db,
            "send_notification",
            {
                "user_id": story.assignee_id,
                "project_id": project.id,
                "type": "story.status_changed",
                "title": f"{project.key}-{story.number} moved to {story.status}",
                "body": f"Story '{story.title}' changed from {before['status']} to {story.status}.",
                "entity_type": ActivityEntityType.STORY.value,
                "entity_id": story.id,
            },
            project_id=project.id,
            created_by=actor_id,
        )
    db.commit()
    db.refresh(story)
    return to_story_response(story, project.key)


def soft_delete_story(db: Session, story: Story, actor_id: str) -> None:
    now = utc_now()
    story.deleted_at = now
    story.version += 1
    db.execute(
        update(Task)
        .where(Task.story_id == story.id, Task.deleted_at.is_(None))
        .values(deleted_at=now, version=Task.version + 1)
    )
    record_activity(
        db,
        project_id=story.project_id,
        actor_id=actor_id,
        entity_type=ActivityEntityType.STORY,
        entity_id=story.id,
        action="story.deleted",
        details={"title": story.title},
    )
    db.commit()

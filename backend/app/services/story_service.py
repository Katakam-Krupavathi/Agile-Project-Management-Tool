from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.orm import Session

from app.core.errors import BadRequestError, ConflictError
from app.core.pagination import decode_cursor, encode_cursor
from app.db.session import begin_immediate_if_sqlite
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
from app.services.ranking import RANK_STEP, compute_insert_position


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
    story_id = story.id
    story_number = story.number
    project_id = project.id
    project_key = project.key

    if "assignee_id" in payload.model_fields_set:
        _validate_assignee(db, project_id, payload.assignee_id)

    before = {
        "title": story.title,
        "description": story.description,
        "acceptance_criteria": story.acceptance_criteria,
        "status": story.status,
        "priority": story.priority,
        "story_points": story.story_points,
        "assignee_id": story.assignee_id,
    }

    new_title = payload.title if payload.title is not None else before["title"]
    new_description = (
        payload.description if "description" in payload.model_fields_set else before["description"]
    )
    new_ac = (
        payload.acceptance_criteria
        if "acceptance_criteria" in payload.model_fields_set
        else before["acceptance_criteria"]
    )
    new_status = payload.status.value if payload.status is not None else before["status"]
    new_priority = payload.priority.value if payload.priority is not None else before["priority"]
    new_points = (
        payload.story_points
        if "story_points" in payload.model_fields_set
        else before["story_points"]
    )
    new_assignee = (
        payload.assignee_id if "assignee_id" in payload.model_fields_set else before["assignee_id"]
    )

    after = {
        "title": new_title,
        "description": new_description,
        "acceptance_criteria": new_ac,
        "status": new_status,
        "priority": new_priority,
        "story_points": new_points,
        "assignee_id": new_assignee,
    }

    now = utc_now()
    new_position = story.position
    begin_immediate_if_sqlite(db)
    if new_status != before["status"]:
        max_pos = db.scalar(
            select(func.max(Story.position)).where(
                Story.project_id == project_id,
                Story.status == new_status,
                Story.deleted_at.is_(None),
                Story.id != story_id,
            )
        )
        new_position = float(max_pos) + RANK_STEP if max_pos is not None else RANK_STEP

    result = db.execute(
        update(Story)
        .where(
            Story.id == story_id,
            Story.version == payload.version,
            Story.deleted_at.is_(None),
        )
        .values(
            title=new_title,
            description=new_description,
            acceptance_criteria=new_ac,
            status=new_status,
            priority=new_priority,
            story_points=new_points,
            assignee_id=new_assignee,
            position=new_position,
            version=payload.version + 1,
            updated_at=now,
        )
    )
    if result.rowcount != 1:
        db.rollback()
        raise ConflictError(
            "Story has been modified by another request. Reload and retry.",
            code="VERSION_CONFLICT",
        )

    record_activity(
        db,
        project_id=project_id,
        actor_id=actor_id,
        entity_type=ActivityEntityType.STORY,
        entity_id=story_id,
        action="story.updated",
        details=compute_diff(before, after),
    )
    if new_assignee and new_assignee != before["assignee_id"]:
        enqueue_job(
            db,
            "send_notification",
            {
                "user_id": new_assignee,
                "project_id": project_id,
                "type": "story.assigned",
                "title": f"Assigned to {project_key}-{story_number}: {new_title}",
                "body": f"You were assigned to story {project_key}-{story_number}.",
                "entity_type": ActivityEntityType.STORY.value,
                "entity_id": story_id,
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
                "type": "story.status_changed",
                "title": f"{project_key}-{story_number} moved to {new_status}",
                "body": f"Story '{new_title}' changed from {before['status']} to {new_status}.",
                "entity_type": ActivityEntityType.STORY.value,
                "entity_id": story_id,
            },
            project_id=project_id,
            created_by=actor_id,
        )
    db.commit()
    updated = db.scalar(select(Story).where(Story.id == story_id))
    assert updated is not None
    return to_story_response(updated, project_key)


def move_story(
    db: Session,
    story: Story,
    project: Project,
    payload: StoryMoveRequest,
    actor_id: str,
) -> StoryResponse:
    story_id = story.id
    story_number = story.number
    story_title = story.title
    story_assignee_id = story.assignee_id
    project_id = project.id
    project_key = project.key
    before = {"status": story.status, "position": story.position}

    if payload.before_id == story_id or payload.after_id == story_id:
        raise BadRequestError("Cannot position a story relative to itself.", code="INVALID_MOVE")

    target_status = payload.status.value
    now = utc_now()

    begin_immediate_if_sqlite(db)
    siblings = list(
        db.scalars(
            select(Story)
            .where(
                Story.project_id == project_id,
                Story.status == target_status,
                Story.deleted_at.is_(None),
                Story.id != story_id,
            )
            .order_by(Story.position.asc(), Story.id.asc())
        ).all()
    )
    sibling_by_id = {item.id: item for item in siblings}

    before_story = sibling_by_id.get(payload.before_id) if payload.before_id else None
    after_story = sibling_by_id.get(payload.after_id) if payload.after_id else None

    if payload.before_id and before_story is None:
        db.rollback()
        raise BadRequestError(
            "Reference before_id not found in target column.", code="INVALID_MOVE"
        )
    if payload.after_id and after_story is None:
        db.rollback()
        raise BadRequestError(
            "Reference after_id not found in target column.", code="INVALID_MOVE"
        )

    before_pos = before_story.position if before_story is not None else None
    after_pos = after_story.position if after_story is not None else None

    if before_pos is None and after_pos is None and siblings:
        before_pos = siblings[-1].position

    new_pos, needs_rebalance = compute_insert_position(before_pos, after_pos)

    if needs_rebalance:
        placeholder = object()
        ordered: list[object] = list(siblings)
        if before_story is not None:
            insert_idx = ordered.index(before_story) + 1
        elif after_story is not None:
            insert_idx = ordered.index(after_story)
        else:
            insert_idx = len(ordered)
        ordered.insert(insert_idx, placeholder)
        new_positions: dict[str, float] = {}
        for idx, item in enumerate(ordered, start=1):
            pos = float(idx) * RANK_STEP
            if item is placeholder:
                new_pos = pos
            else:
                assert isinstance(item, Story)
                new_positions[item.id] = pos

        result = db.execute(
            update(Story)
            .where(
                Story.id == story_id,
                Story.version == payload.version,
                Story.deleted_at.is_(None),
            )
            .values(
                status=target_status,
                position=new_pos,
                version=payload.version + 1,
                updated_at=now,
            )
        )
        if result.rowcount != 1:
            db.rollback()
            raise ConflictError(
                "Story has been modified by another request. Reload and retry.",
                code="VERSION_CONFLICT",
            )
        for sib_id, sib_pos in new_positions.items():
            db.execute(update(Story).where(Story.id == sib_id).values(position=sib_pos))
    else:
        result = db.execute(
            update(Story)
            .where(
                Story.id == story_id,
                Story.version == payload.version,
                Story.deleted_at.is_(None),
            )
            .values(
                status=target_status,
                position=new_pos,
                version=payload.version + 1,
                updated_at=now,
            )
        )
        if result.rowcount != 1:
            db.rollback()
            raise ConflictError(
                "Story has been modified by another request. Reload and retry.",
                code="VERSION_CONFLICT",
            )

    record_activity(
        db,
        project_id=project_id,
        actor_id=actor_id,
        entity_type=ActivityEntityType.STORY,
        entity_id=story_id,
        action="story.moved",
        details=compute_diff(before, {"status": target_status, "position": new_pos}),
    )
    if story_assignee_id and target_status != before["status"]:
        enqueue_job(
            db,
            "send_notification",
            {
                "user_id": story_assignee_id,
                "project_id": project_id,
                "type": "story.status_changed",
                "title": f"{project_key}-{story_number} moved to {target_status}",
                "body": (
                    f"Story '{story_title}' changed from {before['status']} to {target_status}."
                ),
                "entity_type": ActivityEntityType.STORY.value,
                "entity_id": story_id,
            },
            project_id=project_id,
            created_by=actor_id,
        )
    db.commit()
    updated = db.scalar(select(Story).where(Story.id == story_id))
    assert updated is not None
    return to_story_response(updated, project_key)


def soft_delete_story(db: Session, story: Story, actor_id: str) -> None:
    story_id = story.id
    project_id = story.project_id
    story_title = story.title
    expected_version = story.version
    now = utc_now()

    begin_immediate_if_sqlite(db)
    result = db.execute(
        update(Story)
        .where(
            Story.id == story_id,
            Story.version == expected_version,
            Story.deleted_at.is_(None),
        )
        .values(deleted_at=now, version=expected_version + 1, updated_at=now)
    )
    if result.rowcount != 1:
        db.rollback()
        raise ConflictError(
            "Story has been modified by another request. Reload and retry.",
            code="VERSION_CONFLICT",
        )

    db.execute(
        update(Task)
        .where(Task.story_id == story_id, Task.deleted_at.is_(None))
        .values(deleted_at=now, version=Task.version + 1, updated_at=now)
    )
    record_activity(
        db,
        project_id=project_id,
        actor_id=actor_id,
        entity_type=ActivityEntityType.STORY,
        entity_id=story_id,
        action="story.deleted",
        details={"title": story_title},
    )
    db.commit()

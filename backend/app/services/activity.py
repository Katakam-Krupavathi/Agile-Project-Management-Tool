import json
from datetime import datetime
from typing import Any

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.core.errors import BadRequestError
from app.core.pagination import decode_cursor, encode_cursor
from app.models.activity import ActivityLog
from app.models.enums import ActivityEntityType
from app.models.user import User
from app.schemas.activity import ActivityLogResponse


def compute_diff(before: dict[str, Any], after: dict[str, Any]) -> dict[str, dict[str, Any]]:
    diff: dict[str, dict[str, Any]] = {}
    for key in set(before.keys()) | set(after.keys()):
        old_val = before.get(key)
        new_val = after.get(key)
        if old_val != new_val:
            diff[key] = {"from": old_val, "to": new_val}
    return diff


def record_activity(
    db: Session,
    *,
    project_id: str,
    actor_id: str | None,
    entity_type: ActivityEntityType,
    entity_id: str,
    action: str,
    details: dict[str, Any] | None = None,
) -> ActivityLog:
    entry = ActivityLog(
        project_id=project_id,
        actor_id=actor_id,
        entity_type=entity_type.value,
        entity_id=entity_id,
        action=action,
        details=json.dumps(details, default=str) if details is not None else None,
    )
    db.add(entry)
    return entry


def list_project_activity(
    db: Session,
    project_id: str,
    *,
    cursor: str | None = None,
    limit: int = 30,
) -> tuple[list[ActivityLogResponse], str | None, bool]:
    stmt = (
        select(ActivityLog, User.name)
        .outerjoin(User, User.id == ActivityLog.actor_id)
        .where(ActivityLog.project_id == project_id)
    )

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
                ActivityLog.created_at < cursor_created_at,
                and_(ActivityLog.created_at == cursor_created_at, ActivityLog.id < cursor_id),
            )
        )

    stmt = stmt.order_by(ActivityLog.created_at.desc(), ActivityLog.id.desc()).limit(limit + 1)
    rows = db.execute(stmt).all()

    has_more = len(rows) > limit
    page_rows = rows[:limit]
    items: list[ActivityLogResponse] = []
    for log_row, actor_name in page_rows:
        parsed_details: dict[str, Any] | None = None
        if log_row.details:
            try:
                parsed_details = json.loads(log_row.details)
            except ValueError:
                parsed_details = {"raw": log_row.details}
        items.append(
            ActivityLogResponse(
                id=log_row.id,
                project_id=log_row.project_id,
                actor_id=log_row.actor_id,
                actor_name=actor_name,
                entity_type=ActivityEntityType(log_row.entity_type),
                entity_id=log_row.entity_id,
                action=log_row.action,
                details=parsed_details,
                created_at=log_row.created_at,
            )
        )

    next_cursor: str | None = None
    if has_more and page_rows:
        last_log = page_rows[-1][0]
        next_cursor = encode_cursor(
            {"created_at": last_log.created_at.isoformat(), "id": last_log.id}
        )

    return items, next_cursor, has_more

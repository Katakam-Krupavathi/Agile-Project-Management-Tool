from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_csrf
from app.db.session import get_db
from app.models.user import User
from app.schemas.notification import (
    NotificationPageResponse,
    NotificationResponse,
    ReadAllResponse,
)
from app.services import notification_service

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=NotificationPageResponse)
def list_notifications(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    unread_only: Annotated[bool, Query()] = False,
    cursor: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
) -> NotificationPageResponse:
    items, next_cursor, has_more, unread_count = notification_service.list_notifications(
        db,
        current_user.id,
        unread_only=unread_only,
        cursor=cursor,
        limit=limit,
    )
    return NotificationPageResponse(
        items=items,
        next_cursor=next_cursor,
        has_more=has_more,
        unread_count=unread_count,
    )


@router.patch(
    "/{notification_id}/read",
    response_model=NotificationResponse,
    dependencies=[Depends(require_csrf)],
)
def mark_read(
    notification_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> NotificationResponse:
    return notification_service.mark_notification_read(db, notification_id, current_user.id)


@router.post(
    "/read-all",
    response_model=ReadAllResponse,
    dependencies=[Depends(require_csrf)],
)
def mark_all_read(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> ReadAllResponse:
    updated = notification_service.mark_all_notifications_read(db, current_user.id)
    return ReadAllResponse(updated=updated)

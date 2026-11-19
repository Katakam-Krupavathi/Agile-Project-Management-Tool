import asyncio
from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.responses import StreamingResponse
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


@router.get("/stream")
async def stream_notifications(
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    last_event_id_header: Annotated[str | None, Header(alias="Last-Event-ID")] = None,
    last_event_id_query: Annotated[str | None, Query(alias="last_event_id")] = None,
    once: Annotated[bool, Query()] = False,
) -> StreamingResponse:
    cursor_event_id = last_event_id_header or last_event_id_query
    poll_interval_seconds = 1.0
    heartbeat_every_polls = 15

    async def event_generator() -> AsyncGenerator[str, None]:
        nonlocal cursor_event_id
        yield "retry: 3000\n\n"
        polls = 0
        while True:
            if await request.is_disconnected():
                break

            events = notification_service.get_notifications_since(
                db,
                current_user.id,
                last_event_id=cursor_event_id,
            )
            for item in events:
                cursor_event_id = item.id
                payload_json = item.model_dump_json()
                yield f"id: {item.id}\nevent: notification\ndata: {payload_json}\n\n"

            if once:
                yield ": heartbeat\n\n"
                break

            polls += 1
            if polls % heartbeat_every_polls == 0:
                yield ": heartbeat\n\n"

            await asyncio.sleep(poll_interval_seconds)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
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

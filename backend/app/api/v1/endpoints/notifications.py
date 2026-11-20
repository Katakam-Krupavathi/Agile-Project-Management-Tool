import asyncio
import time
from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, is_request_session_valid, require_csrf
from app.core.config import Settings, get_settings
from app.db.session import get_db, open_db_session
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
    settings: Annotated[Settings, Depends(get_settings)],
    last_event_id_header: Annotated[str | None, Header(alias="Last-Event-ID")] = None,
    last_event_id_query: Annotated[str | None, Query(alias="last_event_id")] = None,
    once: Annotated[bool, Query()] = False,
) -> StreamingResponse:
    cursor_event_id = last_event_id_header or last_event_id_query
    poll_interval_seconds = settings.sse_poll_interval_seconds
    max_lifetime_seconds = settings.sse_max_lifetime_seconds
    heartbeat_every_polls = 15
    user_id = current_user.id
    app = request.app
    stream_id = notification_service.acquire_user_stream_slot(
        user_id,
        max_streams=settings.sse_max_streams_per_user,
    )

    def _poll_events(last_id: str | None) -> tuple[bool, list[NotificationResponse]]:
        with open_db_session(app) as db:
            if not is_request_session_valid(request, db, settings, user_id):
                return False, []
            events = notification_service.get_notifications_since(
                db,
                user_id,
                last_event_id=last_id,
            )
            return True, events

    async def event_generator() -> AsyncGenerator[str, None]:
        nonlocal cursor_event_id
        started_at = time.monotonic()
        try:
            yield "retry: 3000\n\n"
            polls = 0
            while True:
                if await request.is_disconnected():
                    break

                session_ok, events = await asyncio.to_thread(_poll_events, cursor_event_id)
                if not session_ok:
                    break
                for item in events:
                    cursor_event_id = item.id
                    payload_json = item.model_dump_json()
                    yield f"id: {item.id}\nevent: notification\ndata: {payload_json}\n\n"

                if once:
                    yield ": heartbeat\n\n"
                    break

                elapsed = time.monotonic() - started_at
                if elapsed >= max_lifetime_seconds:
                    break

                polls += 1
                if polls % heartbeat_every_polls == 0:
                    yield ": heartbeat\n\n"

                remaining = max(0.0, max_lifetime_seconds - elapsed)
                await asyncio.sleep(min(poll_interval_seconds, remaining))
                if (time.monotonic() - started_at) >= max_lifetime_seconds:
                    break
        finally:
            notification_service.release_user_stream_slot(user_id, stream_id)

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

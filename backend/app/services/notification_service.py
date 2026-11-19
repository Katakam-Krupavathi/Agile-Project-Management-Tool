from datetime import datetime

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.orm import Session

from app.core.errors import BadRequestError, NotFoundError
from app.core.pagination import decode_cursor, encode_cursor
from app.models.notification import Notification
from app.models.user import User, utc_now
from app.schemas.notification import NotificationResponse
from app.services.mailer import get_mailer


def to_notification_response(notification: Notification) -> NotificationResponse:
    return NotificationResponse.model_validate(notification)


def create_notification(
    db: Session,
    *,
    user_id: str,
    notification_type: str,
    title: str,
    body: str | None = None,
    project_id: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    send_email: bool = True,
) -> Notification:
    notification = Notification(
        user_id=user_id,
        project_id=project_id,
        type=notification_type,
        title=title,
        body=body,
        entity_type=entity_type,
        entity_id=entity_id,
    )
    db.add(notification)
    db.flush()

    if send_email:
        user = db.scalar(select(User).where(User.id == user_id))
        if user is not None:
            get_mailer().send(
                to_email=user.email,
                subject=title,
                body=body or title,
            )

    return notification


def list_notifications(
    db: Session,
    user_id: str,
    *,
    unread_only: bool = False,
    cursor: str | None = None,
    limit: int = 30,
) -> tuple[list[NotificationResponse], str | None, bool, int]:
    unread_count = int(
        db.scalar(
            select(func.count(Notification.id)).where(
                Notification.user_id == user_id,
                Notification.read_at.is_(None),
            )
        )
        or 0
    )

    stmt = select(Notification).where(Notification.user_id == user_id)
    if unread_only:
        stmt = stmt.where(Notification.read_at.is_(None))

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
                Notification.created_at < cursor_created_at,
                and_(Notification.created_at == cursor_created_at, Notification.id < cursor_id),
            )
        )

    stmt = stmt.order_by(Notification.created_at.desc(), Notification.id.desc()).limit(limit + 1)
    rows = list(db.scalars(stmt).all())

    has_more = len(rows) > limit
    page_rows = rows[:limit]
    items = [to_notification_response(row) for row in page_rows]

    next_cursor: str | None = None
    if has_more and page_rows:
        last_item = page_rows[-1]
        next_cursor = encode_cursor(
            {"created_at": last_item.created_at.isoformat(), "id": last_item.id}
        )

    return items, next_cursor, has_more, unread_count


def mark_notification_read(
    db: Session,
    notification_id: str,
    user_id: str,
) -> NotificationResponse:
    notification = db.scalar(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == user_id,
        )
    )
    if notification is None:
        raise NotFoundError("Notification not found.", code="NOTIFICATION_NOT_FOUND")

    if notification.read_at is None:
        notification.read_at = utc_now()
        db.commit()
        db.refresh(notification)

    return to_notification_response(notification)


def mark_all_notifications_read(db: Session, user_id: str) -> int:
    result = db.execute(
        update(Notification)
        .where(Notification.user_id == user_id, Notification.read_at.is_(None))
        .values(read_at=utc_now())
    )
    db.commit()
    return int(result.rowcount or 0)


def get_notifications_since(
    db: Session,
    user_id: str,
    *,
    last_event_id: str | None = None,
    limit: int = 50,
) -> list[NotificationResponse]:
    db.expire_all()
    stmt = select(Notification).where(Notification.user_id == user_id)

    if last_event_id:
        anchor = db.scalar(
            select(Notification).where(
                Notification.id == last_event_id,
                Notification.user_id == user_id,
            )
        )
        if anchor is not None:
            stmt = stmt.where(
                or_(
                    Notification.created_at > anchor.created_at,
                    and_(
                        Notification.created_at == anchor.created_at,
                        Notification.id > anchor.id,
                    ),
                )
            )
    else:
        stmt = stmt.where(Notification.read_at.is_(None))

    stmt = stmt.order_by(Notification.created_at.asc(), Notification.id.asc()).limit(limit)
    rows = list(db.scalars(stmt).all())
    return [to_notification_response(row) for row in rows]

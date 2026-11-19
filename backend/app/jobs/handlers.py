from typing import Any

from sqlalchemy.orm import Session

from app.jobs.registry import register
from app.services import notification_service


@register("send_notification")
def handle_send_notification(db: Session, payload: dict[str, Any]) -> dict[str, Any]:
    notification = notification_service.create_notification(
        db,
        user_id=str(payload["user_id"]),
        project_id=payload.get("project_id"),
        notification_type=str(payload["type"]),
        title=str(payload["title"]),
        body=payload.get("body"),
        entity_type=payload.get("entity_type"),
        entity_id=payload.get("entity_id"),
        send_email=True,
    )
    return {"notification_id": notification.id}

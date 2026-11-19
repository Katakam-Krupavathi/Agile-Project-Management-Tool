from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.schemas.common import CursorPage


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    project_id: str | None
    type: str
    title: str
    body: str | None
    entity_type: str | None
    entity_id: str | None
    read_at: datetime | None
    created_at: datetime


class NotificationPageResponse(CursorPage[NotificationResponse]):
    unread_count: int


class ReadAllResponse(BaseModel):
    updated: int

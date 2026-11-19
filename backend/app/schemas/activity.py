from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.models.enums import ActivityEntityType


class ActivityLogResponse(BaseModel):
    id: str
    project_id: str
    actor_id: str | None
    actor_name: str | None
    entity_type: ActivityEntityType
    entity_id: str
    action: str
    details: dict[str, Any] | None
    created_at: datetime

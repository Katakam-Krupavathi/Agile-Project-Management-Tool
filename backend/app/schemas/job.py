from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.models.enums import JobStatus


class JobResponse(BaseModel):
    id: str
    job_type: str
    status: JobStatus
    attempts: int
    max_attempts: int
    run_at: datetime
    last_error: str | None
    result: dict[str, Any] | None
    project_id: str | None
    created_by: str | None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None

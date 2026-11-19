from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import JobStatus


class ReportEnqueueResponse(BaseModel):
    job_id: str
    status: JobStatus


class ReportSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    job_id: str | None
    title: str
    created_by: str | None
    created_at: datetime

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import TaskStatus


class TaskCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=10000)
    status: TaskStatus = TaskStatus.TODO
    assignee_id: str | None = Field(default=None, max_length=36)
    estimate_hours: float | None = Field(default=None, ge=0.0, le=1000.0)
    due_date: date | None = None

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Task title must not be blank.")
        return cleaned


class TaskUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=10000)
    status: TaskStatus | None = None
    assignee_id: str | None = Field(default=None, max_length=36)
    estimate_hours: float | None = Field(default=None, ge=0.0, le=1000.0)
    due_date: date | None = None
    version: int = Field(ge=1)

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Task title must not be blank.")
        return cleaned


class TaskMoveRequest(BaseModel):
    before_id: str | None = Field(default=None, max_length=36)
    after_id: str | None = Field(default=None, max_length=36)
    status: TaskStatus | None = None
    version: int | None = Field(default=None, ge=1)


class TaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    story_id: str
    title: str
    description: str | None
    status: TaskStatus
    assignee_id: str | None
    estimate_hours: float | None
    due_date: date | None
    position: float
    version: int
    created_at: datetime
    updated_at: datetime

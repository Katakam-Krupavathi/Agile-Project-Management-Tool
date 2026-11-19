from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import StoryPriority, StoryStatus


class StoryCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=10000)
    acceptance_criteria: str | None = Field(default=None, max_length=10000)
    status: StoryStatus = StoryStatus.BACKLOG
    priority: StoryPriority = StoryPriority.MEDIUM
    story_points: int | None = Field(default=None, ge=0, le=100)
    assignee_id: str | None = Field(default=None, max_length=36)

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Story title must not be blank.")
        return cleaned


class StoryUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=10000)
    acceptance_criteria: str | None = Field(default=None, max_length=10000)
    status: StoryStatus | None = None
    priority: StoryPriority | None = None
    story_points: int | None = Field(default=None, ge=0, le=100)
    assignee_id: str | None = Field(default=None, max_length=36)
    version: int | None = Field(default=None, ge=1)

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Story title must not be blank.")
        return cleaned


class StoryMoveRequest(BaseModel):
    status: StoryStatus
    before_id: str | None = Field(default=None, max_length=36)
    after_id: str | None = Field(default=None, max_length=36)
    version: int | None = Field(default=None, ge=1)


class StoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    number: int
    key: str
    title: str
    description: str | None
    acceptance_criteria: str | None
    status: StoryStatus
    priority: StoryPriority
    story_points: int | None
    assignee_id: str | None
    position: float
    version: int
    created_by: str
    created_at: datetime
    updated_at: datetime

import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import ProjectRole

PROJECT_KEY_PATTERN = re.compile(r"^[A-Z]{2,5}$")


class ProjectCreateRequest(BaseModel):
    key: str = Field(min_length=2, max_length=5)
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=4000)

    @field_validator("key")
    @classmethod
    def validate_key(cls, value: str) -> str:
        cleaned = value.strip()
        if not PROJECT_KEY_PATTERN.match(cleaned):
            raise ValueError("Project key must be 2 to 5 uppercase letters (A-Z).")
        return cleaned

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Project name must not be blank.")
        return cleaned


class ProjectUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=4000)
    version: int = Field(ge=1)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Project name must not be blank.")
        return cleaned


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    key: str
    name: str
    description: str | None
    next_story_number: int
    created_by: str
    version: int
    role: ProjectRole
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None

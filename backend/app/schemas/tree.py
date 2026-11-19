from pydantic import BaseModel

from app.models.enums import StoryStatus
from app.schemas.project import ProjectResponse
from app.schemas.story import StoryResponse
from app.schemas.task import TaskResponse
from app.services.rollup import ProjectHealth


class StoryRollupResponse(BaseModel):
    total_tasks: int
    done_tasks: int
    blocked_tasks: int
    overdue_tasks: int
    progress_pct: float
    is_blocked: bool
    suggested_status: StoryStatus | None


class ProjectRollupResponse(BaseModel):
    health: ProjectHealth
    total_stories: int
    done_stories: int
    stalled_stories: int
    total_tasks: int
    done_tasks: int
    blocked_tasks: int
    overdue_tasks: int
    progress_pct: float


class StoryTreeNode(BaseModel):
    story: StoryResponse
    rollup: StoryRollupResponse
    tasks: list[TaskResponse]


class ProjectTreeResponse(BaseModel):
    project: ProjectResponse
    rollup: ProjectRollupResponse
    stories: list[StoryTreeNode]

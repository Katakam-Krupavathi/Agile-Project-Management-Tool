from enum import StrEnum


class ProjectRole(StrEnum):
    OWNER = "owner"
    MEMBER = "member"
    VIEWER = "viewer"


class StoryStatus(StrEnum):
    BACKLOG = "backlog"
    IN_PROGRESS = "in_progress"
    IN_REVIEW = "in_review"
    DONE = "done"


class StoryPriority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class TaskStatus(StrEnum):
    TODO = "todo"
    DOING = "doing"
    BLOCKED = "blocked"
    DONE = "done"


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    DEAD = "dead"


class ActivityEntityType(StrEnum):
    PROJECT = "project"
    PROJECT_MEMBER = "project_member"
    STORY = "story"
    TASK = "task"

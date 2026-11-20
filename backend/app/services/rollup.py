from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from enum import StrEnum

from app.models.enums import StoryStatus, TaskStatus


class ProjectHealth(StrEnum):
    ON_TRACK = "on_track"
    AT_RISK = "at_risk"
    OFF_TRACK = "off_track"


@dataclass(frozen=True)
class TaskRollupInput:
    status: TaskStatus
    estimate_hours: float | None = None
    due_date: date | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True)
class StoryRollupInput:
    status: StoryStatus
    updated_at: datetime
    tasks: Sequence[TaskRollupInput]


@dataclass(frozen=True)
class StoryRollup:
    total_tasks: int
    done_tasks: int
    blocked_tasks: int
    overdue_tasks: int
    progress_pct: float
    is_blocked: bool
    suggested_status: StoryStatus | None


@dataclass(frozen=True)
class ProjectRollup:
    health: ProjectHealth
    total_stories: int
    done_stories: int
    stalled_stories: int
    total_tasks: int
    done_tasks: int
    blocked_tasks: int
    overdue_tasks: int
    progress_pct: float


def compute_story_rollup(
    tasks: Sequence[TaskRollupInput],
    story_status: StoryStatus,
    *,
    today: date | None = None,
) -> StoryRollup:
    reference_day = today or datetime.now(UTC).date()
    total_tasks = len(tasks)
    done_tasks = sum(1 for task in tasks if task.status == TaskStatus.DONE)
    blocked_tasks = sum(1 for task in tasks if task.status == TaskStatus.BLOCKED)
    overdue_tasks = sum(
        1
        for task in tasks
        if task.due_date is not None
        and task.due_date < reference_day
        and task.status != TaskStatus.DONE
    )

    if total_tasks == 0:
        progress_pct = 0.0
    else:
        total_weight = sum(
            task.estimate_hours
            for task in tasks
            if task.estimate_hours is not None and task.estimate_hours > 0
        )
        if total_weight > 0:
            done_weight = sum(
                task.estimate_hours
                for task in tasks
                if task.status == TaskStatus.DONE
                and task.estimate_hours is not None
                and task.estimate_hours > 0
            )
            progress_pct = round((done_weight / total_weight) * 100.0, 1)
        else:
            progress_pct = round((done_tasks / total_tasks) * 100.0, 1)

    suggested_status: StoryStatus | None = None
    if total_tasks > 0 and done_tasks == total_tasks:
        if story_status not in (StoryStatus.IN_REVIEW, StoryStatus.DONE):
            suggested_status = StoryStatus.IN_REVIEW
    elif story_status == StoryStatus.BACKLOG and any(
        task.status == TaskStatus.DOING for task in tasks
    ):
        suggested_status = StoryStatus.IN_PROGRESS

    return StoryRollup(
        total_tasks=total_tasks,
        done_tasks=done_tasks,
        blocked_tasks=blocked_tasks,
        overdue_tasks=overdue_tasks,
        progress_pct=progress_pct,
        is_blocked=blocked_tasks > 0,
        suggested_status=suggested_status,
    )


def _normalize_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _story_last_activity(story: StoryRollupInput) -> datetime:
    latest = _normalize_utc(story.updated_at)
    for task in story.tasks:
        if task.updated_at is not None:
            task_ts = _normalize_utc(task.updated_at)
            if task_ts > latest:
                latest = task_ts
    return latest


def compute_project_rollup(
    stories: Sequence[StoryRollupInput],
    *,
    now: datetime | None = None,
    stalled_days: int = 7,
) -> ProjectRollup:
    reference_now = _normalize_utc(now or datetime.now(UTC))
    reference_day = reference_now.date()
    stalled_cutoff = reference_now - timedelta(days=stalled_days)

    total_stories = len(stories)
    done_stories = sum(1 for story in stories if story.status == StoryStatus.DONE)
    stalled_stories = sum(
        1
        for story in stories
        if story.status in (StoryStatus.IN_PROGRESS, StoryStatus.IN_REVIEW)
        and _story_last_activity(story) < stalled_cutoff
    )

    all_tasks = [task for story in stories for task in story.tasks]
    total_tasks = len(all_tasks)
    done_tasks = sum(1 for task in all_tasks if task.status == TaskStatus.DONE)
    blocked_tasks = sum(1 for task in all_tasks if task.status == TaskStatus.BLOCKED)
    overdue_tasks = sum(
        1
        for task in all_tasks
        if task.due_date is not None
        and task.due_date < reference_day
        and task.status != TaskStatus.DONE
    )

    if total_tasks > 0:
        progress_pct = round((done_tasks / total_tasks) * 100.0, 1)
        blocked_ratio = blocked_tasks / total_tasks
    else:
        progress_pct = (
            round((done_stories / total_stories) * 100.0, 1) if total_stories > 0 else 0.0
        )
        blocked_ratio = 0.0

    if overdue_tasks >= 3 or blocked_ratio >= 0.30 or stalled_stories >= 3:
        health = ProjectHealth.OFF_TRACK
    elif overdue_tasks >= 1 or blocked_ratio >= 0.15 or stalled_stories >= 1:
        health = ProjectHealth.AT_RISK
    else:
        health = ProjectHealth.ON_TRACK

    return ProjectRollup(
        health=health,
        total_stories=total_stories,
        done_stories=done_stories,
        stalled_stories=stalled_stories,
        total_tasks=total_tasks,
        done_tasks=done_tasks,
        blocked_tasks=blocked_tasks,
        overdue_tasks=overdue_tasks,
        progress_pct=progress_pct,
    )

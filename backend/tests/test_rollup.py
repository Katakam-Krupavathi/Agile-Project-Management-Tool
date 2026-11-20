from datetime import UTC, date, datetime, timedelta

from app.models.enums import StoryStatus, TaskStatus
from app.services.rollup import (
    ProjectHealth,
    StoryRollupInput,
    TaskRollupInput,
    compute_project_rollup,
    compute_story_rollup,
)


def test_story_rollup_empty() -> None:
    result = compute_story_rollup([], StoryStatus.BACKLOG, today=date(2026, 11, 20))
    assert result.total_tasks == 0
    assert result.done_tasks == 0
    assert result.progress_pct == 0.0
    assert result.is_blocked is False
    assert result.suggested_status is None


def test_story_rollup_all_done_suggests_in_review() -> None:
    tasks = [
        TaskRollupInput(status=TaskStatus.DONE),
        TaskRollupInput(status=TaskStatus.DONE),
    ]
    result = compute_story_rollup(tasks, StoryStatus.IN_PROGRESS, today=date(2026, 11, 20))
    assert result.progress_pct == 100.0
    assert result.is_blocked is False
    assert result.suggested_status == StoryStatus.IN_REVIEW

    already_done = compute_story_rollup(tasks, StoryStatus.DONE, today=date(2026, 11, 20))
    assert already_done.suggested_status is None


def test_story_rollup_blocked_and_auto_in_progress_suggestion() -> None:
    tasks = [
        TaskRollupInput(status=TaskStatus.DOING),
        TaskRollupInput(status=TaskStatus.BLOCKED, due_date=date(2026, 11, 10)),
        TaskRollupInput(status=TaskStatus.TODO),
    ]
    result = compute_story_rollup(tasks, StoryStatus.BACKLOG, today=date(2026, 11, 20))
    assert result.is_blocked is True
    assert result.blocked_tasks == 1
    assert result.overdue_tasks == 1
    assert result.progress_pct == 0.0
    assert result.suggested_status == StoryStatus.IN_PROGRESS


def test_story_rollup_weighted_by_estimate_hours() -> None:
    tasks = [
        TaskRollupInput(status=TaskStatus.DONE, estimate_hours=2.0),
        TaskRollupInput(status=TaskStatus.TODO, estimate_hours=6.0),
    ]
    result = compute_story_rollup(tasks, StoryStatus.IN_PROGRESS, today=date(2026, 11, 20))
    assert result.progress_pct == 25.0


def test_project_health_on_track_at_risk_and_off_track() -> None:
    now = datetime(2026, 11, 20, 12, 0, tzinfo=UTC)

    on_track = compute_project_rollup(
        [
            StoryRollupInput(
                status=StoryStatus.IN_PROGRESS,
                updated_at=now - timedelta(days=1),
                tasks=[
                    TaskRollupInput(status=TaskStatus.DONE, due_date=date(2026, 11, 10)),
                    TaskRollupInput(status=TaskStatus.DOING, due_date=date(2026, 11, 25)),
                ],
            )
        ],
        now=now,
    )
    assert on_track.health == ProjectHealth.ON_TRACK
    assert on_track.progress_pct == 50.0

    at_risk_overdue = compute_project_rollup(
        [
            StoryRollupInput(
                status=StoryStatus.IN_PROGRESS,
                updated_at=now - timedelta(days=1),
                tasks=[TaskRollupInput(status=TaskStatus.TODO, due_date=date(2026, 11, 19))],
            )
        ],
        now=now,
    )
    assert at_risk_overdue.health == ProjectHealth.AT_RISK
    assert at_risk_overdue.overdue_tasks == 1

    off_track_blocked = compute_project_rollup(
        [
            StoryRollupInput(
                status=StoryStatus.IN_PROGRESS,
                updated_at=now - timedelta(days=1),
                tasks=[
                    TaskRollupInput(status=TaskStatus.BLOCKED),
                    TaskRollupInput(status=TaskStatus.TODO),
                ],
            )
        ],
        now=now,
    )
    assert off_track_blocked.health == ProjectHealth.OFF_TRACK

    off_track_stalled = compute_project_rollup(
        [
            StoryRollupInput(
                status=StoryStatus.IN_PROGRESS,
                updated_at=now - timedelta(days=10),
                tasks=[],
            ),
            StoryRollupInput(
                status=StoryStatus.IN_REVIEW,
                updated_at=now - timedelta(days=9),
                tasks=[],
            ),
            StoryRollupInput(
                status=StoryStatus.IN_PROGRESS,
                updated_at=now - timedelta(days=8),
                tasks=[],
            ),
        ],
        now=now,
    )
    assert off_track_stalled.health == ProjectHealth.OFF_TRACK
    assert off_track_stalled.stalled_stories == 3


def test_stalled_story_not_flagged_when_task_has_recent_activity() -> None:
    now = datetime(2026, 11, 20, 12, 0, tzinfo=UTC)
    rollup = compute_project_rollup(
        [
            StoryRollupInput(
                status=StoryStatus.IN_PROGRESS,
                updated_at=now - timedelta(days=14),
                tasks=[
                    TaskRollupInput(
                        status=TaskStatus.DOING,
                        updated_at=now - timedelta(days=1),
                    )
                ],
            )
        ],
        now=now,
    )
    assert rollup.stalled_stories == 0
    assert rollup.health == ProjectHealth.ON_TRACK

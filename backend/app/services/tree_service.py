from collections import defaultdict
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import ProjectRole, StoryStatus, TaskStatus
from app.models.project import Project
from app.models.story import Story
from app.models.task import Task
from app.schemas.tree import (
    ProjectRollupResponse,
    ProjectTreeResponse,
    StoryRollupResponse,
    StoryTreeNode,
)
from app.services.project_service import to_project_response
from app.services.rollup import (
    StoryRollupInput,
    TaskRollupInput,
    compute_project_rollup,
    compute_story_rollup,
)
from app.services.story_service import to_story_response
from app.services.task_service import to_task_response


def get_project_tree(
    db: Session,
    project: Project,
    role: ProjectRole,
) -> ProjectTreeResponse:
    now = datetime.now(UTC)
    today = now.date()

    stories = list(
        db.scalars(
            select(Story)
            .where(Story.project_id == project.id, Story.deleted_at.is_(None))
            .order_by(Story.position.asc(), Story.id.asc())
        ).all()
    )

    tasks_by_story: dict[str, list[Task]] = defaultdict(list)
    if stories:
        story_ids = [story.id for story in stories]
        tasks = list(
            db.scalars(
                select(Task)
                .where(Task.story_id.in_(story_ids), Task.deleted_at.is_(None))
                .order_by(Task.story_id.asc(), Task.position.asc(), Task.id.asc())
            ).all()
        )
        for task in tasks:
            tasks_by_story[task.story_id].append(task)

    story_nodes: list[StoryTreeNode] = []
    project_story_inputs: list[StoryRollupInput] = []

    for story in stories:
        story_tasks = tasks_by_story.get(story.id, [])
        task_inputs = [
            TaskRollupInput(
                status=TaskStatus(task.status),
                estimate_hours=task.estimate_hours,
                due_date=task.due_date,
            )
            for task in story_tasks
        ]
        story_status = StoryStatus(story.status)
        s_rollup = compute_story_rollup(task_inputs, story_status, today=today)
        project_story_inputs.append(
            StoryRollupInput(
                status=story_status,
                updated_at=story.updated_at,
                tasks=task_inputs,
            )
        )
        story_nodes.append(
            StoryTreeNode(
                story=to_story_response(story, project.key),
                rollup=StoryRollupResponse(
                    total_tasks=s_rollup.total_tasks,
                    done_tasks=s_rollup.done_tasks,
                    blocked_tasks=s_rollup.blocked_tasks,
                    overdue_tasks=s_rollup.overdue_tasks,
                    progress_pct=s_rollup.progress_pct,
                    is_blocked=s_rollup.is_blocked,
                    suggested_status=s_rollup.suggested_status,
                ),
                tasks=[to_task_response(task) for task in story_tasks],
            )
        )

    p_rollup = compute_project_rollup(project_story_inputs, now=now)
    return ProjectTreeResponse(
        project=to_project_response(project, role),
        rollup=ProjectRollupResponse(
            health=p_rollup.health,
            total_stories=p_rollup.total_stories,
            done_stories=p_rollup.done_stories,
            stalled_stories=p_rollup.stalled_stories,
            total_tasks=p_rollup.total_tasks,
            done_tasks=p_rollup.done_tasks,
            blocked_tasks=p_rollup.blocked_tasks,
            overdue_tasks=p_rollup.overdue_tasks,
            progress_pct=p_rollup.progress_pct,
        ),
        stories=story_nodes,
    )

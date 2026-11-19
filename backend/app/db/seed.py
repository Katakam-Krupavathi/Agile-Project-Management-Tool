from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.enums import (
    ActivityEntityType,
    ProjectRole,
    StoryPriority,
    StoryStatus,
    TaskStatus,
)
from app.models.project import Project, ProjectMember
from app.models.report import Report
from app.models.story import Story
from app.models.task import Task
from app.models.user import User
from app.services.activity import record_activity
from app.services.ranking import RANK_STEP
from app.services.report_service import build_project_report_markdown

DEMO_PASSWORD = "DemoPass123!"
DEMO_USERS = [
    ("alex@agilepm.dev", "Alex Rivera"),
    ("sam@agilepm.dev", "Sam Chen"),
    ("jordan@agilepm.dev", "Jordan Patel"),
]


def seed_demo_data(db: Session) -> bool:
    """Populate a realistic demo workspace idempotently. Returns True if seeded."""
    existing = db.scalar(select(User).where(User.email == DEMO_USERS[0][0]))
    if existing is not None:
        return False

    today = datetime.now(UTC).date()
    password_hash = hash_password(DEMO_PASSWORD)

    users: dict[str, User] = {}
    for email, name in DEMO_USERS:
        user = User(email=email, name=name, password_hash=password_hash, is_active=True)
        db.add(user)
        db.flush()
        users[email] = user

    alex = users["alex@agilepm.dev"]
    sam = users["sam@agilepm.dev"]
    jordan = users["jordan@agilepm.dev"]

    # Project 1: APM (6 stories, 19 tasks)
    apm = Project(
        key="APM",
        name="Agile PM Core",
        description="Core planning workspace, Kanban board, and durable background worker.",
        next_story_number=7,
        created_by=alex.id,
    )
    db.add(apm)
    db.flush()

    db.add_all(
        [
            ProjectMember(project_id=apm.id, user_id=alex.id, role=ProjectRole.OWNER.value),
            ProjectMember(project_id=apm.id, user_id=sam.id, role=ProjectRole.MEMBER.value),
            ProjectMember(project_id=apm.id, user_id=jordan.id, role=ProjectRole.VIEWER.value),
        ]
    )
    record_activity(
        db,
        project_id=apm.id,
        actor_id=alex.id,
        entity_type=ActivityEntityType.PROJECT,
        entity_id=apm.id,
        action="project.created",
        details={"key": apm.key, "name": apm.name},
    )

    apm_stories_spec = [
        (
            1,
            "Cookie sessions and CSRF protection",
            "Harden authentication with Argon2id, httpOnly cookies, and double-submit CSRF.",
            "All mutating routes reject missing or mismatched X-CSRF-Token headers.",
            StoryStatus.DONE,
            StoryPriority.HIGH,
            5,
            alex.id,
            [
                (
                    "Argon2id password hashing",
                    TaskStatus.DONE,
                    alex.id,
                    2.0,
                    today - timedelta(days=5),
                ),
                (
                    "Signed httpOnly session cookies",
                    TaskStatus.DONE,
                    alex.id,
                    3.0,
                    today - timedelta(days=4),
                ),
                (
                    "Sliding-window login rate limiter",
                    TaskStatus.DONE,
                    sam.id,
                    2.0,
                    today - timedelta(days=3),
                ),
            ],
        ),
        (
            2,
            "Role-based project access control",
            "Enforce owner, member, and viewer permissions centrally via require_project_role.",
            "Non-members receive 404; viewers receive 403 on write operations.",
            StoryStatus.DONE,
            StoryPriority.HIGH,
            5,
            sam.id,
            [
                (
                    "Central permission dependency",
                    TaskStatus.DONE,
                    sam.id,
                    3.0,
                    today - timedelta(days=3),
                ),
                (
                    "Last-owner removal guard",
                    TaskStatus.DONE,
                    alex.id,
                    1.5,
                    today - timedelta(days=2),
                ),
                (
                    "RBAC matrix integration tests",
                    TaskStatus.DONE,
                    sam.id,
                    2.5,
                    today - timedelta(days=2),
                ),
            ],
        ),
        (
            3,
            "Kanban board with drag-and-drop ranking",
            "Implement 4-column board with fractional ranking and optimistic rollback on 409.",
            "Dragging a story between columns persists order across page reloads.",
            StoryStatus.IN_REVIEW,
            StoryPriority.URGENT,
            8,
            sam.id,
            [
                (
                    "Fractional position ranker with rebalance",
                    TaskStatus.DONE,
                    sam.id,
                    3.0,
                    today - timedelta(days=1),
                ),
                ("dnd-kit column and card wiring", TaskStatus.DONE, sam.id, 4.0, today),
                ("Optimistic rollback and 409 Reload toast", TaskStatus.DONE, alex.id, 2.0, today),
            ],
        ),
        (
            4,
            "Durable SQLite job queue and worker",
            "Build Redis-free transactional queue with exponential backoff and stuck-job recovery.",
            "Worker recovers stale locks and dead-letters jobs after max_attempts.",
            StoryStatus.IN_PROGRESS,
            StoryPriority.URGENT,
            8,
            alex.id,
            [
                (
                    "Atomic UPDATE claim query",
                    TaskStatus.DONE,
                    alex.id,
                    3.0,
                    today - timedelta(days=1),
                ),
                (
                    "Exponential backoff with jitter",
                    TaskStatus.DOING,
                    alex.id,
                    2.5,
                    today + timedelta(days=1),
                ),
                (
                    "Dead-letter retry endpoint",
                    TaskStatus.BLOCKED,
                    sam.id,
                    2.0,
                    today - timedelta(days=1),
                ),
                (
                    "Multi-worker claim concurrency test",
                    TaskStatus.TODO,
                    sam.id,
                    2.0,
                    today + timedelta(days=2),
                ),
            ],
        ),
        (
            5,
            "Real-time notifications via SSE",
            "Stream assignment and status-change notifications to connected clients.",
            "Reconnecting with Last-Event-ID resumes without duplicating events.",
            StoryStatus.IN_PROGRESS,
            StoryPriority.MEDIUM,
            5,
            sam.id,
            [
                ("Transactional notification enqueueing", TaskStatus.DONE, sam.id, 2.0, today),
                (
                    "SSE endpoint with heartbeat",
                    TaskStatus.DOING,
                    alex.id,
                    3.0,
                    today + timedelta(days=1),
                ),
                (
                    "Top-bar bell dropdown and read-all",
                    TaskStatus.TODO,
                    sam.id,
                    2.5,
                    today + timedelta(days=3),
                ),
            ],
        ),
        (
            6,
            "Markdown status reports",
            "Generate downloadable project status reports asynchronously.",
            "Idempotency-Key deduplicates duplicate requests and returns 202.",
            StoryStatus.BACKLOG,
            StoryPriority.LOW,
            3,
            None,
            [
                (
                    "Markdown report renderer",
                    TaskStatus.TODO,
                    alex.id,
                    2.0,
                    today + timedelta(days=4),
                ),
                (
                    "Report download endpoint",
                    TaskStatus.TODO,
                    sam.id,
                    1.5,
                    today + timedelta(days=5),
                ),
                (
                    "Live job status polling card",
                    TaskStatus.TODO,
                    sam.id,
                    2.0,
                    today + timedelta(days=6),
                ),
            ],
        ),
    ]

    for idx, spec in enumerate(apm_stories_spec, start=1):
        (
            num,
            title,
            desc,
            ac,
            s_status,
            priority,
            points,
            assignee_id,
            tasks_spec,
        ) = spec
        story = Story(
            project_id=apm.id,
            number=num,
            title=title,
            description=desc,
            acceptance_criteria=ac,
            status=s_status.value,
            priority=priority.value,
            story_points=points,
            assignee_id=assignee_id,
            position=float(idx) * RANK_STEP,
            created_by=alex.id,
        )
        db.add(story)
        db.flush()
        record_activity(
            db,
            project_id=apm.id,
            actor_id=alex.id,
            entity_type=ActivityEntityType.STORY,
            entity_id=story.id,
            action="story.created",
            details={"key": f"APM-{num}", "title": title, "status": s_status.value},
        )
        for t_idx, (t_title, t_status, t_assignee, est, due) in enumerate(tasks_spec, start=1):
            task = Task(
                story_id=story.id,
                title=t_title,
                status=t_status.value,
                assignee_id=t_assignee,
                estimate_hours=est,
                due_date=due,
                position=float(t_idx) * RANK_STEP,
            )
            db.add(task)

    # Project 2: MKT (2 stories, 6 tasks) -> Total: 8 stories, 25 tasks
    mkt = Project(
        key="MKT",
        name="Launch Readiness",
        description="Documentation, container packaging, and release verification.",
        next_story_number=3,
        created_by=alex.id,
    )
    db.add(mkt)
    db.flush()

    db.add_all(
        [
            ProjectMember(project_id=mkt.id, user_id=alex.id, role=ProjectRole.OWNER.value),
            ProjectMember(project_id=mkt.id, user_id=sam.id, role=ProjectRole.MEMBER.value),
        ]
    )
    record_activity(
        db,
        project_id=mkt.id,
        actor_id=alex.id,
        entity_type=ActivityEntityType.PROJECT,
        entity_id=mkt.id,
        action="project.created",
        details={"key": mkt.key, "name": mkt.name},
    )

    mkt_stories_spec = [
        (
            1,
            "Docker Compose production stack",
            "Package API, background worker, and Nginx web containers with healthchecks.",
            "Fresh clone starts cleanly with docker compose up.",
            StoryStatus.IN_PROGRESS,
            StoryPriority.HIGH,
            5,
            alex.id,
            [
                ("Backend Dockerfile and entrypoint", TaskStatus.DONE, alex.id, 2.0, today),
                (
                    "Frontend multi-stage Nginx build",
                    TaskStatus.DOING,
                    sam.id,
                    2.0,
                    today + timedelta(days=1),
                ),
                (
                    "Shared SQLite volume healthchecks",
                    TaskStatus.TODO,
                    alex.id,
                    1.5,
                    today + timedelta(days=2),
                ),
            ],
        ),
        (
            2,
            "Architecture and security documentation",
            "Publish ER diagram, async state diagram, API examples, and security notes.",
            "README and docs/ cover setup, tradeoffs, and limitations.",
            StoryStatus.BACKLOG,
            StoryPriority.MEDIUM,
            3,
            sam.id,
            [
                ("Export OpenAPI specification", TaskStatus.DONE, sam.id, 1.0, today),
                (
                    "Write security and decisions docs",
                    TaskStatus.TODO,
                    alex.id,
                    2.0,
                    today + timedelta(days=3),
                ),
                (
                    "Final UI palette and dead-control audit",
                    TaskStatus.TODO,
                    sam.id,
                    1.5,
                    today + timedelta(days=4),
                ),
            ],
        ),
    ]

    for idx, spec in enumerate(mkt_stories_spec, start=1):
        (
            num,
            title,
            desc,
            ac,
            s_status,
            priority,
            points,
            assignee_id,
            tasks_spec,
        ) = spec
        story = Story(
            project_id=mkt.id,
            number=num,
            title=title,
            description=desc,
            acceptance_criteria=ac,
            status=s_status.value,
            priority=priority.value,
            story_points=points,
            assignee_id=assignee_id,
            position=float(idx) * RANK_STEP,
            created_by=alex.id,
        )
        db.add(story)
        db.flush()
        for t_idx, (t_title, t_status, t_assignee, est, due) in enumerate(tasks_spec, start=1):
            db.add(
                Task(
                    story_id=story.id,
                    title=t_title,
                    status=t_status.value,
                    assignee_id=t_assignee,
                    estimate_hours=est,
                    due_date=due,
                    position=float(t_idx) * RANK_STEP,
                )
            )

    db.flush()
    report_title, report_md = build_project_report_markdown(db, apm)
    db.add(
        Report(
            project_id=apm.id,
            created_by=alex.id,
            title=report_title,
            content_markdown=report_md,
        )
    )
    db.commit()
    return True


def main() -> None:
    with SessionLocal() as db:
        seeded = seed_demo_data(db)
        if seeded:
            print("Seeded demo workspace (login: alex@agilepm.dev / DemoPass123!).")
        else:
            print("Demo workspace already exists; skipping seed.")


if __name__ == "__main__":
    main()

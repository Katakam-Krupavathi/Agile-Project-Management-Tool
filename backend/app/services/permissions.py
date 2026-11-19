from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.errors import ForbiddenError, NotFoundError
from app.db.session import get_db
from app.models.enums import ProjectRole
from app.models.project import Project, ProjectMember
from app.models.story import Story
from app.models.user import User

ROLE_RANK: dict[ProjectRole, int] = {
    ProjectRole.VIEWER: 1,
    ProjectRole.MEMBER: 2,
    ProjectRole.OWNER: 3,
}


@dataclass(frozen=True)
class ProjectAccess:
    project: Project
    membership: ProjectMember
    role: ProjectRole
    user: User


def assert_project_role(
    db: Session,
    project_id: str,
    user: User,
    min_role: ProjectRole,
) -> ProjectAccess:
    row = db.execute(
        select(Project, ProjectMember)
        .join(ProjectMember, ProjectMember.project_id == Project.id)
        .where(
            Project.id == project_id,
            Project.deleted_at.is_(None),
            ProjectMember.user_id == user.id,
        )
    ).first()

    if row is None:
        raise NotFoundError("Project not found.", code="PROJECT_NOT_FOUND")

    project, membership = row[0], row[1]
    role = ProjectRole(membership.role)
    if ROLE_RANK[role] < ROLE_RANK[min_role]:
        raise ForbiddenError(
            "You do not have permission to perform this action on this project.",
            code="INSUFFICIENT_ROLE",
        )

    return ProjectAccess(project=project, membership=membership, role=role, user=user)


def require_project_role(min_role: ProjectRole) -> Callable[..., ProjectAccess]:
    def dependency(
        project_id: str,
        current_user: Annotated[User, Depends(get_current_user)],
        db: Annotated[Session, Depends(get_db)],
    ) -> ProjectAccess:
        return assert_project_role(db, project_id, current_user, min_role)

    return dependency


@dataclass(frozen=True)
class StoryAccess:
    story: Story
    project: Project
    membership: ProjectMember
    role: ProjectRole
    user: User


def require_story_role(min_role: ProjectRole) -> Callable[..., StoryAccess]:
    def dependency(
        story_id: str,
        current_user: Annotated[User, Depends(get_current_user)],
        db: Annotated[Session, Depends(get_db)],
    ) -> StoryAccess:
        story = db.scalar(
            select(Story).where(Story.id == story_id, Story.deleted_at.is_(None))
        )
        if story is None:
            raise NotFoundError("Story not found.", code="STORY_NOT_FOUND")
        project_access = assert_project_role(db, story.project_id, current_user, min_role)
        return StoryAccess(
            story=story,
            project=project_access.project,
            membership=project_access.membership,
            role=project_access.role,
            user=current_user,
        )

    return dependency

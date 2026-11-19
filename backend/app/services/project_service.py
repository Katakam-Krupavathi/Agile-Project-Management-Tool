import json
from datetime import datetime

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.core.errors import BadRequestError, ConflictError, NotFoundError
from app.core.pagination import decode_cursor, encode_cursor
from app.models.activity import ActivityLog
from app.models.enums import ActivityEntityType, ProjectRole
from app.models.project import Project, ProjectMember
from app.models.user import User, utc_now
from app.schemas.project import (
    ProjectCreateRequest,
    ProjectMemberCreateRequest,
    ProjectMemberResponse,
    ProjectResponse,
    ProjectUpdateRequest,
)
from app.services.auth_service import normalize_email


def to_project_response(project: Project, role: ProjectRole) -> ProjectResponse:
    return ProjectResponse(
        id=project.id,
        key=project.key,
        name=project.name,
        description=project.description,
        next_story_number=project.next_story_number,
        created_by=project.created_by,
        version=project.version,
        role=role,
        created_at=project.created_at,
        updated_at=project.updated_at,
        deleted_at=project.deleted_at,
    )


def list_projects_for_user(
    db: Session,
    user_id: str,
    *,
    cursor: str | None = None,
    limit: int = 20,
) -> tuple[list[ProjectResponse], str | None, bool]:
    stmt = (
        select(Project, ProjectMember.role)
        .join(ProjectMember, ProjectMember.project_id == Project.id)
        .where(
            ProjectMember.user_id == user_id,
            Project.deleted_at.is_(None),
        )
    )

    if cursor:
        cursor_data = decode_cursor(cursor)
        created_at_raw = cursor_data.get("created_at")
        cursor_id = cursor_data.get("id")
        if not isinstance(created_at_raw, str) or not isinstance(cursor_id, str):
            raise BadRequestError("Invalid pagination cursor.", code="INVALID_CURSOR")
        try:
            cursor_created_at = datetime.fromisoformat(created_at_raw)
        except ValueError as exc:
            raise BadRequestError("Invalid pagination cursor.", code="INVALID_CURSOR") from exc
        stmt = stmt.where(
            or_(
                Project.created_at < cursor_created_at,
                and_(Project.created_at == cursor_created_at, Project.id < cursor_id),
            )
        )

    stmt = stmt.order_by(Project.created_at.desc(), Project.id.desc()).limit(limit + 1)
    rows = db.execute(stmt).all()

    has_more = len(rows) > limit
    page_rows = rows[:limit]
    items = [to_project_response(project, ProjectRole(role)) for project, role in page_rows]

    next_cursor: str | None = None
    if has_more and page_rows:
        last_project = page_rows[-1][0]
        next_cursor = encode_cursor(
            {
                "created_at": last_project.created_at.isoformat(),
                "id": last_project.id,
            }
        )

    return items, next_cursor, has_more


def create_project(
    db: Session,
    user: User,
    payload: ProjectCreateRequest,
) -> ProjectResponse:
    existing = db.scalar(select(Project).where(Project.key == payload.key))
    if existing is not None:
        raise ConflictError(
            f"Project key '{payload.key}' is already in use.",
            code="PROJECT_KEY_EXISTS",
        )

    project = Project(
        key=payload.key,
        name=payload.name,
        description=payload.description,
        created_by=user.id,
    )
    db.add(project)
    db.flush()

    membership = ProjectMember(
        project_id=project.id,
        user_id=user.id,
        role=ProjectRole.OWNER.value,
    )
    db.add(membership)

    db.add(
        ActivityLog(
            project_id=project.id,
            actor_id=user.id,
            entity_type=ActivityEntityType.PROJECT.value,
            entity_id=project.id,
            action="project.created",
            details=json.dumps({"key": project.key, "name": project.name}),
        )
    )
    db.commit()
    db.refresh(project)
    return to_project_response(project, ProjectRole.OWNER)


def update_project(
    db: Session,
    project: Project,
    role: ProjectRole,
    payload: ProjectUpdateRequest,
    actor_id: str,
) -> ProjectResponse:
    if project.version != payload.version:
        raise ConflictError(
            "Project has been modified by another request. Reload and retry.",
            code="VERSION_CONFLICT",
        )

    changes: dict[str, object] = {}
    if payload.name is not None and payload.name != project.name:
        changes["name"] = {"from": project.name, "to": payload.name}
        project.name = payload.name
    if "description" in payload.model_fields_set and payload.description != project.description:
        changes["description"] = {"updated": True}
        project.description = payload.description

    project.version += 1
    db.add(
        ActivityLog(
            project_id=project.id,
            actor_id=actor_id,
            entity_type=ActivityEntityType.PROJECT.value,
            entity_id=project.id,
            action="project.updated",
            details=json.dumps(changes),
        )
    )
    db.commit()
    db.refresh(project)
    return to_project_response(project, role)


def archive_project(
    db: Session,
    project: Project,
    actor_id: str,
) -> None:
    project.deleted_at = utc_now()
    project.version += 1
    db.add(
        ActivityLog(
            project_id=project.id,
            actor_id=actor_id,
            entity_type=ActivityEntityType.PROJECT.value,
            entity_id=project.id,
            action="project.archived",
            details=json.dumps({"key": project.key}),
        )
    )
    db.commit()


def _to_member_response(membership: ProjectMember, user: User) -> ProjectMemberResponse:
    return ProjectMemberResponse(
        id=membership.id,
        project_id=membership.project_id,
        user_id=user.id,
        email=user.email,
        name=user.name,
        role=ProjectRole(membership.role),
        created_at=membership.created_at,
    )


def list_project_members(
    db: Session,
    project_id: str,
    *,
    cursor: str | None = None,
    limit: int = 20,
) -> tuple[list[ProjectMemberResponse], str | None, bool]:
    stmt = (
        select(ProjectMember, User)
        .join(User, User.id == ProjectMember.user_id)
        .where(ProjectMember.project_id == project_id)
    )

    if cursor:
        cursor_data = decode_cursor(cursor)
        created_at_raw = cursor_data.get("created_at")
        cursor_id = cursor_data.get("id")
        if not isinstance(created_at_raw, str) or not isinstance(cursor_id, str):
            raise BadRequestError("Invalid pagination cursor.", code="INVALID_CURSOR")
        try:
            cursor_created_at = datetime.fromisoformat(created_at_raw)
        except ValueError as exc:
            raise BadRequestError("Invalid pagination cursor.", code="INVALID_CURSOR") from exc
        stmt = stmt.where(
            or_(
                ProjectMember.created_at > cursor_created_at,
                and_(ProjectMember.created_at == cursor_created_at, ProjectMember.id > cursor_id),
            )
        )

    stmt = stmt.order_by(ProjectMember.created_at.asc(), ProjectMember.id.asc()).limit(limit + 1)
    rows = db.execute(stmt).all()

    has_more = len(rows) > limit
    page_rows = rows[:limit]
    items = [_to_member_response(membership, user) for membership, user in page_rows]

    next_cursor: str | None = None
    if has_more and page_rows:
        last_membership = page_rows[-1][0]
        next_cursor = encode_cursor(
            {
                "created_at": last_membership.created_at.isoformat(),
                "id": last_membership.id,
            }
        )

    return items, next_cursor, has_more


def add_project_member(
    db: Session,
    project: Project,
    payload: ProjectMemberCreateRequest,
    actor_id: str,
) -> ProjectMemberResponse:
    normalized_email = normalize_email(str(payload.email))
    target_user = db.scalar(
        select(User).where(User.email == normalized_email, User.is_active.is_(True))
    )
    if target_user is None:
        raise NotFoundError("No active user found with that email.", code="USER_NOT_FOUND")

    existing = db.scalar(
        select(ProjectMember).where(
            ProjectMember.project_id == project.id,
            ProjectMember.user_id == target_user.id,
        )
    )
    if existing is not None:
        raise ConflictError(
            "User is already a member of this project.",
            code="MEMBER_ALREADY_EXISTS",
        )

    membership = ProjectMember(
        project_id=project.id,
        user_id=target_user.id,
        role=payload.role.value,
    )
    db.add(membership)
    db.flush()

    db.add(
        ActivityLog(
            project_id=project.id,
            actor_id=actor_id,
            entity_type=ActivityEntityType.PROJECT_MEMBER.value,
            entity_id=membership.id,
            action="project_member.added",
            details=json.dumps({"user_id": target_user.id, "role": payload.role.value}),
        )
    )
    db.commit()
    db.refresh(membership)
    return _to_member_response(membership, target_user)


def remove_project_member(
    db: Session,
    project: Project,
    target_user_id: str,
    actor_id: str,
) -> None:
    membership = db.scalar(
        select(ProjectMember).where(
            ProjectMember.project_id == project.id,
            ProjectMember.user_id == target_user_id,
        )
    )
    if membership is None:
        raise NotFoundError("Project member not found.", code="MEMBER_NOT_FOUND")

    if membership.role == ProjectRole.OWNER.value:
        owner_count = db.scalar(
            select(func.count(ProjectMember.id)).where(
                ProjectMember.project_id == project.id,
                ProjectMember.role == ProjectRole.OWNER.value,
            )
        )
        if (owner_count or 0) <= 1:
            raise ConflictError(
                "Cannot remove the last owner of a project.",
                code="LAST_OWNER_CANNOT_BE_REMOVED",
            )

    membership_id = membership.id
    removed_role = membership.role
    db.delete(membership)
    db.add(
        ActivityLog(
            project_id=project.id,
            actor_id=actor_id,
            entity_type=ActivityEntityType.PROJECT_MEMBER.value,
            entity_id=membership_id,
            action="project_member.removed",
            details=json.dumps({"user_id": target_user_id, "role": removed_role}),
        )
    )
    db.commit()

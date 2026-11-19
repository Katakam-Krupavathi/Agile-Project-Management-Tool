from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_csrf
from app.db.session import get_db
from app.models.enums import ProjectRole
from app.models.user import User
from app.schemas.common import CursorPage
from app.schemas.project import ProjectCreateRequest, ProjectResponse, ProjectUpdateRequest
from app.services import project_service
from app.services.permissions import ProjectAccess, require_project_role

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model=CursorPage[ProjectResponse])
def list_projects(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    cursor: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> CursorPage[ProjectResponse]:
    items, next_cursor, has_more = project_service.list_projects_for_user(
        db,
        current_user.id,
        cursor=cursor,
        limit=limit,
    )
    return CursorPage(items=items, next_cursor=next_cursor, has_more=has_more)


@router.post(
    "",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
def create_project(
    payload: ProjectCreateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> ProjectResponse:
    return project_service.create_project(db, current_user, payload)


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(
    access: Annotated[ProjectAccess, Depends(require_project_role(ProjectRole.VIEWER))],
) -> ProjectResponse:
    return project_service.to_project_response(access.project, access.role)


@router.patch(
    "/{project_id}",
    response_model=ProjectResponse,
    dependencies=[Depends(require_csrf)],
)
def update_project(
    payload: ProjectUpdateRequest,
    access: Annotated[ProjectAccess, Depends(require_project_role(ProjectRole.OWNER))],
    db: Annotated[Session, Depends(get_db)],
) -> ProjectResponse:
    return project_service.update_project(db, access.project, access.role, payload, access.user.id)


@router.delete(
    "/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf)],
)
def archive_project(
    access: Annotated[ProjectAccess, Depends(require_project_role(ProjectRole.OWNER))],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    project_service.archive_project(db, access.project, access.user.id)

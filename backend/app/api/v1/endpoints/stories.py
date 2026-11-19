from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import require_csrf
from app.db.session import get_db
from app.models.enums import ProjectRole, StoryStatus
from app.schemas.common import CursorPage
from app.schemas.story import (
    StoryCreateRequest,
    StoryMoveRequest,
    StoryResponse,
    StoryUpdateRequest,
)
from app.services import story_service
from app.services.permissions import (
    ProjectAccess,
    StoryAccess,
    require_project_role,
    require_story_role,
)

router = APIRouter(tags=["stories"])


@router.get("/projects/{project_id}/stories", response_model=CursorPage[StoryResponse])
def list_stories(
    access: Annotated[ProjectAccess, Depends(require_project_role(ProjectRole.VIEWER))],
    db: Annotated[Session, Depends(get_db)],
    story_status: Annotated[StoryStatus | None, Query(alias="status")] = None,
    assignee: Annotated[str | None, Query()] = None,
    q: Annotated[str | None, Query(max_length=200)] = None,
    cursor: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> CursorPage[StoryResponse]:
    items, next_cursor, has_more = story_service.list_stories(
        db,
        access.project,
        status_filter=story_status,
        assignee_id=assignee,
        q=q,
        cursor=cursor,
        limit=limit,
    )
    return CursorPage(items=items, next_cursor=next_cursor, has_more=has_more)


@router.post(
    "/projects/{project_id}/stories",
    response_model=StoryResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
def create_story(
    payload: StoryCreateRequest,
    access: Annotated[ProjectAccess, Depends(require_project_role(ProjectRole.MEMBER))],
    db: Annotated[Session, Depends(get_db)],
) -> StoryResponse:
    return story_service.create_story(db, access.project, payload, access.user.id)


@router.get("/stories/{story_id}", response_model=StoryResponse)
def get_story(
    access: Annotated[StoryAccess, Depends(require_story_role(ProjectRole.VIEWER))],
) -> StoryResponse:
    return story_service.to_story_response(access.story, access.project.key)


@router.patch(
    "/stories/{story_id}",
    response_model=StoryResponse,
    dependencies=[Depends(require_csrf)],
)
def update_story(
    payload: StoryUpdateRequest,
    access: Annotated[StoryAccess, Depends(require_story_role(ProjectRole.MEMBER))],
    db: Annotated[Session, Depends(get_db)],
) -> StoryResponse:
    return story_service.update_story(db, access.story, access.project, payload, access.user.id)


@router.delete(
    "/stories/{story_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf)],
)
def delete_story(
    access: Annotated[StoryAccess, Depends(require_story_role(ProjectRole.MEMBER))],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    story_service.soft_delete_story(db, access.story, access.user.id)


@router.post(
    "/stories/{story_id}/move",
    response_model=StoryResponse,
    dependencies=[Depends(require_csrf)],
)
def move_story(
    payload: StoryMoveRequest,
    access: Annotated[StoryAccess, Depends(require_story_role(ProjectRole.MEMBER))],
    db: Annotated[Session, Depends(get_db)],
) -> StoryResponse:
    return story_service.move_story(db, access.story, access.project, payload, access.user.id)

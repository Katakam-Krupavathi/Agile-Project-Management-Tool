from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import require_csrf
from app.db.session import get_db
from app.models.enums import ProjectRole
from app.schemas.common import CursorPage
from app.schemas.task import TaskCreateRequest, TaskMoveRequest, TaskResponse, TaskUpdateRequest
from app.services import task_service
from app.services.permissions import StoryAccess, TaskAccess, require_story_role, require_task_role

router = APIRouter(tags=["tasks"])


@router.get("/stories/{story_id}/tasks", response_model=CursorPage[TaskResponse])
def list_tasks(
    access: Annotated[StoryAccess, Depends(require_story_role(ProjectRole.VIEWER))],
    db: Annotated[Session, Depends(get_db)],
    cursor: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> CursorPage[TaskResponse]:
    items, next_cursor, has_more = task_service.list_tasks(
        db,
        access.story.id,
        cursor=cursor,
        limit=limit,
    )
    return CursorPage(items=items, next_cursor=next_cursor, has_more=has_more)


@router.post(
    "/stories/{story_id}/tasks",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
def create_task(
    payload: TaskCreateRequest,
    access: Annotated[StoryAccess, Depends(require_story_role(ProjectRole.MEMBER))],
    db: Annotated[Session, Depends(get_db)],
) -> TaskResponse:
    return task_service.create_task(db, access.story, payload)


@router.patch(
    "/tasks/{task_id}",
    response_model=TaskResponse,
    dependencies=[Depends(require_csrf)],
)
def update_task(
    payload: TaskUpdateRequest,
    access: Annotated[TaskAccess, Depends(require_task_role(ProjectRole.MEMBER))],
    db: Annotated[Session, Depends(get_db)],
) -> TaskResponse:
    return task_service.update_task(db, access.task, access.project.id, payload)


@router.delete(
    "/tasks/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf)],
)
def delete_task(
    access: Annotated[TaskAccess, Depends(require_task_role(ProjectRole.MEMBER))],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    task_service.soft_delete_task(db, access.task)


@router.post(
    "/tasks/{task_id}/move",
    response_model=TaskResponse,
    dependencies=[Depends(require_csrf)],
)
def move_task(
    payload: TaskMoveRequest,
    access: Annotated[TaskAccess, Depends(require_task_role(ProjectRole.MEMBER))],
    db: Annotated[Session, Depends(get_db)],
) -> TaskResponse:
    return task_service.move_task(db, access.task, payload)

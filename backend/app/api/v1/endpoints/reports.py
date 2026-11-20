from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_csrf
from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.models.enums import JobStatus, ProjectRole
from app.models.user import User
from app.schemas.common import CursorPage
from app.schemas.report import ReportEnqueueResponse, ReportSummaryResponse
from app.services import report_service
from app.services.permissions import ProjectAccess, require_project_role

router = APIRouter(tags=["reports"])


@router.post(
    "/projects/{project_id}/reports",
    response_model=ReportEnqueueResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_csrf)],
)
def enqueue_project_report(
    access: Annotated[ProjectAccess, Depends(require_project_role(ProjectRole.MEMBER))],
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key", max_length=100)] = None,
) -> ReportEnqueueResponse:
    job = report_service.request_project_report(
        db,
        access.project,
        access.user,
        idempotency_key=idempotency_key,
        cooldown_seconds=settings.report_cooldown_seconds,
        retention_max=settings.report_retention_max_per_project,
    )
    return ReportEnqueueResponse(job_id=job.id, status=JobStatus(job.status))


@router.get(
    "/projects/{project_id}/reports",
    response_model=CursorPage[ReportSummaryResponse],
)
def list_project_reports(
    access: Annotated[ProjectAccess, Depends(require_project_role(ProjectRole.VIEWER))],
    db: Annotated[Session, Depends(get_db)],
    cursor: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> CursorPage[ReportSummaryResponse]:
    items, next_cursor, has_more = report_service.list_project_reports(
        db,
        access.project.id,
        cursor=cursor,
        limit=limit,
    )
    return CursorPage(items=items, next_cursor=next_cursor, has_more=has_more)


@router.get("/reports/{report_id}")
def download_report(
    report_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    report = report_service.get_report_for_user(db, report_id, current_user)
    filename = f"report-{report.id[:8]}.md"
    return Response(
        content=report.content_markdown,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

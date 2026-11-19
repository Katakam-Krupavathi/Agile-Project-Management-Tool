from fastapi import APIRouter

from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.health import router as health_router
from app.api.v1.endpoints.jobs import router as jobs_router
from app.api.v1.endpoints.notifications import router as notifications_router
from app.api.v1.endpoints.projects import router as projects_router
from app.api.v1.endpoints.reports import router as reports_router
from app.api.v1.endpoints.stories import router as stories_router
from app.api.v1.endpoints.tasks import router as tasks_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(projects_router)
api_router.include_router(stories_router)
api_router.include_router(tasks_router)
api_router.include_router(jobs_router)
api_router.include_router(notifications_router)
api_router.include_router(reports_router)

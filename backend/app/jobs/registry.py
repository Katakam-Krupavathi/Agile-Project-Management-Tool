from collections.abc import Callable
from typing import Any

from sqlalchemy.orm import Session

JobHandler = Callable[[Session, dict[str, Any]], dict[str, Any] | None]

_REGISTRY: dict[str, JobHandler] = {}


def register(job_type: str) -> Callable[[JobHandler], JobHandler]:
    """Register an idempotent job handler for a given ``job_type``."""

    def decorator(func: JobHandler) -> JobHandler:
        _REGISTRY[job_type] = func
        return func

    return decorator


def get_handler(job_type: str) -> JobHandler | None:
    return _REGISTRY.get(job_type)


def list_registered_job_types() -> list[str]:
    return sorted(_REGISTRY.keys())


def unregister(job_type: str) -> None:
    _REGISTRY.pop(job_type, None)

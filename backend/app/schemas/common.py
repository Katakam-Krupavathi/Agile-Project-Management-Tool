from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ValidationErrorItem(BaseModel):
    field: str
    message: str
    type: str


class ProblemDetail(BaseModel):
    type: str
    title: str
    status: int
    detail: str
    instance: str
    code: str
    errors: list[ValidationErrorItem] | None = None


class CursorPage(BaseModel, Generic[T]):
    items: list[T]
    next_cursor: str | None = None
    has_more: bool = False

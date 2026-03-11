"""
Базовые Pydantic-схемы для стандартизированных ответов API.

ВАЖНО: PaginatedResponse определён в app/schemas/common.py — единственный источник правды.
       Не дублировать здесь!
"""

from datetime import datetime
from typing import Any, Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class SuccessResponse(BaseModel, Generic[T]):
    """Стандартный успешный ответ."""
    success: bool = True
    data: T
    message: str | None = None


class ErrorResponse(BaseModel):
    """Стандартный ответ с ошибкой."""
    success: bool = False
    error: str
    detail: str | None = None
    code: str | None = None


class PaginationParams(BaseModel):
    """Параметры пагинации для запросов."""
    page: int = 1
    page_size: int = 20


class StatusResponse(BaseModel):
    """Простой статусный ответ."""
    status: str = "ok"
    message: str | None = None


class BaseSchema(BaseModel):
    """Базовая схема с общими полями."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
    updated_at: datetime
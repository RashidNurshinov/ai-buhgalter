"""
Общие Pydantic-схемы: пагинация, статусные ответы, обёртки.
"""

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PaginationParams(BaseModel):
    """Параметры пагинации."""
    page: int = Field(1, ge=1, description="Номер страницы")
    per_page: int = Field(20, ge=1, le=100, description="Элементов на странице")

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.per_page

    @property
    def limit(self) -> int:
        return self.per_page


class PaginatedResponse(BaseModel, Generic[T]):
    """Обёртка для пагинированного ответа."""
    items: list[Any]
    total: int
    page: int
    per_page: int
    pages: int


class StatusResponse(BaseModel):
    """Простой статусный ответ."""
    status: str = "ok"
    message: str | None = None


class ErrorResponse(BaseModel):
    """Структура ошибки."""
    detail: str
    error_code: str | None = None


class FileUploadResponse(BaseModel):
    """Ответ на загрузку файла."""
    file_path: str
    file_name: str
    file_size: int
    content_type: str
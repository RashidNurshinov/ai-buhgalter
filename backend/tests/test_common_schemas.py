"""
Тесты общих Pydantic-схем: пагинация, статусные ответы.

Тестируем:
- PaginationParams — offset/limit расчёт
- PaginatedResponse — структура пагинированного ответа
- StatusResponse — простой статусный ответ
- ErrorResponse — структура ошибки
- FileUploadResponse — ответ на загрузку
"""

import pytest
from pydantic import ValidationError

from app.schemas.common import (
    ErrorResponse,
    FileUploadResponse,
    PaginatedResponse,
    PaginationParams,
    StatusResponse,
)


# ─── PaginationParams ───────────────────────────────────────────


class TestPaginationParams:
    """Тесты PaginationParams."""

    def test_defaults(self):
        """Значения по умолчанию."""
        p = PaginationParams()
        assert p.page == 1
        assert p.per_page == 20

    def test_offset_page_1(self):
        """offset для первой страницы = 0."""
        p = PaginationParams(page=1, per_page=20)
        assert p.offset == 0

    def test_offset_page_2(self):
        """offset для второй страницы."""
        p = PaginationParams(page=2, per_page=20)
        assert p.offset == 20

    def test_offset_page_5_per_10(self):
        """offset для 5-й страницы по 10 элементов."""
        p = PaginationParams(page=5, per_page=10)
        assert p.offset == 40

    def test_limit_equals_per_page(self):
        """limit = per_page."""
        p = PaginationParams(page=1, per_page=50)
        assert p.limit == 50

    def test_page_minimum_1(self):
        """page не может быть меньше 1."""
        with pytest.raises(ValidationError):
            PaginationParams(page=0)

    def test_per_page_minimum_1(self):
        """per_page не может быть меньше 1."""
        with pytest.raises(ValidationError):
            PaginationParams(per_page=0)

    def test_per_page_maximum_100(self):
        """per_page не может быть больше 100."""
        with pytest.raises(ValidationError):
            PaginationParams(per_page=101)

    def test_per_page_exactly_100(self):
        """per_page = 100 — валидно."""
        p = PaginationParams(per_page=100)
        assert p.per_page == 100


# ─── PaginatedResponse ──────────────────────────────────────────


class TestPaginatedResponse:
    """Тесты PaginatedResponse."""

    def test_empty_items(self):
        """Пустой список items."""
        resp = PaginatedResponse(
            items=[],
            total=0,
            page=1,
            per_page=20,
            pages=0,
        )
        assert len(resp.items) == 0
        assert resp.total == 0
        assert resp.pages == 0

    def test_with_items(self):
        """Ответ с элементами."""
        resp = PaginatedResponse(
            items=[{"id": 1}, {"id": 2}, {"id": 3}],
            total=50,
            page=1,
            per_page=3,
            pages=17,
        )
        assert len(resp.items) == 3
        assert resp.total == 50
        assert resp.pages == 17

    def test_last_page(self):
        """Последняя страница."""
        resp = PaginatedResponse(
            items=[{"id": 50}],
            total=50,
            page=50,
            per_page=1,
            pages=50,
        )
        assert resp.page == 50
        assert len(resp.items) == 1


# ─── StatusResponse ─────────────────────────────────────────────


class TestStatusResponse:
    """Тесты StatusResponse."""

    def test_default(self):
        """Значения по умолчанию."""
        resp = StatusResponse()
        assert resp.status == "ok"
        assert resp.message is None

    def test_with_message(self):
        """С сообщением."""
        resp = StatusResponse(status="ok", message="Операция выполнена")
        assert resp.message == "Операция выполнена"

    def test_custom_status(self):
        """Кастомный статус."""
        resp = StatusResponse(status="error", message="Что-то пошло не так")
        assert resp.status == "error"


# ─── ErrorResponse ──────────────────────────────────────────────


class TestErrorResponse:
    """Тесты ErrorResponse."""

    def test_minimal(self):
        """Минимальная ошибка — только detail."""
        err = ErrorResponse(detail="Не найдено")
        assert err.detail == "Не найдено"
        assert err.error_code is None

    def test_with_error_code(self):
        """Ошибка с кодом."""
        err = ErrorResponse(
            detail="Пользователь не найден",
            error_code="USER_NOT_FOUND",
        )
        assert err.error_code == "USER_NOT_FOUND"


# ─── FileUploadResponse ─────────────────────────────────────────


class TestFileUploadResponse:
    """Тесты FileUploadResponse."""

    def test_valid(self):
        """Валидный ответ на загрузку."""
        resp = FileUploadResponse(
            file_path="/storage/uploads/abc123.pdf",
            file_name="document.pdf",
            file_size=1048576,
            content_type="application/pdf",
        )
        assert resp.file_name == "document.pdf"
        assert resp.file_size == 1048576
        assert resp.content_type == "application/pdf"

    def test_image_upload(self):
        """Загрузка изображения."""
        resp = FileUploadResponse(
            file_path="/storage/uploads/photo.jpg",
            file_name="чек.jpg",
            file_size=512000,
            content_type="image/jpeg",
        )
        assert resp.file_name == "чек.jpg"
        assert resp.content_type == "image/jpeg"
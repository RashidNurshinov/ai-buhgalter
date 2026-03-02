"""
Тесты налогового календаря — TaxCalendarService (пункт 1.14.6).

Тестируем:
- populate_calendar: заполнение из справочника
- get_events: фильтрация по году, статусу, типу
- get_upcoming: ближайшие события
- get_overdue: просроченные
- complete_event: отметка выполнения
- update_overdue_statuses: автообновление статусов
- get_counts: счётчики по статусам
"""

import uuid
from datetime import date, datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.constants.enums import CalendarEventStatus, CalendarEventType
from app.services.tax_calendar_service import TaxCalendarService


# ─── Фикстуры ───────────────────────────────────────────────


@pytest.fixture
def mock_db():
    """Замоканная async-сессия БД."""
    db = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.flush = AsyncMock()
    db.execute = AsyncMock()
    return db


@pytest.fixture
def user_id():
    return str(uuid.UUID("12345678-1234-5678-1234-567812345678"))


@pytest.fixture
def sample_event():
    """Мок события календаря."""
    event = MagicMock()
    event.id = str(uuid.uuid4())
    event.user_id = str(uuid.UUID("12345678-1234-5678-1234-567812345678"))
    event.event_type = CalendarEventType.TAX_PAYMENT
    event.title = "НДС за 1 кв. 2026 (1/3)"
    event.description = "Первый платёж НДС"
    event.deadline = date(2026, 4, 28)
    event.status = CalendarEventStatus.UPCOMING
    event.completed_at = None
    event.reminded_at = None
    event.created_at = datetime.now(timezone.utc)
    event.updated_at = datetime.now(timezone.utc)
    return event


# ─── populate_calendar ──────────────────────────────────────


class TestPopulateCalendar:
    """Тесты заполнения календаря."""

    @pytest.mark.asyncio
    async def test_populate_2026(self, mock_db, user_id):
        """Заполнение календаря на 2026 год."""
        # Мок: нет существующих событий
        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_db.execute.return_value = mock_result

        service = TaxCalendarService(mock_db)
        result = await service.populate_calendar(user_id, year=2026)

        assert result["year"] == 2026
        assert result["created"] > 0
        assert result["skipped"] == 0
        # Проверяем, что add вызывался
        assert mock_db.add.call_count == result["created"]
        mock_db.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_populate_unsupported_year(self, mock_db, user_id):
        """Заполнение на неподдерживаемый год → 0 событий."""
        service = TaxCalendarService(mock_db)
        result = await service.populate_calendar(user_id, year=2025)

        assert result["created"] == 0
        assert "Нет шаблонов" in result.get("message", "")

    @pytest.mark.asyncio
    async def test_populate_skip_existing(self, mock_db, user_id):
        """Пропуск существующих событий (не перезаписываем)."""
        # Мок: одно событие уже существует
        mock_result = MagicMock()
        mock_result.all.return_value = [("НДС за 1 кв. 2026 (1/3)",)]
        mock_db.execute.return_value = mock_result

        service = TaxCalendarService(mock_db)
        result = await service.populate_calendar(user_id, year=2026, overwrite=False)

        assert result["skipped"] >= 1


# ─── get_events ─────────────────────────────────────────────


class TestGetEvents:
    """Тесты получения событий."""

    @pytest.mark.asyncio
    async def test_get_events_returns_list(self, mock_db, user_id, sample_event):
        """get_events возвращает список."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [sample_event]
        mock_db.execute.return_value = mock_result

        service = TaxCalendarService(mock_db)
        events = await service.get_events(user_id, year=2026)

        assert len(events) == 1
        assert events[0].title == "НДС за 1 кв. 2026 (1/3)"

    @pytest.mark.asyncio
    async def test_get_events_empty(self, mock_db, user_id):
        """Нет событий → пустой список."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result

        service = TaxCalendarService(mock_db)
        events = await service.get_events(user_id, year=2026)

        assert events == []


# ─── get_upcoming ────────────────────────────────────────────


class TestGetUpcoming:
    """Тесты получения ближайших событий."""

    @pytest.mark.asyncio
    async def test_get_upcoming_returns_list(self, mock_db, user_id, sample_event):
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [sample_event]
        mock_db.execute.return_value = mock_result

        service = TaxCalendarService(mock_db)
        events = await service.get_upcoming(user_id, days_ahead=30)

        assert len(events) == 1

    @pytest.mark.asyncio
    async def test_get_upcoming_empty(self, mock_db, user_id):
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result

        service = TaxCalendarService(mock_db)
        events = await service.get_upcoming(user_id, days_ahead=7)

        assert events == []


# ─── get_overdue ─────────────────────────────────────────────


class TestGetOverdue:
    """Тесты получения просроченных событий."""

    @pytest.mark.asyncio
    async def test_get_overdue_returns_list(self, mock_db, user_id):
        overdue_event = MagicMock()
        overdue_event.status = CalendarEventStatus.OVERDUE
        overdue_event.title = "Просроченное"
        overdue_event.deadline = date(2026, 1, 25)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [overdue_event]
        mock_db.execute.return_value = mock_result

        service = TaxCalendarService(mock_db)
        events = await service.get_overdue(user_id)

        assert len(events) == 1
        assert events[0].status == CalendarEventStatus.OVERDUE


# ─── complete_event ──────────────────────────────────────────


class TestCompleteEvent:
    """Тесты отметки выполнения."""

    @pytest.mark.asyncio
    async def test_complete_event_success(self, mock_db, user_id, sample_event):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_event
        mock_db.execute.return_value = mock_result

        service = TaxCalendarService(mock_db)
        event = await service.complete_event(user_id, sample_event.id)

        assert event is not None
        assert event.status == CalendarEventStatus.COMPLETED
        assert event.completed_at is not None
        mock_db.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_complete_event_not_found(self, mock_db, user_id):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        service = TaxCalendarService(mock_db)
        event = await service.complete_event(user_id, "nonexistent")

        assert event is None


# ─── get_counts ──────────────────────────────────────────────


class TestGetCounts:
    """Тесты счётчиков."""

    @pytest.mark.asyncio
    async def test_get_counts(self, mock_db, user_id):
        mock_result = MagicMock()
        mock_result.all.return_value = [
            (CalendarEventStatus.UPCOMING, 20),
            (CalendarEventStatus.OVERDUE, 3),
            (CalendarEventStatus.COMPLETED, 10),
        ]
        mock_db.execute.return_value = mock_result

        service = TaxCalendarService(mock_db)
        counts = await service.get_counts(user_id)

        assert counts["upcoming"] == 20
        assert counts["overdue"] == 3
        assert counts["completed"] == 10

    @pytest.mark.asyncio
    async def test_get_counts_empty(self, mock_db, user_id):
        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_db.execute.return_value = mock_result

        service = TaxCalendarService(mock_db)
        counts = await service.get_counts(user_id)

        assert counts["upcoming"] == 0
        assert counts["overdue"] == 0
        assert counts["completed"] == 0


# ─── update_overdue_statuses ─────────────────────────────────


class TestUpdateOverdueStatuses:
    """Тесты автообновления статусов."""

    @pytest.mark.asyncio
    async def test_update_overdue(self, mock_db, user_id):
        mock_result = MagicMock()
        mock_result.rowcount = 5
        mock_db.execute.return_value = mock_result

        service = TaxCalendarService(mock_db)
        count = await service.update_overdue_statuses(user_id=user_id)

        assert count == 5

    @pytest.mark.asyncio
    async def test_update_overdue_no_changes(self, mock_db, user_id):
        mock_result = MagicMock()
        mock_result.rowcount = 0
        mock_db.execute.return_value = mock_result

        service = TaxCalendarService(mock_db)
        count = await service.update_overdue_statuses(user_id=user_id)

        assert count == 0

    @pytest.mark.asyncio
    async def test_update_overdue_all_users(self, mock_db):
        """Обновление для всех пользователей (user_id=None)."""
        mock_result = MagicMock()
        mock_result.rowcount = 12
        mock_db.execute.return_value = mock_result

        service = TaxCalendarService(mock_db)
        count = await service.update_overdue_statuses(user_id=None)

        assert count == 12
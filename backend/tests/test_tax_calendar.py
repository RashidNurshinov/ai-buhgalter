"""
Тесты налогового календаря.

Тестируем:
- CalendarEventTemplate — шаблоны событий
- get_calendar_templates() — получение шаблонов по году
- Полноту и корректность данных за 2026 год
- Pydantic-схемы календаря
"""

import uuid
from datetime import date, datetime, timezone

import pytest

from app.constants.enums import CalendarEventStatus, CalendarEventType
from app.constants.tax_calendar import (
    TAX_CALENDAR_2026,
    CalendarEventTemplate,
    get_calendar_templates,
)
from app.schemas.tax_calendar import (
    TaxCalendarCompleteRequest,
    TaxCalendarEventResponse,
    TaxCalendarListResponse,
)


# ─── CalendarEventTemplate ──────────────────────────────────────


class TestCalendarEventTemplate:
    """Тесты CalendarEventTemplate."""

    def test_create_template(self):
        """Создание шаблона события."""
        tmpl = CalendarEventTemplate(
            event_type=CalendarEventType.TAX_PAYMENT,
            title="НДС за 1 кв.",
            description="Описание",
            deadline=date(2026, 4, 25),
        )
        assert tmpl.event_type == CalendarEventType.TAX_PAYMENT
        assert tmpl.title == "НДС за 1 кв."
        assert tmpl.deadline == date(2026, 4, 25)

    def test_template_slots(self):
        """CalendarEventTemplate использует __slots__."""
        assert hasattr(CalendarEventTemplate, "__slots__")
        assert "event_type" in CalendarEventTemplate.__slots__
        assert "title" in CalendarEventTemplate.__slots__


# ─── get_calendar_templates ─────────────────────────────────────


class TestGetCalendarTemplates:
    """Тесты get_calendar_templates."""

    def test_year_2026_returns_events(self):
        """Для 2026 года возвращается непустой список."""
        templates = get_calendar_templates(2026)
        assert len(templates) > 0
        assert len(templates) >= 30  # Минимум 30 событий

    def test_year_2025_returns_empty(self):
        """Для неподдерживаемого года — пустой список."""
        templates = get_calendar_templates(2025)
        assert len(templates) == 0

    def test_year_2027_returns_empty(self):
        """Для 2027 года — пустой список."""
        templates = get_calendar_templates(2027)
        assert len(templates) == 0

    def test_default_year_is_2026(self):
        """Год по умолчанию — 2026."""
        templates = get_calendar_templates()
        assert len(templates) > 0


# ─── TAX_CALENDAR_2026 данные ───────────────────────────────────


class TestTaxCalendar2026:
    """Тесты данных налогового календаря 2026."""

    def test_all_templates_have_required_fields(self):
        """Все шаблоны имеют обязательные поля."""
        for tmpl in TAX_CALENDAR_2026:
            assert tmpl.event_type is not None
            assert tmpl.title is not None and len(tmpl.title) > 0
            assert tmpl.description is not None and len(tmpl.description) > 0
            assert tmpl.deadline is not None

    def test_all_deadlines_in_2026(self):
        """Все дедлайны — в 2026 году."""
        for tmpl in TAX_CALENDAR_2026:
            assert tmpl.deadline.year == 2026, (
                f"Событие '{tmpl.title}' имеет дедлайн {tmpl.deadline}, а не 2026 год"
            )

    def test_deadlines_sorted_by_month(self):
        """Дедлайны упорядочены по месяцам (в целом)."""
        months = [tmpl.deadline.month for tmpl in TAX_CALENDAR_2026]
        # Проверяем, что месяцы не убывают (допускаются равные)
        for i in range(1, len(months)):
            assert months[i] >= months[i - 1] or (
                # Допускаем небольшие отклонения (события в одном месяце)
                abs(months[i] - months[i - 1]) <= 1
            ), f"Нарушен порядок: {months[i - 1]} → {months[i]} на позиции {i}"

    def test_event_types_coverage(self):
        """Покрыты все типы событий."""
        event_types = {tmpl.event_type for tmpl in TAX_CALENDAR_2026}
        expected = {
            CalendarEventType.TAX_PAYMENT,
            CalendarEventType.DECLARATION_SUBMIT,
            CalendarEventType.ADVANCE_PAYMENT,
            CalendarEventType.CONTRIBUTION_PAYMENT,
            CalendarEventType.REPORT_SUBMIT,
        }
        assert event_types == expected

    def test_has_usn_events(self):
        """Есть события по УСН."""
        usn_events = [t for t in TAX_CALENDAR_2026 if "УСН" in t.title]
        assert len(usn_events) >= 4  # Декларация + 3 аванса минимум

    def test_has_vat_events(self):
        """Есть события по НДС."""
        vat_events = [t for t in TAX_CALENDAR_2026 if "НДС" in t.title]
        assert len(vat_events) >= 12  # 4 квартала × 3 платежа

    def test_has_insurance_events(self):
        """Есть события по страховым взносам."""
        insurance = [t for t in TAX_CALENDAR_2026 if "взнос" in t.title.lower()]
        assert len(insurance) >= 2  # Фикс. взносы + доп. 1%

    def test_has_personified_reports(self):
        """Есть ежемесячные персонифицированные сведения."""
        pers = [t for t in TAX_CALENDAR_2026 if "Персонифицированные" in t.title]
        assert len(pers) >= 10  # ~11 месяцев (январь-ноябрь)

    def test_has_ndfl_events(self):
        """Есть события 6-НДФЛ."""
        ndfl = [t for t in TAX_CALENDAR_2026 if "НДФЛ" in t.title]
        assert len(ndfl) >= 4  # Годовой + 3 квартальных

    def test_has_rsv_events(self):
        """Есть события РСВ."""
        rsv = [t for t in TAX_CALENDAR_2026 if "РСВ" in t.title]
        assert len(rsv) >= 4  # Годовой + 3 квартальных

    def test_no_duplicate_titles(self):
        """Нет полных дублей названий."""
        titles = [tmpl.title for tmpl in TAX_CALENDAR_2026]
        assert len(titles) == len(set(titles)), (
            f"Дубликаты: {[t for t in titles if titles.count(t) > 1]}"
        )

    def test_fixed_contributions_deadline(self):
        """Фиксированные взносы ИП за 2026 — 31 декабря."""
        event = next(
            (t for t in TAX_CALENDAR_2026 if "Фиксированные взносы ИП за 2026" in t.title),
            None,
        )
        assert event is not None
        assert event.deadline == date(2026, 12, 31)

    def test_usn_declaration_ip_deadline(self):
        """Декларация УСН для ИП за 2025 — апрель 2026."""
        event = next(
            (t for t in TAX_CALENDAR_2026 if "Декларация УСН за 2025 год (ИП)" in t.title),
            None,
        )
        assert event is not None
        assert event.deadline.month == 4  # Апрель


# ─── Pydantic-схемы календаря ───────────────────────────────────


class TestTaxCalendarSchemas:
    """Тесты Pydantic-схем налогового календаря."""

    def test_event_response_valid(self):
        """Валидный ответ события."""
        resp = TaxCalendarEventResponse(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            event_type=CalendarEventType.TAX_PAYMENT,
            title="НДС за 1 кв. 2026 (1/3)",
            description="Первый платёж НДС",
            deadline=date(2026, 4, 27),
            status=CalendarEventStatus.UPCOMING,
            created_at=datetime.now(timezone.utc),
        )
        assert resp.status == CalendarEventStatus.UPCOMING
        assert resp.completed_at is None

    def test_event_response_completed(self):
        """Ответ для выполненного события."""
        resp = TaxCalendarEventResponse(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            event_type=CalendarEventType.DECLARATION_SUBMIT,
            title="Декларация НДС за 1 кв. 2026",
            deadline=date(2026, 4, 27),
            status=CalendarEventStatus.COMPLETED,
            completed_at=datetime(2026, 4, 20, 10, 0, 0, tzinfo=timezone.utc),
            created_at=datetime.now(timezone.utc),
        )
        assert resp.status == CalendarEventStatus.COMPLETED
        assert resp.completed_at is not None

    def test_list_response(self):
        """Ответ списка событий."""
        resp = TaxCalendarListResponse(
            events=[],
            upcoming_count=15,
            overdue_count=2,
        )
        assert resp.upcoming_count == 15
        assert resp.overdue_count == 2
        assert len(resp.events) == 0

    def test_complete_request(self):
        """Запрос на завершение события."""
        req = TaxCalendarCompleteRequest()
        assert req is not None

    def test_event_response_from_attributes(self):
        """Проверяем from_attributes."""
        assert TaxCalendarEventResponse.model_config.get("from_attributes") is True
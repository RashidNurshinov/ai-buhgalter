"""
Модель TaxCalendarEvent (событие налогового календаря).
Справочник: СПРАВОЧНИК_СУЩНОСТЕЙ.md → таблица tax_calendar_events

ВАЖНО: Модель должна соответствовать реальной структуре БД.
Текущая миграция: 002_agent_tables
"""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.constants.enums import CalendarEventStatus, CalendarEventType
from app.models.base import BaseModel, PgEnum


class TaxCalendarEvent(BaseModel):
    """Событие налогового календаря (дедлайн, напоминание)."""

    __tablename__ = "tax_calendar_events"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_type: Mapped[CalendarEventType] = mapped_column(
        PgEnum(CalendarEventType, name="calendar_event_type_enum"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    deadline: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    # Колонки amount, is_auto_generated, linked_declaration_id, linked_calculation_id
    # отсутствуют в БД до миграции 003+
    status: Mapped[CalendarEventStatus] = mapped_column(
        PgEnum(CalendarEventStatus, name="calendar_event_status_enum"),
        default=CalendarEventStatus.UPCOMING,
        nullable=False,
        index=True,
    )
    reminded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
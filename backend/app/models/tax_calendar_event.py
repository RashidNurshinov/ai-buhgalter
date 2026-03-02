"""
Модель TaxCalendarEvent (событие налогового календаря).
Справочник: СПРАВОЧНИК_СУЩНОСТЕЙ.md → таблица tax_calendar_events
"""

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.constants.enums import CalendarEventStatus, CalendarEventType
from app.models.base import BaseModel


class TaxCalendarEvent(BaseModel):
    """Событие налогового календаря (сроки сдачи, оплаты)."""

    __tablename__ = "tax_calendar_events"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_type: Mapped[CalendarEventType] = mapped_column(
        Enum(CalendarEventType, name="calendar_event_type_enum"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    deadline: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[CalendarEventStatus] = mapped_column(
        Enum(CalendarEventStatus, name="calendar_event_status_enum"),
        default=CalendarEventStatus.UPCOMING,
        nullable=False,
        index=True,
    )
    reminded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
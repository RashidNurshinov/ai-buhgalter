"""
Pydantic-схемы для налогового календаря.
Справочник: СПРАВОЧНИК_СУЩНОСТЕЙ.md → schemas/tax_calendar.py

Приведено в соответствие с моделью TaxCalendarEvent (models/tax_calendar_event.py).
"""

import uuid
from datetime import date, datetime

from pydantic import BaseModel

from app.constants.enums import CalendarEventStatus, CalendarEventType


class TaxCalendarEventResponse(BaseModel):
    """Ответ с событием налогового календаря."""

    id: uuid.UUID
    user_id: uuid.UUID
    event_type: CalendarEventType
    title: str
    description: str | None = None
    deadline: date
    status: CalendarEventStatus
    reminded_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class TaxCalendarListResponse(BaseModel):
    """Список событий календаря."""

    events: list[TaxCalendarEventResponse]
    upcoming_count: int
    overdue_count: int


class TaxCalendarCompleteRequest(BaseModel):
    """Отметка события как выполненного."""

    pass
"""
Сервис налогового календаря — TaxCalendarService.
Пункт плана: 1.14

Методы:
- populate_calendar() — заполнить календарь событиями из справочника
- get_events() — получить события с фильтрацией
- get_upcoming() — ближайшие события (N дней вперёд)
- get_overdue() — просроченные события
- complete_event() — отметить событие выполненным
- update_overdue_statuses() — обновить статусы просроченных
"""

import logging
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import String, and_, cast, func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.enums import CalendarEventStatus, CalendarEventType
from app.constants.tax_calendar import get_calendar_templates
from app.models.tax_calendar_event import TaxCalendarEvent

logger = logging.getLogger(__name__)


class TaxCalendarService:
    """
    Сервис для работы с налоговым календарём.

    Использование:
        service = TaxCalendarService(db)
        await service.populate_calendar(user_id, year=2026)
        events = await service.get_upcoming(user_id, days_ahead=30)
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    # ─── Заполнение календаря ─────────────────────────────

    async def populate_calendar(
        self,
        user_id: str,
        year: int = 2026,
        overwrite: bool = False,
    ) -> dict[str, Any]:
        """
        Заполнить календарь событиями из справочника на указанный год.

        Args:
            user_id: ID пользователя
            year: Год (по умолчанию 2026)
            overwrite: Перезаписать существующие события

        Returns:
            {"created": int, "skipped": int, "year": int}
        """
        templates = get_calendar_templates(year)
        if not templates:
            return {"created": 0, "skipped": 0, "year": year, "message": f"Нет шаблонов для {year} года"}

        # Проверяем существующие события за год
        existing_titles: set[str] = set()
        if not overwrite:
            result = await self.db.execute(
                select(TaxCalendarEvent.title).where(
                    and_(
                        TaxCalendarEvent.user_id == user_id,
                        TaxCalendarEvent.deadline >= date(year, 1, 1),
                        TaxCalendarEvent.deadline <= date(year, 12, 31),
                    )
                )
            )
            existing_titles = {row[0] for row in result.all()}

        created = 0
        skipped = 0

        for tmpl in templates:
            if tmpl.title in existing_titles:
                skipped += 1
                continue

            event = TaxCalendarEvent(
                user_id=user_id,
                event_type=tmpl.event_type,
                title=tmpl.title,
                description=tmpl.description,
                deadline=tmpl.deadline,
                status=CalendarEventStatus.UPCOMING,
            )
            self.db.add(event)
            created += 1

        await self.db.flush()

        logger.info(
            "Calendar populated for user %s, year %d: created=%d, skipped=%d",
            user_id, year, created, skipped,
        )

        return {"created": created, "skipped": skipped, "year": year}

    # ─── Получение событий ────────────────────────────────

    async def get_events(
        self,
        user_id: str,
        year: int | None = None,
        status: CalendarEventStatus | None = None,
        event_type: CalendarEventType | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[TaxCalendarEvent]:
        """Получить события с фильтрацией."""
        conditions = [TaxCalendarEvent.user_id == user_id]

        if year:
            conditions.append(TaxCalendarEvent.deadline >= date(year, 1, 1))
            conditions.append(TaxCalendarEvent.deadline <= date(year, 12, 31))
        if status:
            # Cast to String to avoid asyncpg enum name/value mismatch
            conditions.append(cast(TaxCalendarEvent.status, String) == status.value)
        if event_type:
            conditions.append(cast(TaxCalendarEvent.event_type, String) == event_type.value)
        if date_from:
            conditions.append(TaxCalendarEvent.deadline >= date_from)
        if date_to:
            conditions.append(TaxCalendarEvent.deadline <= date_to)

        result = await self.db.execute(
            select(TaxCalendarEvent)
            .where(and_(*conditions))
            .order_by(TaxCalendarEvent.deadline)
        )
        return list(result.scalars().all())

    async def get_upcoming(
        self,
        user_id: str,
        days_ahead: int = 30,
    ) -> list[TaxCalendarEvent]:
        """Получить ближайшие предстоящие события."""
        today = date.today()
        end_date = today + timedelta(days=days_ahead)

        status_str = cast(TaxCalendarEvent.status, String)

        result = await self.db.execute(
            select(TaxCalendarEvent)
            .where(
                and_(
                    TaxCalendarEvent.user_id == user_id,
                    status_str == "upcoming",
                    TaxCalendarEvent.deadline >= today,
                    TaxCalendarEvent.deadline <= end_date,
                )
            )
            .order_by(TaxCalendarEvent.deadline)
        )
        return list(result.scalars().all())

    async def get_overdue(
        self,
        user_id: str,
    ) -> list[TaxCalendarEvent]:
        """Получить просроченные события."""
        status_str = cast(TaxCalendarEvent.status, String)

        result = await self.db.execute(
            select(TaxCalendarEvent)
            .where(
                and_(
                    TaxCalendarEvent.user_id == user_id,
                    status_str == "overdue",
                )
            )
            .order_by(TaxCalendarEvent.deadline)
        )
        return list(result.scalars().all())

    async def get_counts(
        self,
        user_id: str,
    ) -> dict[str, int]:
        """Получить количество событий по статусам."""
        status_str = cast(TaxCalendarEvent.status, String)

        result = await self.db.execute(
            select(
                status_str.label("status_val"),
                func.count(TaxCalendarEvent.id),
            )
            .where(TaxCalendarEvent.user_id == user_id)
            .group_by(status_str)
        )
        counts = {row[0]: row[1] for row in result.all()}
        return {
            "upcoming": counts.get("upcoming", 0),
            "overdue": counts.get("overdue", 0),
            "completed": counts.get("completed", 0),
        }

    # ─── Отметка выполнения ───────────────────────────────

    async def complete_event(
        self,
        user_id: str,
        event_id: str,
    ) -> TaxCalendarEvent | None:
        """Отметить событие как выполненное."""
        result = await self.db.execute(
            select(TaxCalendarEvent).where(
                and_(
                    TaxCalendarEvent.id == event_id,
                    TaxCalendarEvent.user_id == user_id,
                )
            )
        )
        event = result.scalar_one_or_none()
        if not event:
            return None

        event.status = CalendarEventStatus.COMPLETED
        event.completed_at = datetime.now(timezone.utc)
        await self.db.flush()

        logger.info("Calendar event %s completed for user %s", event_id, user_id)
        return event

    # ─── Обновление статусов ──────────────────────────────

    async def update_overdue_statuses(
        self,
        user_id: str | None = None,
    ) -> int:
        """
        Обновить статусы просроченных событий.
        Uses raw SQL to avoid asyncpg enum name/value mismatch.

        Args:
            user_id: Если указан — только для одного пользователя.
                     Если None — для всех пользователей.

        Returns:
            Количество обновлённых событий.
        """
        today = date.today()

        # Use raw SQL to bypass asyncpg enum adapter sending NAME instead of VALUE
        if user_id:
            result = await self.db.execute(
                text(
                    "UPDATE tax_calendar_events "
                    "SET status = 'overdue', updated_at = now() "
                    "WHERE status = 'upcoming' "
                    "AND deadline < :today "
                    "AND user_id = :user_id"
                ),
                {"today": today, "user_id": user_id},
            )
        else:
            result = await self.db.execute(
                text(
                    "UPDATE tax_calendar_events "
                    "SET status = 'overdue', updated_at = now() "
                    "WHERE status = 'upcoming' "
                    "AND deadline < :today"
                ),
                {"today": today},
            )

        count = result.rowcount
        if count > 0:
            logger.info("Updated %d overdue calendar events", count)
        return count
"""
API эндпоинты налогового календаря.
Пункт плана: 1.14
Справочник: СПРАВОЧНИК_СУЩНОСТЕЙ.md → api/v1/calendar.py

ИСПРАВЛЕНО: добавлен commit после update_overdue_statuses в GET-эндпоинтах,
иначе обновление статуса просроченных событий терялось при закрытии сессии.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.enums import CalendarEventStatus, CalendarEventType
from app.core.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.tax_calendar import (
    TaxCalendarEventResponse,
    TaxCalendarListResponse,
)
from app.services.tax_calendar_service import TaxCalendarService

router = APIRouter(prefix="/calendar", tags=["Налоговый календарь"])


@router.get(
    "",
    response_model=TaxCalendarListResponse,
    summary="Список событий налогового календаря",
)
async def get_calendar_events(
    year: int | None = Query(None, ge=2024, le=2030, description="Фильтр по году"),
    event_status: CalendarEventStatus | None = Query(
        None, alias="status", description="Фильтр по статусу"
    ),
    event_type: CalendarEventType | None = Query(
        None, alias="type", description="Фильтр по типу события"
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Получить список событий налогового календаря с фильтрацией.

    Фильтры:
    - **year** — год (2024–2030)
    - **status** — статус: upcoming, overdue, completed
    - **type** — тип: tax_payment, declaration_submit, advance_payment, contribution_payment, report_submit
    """
    service = TaxCalendarService(db)

    # Обновляем просроченные при каждом запросе и коммитим
    await service.update_overdue_statuses(user_id=current_user.id)
    await db.commit()

    events = await service.get_events(
        user_id=current_user.id,
        year=year,
        status=event_status,
        event_type=event_type,
    )
    counts = await service.get_counts(user_id=current_user.id)

    return TaxCalendarListResponse(
        events=[TaxCalendarEventResponse.model_validate(e) for e in events],
        upcoming_count=counts["upcoming"],
        overdue_count=counts["overdue"],
    )


@router.get(
    "/upcoming",
    response_model=list[TaxCalendarEventResponse],
    summary="Ближайшие события",
)
async def get_upcoming_events(
    days: int = Query(30, ge=1, le=365, description="Сколько дней вперёд"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Получить ближайшие предстоящие события на N дней вперёд."""
    service = TaxCalendarService(db)
    await service.update_overdue_statuses(user_id=current_user.id)
    await db.commit()
    events = await service.get_upcoming(user_id=current_user.id, days_ahead=days)
    return [TaxCalendarEventResponse.model_validate(e) for e in events]


@router.get(
    "/overdue",
    response_model=list[TaxCalendarEventResponse],
    summary="Просроченные события",
)
async def get_overdue_events(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Получить список просроченных событий."""
    service = TaxCalendarService(db)
    await service.update_overdue_statuses(user_id=current_user.id)
    await db.commit()
    events = await service.get_overdue(user_id=current_user.id)
    return [TaxCalendarEventResponse.model_validate(e) for e in events]


@router.post(
    "/{event_id}/complete",
    response_model=TaxCalendarEventResponse,
    summary="Отметить событие выполненным",
)
async def complete_event(
    event_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Отметить событие налогового календаря как выполненное."""
    service = TaxCalendarService(db)
    event = await service.complete_event(
        user_id=current_user.id,
        event_id=event_id,
    )
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Событие {event_id} не найдено",
        )
    await db.commit()
    return TaxCalendarEventResponse.model_validate(event)


@router.post(
    "/populate",
    summary="Заполнить календарь событиями",
    status_code=status.HTTP_201_CREATED,
)
async def populate_calendar(
    year: int = Query(2026, ge=2024, le=2030, description="Год"),
    overwrite: bool = Query(False, description="Перезаписать существующие"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Заполнить налоговый календарь событиями из справочника на указанный год.
    По умолчанию пропускает уже существующие события.
    """
    service = TaxCalendarService(db)
    result = await service.populate_calendar(
        user_id=current_user.id,
        year=year,
        overwrite=overwrite,
    )
    await db.commit()
    return result
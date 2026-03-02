"""
API эндпоинты дашборда.
Пункт плана: 1.16
Справочник: СПРАВОЧНИК_СУЩНОСТЕЙ.md → api/v1/dashboard.py
"""

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.dashboard import DashboardResponse
from app.services.dashboard_service import DashboardService

router = APIRouter(prefix="/dashboard", tags=["Дашборд"])


@router.get(
    "",
    response_model=DashboardResponse,
    summary="Главный дашборд",
)
async def get_dashboard(
    period_start: date = Query(
        default=None,
        description="Начало периода (YYYY-MM-DD). По умолчанию — начало текущего года.",
    ),
    period_end: date = Query(
        default=None,
        description="Конец периода (YYYY-MM-DD). По умолчанию — сегодня.",
    ),
    include_monthly: bool = Query(
        default=False,
        description="Включить помесячную разбивку доходов/расходов.",
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Получить сводные данные дашборда за период.

    Включает:
    - Доходы, расходы, чистая прибыль
    - Оценка налогов (УСН, НДС)
    - Количество неподтверждённых операций и необработанных документов
    - Ближайшие и просроченные события налогового календаря
    - Помесячная разбивка (опционально)
    """
    today = date.today()

    if period_start is None:
        period_start = date(today.year, 1, 1)
    if period_end is None:
        period_end = today

    service = DashboardService(db)
    return await service.get_dashboard(
        user=current_user,
        period_start=period_start,
        period_end=period_end,
        include_monthly=include_monthly,
    )
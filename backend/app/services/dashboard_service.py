"""
Сервис дашборда — DashboardService.
Пункт плана: 1.16

Агрегирует данные для главной страницы:
- Доходы / расходы за период
- Оценка налогов (УСН, НДС)
- Количество неподтверждённых операций и необработанных документов
- Ближайшие и просроченные события календаря
- Помесячная разбивка (optional)
"""

import logging
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import String, and_, case, cast, extract, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.enums import (
    CalendarEventStatus,
    DocumentStatus,
    OperationStatus,
)
from app.models.bank_operation import BankOperation
from app.models.document import Document
from app.models.tax_calendar_event import TaxCalendarEvent
from app.models.user import User
from app.schemas.dashboard import DashboardResponse, MonthlyAmount
from app.schemas.tax_calendar import TaxCalendarEventResponse
from app.services.tax_calendar_service import TaxCalendarService

logger = logging.getLogger(__name__)

# Use lowercase string values and cast column to String to avoid asyncpg enum name/value bug
_CONFIRMED_STATUSES = ["confirmed", "classified", "reclassified"]
_UNCONFIRMED_STATUSES = ["pending", "classified"]
_UNPROCESSED_DOC_STATUSES = ["uploading", "processing", "recognized"]


class DashboardService:
    """Сервис для сборки данных дашборда."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_dashboard(
        self,
        user: User,
        period_start: date,
        period_end: date,
        include_monthly: bool = False,
    ) -> DashboardResponse:
        """
        Собрать полные данные дашборда за период.

        Args:
            user: Объект пользователя
            period_start: Начало периода
            period_end: Конец периода
            include_monthly: Включить помесячную разбивку
        """
        user_id = user.id

        # 1. Агрегация доходов и расходов из bank_operations
        income_expense = await self._get_income_expense_totals(
            user_id, period_start, period_end
        )

        income_total = income_expense["income_total"]
        expense_total = income_expense["expense_total"]
        net_profit = income_total - expense_total

        # 2. Оценка налогов
        tax_usn = await self._estimate_usn(user, income_total, expense_total)
        tax_vat = await self._estimate_vat(user_id, period_start, period_end)

        # 3. Количество неподтверждённых операций
        unconfirmed_ops = await self._count_unconfirmed_operations(user_id)

        # 4. Количество необработанных документов
        unprocessed_docs = await self._count_unprocessed_documents(user_id)

        # 5. Ближайшие и просроченные события
        calendar_service = TaxCalendarService(self.db)
        await calendar_service.update_overdue_statuses(user_id=user_id)

        upcoming_events = await calendar_service.get_upcoming(user_id, days_ahead=30)
        overdue_events = await calendar_service.get_overdue(user_id)

        # 6. Помесячная разбивка (опционально)
        monthly_income: list[MonthlyAmount] | None = None
        monthly_expense: list[MonthlyAmount] | None = None
        if include_monthly:
            monthly_income = await self._get_monthly_amounts(
                user_id, period_start, period_end, is_income=True
            )
            monthly_expense = await self._get_monthly_amounts(
                user_id, period_start, period_end, is_income=False
            )

        return DashboardResponse(
            period_start=period_start,
            period_end=period_end,
            income_total=income_total,
            expense_total=expense_total,
            net_profit=net_profit,
            tax_usn_estimated=tax_usn,
            tax_vat_estimated=tax_vat,
            unconfirmed_operations_count=unconfirmed_ops,
            unprocessed_documents_count=unprocessed_docs,
            upcoming_events=[
                TaxCalendarEventResponse.model_validate(e) for e in upcoming_events
            ],
            overdue_events=[
                TaxCalendarEventResponse.model_validate(e) for e in overdue_events
            ],
            monthly_income=monthly_income,
            monthly_expense=monthly_expense,
        )

    # ─── Приватные методы ─────────────────────────────────

    async def _get_income_expense_totals(
        self,
        user_id: str,
        period_start: date,
        period_end: date,
    ) -> dict[str, Decimal]:
        """Агрегация доходов и расходов из подтверждённых операций."""
        # Cast status to String to bypass asyncpg enum adapter (sends NAME instead of VALUE)
        status_as_str = cast(BankOperation.status, String)

        result = await self.db.execute(
            select(
                func.coalesce(
                    func.sum(
                        case(
                            (BankOperation.is_income == True, BankOperation.amount),  # noqa: E712
                            else_=Decimal("0"),
                        )
                    ),
                    Decimal("0"),
                ).label("income_total"),
                func.coalesce(
                    func.sum(
                        case(
                            (BankOperation.is_expense == True, BankOperation.amount),  # noqa: E712
                            else_=Decimal("0"),
                        )
                    ),
                    Decimal("0"),
                ).label("expense_total"),
            ).where(
                and_(
                    BankOperation.user_id == user_id,
                    BankOperation.operation_date >= period_start,
                    BankOperation.operation_date <= period_end,
                    status_as_str.in_(_CONFIRMED_STATUSES),
                )
            )
        )
        row = result.one()
        return {
            "income_total": row.income_total or Decimal("0"),
            "expense_total": row.expense_total or Decimal("0"),
        }

    async def _estimate_usn(
        self,
        user: User,
        income_total: Decimal,
        expense_total: Decimal,
    ) -> Decimal:
        """Оценка УСН «Доходы минус расходы» за период."""
        from app.constants.enums import TaxSystem

        if user.tax_system == TaxSystem.USN_INCOME:
            rate = user.usn_rate or Decimal("6.00")
            return (income_total * rate / Decimal("100")).quantize(Decimal("0.01"))

        if user.tax_system == TaxSystem.USN_INCOME_EXPENSE:
            rate = user.usn_rate or Decimal("15.00")
            tax_base = max(income_total - expense_total, Decimal("0"))
            usn = (tax_base * rate / Decimal("100")).quantize(Decimal("0.01"))
            # Минимальный налог: 1% от дохода
            min_tax = (income_total * Decimal("1") / Decimal("100")).quantize(Decimal("0.01"))
            return max(usn, min_tax)

        # Для ОСНО, патента и ЕСХН — 0 (не считаем УСН)
        return Decimal("0")

    async def _estimate_vat(
        self,
        user_id: str,
        period_start: date,
        period_end: date,
    ) -> Decimal:
        """Оценка НДС: сумма НДС по подтверждённым операциям за период."""
        status_as_str = cast(BankOperation.status, String)

        result = await self.db.execute(
            select(
                func.coalesce(
                    func.sum(
                        case(
                            (BankOperation.is_income == True, BankOperation.vat_amount),  # noqa: E712
                            else_=Decimal("0"),
                        )
                    ),
                    Decimal("0"),
                ).label("vat_charged"),
                func.coalesce(
                    func.sum(
                        case(
                            (BankOperation.is_expense == True, BankOperation.vat_amount),  # noqa: E712
                            else_=Decimal("0"),
                        )
                    ),
                    Decimal("0"),
                ).label("vat_deductible"),
            ).where(
                and_(
                    BankOperation.user_id == user_id,
                    BankOperation.operation_date >= period_start,
                    BankOperation.operation_date <= period_end,
                    BankOperation.vat_amount.isnot(None),
                    status_as_str.in_(_CONFIRMED_STATUSES),
                )
            )
        )
        row = result.one()
        vat_charged = row.vat_charged or Decimal("0")
        vat_deductible = row.vat_deductible or Decimal("0")
        return max(vat_charged - vat_deductible, Decimal("0"))

    async def _count_unconfirmed_operations(self, user_id: str) -> int:
        """Количество операций в статусе PENDING или CLASSIFIED (не подтверждены)."""
        status_as_str = cast(BankOperation.status, String)

        result = await self.db.execute(
            select(func.count(BankOperation.id)).where(
                and_(
                    BankOperation.user_id == user_id,
                    status_as_str.in_(_UNCONFIRMED_STATUSES),
                )
            )
        )
        return result.scalar_one()

    async def _count_unprocessed_documents(self, user_id: str) -> int:
        """Количество документов в статусе UPLOADING, PROCESSING или RECOGNIZED."""
        status_as_str = cast(Document.status, String)

        result = await self.db.execute(
            select(func.count(Document.id)).where(
                and_(
                    Document.user_id == user_id,
                    status_as_str.in_(_UNPROCESSED_DOC_STATUSES),
                )
            )
        )
        return result.scalar_one()

    async def _get_monthly_amounts(
        self,
        user_id: str,
        period_start: date,
        period_end: date,
        is_income: bool,
    ) -> list[MonthlyAmount]:
        """Помесячная разбивка доходов или расходов."""
        if is_income:
            condition = BankOperation.is_income == True  # noqa: E712
        else:
            condition = BankOperation.is_expense == True  # noqa: E712

        status_as_str = cast(BankOperation.status, String)

        result = await self.db.execute(
            select(
                extract("month", BankOperation.operation_date).label("month"),
                extract("year", BankOperation.operation_date).label("year"),
                func.coalesce(func.sum(BankOperation.amount), Decimal("0")).label("amount"),
            )
            .where(
                and_(
                    BankOperation.user_id == user_id,
                    BankOperation.operation_date >= period_start,
                    BankOperation.operation_date <= period_end,
                    condition,
                    status_as_str.in_(_CONFIRMED_STATUSES),
                )
            )
            .group_by(
                extract("year", BankOperation.operation_date),
                extract("month", BankOperation.operation_date),
            )
            .order_by(
                extract("year", BankOperation.operation_date),
                extract("month", BankOperation.operation_date),
            )
        )

        return [
            MonthlyAmount(month=int(row.month), year=int(row.year), amount=row.amount)
            for row in result.all()
        ]
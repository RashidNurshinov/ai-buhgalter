"""
Pydantic-схемы для дашборда.
Пункт плана: 1.16
"""

from datetime import date
from decimal import Decimal

from pydantic import BaseModel

from app.schemas.tax_calendar import TaxCalendarEventResponse


class MonthlyAmount(BaseModel):
    """Сумма за месяц."""

    month: int
    year: int
    amount: Decimal


class DashboardResponse(BaseModel):
    """Полный ответ дашборда."""

    # Период
    period_start: date
    period_end: date

    # Финансовые итоги
    income_total: Decimal
    expense_total: Decimal
    net_profit: Decimal

    # Оценка налогов
    tax_usn_estimated: Decimal
    tax_vat_estimated: Decimal

    # Счётчики задач
    unconfirmed_operations_count: int
    unprocessed_documents_count: int

    # Календарь
    upcoming_events: list[TaxCalendarEventResponse]
    overdue_events: list[TaxCalendarEventResponse]

    # Помесячная разбивка (опционально)
    monthly_income: list[MonthlyAmount] | None = None
    monthly_expense: list[MonthlyAmount] | None = None
"""
Pydantic-схемы для налоговых расчётов.
Справочник: СПРАВОЧНИК_СУЩНОСТЕЙ.md → schemas/tax.py
"""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field

from app.constants.enums import CalculationStatus, PeriodType, TaxType


# ─── Запросы ──────────────────────────────────────────────


class TaxCalculationRequest(BaseModel):
    """Запрос расчёта налога за период."""
    tax_type: TaxType | None = Field(None, description="Тип налога. Если не указан — считает все.")
    year: int = Field(..., ge=2020, le=2030, description="Год")
    quarter: int | None = Field(None, ge=1, le=4, description="Квартал (1-4). Если не указан — за год.")


class NdflCalculationRequest(BaseModel):
    """Запрос расчёта НДФЛ за сотрудника."""
    gross_salary: Decimal = Field(..., gt=0, description="Зарплата за месяц (брутто), руб.")
    cumulative_income: Decimal = Field(
        default=Decimal("0"), ge=0,
        description="Накопленный доход с начала года (до текущего месяца)",
    )


class InsuranceCalculationRequest(BaseModel):
    """Запрос расчёта страховых взносов за сотрудника."""
    gross_salary: Decimal = Field(..., gt=0, description="Зарплата за месяц (брутто), руб.")
    cumulative_base: Decimal = Field(
        default=Decimal("0"), ge=0,
        description="Накопленная база с начала года",
    )


# ─── Ответы ──────────────────────────────────────────────


class TaxCalculationResponse(BaseModel):
    """Ответ с результатом расчёта налога (из БД)."""
    id: uuid.UUID
    user_id: uuid.UUID
    tax_type: TaxType
    period_type: PeriodType
    period_start: date
    period_end: date
    income_total: Decimal
    expense_total: Decimal
    tax_base: Decimal
    tax_rate: Decimal
    tax_amount: Decimal
    vat_charged: Decimal | None = None
    vat_deductible: Decimal | None = None
    vat_payable: Decimal | None = None
    insurance_deduction: Decimal | None = None
    min_tax_amount: Decimal | None = None
    status: CalculationStatus
    details_json: dict[str, Any] | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class UsnResultResponse(BaseModel):
    """Результат расчёта УСН."""
    income_total: Decimal = Field(description="Итого доходы")
    expense_total: Decimal = Field(description="Итого расходы")
    tax_base: Decimal = Field(description="Налоговая база (доходы - расходы)")
    tax_rate: Decimal = Field(description="Применённая ставка (%)")
    tax_amount: Decimal = Field(description="Сумма налога (нарастающий итог)")
    min_tax_amount: Decimal = Field(default=Decimal("0"), description="Минимальный налог (1% от доходов)")
    is_minimum_tax: bool = Field(default=False, description="Применён ли минимальный налог")
    insurance_deduction: Decimal = Field(default=Decimal("0"), description="Вычет страховых взносов")
    previous_advances: Decimal = Field(default=Decimal("0"), description="Ранее уплаченные авансы")
    tax_to_pay: Decimal = Field(description="К доплате (с учётом авансов)")
    warnings: list[str] = Field(default_factory=list)
    details: dict[str, Any] = Field(default_factory=dict)


class VatResultResponse(BaseModel):
    """Результат расчёта НДС."""
    quarter: int
    year: int
    vat_charged: Decimal = Field(description="НДС начисленный (продажи)")
    vat_deductible: Decimal = Field(description="НДС к вычету (покупки)")
    vat_payable: Decimal = Field(description="НДС к уплате / к возмещению")
    monthly_payments: list[Decimal] = Field(description="3 ежемесячных платежа по 1/3")
    warnings: list[str] = Field(default_factory=list)
    details: dict[str, Any] = Field(default_factory=dict)


class NdflResultResponse(BaseModel):
    """Результат расчёта НДФЛ."""
    gross_salary: Decimal
    ndfl_amount: Decimal
    net_salary: Decimal
    rate_applied: Decimal
    details: dict[str, Any] = Field(default_factory=dict)


class InsuranceResultResponse(BaseModel):
    """Результат расчёта страховых взносов за сотрудника."""
    gross_salary: Decimal
    contributions_total: Decimal
    rate_applied: Decimal
    cumulative_base: Decimal
    details: dict[str, Any] = Field(default_factory=dict)


class IpContributionsResultResponse(BaseModel):
    """Результат расчёта фиксированных взносов ИП."""
    fixed_amount: Decimal = Field(description="Фиксированная часть")
    additional_amount: Decimal = Field(description="1% с превышения 300 000 ₽")
    total_amount: Decimal = Field(description="Итого взносов")
    income_for_calculation: Decimal = Field(description="Доход для расчёта 1%")
    already_paid: Decimal = Field(description="Уже уплачено")
    remaining: Decimal = Field(description="Осталось к уплате")
    warnings: list[str] = Field(default_factory=list)
    details: dict[str, Any] = Field(default_factory=dict)


class TaxSummaryResponse(BaseModel):
    """Сводка по всем налогам за период."""
    period_start: date
    period_end: date
    usn: UsnResultResponse | None = None
    vat: VatResultResponse | None = None
    ip_contributions: IpContributionsResultResponse | None = None
    total_payable: Decimal = Field(description="Итого к уплате")
    warnings: list[str] = Field(default_factory=list)


class VatSummaryResponse(BaseModel):
    """Сводка НДС за квартал (совместимость)."""
    quarter: int
    year: int
    vat_charged: Decimal = Field(description="НДС начисленный (продажи)")
    vat_deductible: Decimal = Field(description="НДС к вычету (покупки)")
    vat_payable: Decimal = Field(description="НДС к уплате")
    monthly_payments: list[Decimal] = Field(description="3 ежемесячных платежа по 1/3")
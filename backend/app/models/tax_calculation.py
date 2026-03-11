"""
Модель TaxCalculation (расчёт налогов).
Справочник: СПРАВОЧНИК_СУЩНОСТЕЙ.md → таблица tax_calculations

ВАЖНО: Модель должна соответствовать реальной структуре БД.
Текущая миграция: 002_agent_tables

БД колонки: id, user_id, tax_type, period_type, period_start, period_end,
income_total, expense_total, tax_base, tax_rate, tax_amount, vat_charged,
vat_deductible, vat_payable, insurance_deduction, min_tax_amount, status,
details_json, created_at, updated_at
"""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Numeric, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.constants.enums import CalculationStatus, PeriodType, TaxType
from app.models.base import BaseModel, PgEnum


class TaxCalculation(BaseModel):
    """Расчёт налога за период."""

    __tablename__ = "tax_calculations"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tax_type: Mapped[TaxType] = mapped_column(
        PgEnum(TaxType, name="tax_type_enum"),
        nullable=False,
        index=True,
    )
    period_type: Mapped[PeriodType] = mapped_column(
        PgEnum(PeriodType, name="period_type_enum"),
        nullable=False,
    )
    # period_key — отсутствует в БД, используем period_start/period_end
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    income_total: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), default=Decimal("0"), nullable=False
    )
    expense_total: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), default=Decimal("0"), nullable=False
    )
    tax_base: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), default=Decimal("0"), nullable=False
    )
    tax_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), default=Decimal("15.00"), nullable=False
    )
    tax_amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), default=Decimal("0"), nullable=False
    )
    vat_charged: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), default=Decimal("0"), nullable=False
    )
    vat_deductible: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), default=Decimal("0"), nullable=False
    )
    vat_payable: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), default=Decimal("0"), nullable=False
    )
    insurance_deduction: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), default=Decimal("0"), nullable=False
    )
    min_tax_amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), default=Decimal("0"), nullable=False
    )
    details_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[CalculationStatus] = mapped_column(
        PgEnum(CalculationStatus, name="calculation_status_enum"),
        default=CalculationStatus.PRELIMINARY,
        nullable=False,
    )
    # notes — отсутствует в БД
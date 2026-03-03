"""
Модель TaxCalculation (расчёт налога).
Справочник: СПРАВОЧНИК_СУЩНОСТЕЙ.md → таблица tax_calculations
"""

from datetime import date
from decimal import Decimal

from sqlalchemy import Date, Enum, ForeignKey, Numeric
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.constants.enums import CalculationStatus, PeriodType, TaxType
from app.models.base import BaseModel


class TaxCalculation(BaseModel):
    """Расчёт налога за период."""

    __tablename__ = "tax_calculations"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tax_type: Mapped[TaxType] = mapped_column(
        Enum(TaxType, name="tax_type_enum", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        index=True,
    )
    period_type: Mapped[PeriodType] = mapped_column(
        Enum(PeriodType, name="period_type_enum", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    income_total: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), default=Decimal("0.00"), nullable=False
    )
    expense_total: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), default=Decimal("0.00"), nullable=False
    )
    tax_base: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), default=Decimal("0.00"), nullable=False
    )
    tax_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False
    )
    tax_amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), default=Decimal("0.00"), nullable=False
    )
    # Специфичные для НДС
    vat_charged: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), default=Decimal("0.00"), nullable=False
    )
    vat_deductible: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), default=Decimal("0.00"), nullable=False
    )
    vat_payable: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), default=Decimal("0.00"), nullable=False
    )
    # Специфичные для УСН
    insurance_deduction: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), default=Decimal("0.00"), nullable=False
    )
    min_tax_amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), default=Decimal("0.00"), nullable=False
    )
    status: Mapped[CalculationStatus] = mapped_column(
        Enum(CalculationStatus, name="calculation_status_enum", values_callable=lambda x: [e.value for e in x]),
        default=CalculationStatus.PRELIMINARY,
        nullable=False,
    )
    details_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
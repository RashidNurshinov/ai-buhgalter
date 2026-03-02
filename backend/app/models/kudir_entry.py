"""
Модель KudirEntry (запись КУДиР).
Справочник: СПРАВОЧНИК_СУЩНОСТЕЙ.md → таблица kudir_entries
"""

from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class KudirEntry(BaseModel):
    """Запись Книги учёта доходов и расходов (КУДиР)."""

    __tablename__ = "kudir_entries"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    entry_number: Mapped[int] = mapped_column(Integer, nullable=False)
    entry_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    document_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    income_amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), default=Decimal("0.00"), nullable=False
    )
    expense_amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), default=Decimal("0.00"), nullable=False
    )
    quarter: Mapped[int] = mapped_column(Integer, nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    linked_operation_id: Mapped[str | None] = mapped_column(
        ForeignKey("bank_operations.id", ondelete="SET NULL"),
        nullable=True,
    )
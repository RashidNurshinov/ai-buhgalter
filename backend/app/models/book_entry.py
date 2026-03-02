"""
Модели PurchaseBookEntry и SalesBookEntry (книга покупок / книга продаж).
Справочник: СПРАВОЧНИК_СУЩНОСТЕЙ.md → таблицы purchase_book_entries, sales_book_entries
"""

from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class PurchaseBookEntry(BaseModel):
    """Запись книги покупок."""

    __tablename__ = "purchase_book_entries"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    entry_number: Mapped[int] = mapped_column(Integer, nullable=False)
    entry_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    counterparty_id: Mapped[str | None] = mapped_column(
        ForeignKey("counterparties.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    counterparty_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    counterparty_inn: Mapped[str | None] = mapped_column(String(12), nullable=True)
    counterparty_kpp: Mapped[str | None] = mapped_column(String(9), nullable=True)
    invoice_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    invoice_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    total_without_vat: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), default=Decimal("0.00"), nullable=False
    )
    vat_amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), default=Decimal("0.00"), nullable=False
    )
    total_with_vat: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), default=Decimal("0.00"), nullable=False
    )
    vat_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), default=Decimal("22.00"), nullable=False
    )
    quarter: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    linked_document_id: Mapped[str | None] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    counterparty: Mapped["Counterparty | None"] = relationship(  # noqa: F821
        "Counterparty", back_populates="purchase_book_entries"
    )


class SalesBookEntry(BaseModel):
    """Запись книги продаж."""

    __tablename__ = "sales_book_entries"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    entry_number: Mapped[int] = mapped_column(Integer, nullable=False)
    entry_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    buyer_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    buyer_inn: Mapped[str | None] = mapped_column(String(12), nullable=True)
    buyer_kpp: Mapped[str | None] = mapped_column(String(9), nullable=True)
    invoice_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    invoice_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    total_without_vat: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), default=Decimal("0.00"), nullable=False
    )
    vat_amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), default=Decimal("0.00"), nullable=False
    )
    total_with_vat: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), default=Decimal("0.00"), nullable=False
    )
    vat_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), default=Decimal("22.00"), nullable=False
    )
    quarter: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    linked_document_id: Mapped[str | None] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
    )
    linked_receipt_id: Mapped[str | None] = mapped_column(
        ForeignKey("cash_receipts.id", ondelete="SET NULL"),
        nullable=True,
    )
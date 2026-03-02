"""
Модель CashReceipt (кассовый чек).
Справочник: СПРАВОЧНИК_СУЩНОСТЕЙ.md → таблица cash_receipts
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Enum, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.constants.enums import PaymentType
from app.models.base import BaseModel


class CashReceipt(BaseModel):
    """Кассовый чек (из ОФД)."""

    __tablename__ = "cash_receipts"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    receipt_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    receipt_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    fiscal_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    total: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    vat_amount: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    payment_type: Mapped[PaymentType] = mapped_column(
        Enum(PaymentType, name="payment_type_enum"),
        default=PaymentType.CASH,
        nullable=False,
    )
    ofd_source: Mapped[str | None] = mapped_column(String(100), nullable=True)
    items_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Relationships
    linked_operation: Mapped["BankOperation | None"] = relationship(  # noqa: F821
        "BankOperation",
        back_populates="linked_receipt",
        uselist=False,
        foreign_keys="[BankOperation.linked_receipt_id]",
    )
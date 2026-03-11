"""
Модель BankOperation (банковская операция).
Справочник: СПРАВОЧНИК_СУЩНОСТЕЙ.md -> таблица bank_operations
"""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Boolean, Date, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.constants.enums import OperationCategory, OperationStatus
from app.models.base import BaseModel, PgEnum


class BankOperation(BaseModel):
    """Банковская операция (из выписки)."""

    __tablename__ = "bank_operations"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    bank_account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("bank_accounts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    operation_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    is_income: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_expense: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    counterparty_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("counterparties.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    counterparty_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    counterparty_inn: Mapped[str | None] = mapped_column(String(12), nullable=True)
    purpose: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[OperationCategory] = mapped_column(
        PgEnum(OperationCategory, name="operation_category_enum"),
        default=OperationCategory.UNCLASSIFIED,
        nullable=False,
        index=True,
    )
    status: Mapped[OperationStatus] = mapped_column(
        PgEnum(OperationStatus, name="operation_status_enum"),
        default=OperationStatus.PENDING,
        nullable=False,
        index=True,
    )
    vat_amount: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    classification_confidence: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 4), nullable=True
    )

    # FK -> documents, cash_receipts
    linked_document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    linked_receipt_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cash_receipts.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    bank_account: Mapped["BankAccount | None"] = relationship(  # noqa: F821
        "BankAccount", back_populates="operations"
    )
    counterparty: Mapped["Counterparty | None"] = relationship(  # noqa: F821
        "Counterparty", back_populates="bank_operations"
    )
    linked_document: Mapped["Document | None"] = relationship(  # noqa: F821
        "Document", back_populates="linked_operations"
    )
    linked_receipt: Mapped["CashReceipt | None"] = relationship(  # noqa: F821
        "CashReceipt", back_populates="linked_operation",
        foreign_keys=[linked_receipt_id],
    )

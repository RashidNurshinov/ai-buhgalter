"""
Модель Counterparty (контрагент).
Справочник: СПРАВОЧНИК_СУЩНОСТЕЙ.md → таблица counterparties
"""

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class Counterparty(BaseModel):
    """Контрагент (поставщик, покупатель)."""

    __tablename__ = "counterparties"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    inn: Mapped[str | None] = mapped_column(String(12), nullable=True, index=True)
    kpp: Mapped[str | None] = mapped_column(String(9), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    egrul_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Relationships
    documents: Mapped[list["Document"]] = relationship(  # noqa: F821
        "Document", back_populates="counterparty", lazy="selectin"
    )
    bank_operations: Mapped[list["BankOperation"]] = relationship(  # noqa: F821
        "BankOperation", back_populates="counterparty", lazy="selectin"
    )
    purchase_book_entries: Mapped[list["PurchaseBookEntry"]] = relationship(  # noqa: F821
        "PurchaseBookEntry", back_populates="counterparty", lazy="selectin"
    )
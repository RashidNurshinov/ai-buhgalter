"""
Модель BankAccount (банковский счёт).
Справочник: СПРАВОЧНИК_СУЩНОСТЕЙ.md -> таблица bank_accounts
"""

import uuid

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class BankAccount(BaseModel):
    """Банковский счёт пользователя."""

    __tablename__ = "bank_accounts"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    bank_name: Mapped[str] = mapped_column(String(255), nullable=False)
    account_number: Mapped[str] = mapped_column(String(20), nullable=False)
    bik: Mapped[str] = mapped_column(String(9), nullable=False)
    corr_account: Mapped[str | None] = mapped_column(String(20), nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    operations: Mapped[list["BankOperation"]] = relationship(  # noqa: F821
        "BankOperation", back_populates="bank_account", lazy="selectin"
    )

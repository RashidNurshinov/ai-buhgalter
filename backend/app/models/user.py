"""
Модель User (пользователь / ИП / организация).
Справочник: СПРАВОЧНИК_СУЩНОСТЕЙ.md → таблица users
"""

from decimal import Decimal

from sqlalchemy import Boolean, Enum, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.constants.enums import TaxSystem
from app.models.base import BaseModel


class User(BaseModel):
    """Пользователь (владелец бизнеса / бухгалтер)."""

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    inn: Mapped[str | None] = mapped_column(String(12), nullable=True)
    business_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    tax_system: Mapped[TaxSystem] = mapped_column(
        Enum(TaxSystem, name="tax_system_enum", values_callable=lambda x: [e.value for e in x]),
        default=TaxSystem.USN_INCOME_EXPENSE,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Настройки (ранее user_settings — объединены в users для простоты)
    tax_region: Mapped[str] = mapped_column(
        String(10), default="56", nullable=False  # 56 = Оренбургская обл.
    )
    usn_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), default=Decimal("15.00"), nullable=False
    )
    vat_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), default=Decimal("22.00"), nullable=False
    )
    has_employees: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    employee_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
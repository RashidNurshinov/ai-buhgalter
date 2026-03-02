"""
Pydantic-схемы для пользователя.
Справочник: СПРАВОЧНИК_СУЩНОСТЕЙ.md → schemas/user.py

Настройки объединены в таблицу users (без отдельной user_settings).
"""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, EmailStr, Field

from app.constants.enums import TaxSystem


class UserResponse(BaseModel):
    """Ответ с данными пользователя (включая настройки)."""

    id: uuid.UUID
    email: EmailStr
    full_name: str
    inn: str | None = None
    business_name: str | None = None
    tax_system: TaxSystem
    is_active: bool
    # Настройки
    tax_region: str
    usn_rate: Decimal
    vat_rate: Decimal
    has_employees: bool
    employee_count: int
    # Временные метки
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    """Обновление профиля и настроек пользователя."""

    full_name: str | None = Field(None, min_length=2, max_length=255)
    inn: str | None = Field(None, min_length=10, max_length=12)
    business_name: str | None = Field(None, max_length=500)
    tax_system: TaxSystem | None = None
    # Настройки
    tax_region: str | None = Field(None, max_length=10)
    usn_rate: Decimal | None = Field(None, ge=0, le=100)
    vat_rate: Decimal | None = Field(None, ge=0, le=100)
    has_employees: bool | None = None
    employee_count: int | None = Field(None, ge=0)


class UserBriefResponse(BaseModel):
    """Краткая информация о пользователе (для списков, вложений)."""

    id: uuid.UUID
    email: EmailStr
    full_name: str
    tax_system: TaxSystem

    model_config = {"from_attributes": True}
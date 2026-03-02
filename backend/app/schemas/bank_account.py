"""
Pydantic-схемы для банковских счетов.
Справочник: СПРАВОЧНИК_СУЩНОСТЕЙ.md → schemas/bank_account.py (не указан, но логично)
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class BankAccountCreate(BaseModel):
    """Создание банковского счёта."""
    bank_name: str = Field(..., min_length=1, max_length=255)
    account_number: str = Field(..., min_length=20, max_length=20)
    bik: str = Field(..., min_length=9, max_length=9)
    correspondent_account: str | None = Field(None, min_length=20, max_length=20)
    is_primary: bool = False


class BankAccountUpdate(BaseModel):
    """Обновление банковского счёта."""
    bank_name: str | None = Field(None, min_length=1, max_length=255)
    is_primary: bool | None = None
    api_connected: bool | None = None
    api_provider: str | None = Field(None, max_length=50)


class BankAccountResponse(BaseModel):
    """Ответ с данными банковского счёта."""
    id: uuid.UUID
    user_id: uuid.UUID
    bank_name: str
    account_number: str
    bik: str
    correspondent_account: str | None = None
    is_primary: bool
    api_connected: bool
    api_provider: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
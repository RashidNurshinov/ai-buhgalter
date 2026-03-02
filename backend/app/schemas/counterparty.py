"""
Pydantic-схемы для контрагентов.
Справочник: СПРАВОЧНИК_СУЩНОСТЕЙ.md → schemas/counterparty.py
"""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CounterpartyCreate(BaseModel):
    """Создание контрагента."""
    name: str = Field(..., min_length=1, max_length=500)
    inn: str | None = Field(None, min_length=10, max_length=12)
    kpp: str | None = Field(None, min_length=9, max_length=9)
    address: str | None = None


class CounterpartyUpdate(BaseModel):
    """Обновление контрагента."""
    name: str | None = Field(None, min_length=1, max_length=500)
    inn: str | None = Field(None, min_length=10, max_length=12)
    kpp: str | None = Field(None, min_length=9, max_length=9)
    address: str | None = None


class CounterpartyResponse(BaseModel):
    """Ответ с данными контрагента."""
    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    inn: str | None = None
    kpp: str | None = None
    address: str | None = None
    is_verified: bool
    egrul_data: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
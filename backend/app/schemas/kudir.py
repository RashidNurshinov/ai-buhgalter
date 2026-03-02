"""
Pydantic-схемы для КУДиР.
Справочник: СПРАВОЧНИК_СУЩНОСТЕЙ.md → schemas/kudir.py
"""

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class KudirEntryResponse(BaseModel):
    """Ответ с записью КУДиР."""
    id: uuid.UUID
    user_id: uuid.UUID
    entry_number: int
    entry_date: date
    document_ref: str | None = None
    description: str | None = None
    income_amount: Decimal
    expense_amount: Decimal
    quarter: int
    year: int
    linked_operation_id: uuid.UUID | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class KudirPeriodRequest(BaseModel):
    """Запрос КУДиР за период."""
    year: int = Field(..., ge=2020, le=2030)
    quarter: int | None = Field(None, ge=1, le=4)


class KudirPeriodResponse(BaseModel):
    """Сводка КУДиР за период."""
    entries: list[KudirEntryResponse]
    total_income: Decimal
    total_expense: Decimal
    net_result: Decimal
    quarter: int | None = None
    year: int


class KudirGenerateRequest(BaseModel):
    """Запрос на генерацию КУДиР из банковских операций."""
    year: int = Field(..., ge=2020, le=2030)
    quarter: int | None = Field(None, ge=1, le=4)
    overwrite: bool = Field(
        default=False,
        description="Перезаписать существующие записи за указанный период",
    )
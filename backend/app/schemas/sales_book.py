"""
Pydantic-схемы для книги продаж.
Справочник: СПРАВОЧНИК_СУЩНОСТЕЙ.md → schemas/sales_book.py

ВАЖНО: Схема должна соответствовать модели SalesBookEntry (без buyer_kpp, linked_receipt_id).
"""

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class SalesBookEntryResponse(BaseModel):
    """Ответ с записью книги продаж."""
    id: uuid.UUID
    user_id: uuid.UUID
    entry_number: int
    entry_date: date
    buyer_name: str | None = None
    buyer_inn: str | None = None
    # buyer_kpp — отсутствует в модели
    # linked_receipt_id — отсутствует в модели
    invoice_number: str | None = None
    invoice_date: date | None = None
    total_without_vat: Decimal
    vat_amount: Decimal
    total_with_vat: Decimal
    vat_rate: Decimal
    quarter: int
    year: int
    linked_document_id: uuid.UUID | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class SalesBookPeriodRequest(BaseModel):
    """Запрос книги продаж за период."""
    year: int = Field(..., ge=2020, le=2030)
    quarter: int = Field(..., ge=1, le=4)


class SalesBookPeriodResponse(BaseModel):
    """Сводка книги продаж за период."""
    entries: list[SalesBookEntryResponse]
    total_without_vat: Decimal
    total_vat: Decimal
    total_with_vat: Decimal
    quarter: int
    year: int


class SalesBookGenerateRequest(BaseModel):
    """Запрос на генерацию книги продаж из документов/чеков."""
    year: int = Field(..., ge=2020, le=2030)
    quarter: int = Field(..., ge=1, le=4)
    overwrite: bool = Field(
        default=False,
        description="Перезаписать существующие записи за указанный период",
    )
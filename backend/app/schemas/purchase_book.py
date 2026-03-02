"""
Pydantic-схемы для книги покупок.
Справочник: СПРАВОЧНИК_СУЩНОСТЕЙ.md → schemas/purchase_book.py
"""

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class PurchaseBookEntryResponse(BaseModel):
    """Ответ с записью книги покупок."""
    id: uuid.UUID
    user_id: uuid.UUID
    entry_number: int
    entry_date: date
    counterparty_id: uuid.UUID | None = None
    counterparty_name: str | None = None
    counterparty_inn: str | None = None
    counterparty_kpp: str | None = None
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


class PurchaseBookPeriodRequest(BaseModel):
    """Запрос книги покупок за период."""
    year: int = Field(..., ge=2020, le=2030)
    quarter: int = Field(..., ge=1, le=4)


class PurchaseBookPeriodResponse(BaseModel):
    """Сводка книги покупок за период."""
    entries: list[PurchaseBookEntryResponse]
    total_without_vat: Decimal
    total_vat: Decimal
    total_with_vat: Decimal
    quarter: int
    year: int


class PurchaseBookGenerateRequest(BaseModel):
    """Запрос на генерацию книги покупок из документов."""
    year: int = Field(..., ge=2020, le=2030)
    quarter: int = Field(..., ge=1, le=4)
    overwrite: bool = Field(
        default=False,
        description="Перезаписать существующие записи за указанный период",
    )
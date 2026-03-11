"""
Pydantic-схемы для книги покупок.
Справочник: СПРАВОЧНИК_СУЩНОСТЕЙ.md → schemas/purchase_book.py

ВАЖНО: Схема должна соответствовать модели PurchaseBookEntry (без counterparty_name/inn/kpp).
Данные контрагента берутся через relationship.counterparty.
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
    # Данные контрагента берутся из relationship
    counterparty_name: str | None = Field(None, alias="counterparty.name")
    counterparty_inn: str | None = Field(None, alias="counterparty.inn")
    counterparty_kpp: str | None = Field(None, alias="counterparty.kpp")
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
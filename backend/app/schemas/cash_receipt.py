"""
Pydantic-схемы для кассовых чеков.
Справочник: СПРАВОЧНИК_СУЩНОСТЕЙ.md → schemas/cash_receipt.py
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel

from app.constants.enums import PaymentType


class CashReceiptResponse(BaseModel):
    """Ответ с данными кассового чека."""
    id: uuid.UUID
    user_id: uuid.UUID
    receipt_date: datetime
    receipt_number: str | None = None
    fiscal_number: str | None = None
    total: Decimal
    vat_amount: Decimal | None = None
    payment_type: PaymentType | None = None
    ofd_source: str | None = None
    items_json: list[dict[str, Any]] | None = None
    linked_operation_id: uuid.UUID | None = None
    is_return: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
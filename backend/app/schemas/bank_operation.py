"""
Pydantic-схемы для банковских операций.
Справочник: СПРАВОЧНИК_СУЩНОСТЕЙ.md → schemas/bank_operation.py
"""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.constants.enums import OperationCategory, OperationStatus


class BankOperationResponse(BaseModel):
    """Ответ с данными банковской операции."""
    id: str
    user_id: str
    bank_account_id: str | None = None
    operation_date: date
    amount: Decimal
    counterparty_id: str | None = None
    counterparty_name: str | None = None
    counterparty_inn: str | None = None
    purpose: str | None = None
    category: OperationCategory | None = None
    is_income: bool
    is_expense: bool
    vat_amount: Decimal | None = None
    linked_document_id: str | None = None
    linked_receipt_id: str | None = None
    classification_confidence: Decimal | None = None
    status: OperationStatus
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class OperationConfirmRequest(BaseModel):
    """Подтверждение классификации операции."""
    pass


class OperationReclassifyRequest(BaseModel):
    """Ручная переклассификация операции."""
    category: OperationCategory
    is_income: bool | None = None
    is_expense: bool | None = None
    vat_amount: Decimal | None = Field(None, ge=0)
    linked_document_id: str | None = None


class BankOperationFilter(BaseModel):
    """Фильтры для списка операций."""
    date_from: date | None = None
    date_to: date | None = None
    category: OperationCategory | None = None
    status: OperationStatus | None = None
    is_income: bool | None = None
    is_expense: bool | None = None
    bank_account_id: str | None = None
    counterparty_inn: str | None = None
    min_amount: Decimal | None = None
    max_amount: Decimal | None = None
    search: str | None = Field(None, description="Поиск по назначению платежа")
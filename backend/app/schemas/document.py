"""
Pydantic-схемы для документов и позиций документов.
Справочник: СПРАВОЧНИК_СУЩНОСТЕЙ.md → schemas/document.py
"""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field

from app.constants.enums import DocumentSource, DocumentStatus, DocumentType


class DocumentItemCreate(BaseModel):
    """Создание позиции документа."""
    name: str = Field(..., min_length=1, max_length=500)
    quantity: Decimal | None = Field(None, ge=0)
    unit: str | None = Field(None, max_length=20)
    price_without_vat: Decimal | None = Field(None, ge=0)
    vat_rate: Decimal | None = Field(None, ge=0, le=100)
    vat_amount: Decimal | None = Field(None, ge=0)
    total_with_vat: Decimal | None = Field(None, ge=0)


class DocumentItemResponse(BaseModel):
    """Ответ с позицией документа."""
    id: uuid.UUID
    document_id: uuid.UUID
    name: str
    quantity: Decimal | None = None
    unit: str | None = None
    price_without_vat: Decimal | None = None
    vat_rate: Decimal | None = None
    vat_amount: Decimal | None = None
    total_with_vat: Decimal | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class DocumentCreate(BaseModel):
    """Создание документа вручную."""
    doc_type: DocumentType
    doc_number: str | None = Field(None, max_length=100)
    doc_date: date | None = None
    counterparty_id: uuid.UUID | None = None
    total_without_vat: Decimal | None = Field(None, ge=0)
    vat_amount: Decimal | None = Field(None, ge=0)
    total_with_vat: Decimal | None = Field(None, ge=0)
    vat_rate: Decimal | None = Field(None, ge=0, le=100)
    source: DocumentSource = DocumentSource.MANUAL_UPLOAD
    items: list[DocumentItemCreate] | None = None


class DocumentUpdate(BaseModel):
    """Обновление документа (ручная корректировка после OCR)."""
    doc_type: DocumentType | None = None
    doc_number: str | None = Field(None, max_length=100)
    doc_date: date | None = None
    counterparty_id: uuid.UUID | None = None
    total_without_vat: Decimal | None = Field(None, ge=0)
    vat_amount: Decimal | None = Field(None, ge=0)
    total_with_vat: Decimal | None = Field(None, ge=0)
    vat_rate: Decimal | None = Field(None, ge=0, le=100)
    status: DocumentStatus | None = None


class DocumentResponse(BaseModel):
    """Ответ с данными документа."""
    id: uuid.UUID
    user_id: uuid.UUID
    doc_type: DocumentType | None = None
    doc_number: str | None = None
    doc_date: date | None = None
    counterparty_id: uuid.UUID | None = None
    total_without_vat: Decimal | None = None
    vat_amount: Decimal | None = None
    total_with_vat: Decimal | None = None
    vat_rate: Decimal | None = None
    status: DocumentStatus
    source: DocumentSource | None = None
    file_path: str | None = None
    recognized_data_json: dict[str, Any] | None = None
    confidence_score: Decimal | None = None
    items: list[DocumentItemResponse] | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DocumentConfirmRequest(BaseModel):
    """Подтверждение распознанного документа."""
    corrections: DocumentUpdate | None = None
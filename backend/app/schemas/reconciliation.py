"""
Pydantic-схемы для сверки данных.
Справочник: СПРАВОЧНИК_СУЩНОСТЕЙ.md → schemas/reconciliation.py
"""

import uuid
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field


class ReconciliationReportResponse(BaseModel):
    """Ответ с отчётом о сверке."""
    id: uuid.UUID
    user_id: uuid.UUID
    report_date: date
    period_start: date | None = None
    period_end: date | None = None
    discrepancies_json: list[dict[str, Any]] | None = None
    summary: str | None = None
    resolved_count: int
    unresolved_count: int
    total_count: int
    created_at: datetime

    model_config = {"from_attributes": True}


class ReconciliationRunRequest(BaseModel):
    """Запрос на запуск сверки."""
    period_start: date
    period_end: date


class DiscrepancyItem(BaseModel):
    """Одно расхождение."""
    type: str = Field(description="Тип расхождения: missing_document, amount_mismatch, ...")
    description: str
    bank_operation_id: uuid.UUID | None = None
    document_id: uuid.UUID | None = None
    expected_amount: float | None = None
    actual_amount: float | None = None
    is_resolved: bool = False
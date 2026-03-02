"""
Pydantic-схемы для деклараций.
Пункт плана: 1.13.3

Схемы запросов и ответов API декларации:
- DeclarationGenerateRequest  — запрос на генерацию
- DeclarationResponse         — ответ с данными декларации
- DeclarationListResponse     — ответ со списком деклараций
- DeclarationValidateResponse — результат валидации
- DeclarationXmlResponse      — XML-содержимое
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.constants.enums import DeclarationStatus, DeclarationType


# ═══════════════════════════════════════════════════════════════
# Запросы
# ═══════════════════════════════════════════════════════════════


class DeclarationGenerateRequest(BaseModel):
    """Запрос на генерацию декларации."""

    declaration_type: DeclarationType = Field(
        ...,
        description="Тип декларации: vat, usn, ndfl_6, rsv",
        examples=["usn"],
    )
    year: int = Field(
        ...,
        ge=2020,
        le=2030,
        description="Отчётный год",
        examples=[2026],
    )
    quarter: int | None = Field(
        None,
        ge=1,
        le=4,
        description="Квартал (1-4). Обязателен для НДС, необязателен для УСН.",
        examples=[1],
    )


# ═══════════════════════════════════════════════════════════════
# Ответы
# ═══════════════════════════════════════════════════════════════


class ControlRatioErrorResponse(BaseModel):
    """Ошибка контрольного соотношения."""

    code: str = Field(..., description="Код КС", examples=["USN.1"])
    description: str = Field(..., description="Описание ошибки")
    expected: str = Field("", description="Ожидаемое значение")
    actual: str = Field("", description="Фактическое значение")
    severity: str = Field("error", description="Уровень: error / warning")


class DeclarationGenerateResponse(BaseModel):
    """Ответ на генерацию декларации."""

    declaration_id: str = Field(..., description="ID сформированной декларации")
    declaration_type: str = Field(..., description="Тип декларации")
    period: str = Field(..., description="Период: '2026-Q1' или '2026'")
    year: int = Field(..., description="Отчётный год")
    status: str = Field(..., description="Статус декларации")
    xsd_valid: bool = Field(..., description="Пройдена ли XSD-валидация")
    xsd_errors: list[str] = Field(default_factory=list, description="Ошибки XSD")
    control_ratios_valid: bool = Field(
        ..., description="Пройдены ли контрольные соотношения"
    )
    control_ratios_errors: list[ControlRatioErrorResponse] = Field(
        default_factory=list, description="Ошибки контрольных соотношений"
    )
    warnings: list[str] = Field(default_factory=list, description="Предупреждения")


class DeclarationResponse(BaseModel):
    """Ответ с данными декларации (без XML-содержимого)."""

    id: str = Field(..., description="ID декларации")
    declaration_type: DeclarationType = Field(..., description="Тип декларации")
    period: str = Field(..., description="Период")
    year: int = Field(..., description="Год")
    status: DeclarationStatus = Field(..., description="Статус")
    validation_errors: str | None = Field(
        None, description="JSON с ошибками валидации"
    )
    linked_calculation_id: str | None = Field(
        None, description="ID связанного расчёта"
    )
    submitted_at: datetime | None = Field(None, description="Дата отправки в ФНС")
    created_at: datetime = Field(..., description="Дата создания")
    updated_at: datetime = Field(..., description="Дата обновления")

    model_config = {"from_attributes": True}


class DeclarationXmlResponse(BaseModel):
    """Ответ с XML-содержимым декларации."""

    id: str = Field(..., description="ID декларации")
    declaration_type: DeclarationType = Field(..., description="Тип декларации")
    period: str = Field(..., description="Период")
    year: int = Field(..., description="Год")
    status: DeclarationStatus = Field(..., description="Статус")
    xml_content: str = Field(..., description="XML-содержимое декларации")

    model_config = {"from_attributes": True}


class DeclarationValidateResponse(BaseModel):
    """Ответ на запрос валидации декларации."""

    declaration_id: str = Field(..., description="ID декларации")
    status: str = Field(..., description="Обновлённый статус")
    xsd_valid: bool = Field(..., description="Пройдена ли XSD-валидация")
    xsd_errors: list[str] = Field(default_factory=list, description="Ошибки XSD")
    control_ratios_valid: bool = Field(
        ..., description="Пройдены ли контрольные соотношения"
    )
    control_ratios_errors: list[ControlRatioErrorResponse] = Field(
        default_factory=list, description="Ошибки КС"
    )
"""
Модель TaxDeclaration (налоговая декларация).
Справочник: СПРАВОЧНИК_СУЩНОСТЕЙ.md → таблица tax_declarations
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.constants.enums import DeclarationStatus, DeclarationType
from app.models.base import BaseModel, PgEnum


class TaxDeclaration(BaseModel):
    """Налоговая декларация (НДС, УСН, 6-НДФЛ, РСВ и др.)."""

    __tablename__ = "tax_declarations"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    declaration_type: Mapped[DeclarationType] = mapped_column(
        PgEnum(DeclarationType, name="declaration_type_enum"),
        nullable=False,
        index=True,
    )
    period: Mapped[str] = mapped_column(
        String(20), nullable=False  # e.g. "2026-Q1", "2026-01"
    )
    year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    xml_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    xml_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    pdf_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    status: Mapped[DeclarationStatus] = mapped_column(
        PgEnum(DeclarationStatus, name="declaration_status_enum"),
        default=DeclarationStatus.DRAFT,
        nullable=False,
        index=True,
    )
    validation_errors: Mapped[str | None] = mapped_column(Text, nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    fns_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    linked_calculation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tax_calculations.id", ondelete="SET NULL"),
        nullable=True,
    )

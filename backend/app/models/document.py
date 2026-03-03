"""
Модели Document и DocumentItem.
Справочник: СПРАВОЧНИК_СУЩНОСТЕЙ.md → таблицы documents, document_items
"""

from datetime import date
from decimal import Decimal

from sqlalchemy import Date, Enum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.constants.enums import DocumentSource, DocumentStatus, DocumentType
from app.models.base import BaseModel


class Document(BaseModel):
    """Первичный документ (счёт-фактура, УПД, ТОРГ-12, акт и др.)."""

    __tablename__ = "documents"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    doc_type: Mapped[DocumentType] = mapped_column(
        Enum(DocumentType, name="document_type_enum", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        index=True,
    )
    doc_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    doc_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    counterparty_id: Mapped[str | None] = mapped_column(
        ForeignKey("counterparties.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    total_without_vat: Mapped[Decimal | None] = mapped_column(
        Numeric(15, 2), nullable=True
    )
    vat_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(15, 2), nullable=True
    )
    total_with_vat: Mapped[Decimal | None] = mapped_column(
        Numeric(15, 2), nullable=True
    )
    vat_rate: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2), nullable=True
    )
    status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus, name="document_status_enum", values_callable=lambda x: [e.value for e in x]),
        default=DocumentStatus.UPLOADING,
        nullable=False,
        index=True,
    )
    source: Mapped[DocumentSource] = mapped_column(
        Enum(DocumentSource, name="document_source_enum", values_callable=lambda x: [e.value for e in x]),
        default=DocumentSource.MANUAL_UPLOAD,
        nullable=False,
    )
    file_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    recognized_data_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    confidence_score: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 4), nullable=True
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    counterparty: Mapped["Counterparty | None"] = relationship(  # noqa: F821
        "Counterparty", back_populates="documents"
    )
    items: Mapped[list["DocumentItem"]] = relationship(
        "DocumentItem", back_populates="document", cascade="all, delete-orphan",
        lazy="selectin",
    )
    linked_operations: Mapped[list["BankOperation"]] = relationship(  # noqa: F821
        "BankOperation", back_populates="linked_document", lazy="selectin"
    )


class DocumentItem(BaseModel):
    """Позиция документа (товар/услуга)."""

    __tablename__ = "document_items"

    document_id: Mapped[str] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(
        Numeric(15, 3), default=Decimal("1"), nullable=False
    )
    unit: Mapped[str | None] = mapped_column(String(20), nullable=True)
    price_without_vat: Mapped[Decimal | None] = mapped_column(
        Numeric(15, 2), nullable=True
    )
    vat_rate: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2), nullable=True
    )
    vat_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(15, 2), nullable=True
    )
    total_with_vat: Mapped[Decimal | None] = mapped_column(
        Numeric(15, 2), nullable=True
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Relationships
    document: Mapped["Document"] = relationship(
        "Document", back_populates="items"
    )
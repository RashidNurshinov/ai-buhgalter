"""
Модель UploadedFile (загруженный файл).
Справочник: СПРАВОЧНИК_СУЩНОСТЕЙ.md → таблица uploaded_files
"""

import uuid

from sqlalchemy import BigInteger, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.constants.enums import FileType, ProcessingStatus
from app.models.base import BaseModel, PgEnum


class UploadedFile(BaseModel):
    """Метаданные загруженного файла."""

    __tablename__ = "uploaded_files"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    original_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    stored_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    file_type: Mapped[FileType | None] = mapped_column(
        PgEnum(FileType, name="file_type_enum"),
        nullable=True,
    )
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    mime_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    processing_status: Mapped[ProcessingStatus] = mapped_column(
        PgEnum(ProcessingStatus, name="processing_status_enum"),
        default=ProcessingStatus.QUEUED,
        nullable=False,
        index=True,
    )
    processing_result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    processing_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    linked_document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    linked_document: Mapped["Document | None"] = relationship(  # noqa: F821
        "Document", foreign_keys=[linked_document_id]
    )
"""
Модель UploadedFile (загруженный файл).
Справочник: СПРАВОЧНИК_СУЩНОСТЕЙ.md → таблица uploaded_files
"""

from sqlalchemy import BigInteger, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.constants.enums import FileType, ProcessingStatus
from app.models.base import BaseModel


class UploadedFile(BaseModel):
    """Загруженный пользователем файл."""

    __tablename__ = "uploaded_files"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    original_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    stored_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    file_type: Mapped[FileType | None] = mapped_column(
        Enum(FileType, name="file_type_enum", values_callable=lambda x: [e.value for e in x]),
        nullable=True,
    )
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    mime_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    processing_status: Mapped[ProcessingStatus] = mapped_column(
        Enum(ProcessingStatus, name="processing_status_enum", values_callable=lambda x: [e.value for e in x]),
        default=ProcessingStatus.QUEUED,
        nullable=False,
        index=True,
    )
    processing_result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    processing_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    linked_document_id: Mapped[str | None] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
    )
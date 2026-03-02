"""
Pydantic-схемы для загруженных файлов.
Справочник: СПРАВОЧНИК_СУЩНОСТЕЙ.md → schemas/uploaded_file.py
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.constants.enums import FileType, ProcessingStatus


class UploadedFileResponse(BaseModel):
    """Ответ с данными загруженного файла."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    original_filename: str
    stored_path: str
    file_type: FileType | None = None
    file_size: int
    mime_type: str | None = None
    processing_status: ProcessingStatus
    processing_result: dict | None = None
    processing_error: str | None = None
    linked_document_id: UUID | None = None
    created_at: datetime
    updated_at: datetime


class UploadedFileShortResponse(BaseModel):
    """Краткий ответ для списка файлов."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    original_filename: str
    file_type: FileType | None = None
    file_size: int
    processing_status: ProcessingStatus
    processing_error: str | None = None
    created_at: datetime


class FileUploadResult(BaseModel):
    """Результат загрузки одного файла."""
    file_id: UUID
    filename: str
    file_type: FileType | None = None
    file_size: int
    processing_status: ProcessingStatus
    pipeline: str = Field(description="Пайплайн обработки: ocr, xml_parser, table_parser, pdf_parser")


class MultiUploadResponse(BaseModel):
    """Ответ на мультизагрузку файлов."""
    uploaded: list[FileUploadResult]
    errors: list[dict] = Field(default_factory=list, description="Ошибки загрузки отдельных файлов")
    total_uploaded: int
    total_errors: int
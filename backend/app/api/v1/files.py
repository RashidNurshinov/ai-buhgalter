"""
API роутер для загрузки и управления файлами.
Справочник: СПРАВОЧНИК_СУЩНОСТЕЙ.md → api/v1/files.py

Эндпоинты:
  POST   /api/v1/files/upload          — Мультизагрузка файлов
  GET    /api/v1/files/                 — Список загруженных файлов
  GET    /api/v1/files/formats/allowed  — Допустимые форматы
  GET    /api/v1/files/{file_id}        — Статус обработки файла
  DELETE /api/v1/files/{file_id}        — Удалить файл
"""

import math
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.enums import FileType, ProcessingStatus
from app.core.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.uploaded_file import (
    FileUploadResult,
    MultiUploadResponse,
    UploadedFileResponse,
    UploadedFileShortResponse,
)
from app.schemas.base import PaginatedResponse, StatusResponse
from app.services.file_service import FileService
from app.utils.file_utils import ALLOWED_EXTENSIONS

router = APIRouter(prefix="/files", tags=["files"])


# ═══════════════════════════════════════════════════════════
# POST /files/upload — Мультизагрузка файлов
# ═══════════════════════════════════════════════════════════

@router.post(
    "/upload",
    response_model=MultiUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Загрузка файлов",
    description="Мультизагрузка файлов (XML, CSV, XLS, XLSX, PDF, JPG, PNG, TIFF, HEIC). Макс. 10 файлов за раз.",
)
async def upload_files(
    files: list[UploadFile] = File(..., description="Файлы для загрузки (макс. 10)"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Загрузка одного или нескольких файлов.

    - Валидация формата и размера каждого файла
    - Сохранение на диск в storage/uploads/{user_id}/{date}/
    - Создание записи в БД со статусом QUEUED
    - Определение пайплайна обработки (OCR / XML-парсер / табличный парсер / PDF)
    """
    # Ограничение: макс. 10 файлов за один запрос
    if len(files) > 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Максимум 10 файлов за один запрос",
        )

    if len(files) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Необходимо выбрать хотя бы один файл",
        )

    service = FileService(db)
    uploaded: list[FileUploadResult] = []
    errors: list[dict] = []

    for file in files:
        try:
            uploaded_file = await service.upload_file(
                file=file,
                user_id=current_user.id,
            )
            pipeline = service.get_pipeline_for_file(uploaded_file)

            uploaded.append(
                FileUploadResult(
                    file_id=uploaded_file.id,
                    filename=uploaded_file.original_filename,
                    file_type=uploaded_file.file_type,
                    file_size=uploaded_file.file_size,
                    processing_status=uploaded_file.processing_status,
                    pipeline=pipeline,
                )
            )
        except ValueError as e:
            errors.append({
                "filename": file.filename or "unknown",
                "error": str(e),
            })

    # Коммитим все успешные загрузки разом
    if uploaded:
        await db.commit()

    return MultiUploadResponse(
        uploaded=uploaded,
        errors=errors,
        total_uploaded=len(uploaded),
        total_errors=len(errors),
    )


# ═══════════════════════════════════════════════════════════
# GET /files/ — Список загруженных файлов
# ═══════════════════════════════════════════════════════════

@router.get(
    "/",
    response_model=PaginatedResponse[UploadedFileShortResponse],
    summary="Список загруженных файлов",
    description="Получить список файлов текущего пользователя с пагинацией и фильтрами.",
)
async def get_files_list(
    page: int = Query(1, ge=1, description="Номер страницы"),
    page_size: int = Query(20, ge=1, le=100, description="Элементов на странице"),
    processing_status: ProcessingStatus | None = Query(
        None, description="Фильтр по статусу обработки"
    ),
    file_type: FileType | None = Query(None, description="Фильтр по типу файла"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Список файлов с пагинацией. Фильтрация всегда по user_id текущего пользователя."""
    service = FileService(db)
    files, total = await service.get_files_list(
        user_id=current_user.id,
        page=page,
        page_size=page_size,
        processing_status=processing_status,
        file_type=file_type,
    )

    total_pages = math.ceil(total / page_size) if total > 0 else 0

    return PaginatedResponse(
        success=True,
        data=[UploadedFileShortResponse.model_validate(f) for f in files],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


# ═══════════════════════════════════════════════════════════
# GET /files/formats/allowed — Допустимые форматы (СТАТИЧЕСКИЙ — до {file_id})
# ═══════════════════════════════════════════════════════════

@router.get(
    "/formats/allowed",
    summary="Допустимые форматы файлов",
    description="Получить список допустимых форматов файлов для загрузки.",
)
async def get_allowed_formats(
    current_user: User = Depends(get_current_user),
):
    """Справочный эндпоинт: список допустимых расширений."""
    return {
        "allowed_extensions": sorted(ALLOWED_EXTENSIONS),
        "max_file_size_mb": 50,
        "max_files_per_request": 10,
    }


# ═══════════════════════════════════════════════════════════
# GET /files/{file_id} — Информация о файле (ПАРАМЕТРИЗОВАННЫЙ — после статических)
# ═══════════════════════════════════════════════════════════

@router.get(
    "/{file_id}",
    response_model=UploadedFileResponse,
    summary="Информация о файле",
    description="Получить детальную информацию о загруженном файле и статусе его обработки.",
)
async def get_file_detail(
    file_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Получить информацию о конкретном файле (только свои файлы)."""
    service = FileService(db)
    uploaded_file = await service.get_file_by_id(
        file_id=file_id,
        user_id=current_user.id,
    )

    if uploaded_file is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Файл не найден",
        )

    return UploadedFileResponse.model_validate(uploaded_file)


# ═══════════════════════════════════════════════════════════
# DELETE /files/{file_id} — Удалить файл
# ═══════════════════════════════════════════════════════════

@router.delete(
    "/{file_id}",
    response_model=StatusResponse,
    summary="Удалить файл",
    description="Удалить загруженный файл (из хранилища и базы данных).",
)
async def delete_file(
    file_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Удалить файл (только свои файлы). Удаляет и запись в БД, и файл с диска."""
    service = FileService(db)
    deleted = await service.delete_file(
        file_id=file_id,
        user_id=current_user.id,
    )

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Файл не найден",
        )

    await db.commit()

    return StatusResponse(
        status="ok",
        message="Файл успешно удалён",
    )
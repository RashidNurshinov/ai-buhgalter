"""
API роутер для загрузки и управления файлами.
Справочник: СПРАВОЧНИК_СУЩНОСТЕЙ.md -> api/v1/files.py

Эндпоинты:
  POST   /api/v1/files/upload          -- Мультизагрузка файлов
  GET    /api/v1/files/                 -- Список загруженных файлов
  GET    /api/v1/files/formats/allowed  -- Допустимые форматы
  GET    /api/v1/files/{file_id}        -- Статус обработки файла
  POST   /api/v1/files/{file_id}/reprocess -- Повторная обработка
  DELETE /api/v1/files/{file_id}        -- Удалить файл
"""

import logging
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
from app.schemas.common import PaginatedResponse, StatusResponse
from app.services.file_service import FileService
from app.utils.file_utils import ALLOWED_EXTENSIONS

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/files", tags=["files"])


def _dispatch_file_processing(file_id: str, user_id: str) -> None:
    """
    Отправить файл на обработку через Celery.

    Импорт Celery-задачи внутри функции, чтобы избежать
    циклических импортов и проблем при отсутствии Celery-брокера.
    """
    try:
        from app.tasks.file_processing_tasks import task_process_uploaded_file
        task_process_uploaded_file.delay(file_id=file_id, user_id=user_id)
        logger.info("File processing task dispatched: file_id=%s", file_id)
    except Exception as e:
        logger.warning(
            "Failed to dispatch file processing task (Celery may be unavailable): "
            "file_id=%s error=%s",
            file_id, str(e),
        )


def _notify_agent_about_files(user_id: str, files: list[dict]) -> None:
    """
    Уведомить AI-агента о загруженных файлах.

    Args:
        user_id: ID пользователя
        files: Список файлов [{file_id, filename, file_type, size_human}]
    """
    try:
        from app.tasks.agent_tasks import agent_on_file_uploaded
        agent_on_file_uploaded.delay(user_id=user_id, files=files)
        logger.info("Agent notified about %d files for user %s", len(files), user_id)
    except Exception as e:
        logger.warning(
            "Failed to notify agent about files: user_id=%s error=%s",
            user_id, str(e),
        )


# POST /files/upload

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
    """Загрузка одного или нескольких файлов."""
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

    if uploaded:
        await db.commit()

    for file_result in uploaded:
        _dispatch_file_processing(
            file_id=str(file_result.file_id),
            user_id=str(current_user.id),
        )

    if uploaded:
        files_for_agent = [
            {
                "file_id": str(f.file_id),
                "filename": f.filename,
                "file_type": f.file_type.value if hasattr(f.file_type, "value") else str(f.file_type),
                "size_human": f.file_size,
            }
            for f in uploaded
        ]
        _notify_agent_about_files(
            user_id=str(current_user.id),
            files=files_for_agent,
        )

    return MultiUploadResponse(
        uploaded=uploaded,
        errors=errors,
        total_uploaded=len(uploaded),
        total_errors=len(errors),
    )


# GET /files/

@router.get(
    "/",
    response_model=PaginatedResponse,
    summary="Список загруженных файлов",
    description="Получить список файлов текущего пользователя с пагинацией и фильтрами.",
)
async def get_files_list(
    page: int = Query(1, ge=1, description="Номер страницы"),
    per_page: int = Query(20, ge=1, le=100, description="Элементов на странице"),
    processing_status: ProcessingStatus | None = Query(
        None, description="Фильтр по статусу обработки"
    ),
    file_type: FileType | None = Query(None, description="Фильтр по типу файла"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Список файлов с пагинацией."""
    service = FileService(db)
    files, total = await service.get_files_list(
        user_id=current_user.id,
        page=page,
        page_size=per_page,
        processing_status=processing_status,
        file_type=file_type,
    )

    pages = math.ceil(total / per_page) if total > 0 else 0

    return PaginatedResponse(
        items=[UploadedFileShortResponse.model_validate(f) for f in files],
        total=total,
        page=page,
        per_page=per_page,
        pages=pages,
    )


# GET /files/formats/allowed

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


# GET /files/{file_id}

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


# POST /files/{file_id}/reprocess

@router.post(
    "/{file_id}/reprocess",
    response_model=StatusResponse,
    summary="Повторная обработка файла",
    description="Запустить повторную обработку файла (парсинг, OCR, классификация).",
)
async def reprocess_file(
    file_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Повторная обработка файла -- сбрасывает статус и запускает Celery-задачу."""
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

    uploaded_file.processing_status = ProcessingStatus.QUEUED
    uploaded_file.processing_result = None
    await db.commit()

    _dispatch_file_processing(
        file_id=str(file_id),
        user_id=str(current_user.id),
    )

    return StatusResponse(
        status="ok",
        message="Файл отправлен на повторную обработку",
    )


# DELETE /files/{file_id}

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
        message="Файл успешно удален",
    )

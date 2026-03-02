"""
Celery-задачи обработки загруженных файлов.
Пункт плана: 1.8.9

Задачи:
1. task_process_uploaded_file — основная задача обработки файла (OCR/XML-парсинг)
2. task_process_uploaded_file_batch — пакетная обработка нескольких файлов
"""

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

from app.core.celery_app import celery_app

logger = logging.getLogger(__name__)


def _run_async(coro):
    """Запуск async-функции из sync-контекста Celery worker."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


async def _process_file_async(file_id: str, user_id: str) -> dict[str, Any]:
    """
    Async-логика обработки одного файла.

    Алгоритм:
    1. Загрузить запись UploadedFile из БД
    2. Прочитать файл с диска
    3. По типу файла выбрать пайплайн:
       - XML → xml_parser_service
       - PDF/JPG/PNG/TIFF → ocr_service (OCR + LLM)
       - CSV/XLS/XLSX → table_parser (будет в 1.9)
    4. Обновить UploadedFile.processing_status и processing_result
    5. При необходимости создать Document в БД
    """
    from app.constants.enums import FileType, ProcessingStatus
    from app.core.config import settings
    from app.core.database import async_session_factory
    from app.models.uploaded_file import UploadedFile

    import aiofiles
    from sqlalchemy import select

    async with async_session_factory() as db:
        # 1. Загружаем запись файла
        result = await db.execute(
            select(UploadedFile).where(
                UploadedFile.id == file_id,
                UploadedFile.user_id == user_id,
            )
        )
        uploaded_file = result.scalar_one_or_none()

        if uploaded_file is None:
            logger.error("File not found: file_id=%s user_id=%s", file_id, user_id)
            return {"status": "error", "error": "Файл не найден"}

        # Обновляем статус → PROCESSING
        uploaded_file.processing_status = ProcessingStatus.PROCESSING
        await db.commit()

        try:
            # 2. Читаем файл с диска
            file_path = settings.upload_path / uploaded_file.stored_path
            if not file_path.exists():
                raise FileNotFoundError(f"Файл не найден на диске: {file_path}")

            async with aiofiles.open(str(file_path), "rb") as f:
                file_data = await f.read()

            file_type = uploaded_file.file_type

            # 3. Выбираем пайплайн обработки
            processing_result: dict[str, Any]

            if file_type == FileType.XML:
                processing_result = _process_xml_file(file_data)

            elif file_type in (
                FileType.PDF, FileType.JPG, FileType.JPEG,
                FileType.PNG, FileType.TIFF, FileType.HEIC,
            ):
                processing_result = await _process_image_or_pdf_file(
                    file_data, file_type
                )

            elif file_type in (FileType.CSV, FileType.XLS, FileType.XLSX):
                # Табличные файлы — stub на будущее (пункт 1.9)
                processing_result = {
                    "status": "completed",
                    "pipeline": "table_parser",
                    "message": "Обработка таблиц будет реализована в следующей итерации",
                }

            else:
                processing_result = {
                    "status": "completed",
                    "pipeline": "unknown",
                    "message": f"Тип файла {file_type} не поддерживается для автообработки",
                }

            # 4. Обновляем запись в БД
            uploaded_file.processing_status = ProcessingStatus.COMPLETED
            uploaded_file.processing_result = processing_result

            # Если есть linked_document_id из обработки — привязываем
            if processing_result.get("document_id"):
                uploaded_file.linked_document_id = processing_result["document_id"]

            await db.commit()

            logger.info(
                "File processed: file_id=%s pipeline=%s status=completed",
                file_id, processing_result.get("pipeline", "?"),
            )

            return {
                "status": "completed",
                "file_id": file_id,
                "pipeline": processing_result.get("pipeline"),
                "doc_type": processing_result.get("doc_type"),
                "confidence": processing_result.get("confidence"),
            }

        except Exception as e:
            logger.exception("File processing failed: file_id=%s error=%s", file_id, str(e))

            # Обновляем статус → ERROR
            uploaded_file.processing_status = ProcessingStatus.ERROR
            uploaded_file.processing_error = str(e)[:2000]
            uploaded_file.processing_result = {"status": "error", "error": str(e)[:2000]}
            await db.commit()

            return {"status": "error", "file_id": file_id, "error": str(e)[:500]}


def _process_xml_file(file_data: bytes) -> dict[str, Any]:
    """Обработка XML-файла через xml_parser_service."""
    from app.services.xml_parser_service import (
        detect_xml_document_type,
        XmlDocumentType,
        parse_xml_invoice,
        parse_xml_upd,
        parse_xml_torg12,
        parse_xml_bank_statement,
        map_parsed_document_to_dict,
        map_parsed_bank_statement_to_dicts,
    )

    # Определяем тип XML
    xml_type = detect_xml_document_type(file_data)

    if xml_type == XmlDocumentType.INVOICE:
        parsed = parse_xml_invoice(file_data)
        doc_dict = map_parsed_document_to_dict(parsed)
        return {
            "status": "completed",
            "pipeline": "xml_parser",
            "xml_type": xml_type.value,
            "doc_type": parsed.doc_type.value,
            "confidence": float(parsed.confidence_score),
            "document_data": _make_json_serializable(doc_dict),
            "warnings": parsed.warnings,
            "errors": parsed.errors,
        }

    elif xml_type == XmlDocumentType.UPD:
        parsed = parse_xml_upd(file_data)
        doc_dict = map_parsed_document_to_dict(parsed)
        return {
            "status": "completed",
            "pipeline": "xml_parser",
            "xml_type": xml_type.value,
            "doc_type": parsed.doc_type.value,
            "confidence": float(parsed.confidence_score),
            "document_data": _make_json_serializable(doc_dict),
            "warnings": parsed.warnings,
            "errors": parsed.errors,
        }

    elif xml_type == XmlDocumentType.TORG12:
        parsed = parse_xml_torg12(file_data)
        doc_dict = map_parsed_document_to_dict(parsed)
        return {
            "status": "completed",
            "pipeline": "xml_parser",
            "xml_type": xml_type.value,
            "doc_type": parsed.doc_type.value,
            "confidence": float(parsed.confidence_score),
            "document_data": _make_json_serializable(doc_dict),
            "warnings": parsed.warnings,
            "errors": parsed.errors,
        }

    elif xml_type == XmlDocumentType.BANK_STATEMENT_1C:
        parsed = parse_xml_bank_statement(file_data)
        ops = map_parsed_bank_statement_to_dicts(parsed)
        return {
            "status": "completed",
            "pipeline": "xml_parser",
            "xml_type": xml_type.value,
            "doc_type": "bank_statement",
            "confidence": 0.9 if parsed.is_valid else 0.5,
            "operations_count": len(ops),
            "bank_data": {
                "bank_name": parsed.bank_name,
                "account_number": parsed.account_number,
                "operations_count": len(ops),
                "total_income": str(parsed.total_income),
                "total_expense": str(parsed.total_expense),
            },
            "warnings": parsed.warnings,
            "errors": parsed.errors,
        }

    else:
        return {
            "status": "completed",
            "pipeline": "xml_parser",
            "xml_type": xml_type.value,
            "doc_type": "other",
            "confidence": 0.0,
            "warnings": [f"Не удалось определить тип XML: {xml_type.value}"],
            "errors": [],
        }


async def _process_image_or_pdf_file(
    file_data: bytes,
    file_type: "FileType",
) -> dict[str, Any]:
    """Обработка изображения/PDF через OCR-пайплайн."""
    from app.services.ocr_service import (
        process_document_image,
        map_recognized_to_document_dict,
    )

    recognized = await process_document_image(file_data, file_type)

    doc_dict = map_recognized_to_document_dict(recognized)

    return {
        "status": "completed",
        "pipeline": "ocr",
        "doc_type": recognized.doc_type.value,
        "confidence": recognized.confidence_score,
        "ocr_engine": recognized.ocr_engine,
        "llm_model": recognized.llm_model,
        "document_data": _make_json_serializable(doc_dict),
        "warnings": recognized.warnings,
        "errors": recognized.errors,
    }


def _make_json_serializable(obj: Any) -> Any:
    """Рекурсивная конвертация объекта для JSON-сериализации (Decimal, date, etc.)."""
    import datetime
    from decimal import Decimal

    if isinstance(obj, dict):
        return {k: _make_json_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_make_json_serializable(item) for item in obj]
    elif isinstance(obj, Decimal):
        return float(obj)
    elif isinstance(obj, (datetime.date, datetime.datetime)):
        return obj.isoformat()
    elif isinstance(obj, bytes):
        return "<binary>"
    else:
        return obj


# ═══════════════════════════════════════════════════════════
# Задача 1: Обработка одного файла
# ═══════════════════════════════════════════════════════════

@celery_app.task(
    name="app.tasks.file_processing_tasks.task_process_uploaded_file",
    bind=True,
    max_retries=2,
    default_retry_delay=15,
    soft_time_limit=300,   # 5 минут (OCR + LLM может быть долгим)
    time_limit=360,        # 6 минут (hard)
)
def task_process_uploaded_file(
    self,
    file_id: str,
    user_id: str,
):
    """
    Celery-задача обработки загруженного файла.

    Вызывается автоматически после загрузки файла через POST /files/upload.

    Алгоритм:
    1. XML → xml_parser_service (парсинг без LLM)
    2. PDF/JPG/PNG/TIFF → OCR + LLM (Claude Sonnet vision)
    3. CSV/XLS/XLSX → table_parser (стаб)

    Args:
        file_id: ID записи UploadedFile
        user_id: ID пользователя
    """
    logger.info("Processing file: file_id=%s user_id=%s", file_id, user_id)

    try:
        result = _run_async(_process_file_async(file_id, user_id))

        logger.info(
            "File processing result: file_id=%s status=%s pipeline=%s doc_type=%s",
            file_id,
            result.get("status"),
            result.get("pipeline"),
            result.get("doc_type"),
        )

        return result

    except Exception as exc:
        logger.error(
            "File processing task failed: file_id=%s error=%s",
            file_id, str(exc), exc_info=True,
        )
        raise self.retry(exc=exc)


# ═══════════════════════════════════════════════════════════
# Задача 2: Пакетная обработка файлов
# ═══════════════════════════════════════════════════════════

@celery_app.task(
    name="app.tasks.file_processing_tasks.task_process_uploaded_file_batch",
    soft_time_limit=1800,  # 30 минут
    time_limit=2100,       # 35 минут
)
def task_process_uploaded_file_batch(
    file_ids: list[str],
    user_id: str,
):
    """
    Пакетная обработка нескольких файлов.
    Создаёт отдельную задачу для каждого файла.

    Args:
        file_ids: Список ID файлов
        user_id: ID пользователя
    """
    logger.info(
        "Batch processing %d files for user %s",
        len(file_ids), user_id,
    )

    results = []
    for file_id in file_ids:
        try:
            task = task_process_uploaded_file.delay(
                file_id=file_id,
                user_id=user_id,
            )
            results.append({
                "file_id": file_id,
                "task_id": task.id,
                "status": "queued",
            })
        except Exception as e:
            logger.error(
                "Failed to queue file processing: file_id=%s error=%s",
                file_id, str(e),
            )
            results.append({
                "file_id": file_id,
                "status": "error",
                "error": str(e),
            })

    return {
        "total": len(file_ids),
        "queued": sum(1 for r in results if r["status"] == "queued"),
        "errors": sum(1 for r in results if r["status"] == "error"),
        "results": results,
    }
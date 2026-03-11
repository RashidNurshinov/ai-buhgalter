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
                processing_result = await _process_table_file(
                    file_data, file_type, file_id, user_id, db
                )

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


async def _process_table_file(
    file_data: bytes,
    file_type: "FileType",
    file_id: str,
    user_id: str,
    db: "AsyncSession",
) -> dict[str, Any]:
    """
    Обработка CSV/Excel файла через ИИ:
    1. Читаем файл pandas
    2. Извлекаем метаданные и строки операций
    3. Отправляем батчами в LLM для парсинга + классификации
    4. Создаем BankOperation и Counterparty в БД
    """
    import io
    import re
    from datetime import datetime
    from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
    from app.constants.enums import FileType, OperationCategory, OperationStatus
    from app.models.bank_operation import BankOperation
    from app.models.counterparty import Counterparty
    from app.prompts.bank_statement_parser import (
        BANK_STATEMENT_PARSER_PROMPT,
        BANK_STATEMENT_PARSER_USER_PROMPT,
        BANK_STATEMENT_PARSER_BATCH_USER_PROMPT,
    )
    from app.services.openrouter_client import get_openrouter_client
    from sqlalchemy import select
    import pandas as pd

    warnings_list: list[str] = []

    # ── 1. Читаем файл в DataFrame ──
    try:
        if file_type == FileType.CSV:
            # Пробуем разные кодировки
            for enc in ("utf-8", "cp1251", "windows-1251", "latin-1"):
                try:
                    df = pd.read_csv(
                        io.BytesIO(file_data), header=None, dtype=str,
                        keep_default_na=False, encoding=enc, sep=None, engine="python",
                    )
                    break
                except Exception:
                    continue
            else:
                return {"status": "completed", "pipeline": "ai_parser",
                        "message": "Не удалось прочитать CSV"}
        else:
            df = pd.read_excel(
                io.BytesIO(file_data), header=None, dtype=str,
                keep_default_na=False, engine="openpyxl",
            )
    except Exception as e:
        return {"status": "error", "pipeline": "ai_parser",
                "error": f"Ошибка чтения файла: {str(e)[:500]}"}

    if df.empty or len(df) < 2:
        return {"status": "completed", "pipeline": "ai_parser",
                "message": "Файл пуст или содержит менее 2 строк"}

    # ── 2. Находим строку заголовков и разделяем метаданные / операции ──
    header_row_idx = _find_header_row(df)
    if header_row_idx is None:
        # Если заголовки не найдены, отправляем все как есть
        header_row_idx = 0

    metadata_rows = df.iloc[:header_row_idx] if header_row_idx > 0 else pd.DataFrame()
    headers = df.iloc[header_row_idx].tolist()
    data_rows = df.iloc[header_row_idx + 1:]

    # Убираем полностью пустые строки
    data_rows = data_rows.dropna(how="all")
    data_rows = data_rows[data_rows.apply(lambda r: any(str(v).strip() for v in r), axis=1)]

    if data_rows.empty:
        return {"status": "completed", "pipeline": "ai_parser",
                "message": "Нет строк с операциями после заголовков"}

    # ── 3. Формируем текст для LLM (только ключевые колонки) ──
    metadata_text = ""
    if not metadata_rows.empty:
        for _, row in metadata_rows.iterrows():
            vals = [str(v) for v in row if str(v).strip()]
            if vals:
                metadata_text += " | ".join(vals) + "\n"

    # Определяем индексы ключевых колонок
    key_col_indices = _find_key_columns(headers)
    if key_col_indices:
        key_headers = [str(headers[i]) for i in key_col_indices]
    else:
        # Если не нашли — берем первые 8 колонок
        key_col_indices = list(range(min(8, len(headers))))
        key_headers = [str(headers[i]) for i in key_col_indices]

    headers_text = " | ".join(key_headers)

    # ── 4. Отправляем батчами в LLM ──
    BATCH_SIZE = 10  # операций за раз (чтобы ответ LLM не обрезался)
    all_parsed_ops: list[dict] = []
    account_number = None
    client_inn = None
    opening_balance = None
    closing_balance = None

    client = get_openrouter_client()
    total_rows = len(data_rows)

    for batch_start in range(0, total_rows, BATCH_SIZE):
        batch_end = min(batch_start + BATCH_SIZE, total_rows)
        batch_df = data_rows.iloc[batch_start:batch_end]

        ops_lines = []
        for i, (_, row) in enumerate(batch_df.iterrows()):
            # Берем только ключевые колонки
            vals = [str(row.iloc[ci]).strip() if ci < len(row) else "" for ci in key_col_indices]
            ops_lines.append(f"Строка {batch_start + i}: " + " | ".join(vals))

        operations_text = "\n".join(ops_lines)

        if batch_start == 0:
            user_msg = BANK_STATEMENT_PARSER_USER_PROMPT.format(
                metadata=metadata_text or "Нет метаданных",
                headers=headers_text,
                operations_text=operations_text,
            )
        else:
            user_msg = BANK_STATEMENT_PARSER_BATCH_USER_PROMPT.format(
                start_index=batch_start,
                headers=headers_text,
                operations_text=operations_text,
            )

        try:
            llm_response = await client.chat_completion(
                messages=[
                    {"role": "system", "content": BANK_STATEMENT_PARSER_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
                task="agent_reasoning",
            )

            parsed = _parse_llm_json(llm_response.content or "")
            if parsed is None:
                warnings_list.append(
                    f"Не удалось распарсить ответ LLM для батча {batch_start}-{batch_end}"
                )
                logger.warning(
                    "LLM parse failed for batch %d-%d: %s",
                    batch_start, batch_end, (llm_response.content or "")[:200],
                )
                continue

            # Извлекаем метаданные из первого батча
            if batch_start == 0:
                account_number = parsed.get("account_number")
                client_inn = parsed.get("client_inn")
                opening_balance = parsed.get("opening_balance")
                closing_balance = parsed.get("closing_balance")

            ops = parsed.get("operations", [])
            if isinstance(ops, list):
                all_parsed_ops.extend(ops)

            logger.info(
                "AI parsed batch %d-%d: %d operations",
                batch_start, batch_end, len(ops) if isinstance(ops, list) else 0,
            )

        except Exception as e:
            warnings_list.append(f"Ошибка LLM для батча {batch_start}-{batch_end}: {str(e)[:200]}")
            logger.error("LLM error for batch %d-%d: %s", batch_start, batch_end, e)

    if not all_parsed_ops:
        return {
            "status": "completed",
            "pipeline": "ai_parser",
            "message": "ИИ не смог извлечь операции из выписки",
            "warnings": warnings_list,
        }

    # ── 5. Создаем записи в БД ──
    created_ops = 0
    created_counterparties = 0
    total_income = Decimal("0")
    total_expense = Decimal("0")

    for op_data in all_parsed_ops:
        try:
            # Парсим дату
            date_str = op_data.get("operation_date", "")
            try:
                op_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            except (ValueError, TypeError):
                # Пробуем DD.MM.YYYY
                try:
                    op_date = datetime.strptime(date_str, "%d.%m.%Y").date()
                except (ValueError, TypeError):
                    warnings_list.append(f"Пропущена операция: неверная дата '{date_str}'")
                    continue

            # Парсим сумму
            amount_raw = op_data.get("amount", 0)
            try:
                amount = Decimal(str(amount_raw)).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )
            except (InvalidOperation, ValueError):
                warnings_list.append(f"Пропущена операция: неверная сумма '{amount_raw}'")
                continue

            if amount <= 0:
                continue

            is_income = bool(op_data.get("is_income", False))
            is_expense = bool(op_data.get("is_expense", False))

            # Защита: не могут быть оба true
            if is_income and is_expense:
                is_expense = False

            # Категория
            cat_str = op_data.get("category", "unclassified")
            try:
                category = OperationCategory(cat_str)
            except ValueError:
                category = OperationCategory.UNCLASSIFIED

            # НДС
            vat_raw = op_data.get("vat_amount")
            vat_amount = None
            if vat_raw is not None:
                try:
                    vat_amount = Decimal(str(vat_raw)).quantize(
                        Decimal("0.01"), rounding=ROUND_HALF_UP
                    )
                except (InvalidOperation, ValueError):
                    vat_amount = None

            # Контрагент
            cp_name = (op_data.get("counterparty_name") or "").strip()
            cp_inn = (op_data.get("counterparty_inn") or "").strip()
            # Убираем "0" как ИНН
            if cp_inn in ("0", "None", "null", ""):
                cp_inn = ""

            counterparty_id = None
            if cp_name or cp_inn:
                cp_query = select(Counterparty).where(
                    Counterparty.user_id == user_id
                )
                if cp_inn:
                    cp_query = cp_query.where(Counterparty.inn == cp_inn)
                elif cp_name:
                    cp_query = cp_query.where(Counterparty.name == cp_name)

                cp_result = await db.execute(cp_query.limit(1))
                existing_cp = cp_result.scalar_one_or_none()

                if existing_cp:
                    counterparty_id = existing_cp.id
                    if cp_inn and not existing_cp.inn:
                        existing_cp.inn = cp_inn
                else:
                    new_cp = Counterparty(
                        user_id=user_id,
                        name=cp_name or f"Контрагент (ИНН {cp_inn})",
                        inn=cp_inn or None,
                    )
                    db.add(new_cp)
                    await db.flush()
                    counterparty_id = new_cp.id
                    created_counterparties += 1

            # Confidence
            confidence_raw = op_data.get("confidence", 0.0)
            try:
                confidence = Decimal(str(confidence_raw)).quantize(
                    Decimal("0.0001"), rounding=ROUND_HALF_UP
                )
            except (InvalidOperation, ValueError):
                confidence = Decimal("0")

            # Статус на основе confidence
            if float(confidence) >= 0.9:
                status = OperationStatus.CLASSIFIED
            else:
                status = OperationStatus.PENDING

            purpose = (op_data.get("purpose") or "").strip()

            bank_op = BankOperation(
                user_id=user_id,
                operation_date=op_date,
                amount=amount,
                is_income=is_income,
                is_expense=is_expense,
                counterparty_id=counterparty_id,
                counterparty_name=cp_name or None,
                counterparty_inn=cp_inn or None,
                purpose=purpose or None,
                vat_amount=vat_amount,
                category=category,
                status=status,
                classification_confidence=confidence,
            )
            db.add(bank_op)
            created_ops += 1

            if is_income:
                total_income += amount
            if is_expense:
                total_expense += amount

        except Exception as e:
            warnings_list.append(f"Ошибка создания операции: {str(e)[:200]}")
            logger.error("Error creating bank operation: %s", e)

    await db.flush()

    return {
        "status": "completed",
        "pipeline": "ai_parser",
        "doc_type": "bank_statement",
        "operations_count": created_ops,
        "counterparties_created": created_counterparties,
        "total_income": str(total_income),
        "total_expense": str(total_expense),
        "account_number": account_number,
        "client_inn": client_inn,
        "opening_balance": opening_balance,
        "closing_balance": closing_balance,
        "warnings": warnings_list,
    }


def _find_header_row(df) -> int | None:
    """
    Ищем строку заголовков в DataFrame.
    Заголовки содержат ключевые слова: дата, сумма, назначение и т.п.
    """
    header_keywords = {
        "дата", "сумма", "назначение", "операци", "контрагент",
        "плательщик", "получатель", "кредит", "дебет", "тип",
        "номер счёта", "номер счета", "валюта", "описание",
    }
    for idx in range(min(20, len(df))):
        row_text = " ".join(str(v).lower() for v in df.iloc[idx])
        matches = sum(1 for kw in header_keywords if kw in row_text)
        if matches >= 3:
            return idx
    return None


def _find_key_columns(headers: list) -> list[int] | None:
    """
    Находим индексы ключевых колонок для отправки в LLM.
    Возвращает индексы колонок: тип операции, дата, сумма, описание/назначение,
    ИНН контрагента, наименование контрагента.
    """
    key_patterns = {
        "тип операц": None,
        "дата провед": None,
        "дата": None,
        "сумма": None,
        "описание операц": None,
        "назначение платеж": None,
        "назначение": None,
        "инн контрагент": None,
        "наименование контрагент": None,
        "контрагент": None,
        "инн получател": None,
        "наименование получател": None,
    }

    for i, h in enumerate(headers):
        h_lower = str(h).lower().strip()
        for pattern in key_patterns:
            if pattern in h_lower and key_patterns[pattern] is None:
                key_patterns[pattern] = i
                break

    # Собираем уникальные индексы в порядке приоритета
    indices = []
    seen = set()
    # Приоритетные колонки
    priority = [
        "тип операц", "дата провед", "дата", "сумма",
        "назначение платеж", "описание операц", "назначение",
        "наименование контрагент", "контрагент",
        "инн контрагент", "инн получател",
        "наименование получател",
    ]
    for p in priority:
        idx = key_patterns.get(p)
        if idx is not None and idx not in seen:
            indices.append(idx)
            seen.add(idx)

    return indices if len(indices) >= 3 else None


def _parse_llm_json(content: str) -> dict | None:
    """Извлечение JSON из ответа LLM."""
    import json
    if not content:
        return None
    # Прямой парсинг
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass
    # Из markdown блока
    import re
    json_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", content, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass
    # Ищем первый { ... }
    brace_start = content.find("{")
    brace_end = content.rfind("}")
    if brace_start >= 0 and brace_end > brace_start:
        try:
            return json.loads(content[brace_start:brace_end + 1])
        except json.JSONDecodeError:
            pass
    return None


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
    2. PDF/JPG/PNG/TIFF → OCR + LLM (Qwen 2.5 72B vision)
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
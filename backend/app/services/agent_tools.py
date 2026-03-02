"""
Agent Tools Registry — реестр инструментов AI-агента.
Архитектура: АРХИТЕКТУРА_AI_AGENT.md → раздел 3.4

Каждый инструмент:
1. Имеет JSON-описание для LLM (OpenAI tool calling format)
2. Имеет Python-функцию (handler), которая выполняет действие
3. Регистрируется в реестре через декоратор @register_tool

Агент получает список tools, LLM выбирает какой вызвать,
Agent Service выполняет handler и возвращает результат LLM.
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


# ─── Типы ──────────────────────────────────────────────────

ToolHandler = Callable[..., Coroutine[Any, Any, dict[str, Any]]]


@dataclass
class ToolDefinition:
    """Определение инструмента агента."""
    name: str
    description: str
    parameters: dict[str, Any]
    handler: ToolHandler
    category: str = "general"
    requires_confirmation: bool = False


class ToolRegistry:
    """Реестр всех инструментов AI-агента."""

    def __init__(self):
        self._tools: dict[str, ToolDefinition] = {}

    def tool(
        self,
        name: str,
        description: str,
        parameters: dict[str, Any],
        category: str = "general",
        requires_confirmation: bool = False,
    ):
        """Декоратор для регистрации инструмента."""
        def decorator(func: ToolHandler) -> ToolHandler:
            self._tools[name] = ToolDefinition(
                name=name,
                description=description,
                parameters=parameters,
                handler=func,
                category=category,
                requires_confirmation=requires_confirmation,
            )
            logger.debug("Registered agent tool: %s (%s)", name, category)
            return func
        return decorator

    def register(self, tool_def: ToolDefinition):
        self._tools[tool_def.name] = tool_def

    def get_tool(self, name: str) -> ToolDefinition | None:
        return self._tools.get(name)

    def get_all_tools(self) -> list[ToolDefinition]:
        return list(self._tools.values())

    def get_tools_by_category(self, category: str) -> list[ToolDefinition]:
        return [t for t in self._tools.values() if t.category == category]

    def get_tools_for_llm(self, categories: list[str] | None = None) -> list[dict[str, Any]]:
        tools = self._tools.values()
        if categories:
            tools = [t for t in tools if t.category in categories]
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters,
                },
            }
            for t in tools
        ]

    async def execute(
        self,
        tool_name: str,
        db: AsyncSession,
        user_id: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        tool = self._tools.get(tool_name)
        if not tool:
            raise ValueError(f"Unknown tool: {tool_name}")
        logger.info("Executing tool: %s with args: %s", tool_name, kwargs)
        try:
            result = await tool.handler(db=db, user_id=user_id, **kwargs)
            return result
        except Exception as e:
            logger.error("Tool %s failed: %s", tool_name, str(e), exc_info=True)
            return {"error": True, "error_message": str(e), "tool": tool_name}

    def parse_tool_call_arguments(self, arguments: str) -> dict[str, Any]:
        try:
            return json.loads(arguments)
        except json.JSONDecodeError:
            logger.error("Failed to parse tool call arguments: %s", arguments)
            return {}


# ─── Глобальный реестр ──────────────────────────────────────

tool_registry = ToolRegistry()


# ═══════════════════════════════════════════════════════════════
# РЕГИСТРАЦИЯ ИНСТРУМЕНТОВ
# ═══════════════════════════════════════════════════════════════


# ─── DATA: получение данных ──────────────────────────────────


@tool_registry.tool(
    name="get_uploaded_files",
    description=(
        "Получить список загруженных файлов, ожидающих обработки. "
        "Используй когда нужно узнать какие файлы загружены и их статус."
    ),
    parameters={
        "type": "object",
        "properties": {
            "status": {
                "type": "string",
                "enum": ["queued", "processing", "completed", "error"],
                "description": "Фильтр по статусу. По умолчанию 'queued'.",
            },
            "limit": {
                "type": "integer",
                "description": "Максимальное количество файлов. По умолчанию 20.",
            },
        },
        "required": [],
    },
    category="data",
)
async def tool_get_uploaded_files(
    db: AsyncSession, user_id: str, **kwargs: Any
) -> dict[str, Any]:
    """Получить список загруженных файлов."""
    from app.models.uploaded_file import UploadedFile

    status_filter = kwargs.get("status", "queued")
    limit = kwargs.get("limit", 20)

    result = await db.execute(
        select(UploadedFile).where(
            UploadedFile.user_id == user_id,
            UploadedFile.processing_status == status_filter,
        ).limit(limit)
    )
    files = list(result.scalars().all())

    return {
        "files": [
            {
                "id": f.id,
                "filename": f.original_filename,
                "file_type": f.file_type,
                "status": f.processing_status,
                "uploaded_at": str(f.created_at),
            }
            for f in files
        ],
        "total": len(files),
    }


@tool_registry.tool(
    name="get_business_context",
    description=(
        "Получить текущий контекст бизнеса: доходы/расходы за период, "
        "оценка налогов (УСН, НДС), количество неподтверждённых операций, "
        "необработанных документов, ближайшие и просроченные сроки."
    ),
    parameters={
        "type": "object",
        "properties": {
            "period": {
                "type": "string",
                "description": "Период: 'quarter', 'year'. По умолчанию 'quarter'.",
            },
        },
        "required": [],
    },
    category="data",
)
async def tool_get_business_context(
    db: AsyncSession, user_id: str, **kwargs: Any
) -> dict[str, Any]:
    """Сбор контекста бизнеса через DashboardService."""
    from datetime import date
    from app.models.user import User
    from app.services.dashboard_service import DashboardService

    period = kwargs.get("period", "quarter")

    result_db = await db.execute(select(User).where(User.id == user_id))
    user = result_db.scalar_one_or_none()
    if not user:
        return {"error": True, "error_message": f"Пользователь {user_id} не найден"}

    today = date.today()
    if period == "year":
        period_start = date(today.year, 1, 1)
    else:
        q = (today.month - 1) // 3
        period_start = date(today.year, q * 3 + 1, 1)
    period_end = today

    service = DashboardService(db)
    dashboard = await service.get_dashboard(
        user=user,
        period_start=period_start,
        period_end=period_end,
    )

    return {
        "status": "ok",
        "period_start": str(dashboard.period_start),
        "period_end": str(dashboard.period_end),
        "income_total": str(dashboard.income_total),
        "expense_total": str(dashboard.expense_total),
        "net_profit": str(dashboard.net_profit),
        "tax_usn_estimated": str(dashboard.tax_usn_estimated),
        "tax_vat_estimated": str(dashboard.tax_vat_estimated),
        "unconfirmed_operations_count": dashboard.unconfirmed_operations_count,
        "unprocessed_documents_count": dashboard.unprocessed_documents_count,
        "upcoming_events_count": len(dashboard.upcoming_events),
        "overdue_events_count": len(dashboard.overdue_events),
        "overdue_events": [
            {"title": e.title, "deadline": str(e.deadline)} for e in dashboard.overdue_events
        ],
        "upcoming_events": [
            {"title": e.title, "deadline": str(e.deadline)} for e in dashboard.upcoming_events[:5]
        ],
    }


@tool_registry.tool(
    name="query_egrul",
    description=(
        "Проверить контрагента в ЕГРЮЛ/ЕГРИП по ИНН. "
        "Возвращает название, адрес, статус (действующий/ликвидирован). "
        "Требует подключения к API ФНС (Этап 2)."
    ),
    parameters={
        "type": "object",
        "properties": {
            "inn": {
                "type": "string",
                "description": "ИНН контрагента (10 или 12 цифр)",
            },
        },
        "required": ["inn"],
    },
    category="data",
)
async def tool_query_egrul(
    db: AsyncSession, user_id: str, **kwargs: Any
) -> dict[str, Any]:
    """Проверка контрагента в ЕГРЮЛ. Требует API ФНС (Этап 2)."""
    inn = kwargs.get("inn", "")
    # Валидация ИНН
    if not inn or len(inn) not in (10, 12) or not inn.isdigit():
        return {"error": True, "error_message": f"Некорректный ИНН: {inn}. Ожидается 10 или 12 цифр."}
    return {
        "status": "not_implemented",
        "message": (
            f"Проверка ИНН {inn} в ЕГРЮЛ/ЕГРИП требует подключения к API ФНС, "
            f"которое будет реализовано на Этапе 2 (интеграции)."
        ),
        "inn": inn,
    }


# ─── ANALYSIS: парсинг и распознавание ───────────────────────


@tool_registry.tool(
    name="recognize_document",
    description=(
        "Распознать документ через OCR + ИИ-анализ. "
        "Принимает ID файла (PDF, изображение, скан). "
        "Возвращает тип документа, реквизиты, суммы, НДС в структурированном JSON."
    ),
    parameters={
        "type": "object",
        "properties": {
            "file_id": {"type": "string", "description": "ID файла из uploaded_files"},
        },
        "required": ["file_id"],
    },
    category="analysis",
)
async def tool_recognize_document(
    db: AsyncSession, user_id: str, **kwargs: Any
) -> dict[str, Any]:
    """OCR + ИИ-распознавание документа через OcrService."""
    import os
    from app.models.uploaded_file import UploadedFile
    from app.services.ocr_service import process_document_image, map_recognized_to_document_dict
    from app.constants.enums import FileType

    file_id = kwargs.get("file_id", "")
    if not file_id:
        return {"error": True, "error_message": "file_id не указан"}

    # Получаем файл
    result = await db.execute(
        select(UploadedFile).where(
            UploadedFile.id == file_id,
            UploadedFile.user_id == user_id,
        )
    )
    uploaded_file = result.scalar_one_or_none()
    if not uploaded_file:
        return {"error": True, "error_message": f"Файл {file_id} не найден"}

    # Читаем файл с диска
    file_path = uploaded_file.stored_path
    if not os.path.exists(file_path):
        return {"error": True, "error_message": f"Файл не найден на диске: {file_path}"}

    with open(file_path, "rb") as f:
        file_data = f.read()

    # Определяем тип файла
    file_type = uploaded_file.file_type
    if isinstance(file_type, str):
        try:
            file_type = FileType(file_type)
        except ValueError:
            file_type = FileType.OTHER

    # Запускаем OCR-пайплайн
    try:
        recognized = await process_document_image(file_data, file_type)
    except Exception as e:
        logger.error("OCR pipeline failed for file %s: %s", file_id, e, exc_info=True)
        return {"error": True, "error_message": f"Ошибка OCR: {str(e)}"}

    return {
        "status": "recognized" if recognized.is_valid else "recognized_with_errors",
        "file_id": file_id,
        "doc_type": recognized.doc_type.value,
        "confidence": recognized.confidence_score,
        "is_valid": recognized.is_valid,
        "doc_number": recognized.doc_number,
        "doc_date": str(recognized.doc_date) if recognized.doc_date else None,
        "total_with_vat": str(recognized.total_with_vat),
        "vat_amount": str(recognized.vat_amount),
        "seller_name": recognized.seller.name if recognized.seller else None,
        "seller_inn": recognized.seller.inn if recognized.seller else None,
        "items_count": len(recognized.items),
        "warnings": recognized.warnings,
        "errors": recognized.errors,
    }


@tool_registry.tool(
    name="parse_xml_document",
    description=(
        "Распарсить XML-документ в формате ФНС (счёт-фактура, УПД, банковская выписка). "
        "Извлекает все реквизиты в структурированный JSON."
    ),
    parameters={
        "type": "object",
        "properties": {
            "file_id": {"type": "string", "description": "ID XML-файла из uploaded_files"},
        },
        "required": ["file_id"],
    },
    category="analysis",
)
async def tool_parse_xml_document(
    db: AsyncSession, user_id: str, **kwargs: Any
) -> dict[str, Any]:
    """Парсинг XML ФНС. Stub — требует интеграции с xml_parser_service."""
    file_id = kwargs.get("file_id", "")
    return {
        "status": "not_implemented",
        "message": f"XML-парсер для файла {file_id} ещё не подключён к tool.",
        "file_id": file_id,
    }


@tool_registry.tool(
    name="parse_table_file",
    description=(
        "Распарсить табличный файл (CSV, Excel). "
        "Автоопределяет формат (банковская выписка, отчёт ОФД и т.д.) и извлекает данные."
    ),
    parameters={
        "type": "object",
        "properties": {
            "file_id": {"type": "string", "description": "ID CSV/Excel файла из uploaded_files"},
        },
        "required": ["file_id"],
    },
    category="analysis",
)
async def tool_parse_table_file(
    db: AsyncSession, user_id: str, **kwargs: Any
) -> dict[str, Any]:
    """Парсинг CSV/Excel. Stub — требует интеграции с csv_parser_service."""
    file_id = kwargs.get("file_id", "")
    return {
        "status": "not_implemented",
        "message": f"Табличный парсер для файла {file_id} ещё не подключён к tool.",
        "file_id": file_id,
    }


# ─── ANALYSIS: классификация операций (РЕАЛИЗОВАНО 1.10) ─────


@tool_registry.tool(
    name="classify_operation",
    description=(
        "Классифицировать банковскую операцию: определить категорию (доход/расход/не учитывать), "
        "выделить НДС, привязать к контрагенту. "
        "Используй для одной операции."
    ),
    parameters={
        "type": "object",
        "properties": {
            "operation_id": {"type": "string", "description": "ID банковской операции"},
        },
        "required": ["operation_id"],
    },
    category="analysis",
)
async def tool_classify_operation(
    db: AsyncSession, user_id: str, **kwargs: Any
) -> dict[str, Any]:
    """Классификация одной операции через ИИ."""
    from app.models.bank_operation import BankOperation
    from app.services.classifier_service import (
        classify_bank_operation,
        apply_classification,
        match_operation_with_document,
        match_operation_with_receipt,
        apply_match_result,
    )

    operation_id = kwargs.get("operation_id", "")
    if not operation_id:
        return {"error": True, "error_message": "operation_id не указан"}

    result = await db.execute(
        select(BankOperation).where(
            BankOperation.id == operation_id,
            BankOperation.user_id == user_id,
        )
    )
    operation = result.scalar_one_or_none()
    if not operation:
        return {"error": True, "error_message": f"Операция {operation_id} не найдена"}

    cls_result = await classify_bank_operation(db, operation)
    await apply_classification(db, operation.id, user_id, cls_result)

    doc_match = await match_operation_with_document(db, operation)
    if doc_match.matched:
        await apply_match_result(db, operation.id, user_id, doc_match)

    receipt_match = None
    if operation.is_income:
        receipt_match = await match_operation_with_receipt(db, operation)
        if receipt_match.matched:
            await apply_match_result(db, operation.id, user_id, receipt_match)

    await db.flush()

    return {
        "status": "classified",
        "operation_id": operation_id,
        "category": cls_result.category.value,
        "is_income": cls_result.is_income,
        "is_expense": cls_result.is_expense,
        "vat_amount": str(cls_result.vat_amount) if cls_result.vat_amount is not None else None,
        "confidence": cls_result.confidence,
        "reasoning": cls_result.reasoning,
        "source": cls_result.source,
        "document_matched": doc_match.matched if doc_match else False,
        "receipt_matched": receipt_match.matched if receipt_match else False,
    }


@tool_registry.tool(
    name="classify_operations_batch",
    description=(
        "Пакетная классификация нескольких банковских операций. "
        "Эффективнее чем classify_operation для большого количества."
    ),
    parameters={
        "type": "object",
        "properties": {
            "operation_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Массив ID банковских операций. Если пуст — классифицирует все PENDING.",
            },
        },
        "required": [],
    },
    category="analysis",
)
async def tool_classify_operations_batch(
    db: AsyncSession, user_id: str, **kwargs: Any
) -> dict[str, Any]:
    """Пакетная классификация операций через ИИ."""
    from app.models.bank_operation import BankOperation
    from app.constants.enums import OperationStatus
    from app.services.classifier_service import (
        classify_operations_batch,
        apply_classification,
    )

    operation_ids = kwargs.get("operation_ids", [])

    if operation_ids:
        result = await db.execute(
            select(BankOperation).where(
                BankOperation.id.in_(operation_ids),
                BankOperation.user_id == user_id,
            )
        )
        operations = list(result.scalars().all())
    else:
        result = await db.execute(
            select(BankOperation).where(
                BankOperation.user_id == user_id,
                BankOperation.status == OperationStatus.PENDING,
            ).order_by(BankOperation.operation_date).limit(50)
        )
        operations = list(result.scalars().all())

    if not operations:
        return {"status": "ok", "message": "Нет операций для классификации", "total": 0}

    classifications = await classify_operations_batch(db, operations)

    classified = 0
    pending = 0
    for op, cls_result in zip(operations, classifications):
        try:
            await apply_classification(db, op.id, user_id, cls_result)
            if cls_result.confidence >= 0.9:
                classified += 1
            else:
                pending += 1
        except Exception:
            pass

    await db.flush()

    return {
        "status": "ok",
        "total": len(operations),
        "classified": classified,
        "pending_confirmation": pending,
        "message": f"Классифицировано {classified} операций, {pending} требуют подтверждения",
    }


@tool_registry.tool(
    name="match_operation_document",
    description=(
        "Сопоставить банковскую операцию с документом (счёт-фактура, УПД, чек ОФД). "
        "Ищет документ по сумме, дате, контрагенту."
    ),
    parameters={
        "type": "object",
        "properties": {
            "operation_id": {"type": "string", "description": "ID банковской операции"},
        },
        "required": ["operation_id"],
    },
    category="analysis",
)
async def tool_match_operation_document(
    db: AsyncSession, user_id: str, **kwargs: Any
) -> dict[str, Any]:
    """Сопоставление операции с документом."""
    from app.models.bank_operation import BankOperation
    from app.services.classifier_service import (
        match_operation_with_document,
        match_operation_with_receipt,
        apply_match_result,
    )

    operation_id = kwargs.get("operation_id", "")
    if not operation_id:
        return {"error": True, "error_message": "operation_id не указан"}

    result = await db.execute(
        select(BankOperation).where(
            BankOperation.id == operation_id,
            BankOperation.user_id == user_id,
        )
    )
    operation = result.scalar_one_or_none()
    if not operation:
        return {"error": True, "error_message": f"Операция {operation_id} не найдена"}

    doc_match = await match_operation_with_document(db, operation)
    receipt_match = await match_operation_with_receipt(db, operation)

    if doc_match.matched:
        await apply_match_result(db, operation.id, user_id, doc_match)
    if receipt_match.matched:
        await apply_match_result(db, operation.id, user_id, receipt_match)

    await db.flush()

    return {
        "status": "ok",
        "operation_id": operation_id,
        "document_match": {
            "matched": doc_match.matched,
            "entity_id": doc_match.entity_id if doc_match.matched else None,
            "score": doc_match.match_score,
            "reason": doc_match.match_reason,
        },
        "receipt_match": {
            "matched": receipt_match.matched,
            "entity_id": receipt_match.entity_id if receipt_match.matched else None,
            "score": receipt_match.match_score,
            "reason": receipt_match.match_reason,
        },
    }


@tool_registry.tool(
    name="detect_duplicates",
    description=(
        "Найти дубли операций за период. "
        "Одна продажа может учитываться и через ОФД, и через банк — это нужно выявить."
    ),
    parameters={
        "type": "object",
        "properties": {
            "date_from": {"type": "string", "description": "Начало периода (YYYY-MM-DD)"},
            "date_to": {"type": "string", "description": "Конец периода (YYYY-MM-DD)"},
        },
        "required": ["date_from", "date_to"],
    },
    category="analysis",
)
async def tool_detect_duplicates(
    db: AsyncSession, user_id: str, **kwargs: Any
) -> dict[str, Any]:
    """Поиск потенциальных дублей операций."""
    from datetime import datetime
    from app.services.classifier_service import detect_duplicate_operations

    date_from_str = kwargs.get("date_from", "")
    date_to_str = kwargs.get("date_to", "")

    try:
        date_from = datetime.strptime(date_from_str, "%Y-%m-%d").date()
        date_to = datetime.strptime(date_to_str, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return {"error": True, "error_message": "Неверный формат дат. Ожидается YYYY-MM-DD."}

    duplicates = await detect_duplicate_operations(db, user_id, date_from, date_to)

    return {
        "status": "ok",
        "total_groups": len(duplicates),
        "duplicates": [
            {
                "operation_ids": group.operation_ids,
                "reason": group.reason,
                "amount": str(group.total_amount),
                "date": str(group.date) if group.date else None,
            }
            for group in duplicates
        ],
    }


@tool_registry.tool(
    name="detect_anomalies",
    description=(
        "Найти аномалии в данных: необычно большие суммы, продажи без чеков, "
        "оплаты поставщикам без счетов-фактур, расхождения НДС."
    ),
    parameters={
        "type": "object",
        "properties": {
            "date_from": {"type": "string", "description": "Начало периода (YYYY-MM-DD)"},
            "date_to": {"type": "string", "description": "Конец периода (YYYY-MM-DD)"},
        },
        "required": ["date_from", "date_to"],
    },
    category="analysis",
)
async def tool_detect_anomalies(
    db: AsyncSession, user_id: str, **kwargs: Any
) -> dict[str, Any]:
    """Поиск аномалий. Stub."""
    return {"status": "not_implemented", "message": "Поиск аномалий ещё не реализован."}


# ─── ACCOUNTING: расчёты и учёт ──────────────────────────────


@tool_registry.tool(
    name="calculate_taxes",
    description=(
        "Рассчитать налоги за период: УСН (15%), НДС (22%), НДФЛ (13%), страховые взносы. "
        "Возвращает суммы к уплате по каждому налогу."
    ),
    parameters={
        "type": "object",
        "properties": {
            "year": {"type": "integer", "description": "Год"},
            "quarter": {"type": "integer", "description": "Квартал (1-4). Если не указан, считает за весь год."},
            "tax_types": {
                "type": "array",
                "items": {"type": "string", "enum": ["usn", "vat", "ndfl", "insurance_employee", "insurance_ip"]},
                "description": "Какие налоги считать. По умолчанию все.",
            },
        },
        "required": ["year"],
    },
    category="accounting",
)
async def tool_calculate_taxes(
    db: AsyncSession, user_id: str, **kwargs: Any
) -> dict[str, Any]:
    """Расчёт налогов за период через TaxCalculationService."""
    from app.models.user import User
    from app.services.tax_calculation_service import (
        TaxCalculationService,
        get_quarter_dates,
        get_year_dates,
    )
    from app.constants.enums import PeriodType, TaxType

    year = kwargs.get("year", 2026)
    quarter = kwargs.get("quarter")
    tax_types = kwargs.get("tax_types")

    result_db = await db.execute(select(User).where(User.id == user_id))
    user = result_db.scalar_one_or_none()
    if not user:
        return {"error": True, "error_message": f"Пользователь {user_id} не найден"}

    service = TaxCalculationService(db, user)
    results: dict[str, Any] = {"status": "ok", "year": year, "quarter": quarter, "calculations": {}}

    should_calc_all = tax_types is None or len(tax_types) == 0
    warnings: list[str] = []

    if should_calc_all or "usn" in tax_types:
        try:
            if quarter:
                usn = await service.calculate_usn_advance(year, quarter)
                period_start, period_end = get_quarter_dates(year, quarter)
            else:
                usn = await service.calculate_usn(year, period_type=PeriodType.YEAR)
                period_start, period_end = get_year_dates(year)

            await service.save_calculation(
                tax_type=TaxType.USN,
                period_type=PeriodType.QUARTER if quarter else PeriodType.YEAR,
                period_start=period_start,
                period_end=period_end,
                result_data=usn,
            )

            results["calculations"]["usn"] = {
                "income_total": str(usn.income_total),
                "expense_total": str(usn.expense_total),
                "tax_base": str(usn.tax_base),
                "tax_rate": str(usn.tax_rate),
                "tax_amount": str(usn.tax_amount),
                "tax_to_pay": str(usn.tax_to_pay),
                "is_minimum_tax": usn.is_minimum_tax,
            }
            warnings.extend(usn.warnings)
        except Exception as e:
            results["calculations"]["usn"] = {"error": str(e)}

    if should_calc_all or "vat" in tax_types:
        try:
            target_quarter = quarter or 4
            vat = await service.calculate_vat(year, target_quarter)

            q_start, q_end = get_quarter_dates(year, target_quarter)
            await service.save_calculation(
                tax_type=TaxType.VAT,
                period_type=PeriodType.QUARTER,
                period_start=q_start,
                period_end=q_end,
                result_data=vat,
            )

            results["calculations"]["vat"] = {
                "vat_charged": str(vat.vat_charged),
                "vat_deductible": str(vat.vat_deductible),
                "vat_payable": str(vat.vat_payable),
                "monthly_payments": [str(p) for p in vat.monthly_payments],
            }
            warnings.extend(vat.warnings)
        except Exception as e:
            results["calculations"]["vat"] = {"error": str(e)}

    if should_calc_all or "insurance_ip" in tax_types:
        try:
            ip = await service.calculate_ip_fixed_contributions(year)

            y_start, y_end = get_year_dates(year)
            await service.save_calculation(
                tax_type=TaxType.INSURANCE_IP,
                period_type=PeriodType.YEAR,
                period_start=y_start,
                period_end=y_end,
                result_data=ip,
            )

            results["calculations"]["insurance_ip"] = {
                "fixed_amount": str(ip.fixed_amount),
                "additional_amount": str(ip.additional_amount),
                "total_amount": str(ip.total_amount),
                "already_paid": str(ip.already_paid),
                "remaining": str(ip.remaining),
            }
            warnings.extend(ip.warnings)
        except Exception as e:
            results["calculations"]["insurance_ip"] = {"error": str(e)}

    results["warnings"] = warnings
    await db.flush()
    return results


@tool_registry.tool(
    name="generate_kudir",
    description="Сформировать Книгу учёта доходов и расходов (КУДиР) за период.",
    parameters={
        "type": "object",
        "properties": {
            "year": {"type": "integer", "description": "Год"},
            "quarter": {"type": "integer", "description": "Квартал (1-4), необязательно"},
            "overwrite": {"type": "boolean", "description": "Перезаписать существующие записи. По умолчанию false."},
        },
        "required": ["year"],
    },
    category="accounting",
)
async def tool_generate_kudir(
    db: AsyncSession, user_id: str, **kwargs: Any
) -> dict[str, Any]:
    """Формирование КУДиР через KudirService."""
    from app.services.kudir_service import KudirService

    year = kwargs.get("year", 2026)
    quarter = kwargs.get("quarter")
    overwrite = kwargs.get("overwrite", False)

    service = KudirService(db)
    try:
        result = await service.generate(
            user_id=user_id,
            year=year,
            quarter=quarter,
            overwrite=overwrite,
        )
        await db.flush()
        return {
            "status": "ok",
            "message": (
                f"КУДиР за {year}"
                + (f" Q{quarter}" if quarter else "")
                + f": создано {result['created_entries']} записей. "
                f"Доходы: {result['total_income']}, Расходы: {result['total_expense']}, "
                f"Результат: {result['net_result']}"
            ),
            **result,
        }
    except Exception as e:
        return {"error": True, "error_message": f"Ошибка формирования КУДиР: {str(e)}"}


@tool_registry.tool(
    name="generate_purchase_book",
    description="Сформировать книгу покупок (входящий НДС) за квартал.",
    parameters={
        "type": "object",
        "properties": {
            "year": {"type": "integer", "description": "Год"},
            "quarter": {"type": "integer", "description": "Квартал (1-4)"},
            "overwrite": {"type": "boolean", "description": "Перезаписать существующие записи. По умолчанию false."},
        },
        "required": ["year", "quarter"],
    },
    category="accounting",
)
async def tool_generate_purchase_book(
    db: AsyncSession, user_id: str, **kwargs: Any
) -> dict[str, Any]:
    """Формирование книги покупок через PurchaseBookService."""
    from app.services.purchase_book_service import PurchaseBookService

    year = kwargs.get("year", 2026)
    quarter = kwargs.get("quarter", 1)

    service = PurchaseBookService(db)
    try:
        result = await service.generate(
            user_id=user_id,
            year=year,
            quarter=quarter,
            overwrite=kwargs.get("overwrite", False),
        )
        await db.flush()
        return {
            "status": "ok",
            "message": (
                f"Книга покупок за {year} Q{quarter}: "
                f"создано {result['created_entries']} записей. "
                f"Без НДС: {result['total_without_vat']}, "
                f"НДС: {result['total_vat']}, "
                f"С НДС: {result['total_with_vat']}"
            ),
            **result,
        }
    except Exception as e:
        return {"error": True, "error_message": f"Ошибка формирования книги покупок: {str(e)}"}


@tool_registry.tool(
    name="generate_sales_book",
    description="Сформировать книгу продаж (исходящий НДС) за квартал.",
    parameters={
        "type": "object",
        "properties": {
            "year": {"type": "integer", "description": "Год"},
            "quarter": {"type": "integer", "description": "Квартал (1-4)"},
            "overwrite": {"type": "boolean", "description": "Перезаписать существующие записи. По умолчанию false."},
        },
        "required": ["year", "quarter"],
    },
    category="accounting",
)
async def tool_generate_sales_book(
    db: AsyncSession, user_id: str, **kwargs: Any
) -> dict[str, Any]:
    """Формирование книги продаж через SalesBookService."""
    from app.services.sales_book_service import SalesBookService

    year = kwargs.get("year", 2026)
    quarter = kwargs.get("quarter", 1)

    service = SalesBookService(db)
    try:
        result = await service.generate(
            user_id=user_id,
            year=year,
            quarter=quarter,
            overwrite=kwargs.get("overwrite", False),
        )
        await db.flush()
        return {
            "status": "ok",
            "message": (
                f"Книга продаж за {year} Q{quarter}: "
                f"создано {result['created_entries']} записей. "
                f"Без НДС: {result['total_without_vat']}, "
                f"НДС: {result['total_vat']}, "
                f"С НДС: {result['total_with_vat']}"
            ),
            **result,
        }
    except Exception as e:
        return {"error": True, "error_message": f"Ошибка формирования книги продаж: {str(e)}"}


@tool_registry.tool(
    name="reconcile_data",
    description=(
        "Провести сверку данных между источниками. "
        "Типы: 'sales' (ОФД-Банк), 'purchases' (ЭДО-Банк), 'books' (КУДиР-Книги)."
    ),
    parameters={
        "type": "object",
        "properties": {
            "reconcile_type": {"type": "string", "enum": ["sales", "purchases", "books"], "description": "Тип сверки"},
            "date_from": {"type": "string", "description": "Начало периода (YYYY-MM-DD)"},
            "date_to": {"type": "string", "description": "Конец периода (YYYY-MM-DD)"},
        },
        "required": ["reconcile_type", "date_from", "date_to"],
    },
    category="analysis",
)
async def tool_reconcile_data(
    db: AsyncSession, user_id: str, **kwargs: Any
) -> dict[str, Any]:
    """Сверка данных. Stub."""
    return {"status": "not_implemented", "message": "Сверка данных ещё не реализована."}


# ─── REPORTING: декларации (РЕАЛИЗОВАНО 1.13) ────────────────


@tool_registry.tool(
    name="generate_declaration",
    description=(
        "Сформировать налоговую декларацию в формате XML ФНС. "
        "Поддерживает: УСН (годовая), НДС (квартальная), 6-НДФЛ, РСВ. "
        "Автоматически проводит XSD-валидацию и проверку контрольных соотношений."
    ),
    parameters={
        "type": "object",
        "properties": {
            "declaration_type": {
                "type": "string",
                "enum": ["vat", "usn", "ndfl_6", "rsv"],
                "description": "Тип декларации",
            },
            "year": {"type": "integer", "description": "Отчётный год"},
            "quarter": {
                "type": "integer",
                "description": "Квартал (1-4). Обязателен для НДС.",
            },
        },
        "required": ["declaration_type", "year"],
    },
    category="reporting",
    requires_confirmation=True,
)
async def tool_generate_declaration(
    db: AsyncSession, user_id: str, **kwargs: Any
) -> dict[str, Any]:
    """Генерация XML-декларации через DeclarationGeneratorService."""
    from app.models.user import User
    from app.constants.enums import DeclarationType
    from app.services.declaration_generator_service import DeclarationGeneratorService

    declaration_type_str = kwargs.get("declaration_type", "")
    year = kwargs.get("year", 2026)
    quarter = kwargs.get("quarter")

    type_map = {
        "vat": DeclarationType.VAT,
        "usn": DeclarationType.USN,
        "ndfl_6": DeclarationType.NDFL_6,
        "rsv": DeclarationType.RSV,
    }
    declaration_type = type_map.get(declaration_type_str)
    if not declaration_type:
        return {
            "error": True,
            "error_message": f"Неизвестный тип декларации: {declaration_type_str}. "
                             f"Допустимые: vat, usn, ndfl_6, rsv",
        }

    if declaration_type == DeclarationType.VAT and not quarter:
        return {
            "error": True,
            "error_message": "Для декларации НДС необходимо указать квартал (quarter).",
        }

    result_db = await db.execute(select(User).where(User.id == user_id))
    user = result_db.scalar_one_or_none()
    if not user:
        return {"error": True, "error_message": f"Пользователь {user_id} не найден"}

    service = DeclarationGeneratorService(db, user)

    try:
        result = await service.generate(
            declaration_type=declaration_type,
            year=year,
            quarter=quarter,
        )
        await db.flush()
    except Exception as e:
        logger.error("Declaration generation failed: %s", str(e), exc_info=True)
        return {"error": True, "error_message": f"Ошибка генерации декларации: {str(e)}"}

    return {
        "status": "ok",
        "declaration_id": result.declaration_id,
        "declaration_type": result.declaration_type,
        "period": result.period,
        "year": result.year,
        "xml_generated": True,
        "xsd_valid": result.xsd_valid,
        "xsd_errors": result.xsd_errors,
        "control_ratios_valid": result.control_ratios_valid,
        "control_ratios_errors": result.control_ratios_errors,
        "declaration_status": result.status,
        "warnings": result.warnings,
        "message": (
            f"Декларация {result.declaration_type} за {result.period} сформирована. "
            f"Статус: {result.status}. "
            + ("XSD: OK. " if result.xsd_valid else f"XSD: ошибки ({len(result.xsd_errors)}). ")
            + ("КС: OK." if result.control_ratios_valid else f"КС: ошибки ({len(result.control_ratios_errors)}).")
        ),
    }


@tool_registry.tool(
    name="validate_declaration",
    description=(
        "Проверить сформированную декларацию: XSD-валидация XML "
        "и проверка контрольных соотношений ФНС. Обновляет статус декларации."
    ),
    parameters={
        "type": "object",
        "properties": {
            "declaration_id": {
                "type": "string",
                "description": "ID декларации из tax_declarations",
            },
        },
        "required": ["declaration_id"],
    },
    category="reporting",
)
async def tool_validate_declaration(
    db: AsyncSession, user_id: str, **kwargs: Any
) -> dict[str, Any]:
    """Валидация декларации через DeclarationGeneratorService."""
    from app.models.user import User
    from app.services.declaration_generator_service import DeclarationGeneratorService

    declaration_id = kwargs.get("declaration_id", "")
    if not declaration_id:
        return {"error": True, "error_message": "declaration_id не указан"}

    result_db = await db.execute(select(User).where(User.id == user_id))
    user = result_db.scalar_one_or_none()
    if not user:
        return {"error": True, "error_message": f"Пользователь {user_id} не найден"}

    service = DeclarationGeneratorService(db, user)

    try:
        result = await service.validate(declaration_id)
        await db.flush()
    except ValueError as e:
        return {"error": True, "error_message": str(e)}
    except Exception as e:
        logger.error("Declaration validation failed: %s", str(e), exc_info=True)
        return {"error": True, "error_message": f"Ошибка валидации: {str(e)}"}

    return {
        "status": "ok",
        "declaration_id": result["declaration_id"],
        "declaration_status": result["status"],
        "xsd_valid": result["xsd_valid"],
        "xsd_errors": result["xsd_errors"],
        "control_ratios_valid": result["control_ratios_valid"],
        "control_ratios_errors": result["control_ratios_errors"],
        "message": (
            f"Валидация декларации {declaration_id}: "
            + ("XSD: OK. " if result["xsd_valid"] else f"XSD: ошибки ({len(result['xsd_errors'])}). ")
            + ("КС: OK." if result["control_ratios_valid"] else f"КС: ошибки ({len(result['control_ratios_errors'])}).")
        ),
    }


# ─── NOTIFICATION: уведомления ───────────────────────────────


@tool_registry.tool(
    name="get_upcoming_deadlines",
    description="Получить ближайшие сроки сдачи отчётности и оплаты налогов.",
    parameters={
        "type": "object",
        "properties": {
            "days_ahead": {"type": "integer", "description": "За сколько дней вперёд показать. По умолчанию 30."},
        },
        "required": [],
    },
    category="notification",
)
async def tool_get_upcoming_deadlines(
    db: AsyncSession, user_id: str, **kwargs: Any
) -> dict[str, Any]:
    """Получение ближайших сроков через TaxCalendarService."""
    from app.services.tax_calendar_service import TaxCalendarService

    days_ahead = kwargs.get("days_ahead", 30)

    service = TaxCalendarService(db)
    await service.update_overdue_statuses(user_id=user_id)

    upcoming = await service.get_upcoming(user_id, days_ahead=days_ahead)
    overdue = await service.get_overdue(user_id)
    counts = await service.get_counts(user_id)

    return {
        "status": "ok",
        "upcoming_count": counts["upcoming"],
        "overdue_count": counts["overdue"],
        "completed_count": counts["completed"],
        "upcoming_events": [
            {
                "id": str(e.id),
                "title": e.title,
                "deadline": str(e.deadline),
                "event_type": e.event_type.value,
                "description": e.description,
            }
            for e in upcoming
        ],
        "overdue_events": [
            {
                "id": str(e.id),
                "title": e.title,
                "deadline": str(e.deadline),
                "event_type": e.event_type.value,
                "description": e.description,
            }
            for e in overdue
        ],
    }


@tool_registry.tool(
    name="send_notification",
    description="Отправить уведомление пользователю (dashboard, email, telegram).",
    parameters={
        "type": "object",
        "properties": {
            "channel": {"type": "string", "enum": ["dashboard", "email", "telegram"], "description": "Канал"},
            "message": {"type": "string", "description": "Текст уведомления"},
            "priority": {"type": "string", "enum": ["low", "normal", "high", "critical"], "description": "Приоритет"},
        },
        "required": ["channel", "message"],
    },
    category="notification",
)
async def tool_send_notification(
    db: AsyncSession, user_id: str, **kwargs: Any
) -> dict[str, Any]:
    """Отправка уведомления."""
    channel = kwargs.get("channel", "dashboard")
    message = kwargs.get("message", "")
    logger.info("Notification [%s] for user %s: %s", channel, user_id, message)
    return {"status": "sent", "channel": channel, "message": message}


@tool_registry.tool(
    name="request_user_confirmation",
    description=(
        "Запросить подтверждение у пользователя. Используй когда не уверен "
        "в классификации операции, данных документа, или перед важным действием."
    ),
    parameters={
        "type": "object",
        "properties": {
            "question": {"type": "string", "description": "Вопрос пользователю простым языком"},
            "confirmation_type": {
                "type": "string",
                "enum": ["operation_classification", "document_recognition", "tax_calculation", "declaration_submit", "anomaly_resolution", "general"],
                "description": "Тип подтверждения",
            },
            "proposed_data": {"type": "object", "description": "Предлагаемые данные"},
            "options": {"type": "array", "items": {"type": "string"}, "description": "Варианты ответа"},
            "related_entity_type": {"type": "string", "description": "Тип связанной сущности"},
            "related_entity_id": {"type": "string", "description": "ID связанной сущности"},
        },
        "required": ["question", "confirmation_type"],
    },
    category="notification",
)
async def tool_request_user_confirmation(
    db: AsyncSession, user_id: str, **kwargs: Any
) -> dict[str, Any]:
    """Создание запроса подтверждения. Сохраняет в БД."""
    from app.models.agent_confirmation import AgentConfirmation
    from app.constants.enums import AgentConfirmationType, AgentConfirmationStatus

    confirmation = AgentConfirmation(
        user_id=user_id,
        event_id=kwargs.get("_event_id"),
        confirmation_type=kwargs.get("confirmation_type", AgentConfirmationType.GENERAL),
        status=AgentConfirmationStatus.PENDING,
        question=kwargs.get("question", ""),
        proposed_data=kwargs.get("proposed_data"),
        options=kwargs.get("options"),
        related_entity_type=kwargs.get("related_entity_type"),
        related_entity_id=kwargs.get("related_entity_id"),
    )
    db.add(confirmation)
    await db.flush()

    return {
        "status": "confirmation_requested",
        "confirmation_id": confirmation.id,
        "question": confirmation.question,
    }
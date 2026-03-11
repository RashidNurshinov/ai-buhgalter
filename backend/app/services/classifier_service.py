"""
Сервис ИИ-классификации банковских операций.
Пункты плана: 1.10.2–1.10.7

Функции:
- classify_bank_operation() — классификация одной операции через LLM
- classify_operations_batch() — пакетная классификация
- match_operation_with_document() — сопоставление операции с документом
- match_operation_with_receipt() — сопоставление с чеком ОФД
- detect_duplicate_operations() — поиск дублей
- calculate_vat_from_operation() — выделение НДС расчётным путём
"""

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Optional
from collections import defaultdict

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.constants.enums import (
    OperationCategory,
    OperationStatus,
)
from app.models.bank_operation import BankOperation
from app.models.cash_receipt import CashReceipt
from app.models.counterparty import Counterparty
from app.models.document import Document
from app.prompts.operation_classifier import (
    BATCH_CLASSIFIER_PROMPT,
    BATCH_CLASSIFIER_USER_PROMPT,
    OPERATION_CLASSIFIER_PROMPT,
    OPERATION_CLASSIFIER_USER_PROMPT,
)
from app.services.openrouter_client import get_openrouter_client
from app.services.xml_parser_service import _extract_vat_from_purpose

logger = logging.getLogger(__name__)

# Категории, которые считаются доходом для УСН
INCOME_CATEGORIES = {
    OperationCategory.SALES_REVENUE,
    OperationCategory.ACQUIRING,
    OperationCategory.SUPPLIER_RETURN,
    OperationCategory.OTHER_INCOME,
}

# Категории, которые считаются расходом для УСН
EXPENSE_CATEGORIES = {
    OperationCategory.PURCHASE_GOODS,
    OperationCategory.RENT,
    OperationCategory.SALARY,
    OperationCategory.TAXES_AND_FEES,
    OperationCategory.INSURANCE_PAYMENT,
    OperationCategory.BANK_COMMISSION,
    OperationCategory.UTILITIES,
    OperationCategory.TRANSPORT,
    OperationCategory.ADVERTISING,
    OperationCategory.SERVICES,
    OperationCategory.LOAN_REPAYMENT,
    OperationCategory.OTHER_EXPENSE,
}

# Категории без НДС
NO_VAT_CATEGORIES = {
    OperationCategory.TAXES_AND_FEES,
    OperationCategory.INSURANCE_PAYMENT,
    OperationCategory.BANK_COMMISSION,
    OperationCategory.SALARY,
    OperationCategory.OWN_FUNDS,
    OperationCategory.INTERNAL_TRANSFER,
    OperationCategory.LOAN_RECEIVED,
    OperationCategory.PERSONAL_WITHDRAWAL,
    OperationCategory.CASH_WITHDRAWAL,
}

# Ставка НДС для расчётного метода (2026)
VAT_RATE = Decimal("22")
VAT_CALCULATED_RATE = VAT_RATE / (Decimal("100") + VAT_RATE)  # 22/122


# ─── Dataclasses результатов ─────────────────────────────────────


@dataclass
class ClassificationResult:
    """Результат классификации одной операции."""
    category: OperationCategory = OperationCategory.UNCLASSIFIED
    is_income: bool = False
    is_expense: bool = False
    vat_amount: Optional[Decimal] = None
    confidence: float = 0.0
    reasoning: str = ""
    source: str = "llm"  # "llm", "rule", "manual"
    errors: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0 and self.category != OperationCategory.UNCLASSIFIED


@dataclass
class MatchResult:
    """Результат сопоставления операции с документом/чеком."""
    matched: bool = False
    entity_type: str = ""  # "document" или "cash_receipt"
    entity_id: str = ""
    match_score: float = 0.0
    match_reason: str = ""


@dataclass
class DuplicateGroup:
    """Группа потенциальных дублей операций."""
    operation_ids: list[str] = field(default_factory=list)
    reason: str = ""
    total_amount: Decimal = Decimal("0")
    date: Optional[date] = None


# ─── 1.10.7: Расчёт НДС ─────────────────────────────────────────


def calculate_vat_from_operation(
    amount: Decimal,
    purpose: str = "",
    category: OperationCategory = OperationCategory.UNCLASSIFIED,
) -> Optional[Decimal]:
    """
    Выделение НДС из суммы операции.

    Приоритет:
    1. Явное указание в назначении платежа (в т.ч. НДС ...)
    2. «Без НДС» / «НДС не облагается» -> 0
    3. Категории без НДС (налоги, взносы, комиссия банка) -> 0
    4. Расчётный метод: сумма * 22/122
    """
    if amount <= 0:
        return Decimal("0")

    # 1. Пробуем извлечь из назначения платежа
    if purpose:
        vat_from_purpose = _extract_vat_from_purpose(purpose)
        if vat_from_purpose is not None:
            return vat_from_purpose

    # 2. Категории без НДС
    if category in NO_VAT_CATEGORIES:
        return Decimal("0")

    # 3. Расчётный метод для остальных
    vat = (amount * VAT_CALCULATED_RATE).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    return vat


# ─── 1.10.2: Классификация одной операции через LLM ─────────────


async def classify_bank_operation(
    db: AsyncSession,
    operation: BankOperation,
) -> ClassificationResult:
    """
    Классификация одной банковской операции.
    Сначала rule-based, затем LLM если нужно.
    """
    # Шаг 1: Пробуем rule-based
    rule_result = _classify_by_rules(operation)
    if rule_result.confidence >= 0.85:
        logger.info(
            "Operation %s classified by rules: %s (%.2f)",
            operation.id, rule_result.category.value, rule_result.confidence,
        )
        return rule_result

    # Шаг 2: LLM
    try:
        llm_result = await _classify_via_llm(operation)
        if llm_result.confidence > rule_result.confidence:
            return llm_result
        return rule_result
    except Exception as e:
        logger.error("LLM classification failed for %s: %s", operation.id, e)
        if rule_result.confidence > 0:
            return rule_result
        result = ClassificationResult()
        result.errors.append(f"Ошибка LLM: {str(e)}")
        return result


def _classify_by_rules(operation: BankOperation) -> ClassificationResult:
    """Rule-based классификация по назначению платежа."""
    result = ClassificationResult(source="rule")
    purpose = (operation.purpose or "").lower()
    amount = operation.amount or Decimal("0")
    is_incoming = operation.is_income
    is_outgoing = operation.is_expense

    if not purpose:
        return result

    # === ИСХОДЯЩИЕ ===
    if is_outgoing:
        if _matches_any(purpose, ["налог", "усн", "единый налог", "ндс", "ндфл", "госпошлин", "пени по налог", "штраф фнс"]) and _matches_any(purpose, ["уплат", "оплат", "перечисл", "платёж", "платеж", "по требован", "налоговый платёж", "налоговый платеж"]):
            result.category = OperationCategory.TAXES_AND_FEES
            result.is_expense = True
            result.vat_amount = Decimal("0")
            result.confidence = 0.92
            result.reasoning = "Уплата налога"
            return result

        if _matches_any(purpose, ["страхов", "взнос", "пфр", "омс", "фсс", "пенсион", "медицинск", "социальн", "фиксированн"]):
            result.category = OperationCategory.INSURANCE_PAYMENT
            result.is_expense = True
            result.vat_amount = Decimal("0")
            result.confidence = 0.90
            result.reasoning = "Страховые взносы"
            return result

        if _matches_any(purpose, ["зарплат", "заработн", "з/п", "аванс по зп", "заработная плата", "оплата труда"]):
            result.category = OperationCategory.SALARY
            result.is_expense = True
            result.vat_amount = Decimal("0")
            result.confidence = 0.90
            result.reasoning = "Выплата заработной платы"
            return result

        if _matches_any(purpose, ["аренд", "арендн"]):
            result.category = OperationCategory.RENT
            result.is_expense = True
            result.vat_amount = calculate_vat_from_operation(amount, operation.purpose or "", OperationCategory.RENT)
            result.confidence = 0.88
            result.reasoning = "Оплата аренды"
            return result

        if _matches_any(purpose, ["комисси", "обслуживан", "ведение счёта", "ведение счета", "за расчётно-кассовое", "за расчетно-кассовое", "за рко", "тариф банк"]):
            result.category = OperationCategory.BANK_COMMISSION
            result.is_expense = True
            result.vat_amount = Decimal("0")
            result.confidence = 0.93
            result.reasoning = "Банковская комиссия (без НДС по ст.149 НК РФ)"
            return result

        if _matches_any(purpose, ["коммунальн", "электроэнерг", "электричеств", "теплоснабж", "водоснабж", "отоплен", "газоснабж", "за свет"]):
            result.category = OperationCategory.UTILITIES
            result.is_expense = True
            result.vat_amount = calculate_vat_from_operation(amount, operation.purpose or "", OperationCategory.UTILITIES)
            result.confidence = 0.87
            result.reasoning = "Коммунальные услуги"
            return result

        if _matches_any(purpose, ["за товар", "за материал", "закупк", "поставк", "оплата по счёту", "оплата по счету", "оплата по сч.", "за продукц", "за комплектующ"]):
            result.category = OperationCategory.PURCHASE_GOODS
            result.is_expense = True
            result.vat_amount = calculate_vat_from_operation(amount, operation.purpose or "", OperationCategory.PURCHASE_GOODS)
            result.confidence = 0.85
            result.reasoning = "Оплата за товар/материалы"
            return result

        if _matches_any(purpose, ["за услуг", "по договору услуг", "оказан", "за связь", "интернет", "телефон"]):
            result.category = OperationCategory.SERVICES
            result.is_expense = True
            result.vat_amount = calculate_vat_from_operation(amount, operation.purpose or "", OperationCategory.SERVICES)
            result.confidence = 0.82
            result.reasoning = "Оплата услуг"
            return result

        if _matches_any(purpose, ["реклам", "яндекс.директ", "яндекс директ", "google ads", "вконтакте", "продвижен"]):
            result.category = OperationCategory.ADVERTISING
            result.is_expense = True
            result.vat_amount = calculate_vat_from_operation(amount, operation.purpose or "", OperationCategory.ADVERTISING)
            result.confidence = 0.87
            result.reasoning = "Расходы на рекламу"
            return result

        if _matches_any(purpose, ["доставк", "транспорт", "перевозк", "логистик", "грузоперевоз", "курьер"]):
            result.category = OperationCategory.TRANSPORT
            result.is_expense = True
            result.vat_amount = calculate_vat_from_operation(amount, operation.purpose or "", OperationCategory.TRANSPORT)
            result.confidence = 0.85
            result.reasoning = "Транспортные расходы / доставка"
            return result

        if _matches_any(purpose, ["процент", "% по кредит", "% по договору"]):
            result.category = OperationCategory.LOAN_REPAYMENT
            result.is_expense = True
            result.vat_amount = Decimal("0")
            result.confidence = 0.87
            result.reasoning = "Погашение процентов по кредиту"
            return result

        if _matches_any(purpose, ["на личные нужды", "личные расходы", "перевод на карту", "на собственные нужды", "снятие ип на личные"]):
            result.category = OperationCategory.PERSONAL_WITHDRAWAL
            result.is_expense = False
            result.is_income = False
            result.vat_amount = Decimal("0")
            result.confidence = 0.90
            result.reasoning = "Снятие на личные нужды ИП (не расход для УСН)"
            return result

        if _matches_any(purpose, ["снятие наличн", "выдача наличн", "инкассац"]):
            result.category = OperationCategory.CASH_WITHDRAWAL
            result.is_expense = False
            result.is_income = False
            result.vat_amount = Decimal("0")
            result.confidence = 0.88
            result.reasoning = "Снятие наличных"
            return result

        if _matches_any(purpose, ["перевод между счетами", "перевод между своими", "внутренний перевод", "перевод на свой счёт", "перевод на свой счет"]):
            result.category = OperationCategory.INTERNAL_TRANSFER
            result.is_expense = False
            result.is_income = False
            result.vat_amount = Decimal("0")
            result.confidence = 0.90
            result.reasoning = "Перевод между своими счетами"
            return result

    # === ВХОДЯЩИЕ ===
    if is_incoming:
        if _matches_any(purpose, ["эквайринг", "acquiring", "зачисление по терминал", "торговый эквайринг", "безналичная выручка"]):
            result.category = OperationCategory.ACQUIRING
            result.is_income = True
            result.vat_amount = None
            result.confidence = 0.92
            result.reasoning = "Поступление по эквайрингу"
            return result

        if _matches_any(purpose, ["возврат"]) and _matches_any(purpose, ["поставщик", "переплат", "излишне уплач"]):
            result.category = OperationCategory.SUPPLIER_RETURN
            result.is_income = True
            result.vat_amount = calculate_vat_from_operation(amount, operation.purpose or "", OperationCategory.SUPPLIER_RETURN)
            result.confidence = 0.85
            result.reasoning = "Возврат от поставщика"
            return result

        if _matches_any(purpose, ["взнос собственных", "пополнение", "взнос наличных", "внесение наличных", "собственные средства"]):
            result.category = OperationCategory.OWN_FUNDS
            result.is_income = False
            result.is_expense = False
            result.vat_amount = Decimal("0")
            result.confidence = 0.90
            result.reasoning = "Взнос собственных средств ИП (не доход)"
            return result

        if _matches_any(purpose, ["кредит", "заём", "займ", "выдача кредит", "транш", "кредитная линия", "овердрафт"]):
            result.category = OperationCategory.LOAN_RECEIVED
            result.is_income = False
            result.is_expense = False
            result.vat_amount = Decimal("0")
            result.confidence = 0.85
            result.reasoning = "Получение кредита/займа (не доход для УСН)"
            return result

        if _matches_any(purpose, ["перевод между счетами", "перевод между своими", "внутренний перевод", "со своего счёта", "со своего счета"]):
            result.category = OperationCategory.INTERNAL_TRANSFER
            result.is_income = False
            result.is_expense = False
            result.vat_amount = Decimal("0")
            result.confidence = 0.90
            result.reasoning = "Перевод между своими счетами (не доход)"
            return result

        if _matches_any(purpose, ["оплата по счёту", "оплата по счету", "за товар", "за услуг", "по договор", "за выполнен"]):
            result.category = OperationCategory.SALES_REVENUE
            result.is_income = True
            result.vat_amount = calculate_vat_from_operation(amount, operation.purpose or "", OperationCategory.SALES_REVENUE)
            result.confidence = 0.80
            result.reasoning = "Оплата от покупателя (выручка)"
            return result

    return result


def _matches_any(text: str, keywords: list[str]) -> bool:
    """Проверяет, содержит ли текст хотя бы одно из ключевых слов."""
    return any(kw in text for kw in keywords)


async def _classify_via_llm(operation: BankOperation) -> ClassificationResult:
    """Классификация операции через LLM (Qwen 2.5 Coder 32B)."""
    result = ClassificationResult(source="llm")

    direction = "Приход (зачисление)" if operation.is_income else "Расход (списание)"

    user_message = OPERATION_CLASSIFIER_USER_PROMPT.format(
        direction=direction,
        amount=str(operation.amount),
        date=str(operation.operation_date) if operation.operation_date else "не указана",
        counterparty=operation.counterparty_name or "не указан",
        inn=operation.counterparty_inn or "не указан",
        purpose=operation.purpose or "не указано",
    )

    client = get_openrouter_client()
    llm_response = await client.chat_completion(
        messages=[
            {"role": "system", "content": OPERATION_CLASSIFIER_PROMPT},
            {"role": "user", "content": user_message},
        ],
        task="operation_classification",
    )

    parsed = _parse_classification_json(llm_response.content or "")
    if parsed is None:
        result.errors.append(f"Не удалось распарсить ответ LLM: {(llm_response.content or '')[:200]}")
        return result

    try:
        result.category = OperationCategory(parsed.get("category", "unclassified"))
    except ValueError:
        result.category = OperationCategory.UNCLASSIFIED
        result.errors.append(f"Неизвестная категория: {parsed.get('category')}")

    result.is_income = bool(parsed.get("is_income", False))
    result.is_expense = bool(parsed.get("is_expense", False))
    result.confidence = float(parsed.get("confidence", 0.0))
    result.reasoning = parsed.get("reasoning", "")

    vat = parsed.get("vat_amount")
    if vat is not None:
        try:
            result.vat_amount = Decimal(str(vat)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        except (InvalidOperation, ValueError):
            result.vat_amount = None

    if result.is_income and result.is_expense:
        result.is_expense = False
        result.errors.append("LLM вернул is_income=true и is_expense=true одновременно, исправлено")

    _validate_category_direction(result)

    logger.info(
        "LLM classified operation %s: %s (%.2f) - %s",
        operation.id, result.category.value, result.confidence, result.reasoning,
    )
    return result


def _validate_category_direction(result: ClassificationResult):
    """Проверяет и исправляет соответствие категории и направления."""
    if result.category in INCOME_CATEGORIES and not result.is_income:
        result.is_income = True
        result.is_expense = False
    elif result.category in EXPENSE_CATEGORIES and not result.is_expense:
        result.is_expense = True
        result.is_income = False
    elif result.category in (
        OperationCategory.OWN_FUNDS, OperationCategory.INTERNAL_TRANSFER,
        OperationCategory.LOAN_RECEIVED, OperationCategory.PERSONAL_WITHDRAWAL,
        OperationCategory.CASH_WITHDRAWAL,
    ):
        result.is_income = False
        result.is_expense = False


def _parse_classification_json(content: str) -> Optional[dict[str, Any]]:
    """Извлечение JSON из ответа LLM."""
    if not content:
        return None
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass
    json_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", content, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass
    brace_match = re.search(r"\{[^{}]*\}", content, re.DOTALL)
    if brace_match:
        try:
            return json.loads(brace_match.group(0))
        except json.JSONDecodeError:
            pass
    return None


# ─── 1.10.3: Пакетная классификация ─────────────────────────────


async def classify_operations_batch(
    db: AsyncSession,
    operations: list[BankOperation],
    batch_size: int = 15,
) -> list[ClassificationResult]:
    """Пакетная классификация операций."""
    results: list[ClassificationResult] = []
    llm_needed: list[tuple[int, BankOperation]] = []

    for i, op in enumerate(operations):
        rule_result = _classify_by_rules(op)
        results.append(rule_result)
        if rule_result.confidence < 0.85:
            llm_needed.append((i, op))

    if not llm_needed:
        logger.info("Batch: все %d операций классифицированы rule-based", len(operations))
        return results

    logger.info("Batch: %d из %d операций отправляются в LLM", len(llm_needed), len(operations))

    for batch_start in range(0, len(llm_needed), batch_size):
        batch = llm_needed[batch_start:batch_start + batch_size]
        try:
            llm_results = await _classify_batch_via_llm([op for _, op in batch])
            for j, (orig_idx, _) in enumerate(batch):
                if j < len(llm_results) and llm_results[j].confidence > results[orig_idx].confidence:
                    results[orig_idx] = llm_results[j]
        except Exception as e:
            logger.error("Batch LLM classification failed: %s", e)

    return results


async def _classify_batch_via_llm(operations: list[BankOperation]) -> list[ClassificationResult]:
    """Пакетная классификация через LLM."""
    ops_lines = []
    for i, op in enumerate(operations):
        direction = "Приход" if op.is_income else "Расход"
        ops_lines.append(
            f"{i}. [{direction}] {op.amount} руб. | "
            f"{op.operation_date or '?'} | "
            f"{op.counterparty_name or 'не указан'} "
            f"(ИНН: {op.counterparty_inn or '?'}) | "
            f"Назначение: {op.purpose or 'не указано'}"
        )

    operations_text = "\n".join(ops_lines)
    user_message = BATCH_CLASSIFIER_USER_PROMPT.format(operations_text=operations_text)

    client = get_openrouter_client()
    llm_response = await client.chat_completion(
        messages=[
            {"role": "system", "content": BATCH_CLASSIFIER_PROMPT},
            {"role": "user", "content": user_message},
        ],
        task="operation_classification",
    )

    parsed_list = _parse_batch_json(llm_response.content or "")
    if not parsed_list:
        logger.warning("Failed to parse batch LLM response")
        return [ClassificationResult(source="llm") for _ in operations]

    results: list[ClassificationResult] = []
    parsed_by_index = {item.get("operation_index", -1): item for item in parsed_list}

    for i in range(len(operations)):
        parsed = parsed_by_index.get(i)
        if parsed is None:
            results.append(ClassificationResult(source="llm"))
            continue

        result = ClassificationResult(source="llm")
        try:
            result.category = OperationCategory(parsed.get("category", "unclassified"))
        except ValueError:
            result.category = OperationCategory.UNCLASSIFIED

        result.is_income = bool(parsed.get("is_income", False))
        result.is_expense = bool(parsed.get("is_expense", False))
        result.confidence = float(parsed.get("confidence", 0.0))
        result.reasoning = parsed.get("reasoning", "")

        vat = parsed.get("vat_amount")
        if vat is not None:
            try:
                result.vat_amount = Decimal(str(vat)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            except (InvalidOperation, ValueError):
                result.vat_amount = None

        if result.is_income and result.is_expense:
            result.is_expense = False
        _validate_category_direction(result)
        results.append(result)

    return results


def _parse_batch_json(content: str) -> Optional[list[dict[str, Any]]]:
    """Извлечение JSON-массива из ответа LLM."""
    if not content:
        return None
    try:
        data = json.loads(content)
        if isinstance(data, list):
            return data
    except json.JSONDecodeError:
        pass
    json_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", content, re.DOTALL)
    if json_match:
        try:
            data = json.loads(json_match.group(1))
            if isinstance(data, list):
                return data
        except json.JSONDecodeError:
            pass
    bracket_match = re.search(r"\[.*\]", content, re.DOTALL)
    if bracket_match:
        try:
            data = json.loads(bracket_match.group(0))
            if isinstance(data, list):
                return data
        except json.JSONDecodeError:
            pass
    return None


# ─── 1.10.4: Сопоставление операции с документом ─────────────────


async def match_operation_with_document(
    db: AsyncSession,
    operation: BankOperation,
    tolerance_amount: Decimal = Decimal("1.00"),
    tolerance_days: int = 30,
) -> MatchResult:
    """
    Сопоставление банковской операции с документом из БД.
    Ищет по совпадению суммы, ИНН контрагента (через JOIN), близости даты.
    """
    result = MatchResult(entity_type="document")

    if not operation.operation_date:
        return result

    date_from = operation.operation_date - timedelta(days=tolerance_days)
    date_to = operation.operation_date + timedelta(days=tolerance_days)

    # Загружаем документы с counterparty (для доступа к ИНН)
    query = (
        select(Document)
        .options(selectinload(Document.counterparty))
        .where(
            Document.user_id == operation.user_id,
            Document.total_with_vat.isnot(None),
            Document.doc_date.isnot(None),
            Document.doc_date >= date_from,
            Document.doc_date <= date_to,
        )
    )

    db_result = await db.execute(query)
    candidates = list(db_result.scalars().all())

    if not candidates:
        return result

    best_score = 0.0
    best_doc = None

    for doc in candidates:
        score = 0.0

        # Совпадение суммы
        if doc.total_with_vat and operation.amount:
            amount_diff = abs(doc.total_with_vat - operation.amount)
            if amount_diff <= tolerance_amount:
                score += 0.5
            elif amount_diff <= Decimal("10"):
                score += 0.3
            elif amount_diff <= Decimal("100"):
                score += 0.1

        # Совпадение ИНН (через relationship counterparty)
        doc_inn = doc.counterparty.inn if doc.counterparty else None
        if operation.counterparty_inn and doc_inn:
            if operation.counterparty_inn == doc_inn:
                score += 0.35

        # Близость дат
        if doc.doc_date and operation.operation_date:
            days_diff = abs((operation.operation_date - doc.doc_date).days)
            if days_diff == 0:
                score += 0.15
            elif days_diff <= 3:
                score += 0.10
            elif days_diff <= 7:
                score += 0.05

        if score > best_score:
            best_score = score
            best_doc = doc

    if best_doc and best_score >= 0.5:
        result.matched = True
        result.entity_id = best_doc.id
        result.match_score = best_score
        reasons = []
        if best_doc.total_with_vat and operation.amount:
            diff = abs(best_doc.total_with_vat - operation.amount)
            if diff <= tolerance_amount:
                reasons.append(f"сумма совпадает ({best_doc.total_with_vat})")
        best_doc_inn = best_doc.counterparty.inn if best_doc.counterparty else None
        if operation.counterparty_inn and best_doc_inn and operation.counterparty_inn == best_doc_inn:
            reasons.append(f"ИНН совпадает ({best_doc_inn})")
        result.match_reason = "; ".join(reasons)

    return result


# ─── 1.10.5: Сопоставление операции с чеком ОФД ─────────────────


async def match_operation_with_receipt(
    db: AsyncSession,
    operation: BankOperation,
    tolerance_amount: Decimal = Decimal("1.00"),
    tolerance_days: int = 3,
) -> MatchResult:
    """
    Сопоставление банковской операции с чеком ОФД.
    Типичный кейс: зачисление по эквайрингу <-> сумма чеков за день.
    """
    result = MatchResult(entity_type="cash_receipt")

    if not operation.operation_date or not operation.is_income:
        return result

    date_from = operation.operation_date - timedelta(days=tolerance_days)
    date_to = operation.operation_date + timedelta(days=tolerance_days)

    # Запрос чеков за период (без фильтра is_return и linked_operation_id,
    # т.к. CashReceipt может не иметь этих полей)
    query = select(CashReceipt).where(
        CashReceipt.user_id == operation.user_id,
        func.date(CashReceipt.receipt_date) >= date_from,
        func.date(CashReceipt.receipt_date) <= date_to,
    )

    db_result = await db.execute(query)
    receipts = list(db_result.scalars().all())

    if not receipts:
        return result

    # Ищем один чек с совпадающей суммой
    for receipt in receipts:
        if receipt.total and operation.amount:
            diff = abs(receipt.total - operation.amount)
            if diff <= tolerance_amount:
                result.matched = True
                result.entity_id = receipt.id
                result.match_score = 0.9
                result.match_reason = f"Сумма чека {receipt.total} совпадает с операцией {operation.amount}"
                return result

    # Ищем группу чеков за день, сумма которых совпадает
    receipts_by_date: dict[date, list[CashReceipt]] = defaultdict(list)
    for receipt in receipts:
        if receipt.receipt_date:
            rd = receipt.receipt_date.date() if hasattr(receipt.receipt_date, 'date') and callable(receipt.receipt_date.date) else receipt.receipt_date
            receipts_by_date[rd].append(receipt)

    for day, day_receipts in receipts_by_date.items():
        day_total = sum((r.total for r in day_receipts if r.total), Decimal("0"))
        diff = abs(day_total - (operation.amount or Decimal("0")))
        if diff <= tolerance_amount:
            result.matched = True
            result.entity_id = day_receipts[0].id
            result.match_score = 0.75
            result.match_reason = (
                f"Сумма {len(day_receipts)} чеков за {day} = {day_total} "
                f"совпадает с операцией {operation.amount}"
            )
            return result

    return result


# ─── 1.10.6: Поиск дублей ───────────────────────────────────────


async def detect_duplicate_operations(
    db: AsyncSession,
    user_id: str,
    date_from: date,
    date_to: date,
    tolerance_amount: Decimal = Decimal("0.01"),
) -> list[DuplicateGroup]:
    """Поиск потенциальных дублей банковских операций."""
    query = select(BankOperation).where(
        BankOperation.user_id == user_id,
        BankOperation.operation_date >= date_from,
        BankOperation.operation_date <= date_to,
    ).order_by(BankOperation.operation_date, BankOperation.amount)

    db_result = await db.execute(query)
    operations = list(db_result.scalars().all())

    if len(operations) < 2:
        return []

    duplicates: list[DuplicateGroup] = []
    seen_ids: set[str] = set()

    for i in range(len(operations)):
        if operations[i].id in seen_ids:
            continue
        group_ids = [operations[i].id]
        for j in range(i + 1, len(operations)):
            if operations[j].id in seen_ids:
                continue
            if _is_potential_duplicate(operations[i], operations[j], tolerance_amount):
                group_ids.append(operations[j].id)
        if len(group_ids) > 1:
            seen_ids.update(group_ids)
            duplicates.append(DuplicateGroup(
                operation_ids=group_ids,
                reason=_describe_duplicate(operations[i]),
                total_amount=operations[i].amount or Decimal("0"),
                date=operations[i].operation_date,
            ))

    logger.info("Duplicate detection: %d groups in %d operations (%s — %s)", len(duplicates), len(operations), date_from, date_to)
    return duplicates


def _is_potential_duplicate(op1: BankOperation, op2: BankOperation, tolerance: Decimal) -> bool:
    """Проверяет, являются ли две операции потенциальным дублем."""
    if op1.operation_date != op2.operation_date:
        return False
    if op1.amount and op2.amount:
        if abs(op1.amount - op2.amount) > tolerance:
            return False
    else:
        return False
    if op1.is_income != op2.is_income or op1.is_expense != op2.is_expense:
        return False
    inn_match = (op1.counterparty_inn and op2.counterparty_inn and op1.counterparty_inn == op2.counterparty_inn)
    name_match = (op1.counterparty_name and op2.counterparty_name and op1.counterparty_name.strip().lower() == op2.counterparty_name.strip().lower())
    return bool(inn_match or name_match)


def _describe_duplicate(op: BankOperation) -> str:
    parts = [f"дата={op.operation_date}", f"сумма={op.amount}"]
    if op.counterparty_name:
        parts.append(f"контрагент={op.counterparty_name}")
    if op.counterparty_inn:
        parts.append(f"ИНН={op.counterparty_inn}")
    return f"Совпадение: {', '.join(parts)}"


# ─── Сервисные функции для применения результатов ────────────────


async def apply_classification(
    db: AsyncSession,
    operation_id: str,
    user_id: str,
    result: ClassificationResult,
) -> BankOperation:
    """Применить результат классификации к операции в БД."""
    db_result = await db.execute(
        select(BankOperation).where(
            BankOperation.id == operation_id,
            BankOperation.user_id == user_id,
        )
    )
    operation = db_result.scalar_one_or_none()
    if not operation:
        raise ValueError(f"Операция {operation_id} не найдена")

    operation.category = result.category
    operation.is_income = result.is_income
    operation.is_expense = result.is_expense
    operation.vat_amount = result.vat_amount
    operation.classification_confidence = Decimal(str(result.confidence)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

    if result.confidence >= 0.9:
        operation.status = OperationStatus.CLASSIFIED
    else:
        operation.status = OperationStatus.PENDING

    await db.flush()
    return operation


async def apply_match_result(
    db: AsyncSession,
    operation_id: str,
    user_id: str,
    match: MatchResult,
) -> BankOperation:
    """Применить результат сопоставления: привязать документ/чек к операции."""
    db_result = await db.execute(
        select(BankOperation).where(
            BankOperation.id == operation_id,
            BankOperation.user_id == user_id,
        )
    )
    operation = db_result.scalar_one_or_none()
    if not operation:
        raise ValueError(f"Операция {operation_id} не найдена")

    if match.entity_type == "document":
        operation.linked_document_id = match.entity_id
    elif match.entity_type == "cash_receipt":
        operation.linked_receipt_id = match.entity_id

    await db.flush()
    return operation
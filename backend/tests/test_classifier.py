"""
Тесты для сервиса классификации банковских операций.
Пункт плана: 1.10.9

Тестируем:
- Rule-based классификация
- Расчёт НДС
- Поиск дублей (без БД)
- Валидация результатов
"""

import pytest
from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock

from app.constants.enums import OperationCategory, OperationStatus
from app.services.classifier_service import (
    ClassificationResult,
    DuplicateGroup,
    calculate_vat_from_operation,
    _classify_by_rules,
    _is_potential_duplicate,
    _matches_any,
    _parse_classification_json,
    _parse_batch_json,
    _validate_category_direction,
    INCOME_CATEGORIES,
    EXPENSE_CATEGORIES,
    NO_VAT_CATEGORIES,
    VAT_CALCULATED_RATE,
)


# ─── Фикстура: мок BankOperation ────────────────────────────────


def _make_operation(
    purpose: str = "",
    amount: Decimal = Decimal("10000.00"),
    is_income: bool = False,
    is_expense: bool = False,
    counterparty_name: str = "",
    counterparty_inn: str = "",
    operation_date: date = date(2026, 3, 1),
    op_id: str = "op_test_001",
) -> MagicMock:
    """Создаёт мок BankOperation для тестов."""
    op = MagicMock()
    op.id = op_id
    op.user_id = "user_test_001"
    op.purpose = purpose
    op.amount = amount
    op.is_income = is_income
    op.is_expense = is_expense
    op.counterparty_name = counterparty_name
    op.counterparty_inn = counterparty_inn
    op.operation_date = operation_date
    op.bank_account_id = None
    op.category = OperationCategory.UNCLASSIFIED
    op.status = OperationStatus.PENDING
    op.classification_confidence = None
    op.vat_amount = None
    op.linked_document_id = None
    op.linked_receipt_id = None
    return op


# ─── Тесты расчёта НДС (1.10.7) ────────────────────────────────


class TestCalculateVat:
    """Тесты функции calculate_vat_from_operation."""

    def test_vat_from_purpose_explicit(self):
        """НДС указан явно в назначении платежа."""
        vat = calculate_vat_from_operation(
            Decimal("122000"), "Оплата за товар в т.ч. НДС 22% — 22000.00"
        )
        assert vat == Decimal("22000.00")

    def test_vat_from_purpose_no_vat(self):
        """'Без НДС' в назначении."""
        vat = calculate_vat_from_operation(
            Decimal("100000"), "Оплата по договору. Без НДС"
        )
        assert vat == Decimal("0")

    def test_vat_no_vat_category_taxes(self):
        """Налоги — НДС = 0."""
        vat = calculate_vat_from_operation(
            Decimal("50000"), "Уплата УСН за 1 квартал",
            category=OperationCategory.TAXES_AND_FEES,
        )
        assert vat == Decimal("0")

    def test_vat_no_vat_category_bank_commission(self):
        """Банковская комиссия — НДС = 0."""
        vat = calculate_vat_from_operation(
            Decimal("500"), "Комиссия за обслуживание счёта",
            category=OperationCategory.BANK_COMMISSION,
        )
        assert vat == Decimal("0")

    def test_vat_no_vat_category_salary(self):
        """Зарплата — НДС = 0."""
        vat = calculate_vat_from_operation(
            Decimal("30000"), "",
            category=OperationCategory.SALARY,
        )
        assert vat == Decimal("0")

    def test_vat_calculated_method(self):
        """Расчётный метод 22/122."""
        amount = Decimal("122000")
        vat = calculate_vat_from_operation(amount, "")
        expected = (amount * VAT_CALCULATED_RATE).quantize(Decimal("0.01"))
        assert vat == expected
        # 122000 * 22/122 = 22000
        assert vat == Decimal("22000.00")

    def test_vat_zero_amount(self):
        """Нулевая сумма — НДС = 0."""
        vat = calculate_vat_from_operation(Decimal("0"), "")
        assert vat == Decimal("0")

    def test_vat_negative_amount(self):
        """Отрицательная сумма — НДС = 0."""
        vat = calculate_vat_from_operation(Decimal("-100"), "")
        assert vat == Decimal("0")


# ─── Тесты rule-based классификации (1.10.2) ────────────────────


class TestRuleBasedClassification:
    """Тесты rule-based классификации по назначению платежа."""

    def test_tax_payment(self):
        """Уплата налога."""
        op = _make_operation(
            purpose="Уплата единого налога УСН за 1 кв. 2026",
            is_expense=True,
        )
        result = _classify_by_rules(op)
        assert result.category == OperationCategory.TAXES_AND_FEES
        assert result.is_expense is True
        assert result.vat_amount == Decimal("0")
        assert result.confidence >= 0.85

    def test_insurance_payment(self):
        """Страховые взносы."""
        op = _make_operation(
            purpose="Фиксированные страховые взносы ИП на ОМС",
            is_expense=True,
        )
        result = _classify_by_rules(op)
        assert result.category == OperationCategory.INSURANCE_PAYMENT
        assert result.is_expense is True
        assert result.vat_amount == Decimal("0")

    def test_salary(self):
        """Зарплата."""
        op = _make_operation(
            purpose="Заработная плата за февраль 2026",
            is_expense=True,
        )
        result = _classify_by_rules(op)
        assert result.category == OperationCategory.SALARY
        assert result.is_expense is True

    def test_bank_commission(self):
        """Комиссия банка."""
        op = _make_operation(
            purpose="Комиссия за расчётно-кассовое обслуживание",
            amount=Decimal("500"),
            is_expense=True,
        )
        result = _classify_by_rules(op)
        assert result.category == OperationCategory.BANK_COMMISSION
        assert result.vat_amount == Decimal("0")
        assert result.confidence >= 0.90

    def test_rent(self):
        """Аренда."""
        op = _make_operation(
            purpose="Оплата аренды помещения за март 2026",
            amount=Decimal("50000"),
            is_expense=True,
        )
        result = _classify_by_rules(op)
        assert result.category == OperationCategory.RENT
        assert result.is_expense is True

    def test_purchase_goods(self):
        """Закупка товара."""
        op = _make_operation(
            purpose="Оплата по счёту №123 за товар. В т.ч. НДС 22% — 5000.00",
            amount=Decimal("27727.27"),
            is_expense=True,
        )
        result = _classify_by_rules(op)
        assert result.category == OperationCategory.PURCHASE_GOODS
        assert result.is_expense is True

    def test_acquiring_income(self):
        """Поступление по эквайрингу."""
        op = _make_operation(
            purpose="Торговый эквайринг, зачисление за 01.03.2026",
            amount=Decimal("150000"),
            is_income=True,
        )
        result = _classify_by_rules(op)
        assert result.category == OperationCategory.ACQUIRING
        assert result.is_income is True

    def test_own_funds(self):
        """Взнос собственных средств."""
        op = _make_operation(
            purpose="Взнос собственных средств ИП",
            amount=Decimal("100000"),
            is_income=True,
        )
        result = _classify_by_rules(op)
        assert result.category == OperationCategory.OWN_FUNDS
        assert result.is_income is False
        assert result.is_expense is False

    def test_personal_withdrawal(self):
        """Снятие на личные нужды."""
        op = _make_operation(
            purpose="Перевод на карту ИП на личные нужды",
            is_expense=True,
        )
        result = _classify_by_rules(op)
        assert result.category == OperationCategory.PERSONAL_WITHDRAWAL
        assert result.is_income is False
        assert result.is_expense is False

    def test_internal_transfer_outgoing(self):
        """Внутренний перевод (исходящий)."""
        op = _make_operation(
            purpose="Перевод между своими счетами",
            is_expense=True,
        )
        result = _classify_by_rules(op)
        assert result.category == OperationCategory.INTERNAL_TRANSFER
        assert result.is_income is False
        assert result.is_expense is False

    def test_loan_received(self):
        """Получение кредита."""
        op = _make_operation(
            purpose="Выдача кредита по договору №КЛ-123",
            amount=Decimal("500000"),
            is_income=True,
        )
        result = _classify_by_rules(op)
        assert result.category == OperationCategory.LOAN_RECEIVED
        assert result.is_income is False
        assert result.is_expense is False

    def test_loan_interest(self):
        """Проценты по кредиту (расход)."""
        op = _make_operation(
            purpose="Погашение процентов по кредитному договору",
            is_expense=True,
        )
        result = _classify_by_rules(op)
        assert result.category == OperationCategory.LOAN_REPAYMENT
        assert result.is_expense is True

    def test_sales_revenue(self):
        """Оплата от покупателя (выручка)."""
        op = _make_operation(
            purpose="Оплата по счёту №456 за товар",
            amount=Decimal("75000"),
            is_income=True,
        )
        result = _classify_by_rules(op)
        assert result.category == OperationCategory.SALES_REVENUE
        assert result.is_income is True

    def test_empty_purpose_no_classification(self):
        """Пустое назначение — нет классификации."""
        op = _make_operation(purpose="", is_expense=True)
        result = _classify_by_rules(op)
        assert result.category == OperationCategory.UNCLASSIFIED
        assert result.confidence == 0.0

    def test_unknown_purpose(self):
        """Неизвестное назначение — low confidence."""
        op = _make_operation(
            purpose="Перевод по реестру №987654321",
            is_expense=True,
        )
        result = _classify_by_rules(op)
        assert result.confidence < 0.85  # Не хватило rule-based


# ─── Тесты валидации категорий ───────────────────────────────────


class TestValidateCategoryDirection:
    """Тесты _validate_category_direction."""

    def test_income_category_sets_is_income(self):
        """Доходная категория устанавливает is_income=True."""
        result = ClassificationResult(
            category=OperationCategory.SALES_REVENUE,
            is_income=False, is_expense=True,
        )
        _validate_category_direction(result)
        assert result.is_income is True
        assert result.is_expense is False

    def test_expense_category_sets_is_expense(self):
        """Расходная категория устанавливает is_expense=True."""
        result = ClassificationResult(
            category=OperationCategory.RENT,
            is_income=True, is_expense=False,
        )
        _validate_category_direction(result)
        assert result.is_expense is True
        assert result.is_income is False

    def test_neutral_category_clears_both(self):
        """Нейтральная категория обнуляет оба флага."""
        result = ClassificationResult(
            category=OperationCategory.OWN_FUNDS,
            is_income=True, is_expense=True,
        )
        _validate_category_direction(result)
        assert result.is_income is False
        assert result.is_expense is False


# ─── Тесты парсинга JSON ─────────────────────────────────────────


class TestParseClassificationJson:
    """Тесты парсинга JSON из ответа LLM."""

    def test_parse_direct_json(self):
        """Прямой JSON."""
        content = '{"category": "rent", "is_income": false, "is_expense": true, "confidence": 0.9}'
        result = _parse_classification_json(content)
        assert result is not None
        assert result["category"] == "rent"

    def test_parse_markdown_json(self):
        """JSON в markdown-блоке."""
        content = '```json\n{"category": "salary", "confidence": 0.85}\n```'
        result = _parse_classification_json(content)
        assert result is not None
        assert result["category"] == "salary"

    def test_parse_json_with_text(self):
        """JSON среди текста."""
        content = 'Вот результат: {"category": "rent", "confidence": 0.9} — готово.'
        result = _parse_classification_json(content)
        assert result is not None
        assert result["category"] == "rent"

    def test_parse_empty(self):
        """Пустой ответ."""
        assert _parse_classification_json("") is None
        assert _parse_classification_json("тут нет JSON") is None

    def test_parse_batch_json_array(self):
        """JSON-массив для пакетной классификации."""
        content = '[{"operation_index": 0, "category": "rent"}, {"operation_index": 1, "category": "salary"}]'
        result = _parse_batch_json(content)
        assert result is not None
        assert len(result) == 2
        assert result[0]["category"] == "rent"

    def test_parse_batch_json_markdown(self):
        """JSON-массив в markdown."""
        content = '```json\n[{"operation_index": 0, "category": "rent"}]\n```'
        result = _parse_batch_json(content)
        assert result is not None
        assert len(result) == 1


# ─── Тесты поиска дублей ─────────────────────────────────────────


class TestDuplicateDetection:
    """Тесты _is_potential_duplicate."""

    def test_duplicate_same_date_amount_inn(self):
        """Дубль: одинаковая дата, сумма, ИНН."""
        op1 = _make_operation(
            op_id="op1",
            amount=Decimal("50000"),
            is_expense=True,
            counterparty_inn="7712345678",
            operation_date=date(2026, 3, 1),
        )
        op2 = _make_operation(
            op_id="op2",
            amount=Decimal("50000"),
            is_expense=True,
            counterparty_inn="7712345678",
            operation_date=date(2026, 3, 1),
        )
        assert _is_potential_duplicate(op1, op2, Decimal("0.01")) is True

    def test_not_duplicate_different_date(self):
        """Не дубль: разные даты."""
        op1 = _make_operation(
            op_id="op1", amount=Decimal("50000"), is_expense=True,
            counterparty_inn="7712345678", operation_date=date(2026, 3, 1),
        )
        op2 = _make_operation(
            op_id="op2", amount=Decimal("50000"), is_expense=True,
            counterparty_inn="7712345678", operation_date=date(2026, 3, 2),
        )
        assert _is_potential_duplicate(op1, op2, Decimal("0.01")) is False

    def test_not_duplicate_different_amount(self):
        """Не дубль: разные суммы."""
        op1 = _make_operation(
            op_id="op1", amount=Decimal("50000"), is_expense=True,
            counterparty_inn="7712345678", operation_date=date(2026, 3, 1),
        )
        op2 = _make_operation(
            op_id="op2", amount=Decimal("60000"), is_expense=True,
            counterparty_inn="7712345678", operation_date=date(2026, 3, 1),
        )
        assert _is_potential_duplicate(op1, op2, Decimal("0.01")) is False

    def test_not_duplicate_different_direction(self):
        """Не дубль: разные направления."""
        op1 = _make_operation(
            op_id="op1", amount=Decimal("50000"), is_expense=True, is_income=False,
            counterparty_inn="7712345678", operation_date=date(2026, 3, 1),
        )
        op2 = _make_operation(
            op_id="op2", amount=Decimal("50000"), is_expense=False, is_income=True,
            counterparty_inn="7712345678", operation_date=date(2026, 3, 1),
        )
        assert _is_potential_duplicate(op1, op2, Decimal("0.01")) is False

    def test_duplicate_by_name(self):
        """Дубль: совпадение по имени контрагента."""
        op1 = _make_operation(
            op_id="op1", amount=Decimal("50000"), is_expense=True,
            counterparty_name="ООО Ромашка", operation_date=date(2026, 3, 1),
        )
        op2 = _make_operation(
            op_id="op2", amount=Decimal("50000"), is_expense=True,
            counterparty_name="ООО Ромашка", operation_date=date(2026, 3, 1),
        )
        assert _is_potential_duplicate(op1, op2, Decimal("0.01")) is True

    def test_not_duplicate_no_counterparty(self):
        """Не дубль: нет данных контрагента."""
        op1 = _make_operation(
            op_id="op1", amount=Decimal("50000"), is_expense=True,
            operation_date=date(2026, 3, 1),
        )
        op2 = _make_operation(
            op_id="op2", amount=Decimal("50000"), is_expense=True,
            operation_date=date(2026, 3, 1),
        )
        assert _is_potential_duplicate(op1, op2, Decimal("0.01")) is False


# ─── Тесты вспомогательных функций ──────────────────────────────


class TestHelpers:
    """Тесты вспомогательных функций."""

    def test_matches_any_positive(self):
        assert _matches_any("оплата за аренду помещения", ["аренд"]) is True
        assert _matches_any("комиссия банка", ["комисси", "обслуживан"]) is True

    def test_matches_any_negative(self):
        assert _matches_any("оплата за товар", ["аренд"]) is False

    def test_income_expense_categories_no_overlap(self):
        """Доходные и расходные категории не пересекаются."""
        assert INCOME_CATEGORIES.isdisjoint(EXPENSE_CATEGORIES)

    def test_no_vat_categories_subset(self):
        """Категории без НДС содержат ожидаемые."""
        assert OperationCategory.TAXES_AND_FEES in NO_VAT_CATEGORIES
        assert OperationCategory.BANK_COMMISSION in NO_VAT_CATEGORIES
        assert OperationCategory.SALARY in NO_VAT_CATEGORIES

    def test_classification_result_is_valid(self):
        """ClassificationResult.is_valid работает корректно."""
        r = ClassificationResult(category=OperationCategory.RENT, confidence=0.9)
        assert r.is_valid is True

        r2 = ClassificationResult(category=OperationCategory.UNCLASSIFIED)
        assert r2.is_valid is False

        r3 = ClassificationResult(category=OperationCategory.RENT, errors=["error"])
        assert r3.is_valid is False
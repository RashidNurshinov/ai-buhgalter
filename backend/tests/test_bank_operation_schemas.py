"""
Тесты Pydantic-схем банковских операций.

Тестируем:
- BankOperationResponse — полный ответ с from_attributes
- OperationReclassifyRequest — переклассификация
- BankOperationFilter — фильтры для списка
"""

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.constants.enums import OperationCategory, OperationStatus
from app.schemas.bank_operation import (
    BankOperationFilter,
    BankOperationResponse,
    OperationConfirmRequest,
    OperationReclassifyRequest,
)


# ─── BankOperationResponse ──────────────────────────────────────


class TestBankOperationResponse:
    """Тесты BankOperationResponse."""

    def test_valid_income(self):
        """Валидная операция дохода."""
        resp = BankOperationResponse(
            id=str(uuid.uuid4()),
            user_id=str(uuid.uuid4()),
            operation_date=date(2026, 3, 15),
            amount=Decimal("150000.00"),
            counterparty_name="ООО Ромашка",
            counterparty_inn="7712345678",
            purpose="Оплата по договору №123",
            category=OperationCategory.SALES_REVENUE,
            is_income=True,
            is_expense=False,
            vat_amount=Decimal("25000.00"),
            classification_confidence=Decimal("0.9500"),
            status=OperationStatus.CLASSIFIED,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        assert resp.is_income is True
        assert resp.is_expense is False
        assert resp.category == OperationCategory.SALES_REVENUE

    def test_valid_expense(self):
        """Валидная операция расхода."""
        resp = BankOperationResponse(
            id=str(uuid.uuid4()),
            user_id=str(uuid.uuid4()),
            operation_date=date(2026, 3, 20),
            amount=Decimal("50000.00"),
            counterparty_name="ООО Поставщик",
            purpose="Закупка товара",
            category=OperationCategory.PURCHASE_GOODS,
            is_income=False,
            is_expense=True,
            status=OperationStatus.CONFIRMED,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        assert resp.is_expense is True
        assert resp.category == OperationCategory.PURCHASE_GOODS

    def test_neutral_operation(self):
        """Нейтральная операция (не доход и не расход)."""
        resp = BankOperationResponse(
            id=str(uuid.uuid4()),
            user_id=str(uuid.uuid4()),
            operation_date=date(2026, 3, 25),
            amount=Decimal("200000.00"),
            purpose="Взнос собственных средств",
            category=OperationCategory.OWN_FUNDS,
            is_income=False,
            is_expense=False,
            status=OperationStatus.CONFIRMED,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        assert resp.is_income is False
        assert resp.is_expense is False

    def test_optional_fields_none(self):
        """Опциональные поля могут быть None."""
        resp = BankOperationResponse(
            id=str(uuid.uuid4()),
            user_id=str(uuid.uuid4()),
            operation_date=date(2026, 1, 1),
            amount=Decimal("1000.00"),
            is_income=True,
            is_expense=False,
            status=OperationStatus.PENDING,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        assert resp.bank_account_id is None
        assert resp.counterparty_id is None
        assert resp.counterparty_name is None
        assert resp.vat_amount is None
        assert resp.linked_document_id is None

    def test_all_statuses(self):
        """Все статусы операций работают."""
        for status in OperationStatus:
            resp = BankOperationResponse(
                id=str(uuid.uuid4()),
                user_id=str(uuid.uuid4()),
                operation_date=date(2026, 1, 1),
                amount=Decimal("100.00"),
                is_income=False,
                is_expense=False,
                status=status,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            assert resp.status == status

    def test_from_attributes_config(self):
        """Проверяем from_attributes конфигурацию."""
        assert BankOperationResponse.model_config.get("from_attributes") is True


# ─── OperationReclassifyRequest ─────────────────────────────────


class TestOperationReclassifyRequest:
    """Тесты OperationReclassifyRequest."""

    def test_minimal(self):
        """Минимальный запрос — только категория."""
        req = OperationReclassifyRequest(
            category=OperationCategory.RENT,
        )
        assert req.category == OperationCategory.RENT
        assert req.is_income is None
        assert req.is_expense is None
        assert req.vat_amount is None

    def test_full(self):
        """Полный запрос на переклассификацию."""
        req = OperationReclassifyRequest(
            category=OperationCategory.PURCHASE_GOODS,
            is_income=False,
            is_expense=True,
            vat_amount=Decimal("5000.00"),
            linked_document_id=str(uuid.uuid4()),
        )
        assert req.is_expense is True
        assert req.vat_amount == Decimal("5000.00")

    def test_all_categories_valid(self):
        """Все категории валидны для переклассификации."""
        for cat in OperationCategory:
            req = OperationReclassifyRequest(category=cat)
            assert req.category == cat

    def test_negative_vat_rejected(self):
        """Отрицательный НДС отклоняется."""
        with pytest.raises(ValidationError):
            OperationReclassifyRequest(
                category=OperationCategory.PURCHASE_GOODS,
                vat_amount=Decimal("-100.00"),
            )

    def test_zero_vat_valid(self):
        """Нулевой НДС — валидно."""
        req = OperationReclassifyRequest(
            category=OperationCategory.SALARY,
            vat_amount=Decimal("0.00"),
        )
        assert req.vat_amount == Decimal("0.00")


# ─── OperationConfirmRequest ────────────────────────────────────


class TestOperationConfirmRequest:
    """Тесты OperationConfirmRequest."""

    def test_empty_body(self):
        """Пустой запрос на подтверждение — валидно."""
        req = OperationConfirmRequest()
        assert req is not None


# ─── BankOperationFilter ────────────────────────────────────────


class TestBankOperationFilter:
    """Тесты BankOperationFilter."""

    def test_empty_filter(self):
        """Пустой фильтр — все поля None."""
        f = BankOperationFilter()
        assert f.date_from is None
        assert f.date_to is None
        assert f.category is None
        assert f.status is None
        assert f.search is None

    def test_date_range(self):
        """Фильтр по диапазону дат."""
        f = BankOperationFilter(
            date_from=date(2026, 1, 1),
            date_to=date(2026, 3, 31),
        )
        assert f.date_from == date(2026, 1, 1)
        assert f.date_to == date(2026, 3, 31)

    def test_category_filter(self):
        """Фильтр по категории."""
        f = BankOperationFilter(category=OperationCategory.RENT)
        assert f.category == OperationCategory.RENT

    def test_amount_range(self):
        """Фильтр по сумме."""
        f = BankOperationFilter(
            min_amount=Decimal("1000.00"),
            max_amount=Decimal("100000.00"),
        )
        assert f.min_amount == Decimal("1000.00")
        assert f.max_amount == Decimal("100000.00")

    def test_search_filter(self):
        """Фильтр по назначению платежа."""
        f = BankOperationFilter(search="аренда")
        assert f.search == "аренда"

    def test_combined_filters(self):
        """Комбинированные фильтры."""
        f = BankOperationFilter(
            date_from=date(2026, 1, 1),
            category=OperationCategory.SALARY,
            is_expense=True,
            status=OperationStatus.CONFIRMED,
            search="зарплата",
        )
        assert f.date_from == date(2026, 1, 1)
        assert f.category == OperationCategory.SALARY
        assert f.is_expense is True
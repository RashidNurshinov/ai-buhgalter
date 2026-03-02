"""
Фикстуры для тестов AI-Buhgalter.

Предоставляет:
- mock_db: замоканная async-сессия БД
- test_user: объект User для тестов
- auth_headers: заголовки авторизации
- test_settings: тестовые настройки
"""

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.constants.enums import (
    OperationCategory,
    OperationStatus,
    TaxSystem,
    TaxType,
    PeriodType,
    CalculationStatus,
    CalendarEventType,
    CalendarEventStatus,
    DeclarationType,
    DeclarationStatus,
    DocumentType,
    DocumentStatus,
    FileType,
    ProcessingStatus,
)
from app.core.security import create_access_token, hash_password


# ─── Фикстуры для моков БД ──────────────────────────────────────


@pytest.fixture
def mock_db():
    """Замоканная async-сессия БД."""
    db = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.flush = AsyncMock()
    db.rollback = AsyncMock()
    db.execute = AsyncMock()
    db.close = AsyncMock()
    return db


# ─── Фикстуры для User ──────────────────────────────────────────


@pytest.fixture
def test_user_id():
    """UUID тестового пользователя."""
    return uuid.UUID("12345678-1234-5678-1234-567812345678")


@pytest.fixture
def test_user(test_user_id):
    """Мок-объект User для тестов."""
    user = MagicMock()
    user.id = test_user_id
    user.email = "test@example.com"
    user.hashed_password = hash_password("testpassword123")
    user.full_name = "Тестовый Пользователь"
    user.inn = "1234567890"
    user.business_name = "ИП Тестовый"
    user.tax_system = TaxSystem.USN_INCOME_EXPENSE
    user.is_active = True
    user.tax_region = "56"
    user.usn_rate = Decimal("15.00")
    user.vat_rate = Decimal("22.00")
    user.has_employees = False
    user.employee_count = 0
    user.created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    user.updated_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return user


@pytest.fixture
def test_user_osno(test_user_id):
    """Мок-объект User на ОСНО."""
    user = MagicMock()
    user.id = test_user_id
    user.email = "osno@example.com"
    user.full_name = "ИП на ОСНО"
    user.inn = "9876543210"
    user.business_name = "ИП ОСНО"
    user.tax_system = TaxSystem.OSNO
    user.is_active = True
    user.tax_region = "77"
    user.usn_rate = Decimal("0.00")
    user.vat_rate = Decimal("22.00")
    user.has_employees = True
    user.employee_count = 3
    user.created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    user.updated_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return user


@pytest.fixture
def auth_headers(test_user_id):
    """Заголовки авторизации с валидным access-токеном."""
    token = create_access_token(subject=str(test_user_id))
    return {"Authorization": f"Bearer {token}"}


# ─── Фикстуры для BankOperation ─────────────────────────────────


@pytest.fixture
def sample_bank_operation(test_user_id):
    """Мок-объект банковской операции (доход)."""
    op = MagicMock()
    op.id = uuid.uuid4()
    op.user_id = test_user_id
    op.bank_account_id = None
    op.operation_date = date(2026, 3, 15)
    op.amount = Decimal("150000.00")
    op.counterparty_name = "ООО Ромашка"
    op.counterparty_inn = "7712345678"
    op.purpose = "Оплата по договору №123 от 01.03.2026"
    op.category = OperationCategory.SALES_REVENUE
    op.is_income = True
    op.is_expense = False
    op.vat_amount = Decimal("25000.00")
    op.linked_document_id = None
    op.linked_receipt_id = None
    op.classification_confidence = Decimal("0.9500")
    op.status = OperationStatus.CLASSIFIED
    op.created_at = datetime(2026, 3, 15, 10, 0, 0, tzinfo=timezone.utc)
    op.updated_at = datetime(2026, 3, 15, 10, 0, 0, tzinfo=timezone.utc)
    return op


@pytest.fixture
def sample_expense_operation(test_user_id):
    """Мок-объект банковской операции (расход)."""
    op = MagicMock()
    op.id = uuid.uuid4()
    op.user_id = test_user_id
    op.bank_account_id = None
    op.operation_date = date(2026, 3, 20)
    op.amount = Decimal("50000.00")
    op.counterparty_name = "ООО Поставщик"
    op.counterparty_inn = "7799887766"
    op.purpose = "Закупка товара по счёту №456"
    op.category = OperationCategory.PURCHASE_GOODS
    op.is_income = False
    op.is_expense = True
    op.vat_amount = Decimal("8333.33")
    op.linked_document_id = None
    op.linked_receipt_id = None
    op.classification_confidence = Decimal("0.8800")
    op.status = OperationStatus.CLASSIFIED
    op.created_at = datetime(2026, 3, 20, 14, 0, 0, tzinfo=timezone.utc)
    op.updated_at = datetime(2026, 3, 20, 14, 0, 0, tzinfo=timezone.utc)
    return op


@pytest.fixture
def sample_operations_batch(test_user_id):
    """Пакет из 5 операций для тестов пагинации и фильтрации."""
    operations = []
    categories = [
        (OperationCategory.SALES_REVENUE, True, False, Decimal("100000.00")),
        (OperationCategory.PURCHASE_GOODS, False, True, Decimal("50000.00")),
        (OperationCategory.RENT, False, True, Decimal("30000.00")),
        (OperationCategory.SALARY, False, True, Decimal("80000.00")),
        (OperationCategory.OWN_FUNDS, False, False, Decimal("200000.00")),
    ]
    for i, (cat, is_inc, is_exp, amount) in enumerate(categories):
        op = MagicMock()
        op.id = uuid.uuid4()
        op.user_id = test_user_id
        op.operation_date = date(2026, 3, 1 + i)
        op.amount = amount
        op.counterparty_name = f"Контрагент {i + 1}"
        op.counterparty_inn = f"77{i:010d}"
        op.purpose = f"Назначение платежа {i + 1}"
        op.category = cat
        op.is_income = is_inc
        op.is_expense = is_exp
        op.vat_amount = None
        op.classification_confidence = Decimal("0.9000")
        op.status = OperationStatus.CLASSIFIED
        op.created_at = datetime(2026, 3, 1 + i, tzinfo=timezone.utc)
        op.updated_at = datetime(2026, 3, 1 + i, tzinfo=timezone.utc)
        operations.append(op)
    return operations
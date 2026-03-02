"""
Тесты Pydantic-схем пользователя.

Тестируем:
- UserResponse — полный ответ с настройками
- UserUpdate — обновление профиля и настроек
- UserBriefResponse — краткая информация
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.constants.enums import TaxSystem
from app.schemas.user import UserBriefResponse, UserResponse, UserUpdate


# ─── UserResponse ───────────────────────────────────────────────


class TestUserResponse:
    """Тесты UserResponse."""

    def test_valid_full(self):
        """Полный валидный ответ пользователя."""
        resp = UserResponse(
            id=uuid.uuid4(),
            email="user@example.com",
            full_name="Иванов Иван Иванович",
            inn="1234567890",
            business_name="ИП Иванов",
            tax_system=TaxSystem.USN_INCOME_EXPENSE,
            is_active=True,
            tax_region="56",
            usn_rate=Decimal("15.00"),
            vat_rate=Decimal("22.00"),
            has_employees=False,
            employee_count=0,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        assert resp.full_name == "Иванов Иван Иванович"
        assert resp.tax_system == TaxSystem.USN_INCOME_EXPENSE
        assert resp.usn_rate == Decimal("15.00")

    def test_optional_fields_none(self):
        """Опциональные поля могут быть None."""
        resp = UserResponse(
            id=uuid.uuid4(),
            email="user@example.com",
            full_name="Тест",
            inn=None,
            business_name=None,
            tax_system=TaxSystem.USN_INCOME,
            is_active=True,
            tax_region="77",
            usn_rate=Decimal("6.00"),
            vat_rate=Decimal("22.00"),
            has_employees=False,
            employee_count=0,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        assert resp.inn is None
        assert resp.business_name is None

    def test_all_tax_systems(self):
        """Все системы налогообложения валидны."""
        for ts in TaxSystem:
            resp = UserResponse(
                id=uuid.uuid4(),
                email="user@example.com",
                full_name="Тест",
                tax_system=ts,
                is_active=True,
                tax_region="56",
                usn_rate=Decimal("15.00"),
                vat_rate=Decimal("22.00"),
                has_employees=False,
                employee_count=0,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            assert resp.tax_system == ts


# ─── UserUpdate ─────────────────────────────────────────────────


class TestUserUpdate:
    """Тесты UserUpdate."""

    def test_empty_update(self):
        """Пустое обновление (все поля None)."""
        upd = UserUpdate()
        assert upd.full_name is None
        assert upd.inn is None
        assert upd.tax_system is None

    def test_partial_update(self):
        """Частичное обновление."""
        upd = UserUpdate(
            full_name="Новое Имя",
            usn_rate=Decimal("6.00"),
        )
        assert upd.full_name == "Новое Имя"
        assert upd.usn_rate == Decimal("6.00")
        assert upd.inn is None

    def test_full_update(self):
        """Полное обновление всех полей."""
        upd = UserUpdate(
            full_name="Новый ФИО",
            inn="9876543210",
            business_name="Новый Бизнес",
            tax_system=TaxSystem.OSNO,
            tax_region="77",
            usn_rate=Decimal("0.00"),
            vat_rate=Decimal("22.00"),
            has_employees=True,
            employee_count=5,
        )
        assert upd.tax_system == TaxSystem.OSNO
        assert upd.employee_count == 5

    def test_full_name_too_short(self):
        """Имя менее 2 символов — ошибка."""
        with pytest.raises(ValidationError):
            UserUpdate(full_name="А")

    def test_inn_valid_lengths(self):
        """ИНН длиной 10 и 12 символов — валидно."""
        upd10 = UserUpdate(inn="1234567890")
        assert upd10.inn == "1234567890"
        upd12 = UserUpdate(inn="123456789012")
        assert upd12.inn == "123456789012"

    def test_inn_too_short(self):
        """ИНН менее 10 символов — ошибка."""
        with pytest.raises(ValidationError):
            UserUpdate(inn="123")

    def test_usn_rate_boundaries(self):
        """usn_rate: 0-100 валидно, вне диапазона — ошибка."""
        upd = UserUpdate(usn_rate=Decimal("0.00"))
        assert upd.usn_rate == Decimal("0.00")
        upd = UserUpdate(usn_rate=Decimal("100.00"))
        assert upd.usn_rate == Decimal("100.00")
        with pytest.raises(ValidationError):
            UserUpdate(usn_rate=Decimal("-1.00"))
        with pytest.raises(ValidationError):
            UserUpdate(usn_rate=Decimal("101.00"))

    def test_employee_count_non_negative(self):
        """employee_count >= 0."""
        upd = UserUpdate(employee_count=0)
        assert upd.employee_count == 0
        with pytest.raises(ValidationError):
            UserUpdate(employee_count=-1)


# ─── UserBriefResponse ──────────────────────────────────────────


class TestUserBriefResponse:
    """Тесты UserBriefResponse."""

    def test_valid(self):
        """Валидный краткий ответ."""
        resp = UserBriefResponse(
            id=uuid.uuid4(),
            email="user@example.com",
            full_name="Иванов Иван",
            tax_system=TaxSystem.USN_INCOME,
        )
        assert resp.full_name == "Иванов Иван"
        assert resp.tax_system == TaxSystem.USN_INCOME

    def test_from_attributes_config(self):
        """Проверяем, что from_attributes настроен."""
        assert UserBriefResponse.model_config.get("from_attributes") is True
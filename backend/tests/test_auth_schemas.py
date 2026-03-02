"""
Тесты Pydantic-схем аутентификации.

Тестируем:
- RegisterRequest — валидация email, пароля, ИНН
- LoginRequest — базовая валидация
- TokenResponse — структура ответа
- RefreshTokenRequest — обязательное поле
"""

import pytest
from pydantic import ValidationError

from app.schemas.auth import (
    LoginRequest,
    RefreshTokenRequest,
    RegisterRequest,
    TokenResponse,
)


# ─── RegisterRequest ────────────────────────────────────────────


class TestRegisterRequest:
    """Тесты валидации RegisterRequest."""

    def test_valid_minimal(self):
        """Минимальный валидный запрос."""
        req = RegisterRequest(
            email="user@example.com",
            password="password123",
            full_name="Иванов Иван",
        )
        assert req.email == "user@example.com"
        assert req.password == "password123"
        assert req.full_name == "Иванов Иван"
        assert req.inn is None
        assert req.business_name is None
        assert req.tax_system == "usn_income_expense"

    def test_valid_full(self):
        """Полный валидный запрос."""
        req = RegisterRequest(
            email="ip@business.ru",
            password="securepass1",
            full_name="Петров Пётр Петрович",
            inn="1234567890",
            business_name="ИП Петров",
            tax_system="osno",
        )
        assert req.inn == "1234567890"
        assert req.business_name == "ИП Петров"
        assert req.tax_system == "osno"

    def test_invalid_email(self):
        """Невалидный email."""
        with pytest.raises(ValidationError) as exc_info:
            RegisterRequest(
                email="not-an-email",
                password="password123",
                full_name="Тест",
            )
        assert "email" in str(exc_info.value).lower() or "value" in str(exc_info.value).lower()

    def test_password_too_short(self):
        """Пароль менее 8 символов."""
        with pytest.raises(ValidationError):
            RegisterRequest(
                email="user@example.com",
                password="short",
                full_name="Тест Тестов",
            )

    def test_password_too_long(self):
        """Пароль более 128 символов."""
        with pytest.raises(ValidationError):
            RegisterRequest(
                email="user@example.com",
                password="x" * 129,
                full_name="Тест Тестов",
            )

    def test_password_exactly_8_chars(self):
        """Пароль ровно 8 символов — валидно."""
        req = RegisterRequest(
            email="user@example.com",
            password="12345678",
            full_name="Тест Тестов",
        )
        assert len(req.password) == 8

    def test_password_exactly_128_chars(self):
        """Пароль ровно 128 символов — валидно."""
        req = RegisterRequest(
            email="user@example.com",
            password="x" * 128,
            full_name="Тест Тестов",
        )
        assert len(req.password) == 128

    def test_full_name_too_short(self):
        """Имя менее 2 символов."""
        with pytest.raises(ValidationError):
            RegisterRequest(
                email="user@example.com",
                password="password123",
                full_name="А",
            )

    def test_full_name_exactly_2_chars(self):
        """Имя ровно 2 символа — валидно."""
        req = RegisterRequest(
            email="user@example.com",
            password="password123",
            full_name="АБ",
        )
        assert req.full_name == "АБ"

    def test_inn_10_digits(self):
        """ИНН из 10 цифр (юрлицо)."""
        req = RegisterRequest(
            email="user@example.com",
            password="password123",
            full_name="Тест",
            inn="1234567890",
        )
        assert req.inn == "1234567890"

    def test_inn_12_digits(self):
        """ИНН из 12 цифр (физлицо/ИП)."""
        req = RegisterRequest(
            email="user@example.com",
            password="password123",
            full_name="Тест",
            inn="123456789012",
        )
        assert req.inn == "123456789012"

    def test_inn_too_short(self):
        """ИНН менее 10 символов."""
        with pytest.raises(ValidationError):
            RegisterRequest(
                email="user@example.com",
                password="password123",
                full_name="Тест",
                inn="12345",
            )

    def test_inn_none_is_valid(self):
        """ИНН = None — валидно."""
        req = RegisterRequest(
            email="user@example.com",
            password="password123",
            full_name="Тест",
            inn=None,
        )
        assert req.inn is None

    def test_missing_required_email(self):
        """Отсутствует обязательное поле email."""
        with pytest.raises(ValidationError):
            RegisterRequest(
                password="password123",
                full_name="Тест",
            )

    def test_missing_required_password(self):
        """Отсутствует обязательное поле password."""
        with pytest.raises(ValidationError):
            RegisterRequest(
                email="user@example.com",
                full_name="Тест",
            )

    def test_missing_required_full_name(self):
        """Отсутствует обязательное поле full_name."""
        with pytest.raises(ValidationError):
            RegisterRequest(
                email="user@example.com",
                password="password123",
            )

    def test_default_tax_system(self):
        """Система налогообложения по умолчанию — usn_income_expense."""
        req = RegisterRequest(
            email="user@example.com",
            password="password123",
            full_name="Тест",
        )
        assert req.tax_system == "usn_income_expense"


# ─── LoginRequest ───────────────────────────────────────────────


class TestLoginRequest:
    """Тесты валидации LoginRequest."""

    def test_valid(self):
        """Валидный запрос на вход."""
        req = LoginRequest(
            email="user@example.com",
            password="password123",
        )
        assert req.email == "user@example.com"
        assert req.password == "password123"

    def test_invalid_email(self):
        """Невалидный email при входе."""
        with pytest.raises(ValidationError):
            LoginRequest(
                email="not-email",
                password="password123",
            )

    def test_missing_password(self):
        """Отсутствует пароль."""
        with pytest.raises(ValidationError):
            LoginRequest(
                email="user@example.com",
            )

    def test_empty_password_allowed(self):
        """Пустой пароль формально проходит валидацию (проверка — в сервисе)."""
        req = LoginRequest(
            email="user@example.com",
            password="",
        )
        assert req.password == ""


# ─── TokenResponse ──────────────────────────────────────────────


class TestTokenResponse:
    """Тесты TokenResponse."""

    def test_valid(self):
        """Валидный ответ с токенами."""
        resp = TokenResponse(
            access_token="access.jwt.token",
            refresh_token="refresh.jwt.token",
        )
        assert resp.access_token == "access.jwt.token"
        assert resp.refresh_token == "refresh.jwt.token"
        assert resp.token_type == "bearer"

    def test_default_token_type(self):
        """token_type по умолчанию — 'bearer'."""
        resp = TokenResponse(
            access_token="a",
            refresh_token="b",
        )
        assert resp.token_type == "bearer"

    def test_custom_token_type(self):
        """Кастомный token_type."""
        resp = TokenResponse(
            access_token="a",
            refresh_token="b",
            token_type="custom",
        )
        assert resp.token_type == "custom"


# ─── RefreshTokenRequest ────────────────────────────────────────


class TestRefreshTokenRequest:
    """Тесты RefreshTokenRequest."""

    def test_valid(self):
        """Валидный запрос на обновление."""
        req = RefreshTokenRequest(refresh_token="some.refresh.token")
        assert req.refresh_token == "some.refresh.token"

    def test_missing_token(self):
        """Отсутствует refresh_token."""
        with pytest.raises(ValidationError):
            RefreshTokenRequest()
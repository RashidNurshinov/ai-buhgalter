"""
Тесты аутентификации (пункт 1.3.9).

Тестируем:
- AuthService: register, login, refresh_tokens
- Валидация входных данных
- Обработка ошибок (дубликат email, неверный пароль, неактивный аккаунт)
- Корректность JWT-токенов после регистрации/логина
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.constants.enums import TaxSystem
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.schemas.auth import (
    LoginRequest,
    RefreshTokenRequest,
    RegisterRequest,
    TokenResponse,
)
from app.services.auth_service import AuthService


# ─── Фикстуры ───────────────────────────────────────────────


@pytest.fixture
def mock_db():
    """Замоканная async-сессия БД."""
    db = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.flush = AsyncMock()
    db.execute = AsyncMock()
    return db


@pytest.fixture
def existing_user():
    """Мок существующего пользователя в БД."""
    user = MagicMock()
    user.id = uuid.UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
    user.email = "existing@example.com"
    user.hashed_password = hash_password("correctpassword123")
    user.full_name = "Существующий Пользователь"
    user.inn = "1234567890"
    user.business_name = "ИП Тест"
    user.tax_system = TaxSystem.USN_INCOME_EXPENSE
    user.is_active = True
    user.created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    user.updated_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return user


@pytest.fixture
def inactive_user():
    """Мок деактивированного пользователя."""
    user = MagicMock()
    user.id = uuid.UUID("11111111-2222-3333-4444-555555555555")
    user.email = "inactive@example.com"
    user.hashed_password = hash_password("password123")
    user.full_name = "Неактивный Пользователь"
    user.is_active = False
    return user


# ─── RegisterRequest (Pydantic) ─────────────────────────────


class TestRegisterRequestSchema:
    """Тесты Pydantic-схемы RegisterRequest."""

    def test_valid_register_request(self):
        """Валидный запрос на регистрацию."""
        req = RegisterRequest(
            email="test@example.com",
            password="password123",
            full_name="Иванов Иван",
            inn="1234567890",
            business_name="ИП Иванов",
            tax_system="usn_income_expense",
        )
        assert req.email == "test@example.com"
        assert req.password == "password123"
        assert req.full_name == "Иванов Иван"

    def test_minimal_register_request(self):
        """Минимальный запрос (только обязательные поля)."""
        req = RegisterRequest(
            email="min@example.com",
            password="12345678",
            full_name="Тест",
        )
        assert req.inn is None
        assert req.business_name is None
        assert req.tax_system == "usn_income_expense"

    def test_register_request_short_password(self):
        """Слишком короткий пароль → ошибка валидации."""
        with pytest.raises(Exception):
            RegisterRequest(
                email="test@example.com",
                password="short",
                full_name="Тест",
            )

    def test_register_request_short_name(self):
        """Слишком короткое имя → ошибка валидации."""
        with pytest.raises(Exception):
            RegisterRequest(
                email="test@example.com",
                password="password123",
                full_name="A",
            )

    def test_register_request_invalid_email(self):
        """Невалидный email → ошибка валидации."""
        with pytest.raises(Exception):
            RegisterRequest(
                email="not-an-email",
                password="password123",
                full_name="Тест",
            )


# ─── LoginRequest (Pydantic) ────────────────────────────────


class TestLoginRequestSchema:
    """Тесты Pydantic-схемы LoginRequest."""

    def test_valid_login_request(self):
        """Валидный запрос на вход."""
        req = LoginRequest(
            email="test@example.com",
            password="password123",
        )
        assert req.email == "test@example.com"

    def test_login_request_invalid_email(self):
        """Невалидный email → ошибка."""
        with pytest.raises(Exception):
            LoginRequest(email="bad-email", password="password123")


# ─── TokenResponse (Pydantic) ───────────────────────────────


class TestTokenResponseSchema:
    """Тесты Pydantic-схемы TokenResponse."""

    def test_token_response(self):
        """Создание ответа с токенами."""
        resp = TokenResponse(
            access_token="abc.def.ghi",
            refresh_token="jkl.mno.pqr",
        )
        assert resp.access_token == "abc.def.ghi"
        assert resp.refresh_token == "jkl.mno.pqr"
        assert resp.token_type == "bearer"


# ─── AuthService.register ───────────────────────────────────


class TestAuthServiceRegister:
    """Тесты регистрации через AuthService."""

    @pytest.mark.asyncio
    async def test_register_success(self, mock_db):
        """Успешная регистрация нового пользователя."""
        # Мок: пользователь с таким email не найден
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        # Мок refresh: присваиваем ID
        async def fake_refresh(user):
            user.id = uuid.uuid4()

        mock_db.refresh = AsyncMock(side_effect=fake_refresh)

        service = AuthService(mock_db)
        data = RegisterRequest(
            email="new@example.com",
            password="securepassword",
            full_name="Новый Пользователь",
        )

        result = await service.register(data)

        assert isinstance(result, TokenResponse)
        assert result.access_token != ""
        assert result.refresh_token != ""
        assert result.token_type == "bearer"
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_register_duplicate_email(self, mock_db, existing_user):
        """Регистрация с существующим email → ValueError."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_user
        mock_db.execute.return_value = mock_result

        service = AuthService(mock_db)
        data = RegisterRequest(
            email="existing@example.com",
            password="securepassword",
            full_name="Дубликат",
        )

        with pytest.raises(ValueError, match="уже существует"):
            await service.register(data)

    @pytest.mark.asyncio
    async def test_register_invalid_tax_system_fallback(self, mock_db):
        """Невалидная система налогообложения → fallback на USN_INCOME_EXPENSE."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        async def fake_refresh(user):
            user.id = uuid.uuid4()
            # Проверяем, что tax_system — корректный fallback
            assert user.tax_system == TaxSystem.USN_INCOME_EXPENSE

        mock_db.refresh = AsyncMock(side_effect=fake_refresh)

        service = AuthService(mock_db)
        data = RegisterRequest(
            email="new@example.com",
            password="securepassword",
            full_name="Тест",
            tax_system="invalid_system",
        )

        result = await service.register(data)
        assert isinstance(result, TokenResponse)

    @pytest.mark.asyncio
    async def test_register_tokens_are_valid_jwt(self, mock_db):
        """Токены после регистрации — валидные JWT."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        test_id = uuid.uuid4()

        async def fake_refresh(user):
            user.id = test_id

        mock_db.refresh = AsyncMock(side_effect=fake_refresh)

        service = AuthService(mock_db)
        data = RegisterRequest(
            email="jwt@example.com",
            password="securepassword",
            full_name="JWT Тест",
        )

        result = await service.register(data)

        # Декодируем токены
        access_payload = decode_token(result.access_token)
        refresh_payload = decode_token(result.refresh_token)

        assert access_payload is not None
        assert access_payload["sub"] == str(test_id)
        assert access_payload["type"] == "access"

        assert refresh_payload is not None
        assert refresh_payload["sub"] == str(test_id)
        assert refresh_payload["type"] == "refresh"


# ─── AuthService.login ──────────────────────────────────────


class TestAuthServiceLogin:
    """Тесты входа через AuthService."""

    @pytest.mark.asyncio
    async def test_login_success(self, mock_db, existing_user):
        """Успешный вход."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_user
        mock_db.execute.return_value = mock_result

        service = AuthService(mock_db)
        result = await service.login(
            email="existing@example.com",
            password="correctpassword123",
        )

        assert isinstance(result, TokenResponse)
        assert result.access_token != ""
        assert result.refresh_token != ""

    @pytest.mark.asyncio
    async def test_login_wrong_email(self, mock_db):
        """Несуществующий email → ValueError."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        service = AuthService(mock_db)
        with pytest.raises(ValueError, match="Неверный email или пароль"):
            await service.login(email="nonexistent@example.com", password="anything")

    @pytest.mark.asyncio
    async def test_login_wrong_password(self, mock_db, existing_user):
        """Неверный пароль → ValueError."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_user
        mock_db.execute.return_value = mock_result

        service = AuthService(mock_db)
        with pytest.raises(ValueError, match="Неверный email или пароль"):
            await service.login(email="existing@example.com", password="wrongpassword")

    @pytest.mark.asyncio
    async def test_login_inactive_user(self, mock_db, inactive_user):
        """Деактивированный аккаунт → ValueError."""
        # Устанавливаем корректный пароль для inactive_user
        inactive_user.hashed_password = hash_password("password123")

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = inactive_user
        mock_db.execute.return_value = mock_result

        service = AuthService(mock_db)
        with pytest.raises(ValueError, match="деактивирован"):
            await service.login(email="inactive@example.com", password="password123")

    @pytest.mark.asyncio
    async def test_login_tokens_contain_user_id(self, mock_db, existing_user):
        """Токены после логина содержат user_id в sub."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_user
        mock_db.execute.return_value = mock_result

        service = AuthService(mock_db)
        result = await service.login(
            email="existing@example.com",
            password="correctpassword123",
        )

        payload = decode_token(result.access_token)
        assert payload["sub"] == str(existing_user.id)


# ─── AuthService.refresh_tokens ─────────────────────────────


class TestAuthServiceRefresh:
    """Тесты обновления токенов."""

    @pytest.mark.asyncio
    async def test_refresh_success(self, mock_db, existing_user):
        """Успешное обновление токенов."""
        import time

        refresh = create_refresh_token(subject=str(existing_user.id))

        # JWT exp is integer seconds, so we must cross a second boundary
        # for the new token to differ from the old one
        time.sleep(1.1)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_user
        mock_db.execute.return_value = mock_result

        service = AuthService(mock_db)
        result = await service.refresh_tokens(refresh)

        assert isinstance(result, TokenResponse)
        assert result.access_token != ""
        assert result.refresh_token != ""
        # After sleeping 1s, the new token should differ
        assert result.refresh_token != refresh

    @pytest.mark.asyncio
    async def test_refresh_invalid_token(self, mock_db):
        """Невалидный refresh-токен → ValueError."""
        service = AuthService(mock_db)
        with pytest.raises(ValueError, match="Невалидный"):
            await service.refresh_tokens("not.a.valid.token")

    @pytest.mark.asyncio
    async def test_refresh_with_access_token(self, mock_db, existing_user):
        """Попытка обновить через access-токен → ValueError."""
        access = create_access_token(subject=str(existing_user.id))

        service = AuthService(mock_db)
        with pytest.raises(ValueError, match="не является refresh"):
            await service.refresh_tokens(access)

    @pytest.mark.asyncio
    async def test_refresh_user_not_found(self, mock_db):
        """Пользователь удалён — refresh должен упасть."""
        refresh = create_refresh_token(subject=str(uuid.uuid4()))

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        service = AuthService(mock_db)
        with pytest.raises(ValueError, match="не найден"):
            await service.refresh_tokens(refresh)

    @pytest.mark.asyncio
    async def test_refresh_inactive_user(self, mock_db, inactive_user):
        """Обновление для деактивированного пользователя → ValueError."""
        refresh = create_refresh_token(subject=str(inactive_user.id))

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = inactive_user
        mock_db.execute.return_value = mock_result

        service = AuthService(mock_db)
        with pytest.raises(ValueError, match="деактивирован"):
            await service.refresh_tokens(refresh)
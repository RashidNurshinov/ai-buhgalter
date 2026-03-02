"""
Тесты модуля безопасности: JWT-токены и хэширование паролей.

Тестируем:
- Хэширование и проверка паролей (bcrypt)
- Создание и декодирование access/refresh JWT-токенов
- Обработка невалидных токенов
- Срок действия токенов
"""

from datetime import timedelta

import pytest

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)


# ─── Хэширование паролей ────────────────────────────────────────


class TestPasswordHashing:
    """Тесты хэширования и проверки паролей."""

    def test_hash_password_returns_string(self):
        """hash_password возвращает строку."""
        hashed = hash_password("mypassword123")
        assert isinstance(hashed, str)
        assert len(hashed) > 0

    def test_hash_password_different_from_plain(self):
        """Хэш отличается от исходного пароля."""
        password = "securepassword"
        hashed = hash_password(password)
        assert hashed != password

    def test_hash_password_different_each_time(self):
        """Каждый вызов hash_password генерирует разный хэш (соль)."""
        password = "samepassword"
        hash1 = hash_password(password)
        hash2 = hash_password(password)
        assert hash1 != hash2  # Разные соли → разные хэши

    def test_verify_password_correct(self):
        """verify_password возвращает True для правильного пароля."""
        password = "correctpassword"
        hashed = hash_password(password)
        assert verify_password(password, hashed) is True

    def test_verify_password_incorrect(self):
        """verify_password возвращает False для неправильного пароля."""
        hashed = hash_password("correctpassword")
        assert verify_password("wrongpassword", hashed) is False

    def test_verify_password_empty_string(self):
        """verify_password с пустой строкой — False."""
        hashed = hash_password("somepassword")
        assert verify_password("", hashed) is False

    def test_hash_password_unicode(self):
        """Хэширование unicode-пароля (кириллица)."""
        password = "пароль123"
        hashed = hash_password(password)
        assert verify_password(password, hashed) is True
        assert verify_password("другойпароль", hashed) is False

    def test_hash_password_special_chars(self):
        """Хэширование пароля со спецсимволами."""
        password = "p@$$w0rd!#%^&*()"
        hashed = hash_password(password)
        assert verify_password(password, hashed) is True

    def test_hash_password_long(self):
        """Хэширование длинного пароля."""
        password = "a" * 128
        hashed = hash_password(password)
        assert verify_password(password, hashed) is True


# ─── JWT Access Token ────────────────────────────────────────────


class TestAccessToken:
    """Тесты создания и декодирования access-токенов."""

    def test_create_access_token_returns_string(self):
        """create_access_token возвращает строку."""
        token = create_access_token(subject="user-123")
        assert isinstance(token, str)
        assert len(token) > 0

    def test_decode_access_token_valid(self):
        """Декодирование валидного access-токена."""
        subject = "user-uuid-12345"
        token = create_access_token(subject=subject)
        payload = decode_token(token)

        assert payload is not None
        assert payload["sub"] == subject
        assert payload["type"] == "access"
        assert "exp" in payload

    def test_access_token_custom_expiry(self):
        """Access-токен с кастомным сроком."""
        token = create_access_token(
            subject="user-123",
            expires_delta=timedelta(hours=2),
        )
        payload = decode_token(token)
        assert payload is not None
        assert payload["sub"] == "user-123"

    def test_access_token_expired(self):
        """Просроченный access-токен возвращает None."""
        token = create_access_token(
            subject="user-123",
            expires_delta=timedelta(seconds=-1),  # Уже истёк
        )
        payload = decode_token(token)
        assert payload is None

    def test_access_token_type_is_access(self):
        """Поле type в access-токене = 'access'."""
        token = create_access_token(subject="user-123")
        payload = decode_token(token)
        assert payload["type"] == "access"


# ─── JWT Refresh Token ──────────────────────────────────────────


class TestRefreshToken:
    """Тесты создания и декодирования refresh-токенов."""

    def test_create_refresh_token_returns_string(self):
        """create_refresh_token возвращает строку."""
        token = create_refresh_token(subject="user-123")
        assert isinstance(token, str)
        assert len(token) > 0

    def test_decode_refresh_token_valid(self):
        """Декодирование валидного refresh-токена."""
        subject = "user-uuid-67890"
        token = create_refresh_token(subject=subject)
        payload = decode_token(token)

        assert payload is not None
        assert payload["sub"] == subject
        assert payload["type"] == "refresh"
        assert "exp" in payload

    def test_refresh_token_custom_expiry(self):
        """Refresh-токен с кастомным сроком."""
        token = create_refresh_token(
            subject="user-123",
            expires_delta=timedelta(days=30),
        )
        payload = decode_token(token)
        assert payload is not None

    def test_refresh_token_expired(self):
        """Просроченный refresh-токен возвращает None."""
        token = create_refresh_token(
            subject="user-123",
            expires_delta=timedelta(seconds=-1),
        )
        payload = decode_token(token)
        assert payload is None

    def test_refresh_token_type_is_refresh(self):
        """Поле type в refresh-токене = 'refresh'."""
        token = create_refresh_token(subject="user-123")
        payload = decode_token(token)
        assert payload["type"] == "refresh"

    def test_access_and_refresh_tokens_different(self):
        """Access и refresh токены для одного пользователя различаются."""
        subject = "user-123"
        access = create_access_token(subject=subject)
        refresh = create_refresh_token(subject=subject)
        assert access != refresh


# ─── decode_token Edge Cases ────────────────────────────────────


class TestDecodeToken:
    """Тесты decode_token с невалидными входами."""

    def test_decode_empty_string(self):
        """Пустая строка → None."""
        assert decode_token("") is None

    def test_decode_random_string(self):
        """Случайная строка → None."""
        assert decode_token("this.is.not.a.jwt") is None

    def test_decode_tampered_token(self):
        """Токен с подменённой подписью → None."""
        token = create_access_token(subject="user-123")
        # Подменяем послед��ий символ
        tampered = token[:-1] + ("A" if token[-1] != "A" else "B")
        assert decode_token(tampered) is None

    def test_decode_none_handling(self):
        """Передача невалидного токена не вызывает исключение."""
        # Не должно упасть — возвращает None
        result = decode_token("invalid-token-data")
        assert result is None

    def test_decode_token_preserves_subject(self):
        """Subject сохраняется в токене при декодировании."""
        subjects = [
            "12345678-1234-5678-1234-567812345678",
            "user@example.com",
            "42",
        ]
        for subject in subjects:
            token = create_access_token(subject=subject)
            payload = decode_token(token)
            assert payload["sub"] == subject
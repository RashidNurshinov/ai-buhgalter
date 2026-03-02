"""
Тесты конфигурации приложения.

Тестируем:
- Settings — загрузка настроек
- Свойства: is_production, is_development, upload_path
- Значения по умолчанию
"""

from pathlib import Path

import pytest

from app.core.config import Settings, settings


class TestSettings:
    """Тесты объекта Settings."""

    def test_singleton_exists(self):
        """Singleton settings инициализирован."""
        assert settings is not None
        assert isinstance(settings, Settings)

    def test_app_name(self):
        """Название приложения."""
        assert settings.APP_NAME == "AI-Buhgalter"

    def test_default_env_development(self):
        """Окружение по умолчанию — development."""
        s = Settings(APP_ENV="development")
        assert s.APP_ENV == "development"
        assert s.is_development is True
        assert s.is_production is False

    def test_production_env(self):
        """Продакшн-окружение."""
        s = Settings(APP_ENV="production")
        assert s.is_production is True
        assert s.is_development is False

    def test_staging_env(self):
        """Staging — ни production, ни development."""
        s = Settings(APP_ENV="staging")
        assert s.is_production is False
        assert s.is_development is False

    def test_jwt_defaults(self):
        """Параметры JWT по умолчанию."""
        s = Settings()
        assert s.JWT_ACCESS_TOKEN_EXPIRE_MINUTES == 30
        assert s.JWT_REFRESH_TOKEN_EXPIRE_DAYS == 7
        assert s.JWT_ALGORITHM == "HS256"

    def test_max_file_size_bytes(self):
        """Конвертация размера файла в байты."""
        s = Settings(MAX_FILE_SIZE_MB=50)
        assert s.max_file_size_bytes == 50 * 1024 * 1024

    def test_max_file_size_bytes_custom(self):
        """Кастомный размер файла."""
        s = Settings(MAX_FILE_SIZE_MB=100)
        assert s.max_file_size_bytes == 100 * 1024 * 1024

    def test_upload_path_returns_path(self):
        """upload_path возвращает Path."""
        s = Settings(UPLOAD_DIR="./test_storage/uploads")
        assert isinstance(s.upload_path, Path)

    def test_database_echo_default_false(self):
        """DATABASE_ECHO по умолчанию False."""
        s = Settings()
        assert s.DATABASE_ECHO is False

    def test_openrouter_defaults(self):
        """Параметры OpenRouter по умолчанию."""
        s = Settings()
        assert "openrouter.ai" in s.OPENROUTER_BASE_URL
        assert s.OPENROUTER_REQUEST_TIMEOUT == 120

    def test_smtp_defaults(self):
        """Параметры SMTP по умолчанию."""
        s = Settings()
        assert s.SMTP_HOST == "smtp.gmail.com"
        assert s.SMTP_PORT == 587

    def test_redis_url_default(self):
        """Redis URL по умолчанию."""
        s = Settings()
        assert "redis://" in s.REDIS_URL

    def test_celery_urls(self):
        """Celery broker и result backend."""
        s = Settings()
        assert "redis://" in s.CELERY_BROKER_URL
        assert "redis://" in s.CELERY_RESULT_BACKEND
        # Broker и backend должны быть разными
        assert s.CELERY_BROKER_URL != s.CELERY_RESULT_BACKEND

    def test_extra_ignore(self):
        """extra='ignore' — лишние поля не вызывают ошибку."""
        s = Settings(UNKNOWN_FIELD="value")
        assert not hasattr(s, "UNKNOWN_FIELD")


class TestSettingsEnvironment:
    """Тесты свойств окружения."""

    def test_is_development_true(self):
        s = Settings(APP_ENV="development")
        assert s.is_development is True

    def test_is_development_false(self):
        s = Settings(APP_ENV="production")
        assert s.is_development is False

    def test_is_production_true(self):
        s = Settings(APP_ENV="production")
        assert s.is_production is True

    def test_is_production_false(self):
        s = Settings(APP_ENV="development")
        assert s.is_production is False
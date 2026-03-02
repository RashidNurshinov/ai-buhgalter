"""
Конфигурация приложения через Pydantic Settings.
Значения загружаются из переменных окружения / файла .env
"""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Главный объект настроек приложения."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # === Приложение ===
    APP_NAME: str = "AI-Buhgalter"
    APP_ENV: str = "development"  # development | staging | production
    APP_DEBUG: bool = True
    APP_SECRET_KEY: str = "change-me-in-production"
    APP_DOMAIN: str = "localhost"
    APP_URL: str = "http://localhost:8000"

    # === База данных ===
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/ai_buhgalter"
    DATABASE_ECHO: bool = False

    # === Redis ===
    REDIS_URL: str = "redis://localhost:6379/0"

    # === Celery ===
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # === JWT ===
    JWT_SECRET_KEY: str = "change-me-jwt-secret"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    JWT_ALGORITHM: str = "HS256"

    # === OpenRouter (ИИ) ===
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    OPENROUTER_DEFAULT_MODEL: str = "anthropic/claude-sonnet-4-20250514"
    OPENROUTER_FAST_MODEL: str = "anthropic/claude-haiku-3"
    OPENROUTER_REQUEST_TIMEOUT: int = 120

    # === Email (SMTP) ===
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_NAME: str = "ИИ-Бухгалтер"
    SMTP_FROM_EMAIL: str = ""

    # === Telegram (Этап 3) ===
    TELEGRAM_BOT_TOKEN: str = ""

    # === Файловое хранилище ===
    UPLOAD_DIR: str = "./storage/uploads"
    MAX_FILE_SIZE_MB: int = 50

    # === Свойства ===
    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"

    @property
    def is_development(self) -> bool:
        return self.APP_ENV == "development"

    @property
    def max_file_size_bytes(self) -> int:
        return self.MAX_FILE_SIZE_MB * 1024 * 1024

    @property
    def upload_path(self) -> Path:
        path = Path(self.UPLOAD_DIR)
        path.mkdir(parents=True, exist_ok=True)
        return path


# Singleton — единственный экземпляр настроек
settings = Settings()
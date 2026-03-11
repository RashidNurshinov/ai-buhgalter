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
    # Основная модель: Qwen 2.5 72B — мощная и недорогая (~$0.35/1M input, ~$0.40/1M output)
    OPENROUTER_DEFAULT_MODEL: str = "qwen/qwen-2.5-72b-instruct"
    # Быстрая модель для простых задач: Qwen 2.5 Coder 32B
    OPENROUTER_FAST_MODEL: str = "qwen/qwen-2.5-coder-32b-instruct"
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

    # === Сбербанк API (Этап 2) ===
    SBERBANK_API_URL: str = "https://api.sberbank.ru/prod"
    SBERBANK_CLIENT_ID: str = ""
    SBERBANK_CLIENT_SECRET: str = ""
    SBERBANK_SCOPE: str = "/statement /accounts"

    # === Тинькофф API (Этап 2) ===
    TINKOFF_API_URL: str = "https://business.tinkoff.ru/openapi"
    TINKOFF_API_TOKEN: str = ""

    # === ОФД API (Этап 2) ===
    OFD_API_URL: str = ""
    OFD_API_KEY: str = ""

    # === Сфера / Контур API (Этап 2) ===
    SFERA_API_URL: str = ""
    SFERA_API_TOKEN: str = ""

    # === СБИС API (Этап 2) ===
    SBIS_API_URL: str = ""
    SBIS_APP_CLIENT_ID: str = ""

    # === МойСклад API (Этап 2) ===
    MOYSKLAD_API_URL: str = "https://api.moysklad.ru/api/remap/1.2"
    MOYSKLAD_API_TOKEN: str = ""

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


def validate_production_settings() -> None:
    """Проверка критических настроек при запуске в production."""
    if settings.is_production:
        if "change-me" in settings.JWT_SECRET_KEY:
            raise RuntimeError("JWT_SECRET_KEY must be changed in production!")
        if "change-me" in settings.APP_SECRET_KEY:
            raise RuntimeError("APP_SECRET_KEY must be changed in production!")

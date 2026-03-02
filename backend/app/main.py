"""
Точка входа FastAPI-приложения AI-Buhgalter.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.middleware import RequestLoggingMiddleware, ErrorHandlerMiddleware
from app.core.redis import close_redis


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Жизненный цикл приложения: startup / shutdown."""
    # === Startup ===
    from app.core.logging import setup_logging
    setup_logging(
        log_level="DEBUG" if settings.is_development else "INFO",
        json_output=settings.is_production,
    )
    print(f"🚀 {settings.APP_NAME} starting up (env={settings.APP_ENV})")
    yield
    # === Shutdown ===
    await close_redis()
    print(f"🛑 {settings.APP_NAME} shutting down")


app = FastAPI(
    title=settings.APP_NAME,
    description="ИИ-бухгалтер для ИП на УСН — автоматизация учёта, налогов и деклараций",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/api/docs" if settings.is_development else None,
    redoc_url="/api/redoc" if settings.is_development else None,
    openapi_url="/api/openapi.json" if settings.is_development else None,
)

# === CORS ===
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# === Middleware: логирование и обработка ошибок ===
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(ErrorHandlerMiddleware)


# === Health check ===
@app.get("/api/health", tags=["system"])
async def health_check():
    """Проверка состояния сервиса."""
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "env": settings.APP_ENV,
    }


# === Подключение роутеров API v1 ===
from app.api.v1.router import router as api_v1_router

app.include_router(api_v1_router, prefix="/api/v1")
"""
Middleware: логирование запросов, обработка ошибок.
"""

import time
import traceback
import logging

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("ai_buhgalter")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Логирование всех HTTP-запросов с временем выполнения."""

    async def dispatch(self, request: Request, call_next) -> Response:
        start_time = time.time()
        method = request.method
        url = str(request.url.path)
        query = str(request.url.query) if request.url.query else ""

        try:
            response = await call_next(request)
        except Exception as exc:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(
                f"❌ {method} {url} — EXCEPTION after {duration_ms:.0f}ms: {exc}"
            )
            return JSONResponse(
                status_code=500,
                content={
                    "success": False,
                    "error": "Internal Server Error",
                    "detail": str(exc) if logger.isEnabledFor(logging.DEBUG) else None,
                },
            )

        duration_ms = (time.time() - start_time) * 1000
        status = response.status_code

        # Цветовая маркировка по статусу
        if status < 400:
            log_fn = logger.info
            icon = "✅"
        elif status < 500:
            log_fn = logger.warning
            icon = "⚠️"
        else:
            log_fn = logger.error
            icon = "❌"

        log_line = f"{icon} {method} {url}"
        if query:
            log_line += f"?{query}"
        log_line += f" → {status} ({duration_ms:.0f}ms)"

        log_fn(log_line)

        # Добавляем заголовок с временем обработки
        response.headers["X-Process-Time-Ms"] = f"{duration_ms:.0f}"
        return response


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """Перехват необработанных исключений и возврат JSON."""

    async def dispatch(self, request: Request, call_next) -> Response:
        try:
            return await call_next(request)
        except Exception as exc:
            logger.error(
                f"Unhandled exception: {type(exc).__name__}: {exc}\n"
                f"{traceback.format_exc()}"
            )
            return JSONResponse(
                status_code=500,
                content={
                    "success": False,
                    "error": "Internal Server Error",
                    "detail": "Произошла внутренняя ошибка сервера. Пожалуйста, попробуйте позже.",
                },
            )
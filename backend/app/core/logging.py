"""
Настройка структурированного логирования через structlog.
Пункт плана: 1.1.6

Использование:
    from app.core.logging import setup_logging, get_logger

    setup_logging()  # Вызвать при старте приложения
    logger = get_logger(__name__)
    logger.info("event_name", user_id="123", action="login")
"""

import logging
import sys

import structlog


def setup_logging(
    log_level: str = "INFO",
    json_output: bool = False,
):
    """
    Настроить structlog + стандартный logging.

    Args:
        log_level: Уровень логирования (DEBUG, INFO, WARNING, ERROR)
        json_output: True — JSON-формат (для production), False — человекочитаемый
    """
    # Общие процессоры structlog
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    if json_output:
        # Production: JSON-формат для сбора логов
        renderer = structlog.processors.JSONRenderer(ensure_ascii=False)
    else:
        # Development: красивый вывод в консоль
        renderer = structlog.dev.ConsoleRenderer(
            colors=True,
            pad_event=35,
        )

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Настраиваем форматтер для стандартного logging
    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
        foreign_pre_chain=shared_processors,
    )

    # Корневой handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    # Настраиваем корневой логгер
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Уменьшаем шум от библиотек
    for noisy_logger in [
        "uvicorn.access",
        "uvicorn.error",
        "sqlalchemy.engine",
        "httpx",
        "httpcore",
        "celery",
    ]:
        logging.getLogger(noisy_logger).setLevel(logging.WARNING)

    # SQLAlchemy echo — только в DEBUG
    if log_level.upper() == "DEBUG":
        logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO)


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """
    Получить structlog-логгер.

    Использование:
        logger = get_logger(__name__)
        logger.info("user_login", user_id="abc123")
    """
    return structlog.get_logger(name)
"""
Базовая модель SQLAlchemy с общими полями для всех сущностей.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy import Enum as SaEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


# ─── PgEnum: корректная работа Python Enum ↔ PostgreSQL ────────
class PgEnum(SaEnum):
    """
    Обёртка над SQLAlchemy Enum, которая ГАРАНТИРУЕТ использование
    .value (lowercase) вместо .name (UPPERCASE) при записи в PostgreSQL.

    Проблема: стандартный sa.Enum с values_callable корректно создаёт
    PostgreSQL enum с lowercase значениями, но при INSERT отправляет
    .name (UPPERCASE), что вызывает:
        invalid input value for enum xxx_enum: "UPPERCASE"

    Решение: переопределяем _resolve_for_literal чтобы всегда
    передавать .value.
    """

    def __init__(self, enum_class, **kw):
        kw.setdefault("values_callable", lambda x: [e.value for e in x])
        kw.setdefault("native_enum", True)
        kw.setdefault("create_constraint", False)
        super().__init__(enum_class, **kw)
        self._enum_class = enum_class

    def _resolve_for_literal(self, value):
        """Конвертируем Python enum → .value строку перед отправкой в БД."""
        if isinstance(value, enum.Enum):
            return value.value
        return value

    def result_processor(self, dialect, coltype):
        """Конвертируем строку из БД → Python enum."""
        _enum_class = self._enum_class

        def process(value):
            if value is None:
                return None
            if isinstance(value, _enum_class):
                return value
            # Пробуем по value (lowercase)
            try:
                return _enum_class(value)
            except ValueError:
                pass
            # Пробуем по name (UPPERCASE) — fallback
            try:
                return _enum_class[value]
            except KeyError:
                return value

        return process

    def bind_processor(self, dialect):
        """Конвертируем Python enum → строку для отправки в БД."""
        def process(value):
            if value is None:
                return None
            if isinstance(value, enum.Enum):
                return value.value
            return value

        return process


# ─── Базовая модель ─────────────────────────────────────
class BaseModel(Base):
    """
    Абстрактная базовая модель.
    Все сущности наследуют id, created_at, updated_at.
    """

    __abstract__ = True

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
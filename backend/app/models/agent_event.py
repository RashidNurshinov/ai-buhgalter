"""
Модель AgentEvent (событие / триггер для AI-агента).
Справочник: СПРАВОЧНИК_СУЩНОСТЕЙ.md → models/agent_event.py
Архитектура: АРХИТЕКТУРА_AI_AGENT.md → раздел 8.2

Поля синхронизированы с миграцией 002_agent_tables.py
"""

import uuid

from sqlalchemy import Integer, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.constants.enums import AgentActionStatus, AgentTriggerType
from app.models.base import BaseModel, PgEnum


class AgentEvent(BaseModel):
    """
    Событие, запускающее цикл AI-агента.

    Примеры триггеров:
    - file_uploaded  → пользователь загрузил файл
    - chat_message   → пользователь написал в чат
    - scheduled      → плановое задание (пересчёт налогов, календарь)
    """

    __tablename__ = "agent_events"

    # Владелец
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Тип триггера
    trigger_type: Mapped[AgentTriggerType] = mapped_column(
        PgEnum(AgentTriggerType, name="agent_trigger_type_enum"),
        nullable=False,
        index=True,
    )

    # Статус обработки (миграция: agent_event_status_enum)
    status: Mapped[AgentActionStatus] = mapped_column(
        PgEnum(AgentActionStatus, name="agent_event_status_enum"),
        default=AgentActionStatus.PENDING,
        nullable=False,
        index=True,
    )

    # Приоритет (0=low, 5=normal, 10=critical)
    priority: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="5",
    )

    # Входные данные (JSON)
    payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Резюме агента (текстовый итог обработки)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Количество вызовов инструментов
    tool_calls_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
    )

    # Количество использованных токенов
    tokens_used: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
    )

    # Текст ошибки (если status = FAILED)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
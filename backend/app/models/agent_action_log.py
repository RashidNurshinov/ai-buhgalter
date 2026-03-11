"""
Модель AgentActionLog (лог действий AI-агента).
Справочник: СПРАВОЧНИК_СУЩНОСТЕЙ.md → models/agent_action_log.py

Поля синхронизированы с миграцией 002_agent_tables.py
"""

import uuid
from decimal import Decimal

from sqlalchemy import ForeignKey, Integer, Numeric, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.constants.enums import AgentActionStatus, AgentActionType
from app.models.base import BaseModel, PgEnum


class AgentActionLog(BaseModel):
    """
    Лог конкретного действия (tool call), выполненного AI-агентом
    в рамках обработки AgentEvent.
    """

    __tablename__ = "agent_action_logs"

    # Владелец (денормализация для быстрых выборок)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Ссылка на событие-триггер
    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agent_events.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Тип действия
    action_type: Mapped[AgentActionType] = mapped_column(
        PgEnum(AgentActionType, name="agent_action_type_enum"),
        nullable=False,
        index=True,
    )

    # Статус (миграция: agent_action_log_status_enum)
    status: Mapped[AgentActionStatus] = mapped_column(
        PgEnum(AgentActionStatus, name="agent_action_log_status_enum"),
        default=AgentActionStatus.PENDING,
        nullable=False,
    )

    # Номер шага в цикле агента
    step_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="1",
    )

    # Входные параметры (JSON) — имя колонки в БД: input_params
    input_params: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Результат (JSON) — имя колонки в БД: output_result
    output_result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Рассуждение агента (текст из LLM)
    agent_reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Длительность выполнения (мс)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Токены входные
    tokens_input: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
    )

    # Токены выходные
    tokens_output: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
    )

    # Стоимость (USD)
    cost_usd: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 6),
        nullable=True,
    )

    # Ошибка
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
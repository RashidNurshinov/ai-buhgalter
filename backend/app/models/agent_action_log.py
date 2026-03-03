"""
Модель лога действий AI-агента.
Справочник: СПРАВОЧНИК_СУЩНОСТЕЙ.md → models/agent_action_log.py
Архитектура: АРХИТЕКТУРА_AI_AGENT.md → раздел 3, 8
"""

import uuid
from decimal import Decimal

from sqlalchemy import Enum, ForeignKey, Integer, Numeric, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.constants.enums import AgentActionStatus, AgentActionType
from app.models.base import BaseModel


class AgentActionLog(BaseModel):
    """
    Лог каждого действия (tool call) AI-агента.

    Каждый вызов инструмента агентом записывается сюда.
    Связан с AgentEvent (одно событие → несколько действий).
    """

    __tablename__ = "agent_action_logs"

    # Владелец
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Родительское событие
    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agent_events.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Тип действия (какой tool вызван)
    action_type: Mapped[AgentActionType] = mapped_column(
        Enum(
            AgentActionType,
            name="agent_action_type_enum",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        index=True,
    )

    # Статус действия
    status: Mapped[AgentActionStatus] = mapped_column(
        Enum(
            AgentActionStatus,
            name="agent_action_log_status_enum",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=AgentActionStatus.PENDING,
    )

    # Порядковый номер действия в рамках события (step 1, 2, 3...)
    step_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    # Входные параметры tool call (JSON)
    input_params: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Результат выполнения tool call (JSON)
    output_result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Рассуждение агента перед вызовом (LLM reasoning)
    agent_reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Длительность выполнения в миллисекундах
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Токены, потраченные на этот шаг
    tokens_input: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tokens_output: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Стоимость в USD (примерная)
    cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)

    # Ошибка (если status = FAILED)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
"""
Модель лога действий AI-агента.
Справочник: СПРАВОЧНИК_СУЩНОСТЕЙ.md → models/agent_action_log.py
Архитектура: АРХИТЕКТУРА_AI_AGENT.md → раздел 3, 8
"""

from sqlalchemy import Column, Enum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB

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
    user_id = Column(
        String(32),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Родительское событие
    event_id = Column(
        String(32),
        ForeignKey("agent_events.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Тип действия (какой tool вызван)
    action_type = Column(
        Enum(AgentActionType, name="agent_action_type_enum"),
        nullable=False,
        index=True,
    )

    # Статус действия
    status = Column(
        Enum(AgentActionStatus, name="agent_action_log_status_enum"),
        nullable=False,
        default=AgentActionStatus.PENDING,
    )

    # Порядковый номер действия в рамках события (step 1, 2, 3...)
    step_number = Column(Integer, nullable=False, default=1)

    # Входные параметры tool call (JSON)
    input_params = Column(JSONB, nullable=True)

    # Результат выполнения tool call (JSON)
    output_result = Column(JSONB, nullable=True)

    # Рассуждение агента перед вызовом (LLM reasoning)
    agent_reasoning = Column(Text, nullable=True)

    # Длительность выполнения в миллисекундах
    duration_ms = Column(Integer, nullable=True)

    # Токены, потраченные на этот шаг
    tokens_input = Column(Integer, nullable=False, default=0)
    tokens_output = Column(Integer, nullable=False, default=0)

    # Стоимость в USD (примерная)
    cost_usd = Column(Numeric(10, 6), nullable=True)

    # Ошибка (если status = FAILED)
    error_message = Column(Text, nullable=True)
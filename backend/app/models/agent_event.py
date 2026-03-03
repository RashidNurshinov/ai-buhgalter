"""
Модель события AI-агента.
Справочник: СПРАВОЧНИК_СУЩНОСТЕЙ.md → models/agent_event.py
Архитектура: АРХИТЕКТУРА_AI_AGENT.md → раздел 4
"""

import uuid

from sqlalchemy import Enum, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.constants.enums import AgentActionStatus, AgentTriggerType
from app.models.base import BaseModel


class AgentEvent(BaseModel):
    """
    Событие, запускающее цикл AI-агента.

    Каждое событие — один запуск Agent Loop (observe → think → act → report).
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
        Enum(
            AgentTriggerType,
            name="agent_trigger_type_enum",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        index=True,
    )

    # Статус обработки события
    status: Mapped[AgentActionStatus] = mapped_column(
        Enum(
            AgentActionStatus,
            name="agent_event_status_enum",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=AgentActionStatus.PENDING,
        index=True,
    )

    # Приоритет (0 = low, 5 = normal, 10 = critical)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=5)

    # Данные события (payload): file_id, operation_ids, question и т.д.
    payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Итоговое резюме агента после обработки события
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Сколько tool-вызовов было сделано
    tool_calls_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Сколько токенов потрачено (input + output)
    tokens_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Ошибка (если status = FAILED)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
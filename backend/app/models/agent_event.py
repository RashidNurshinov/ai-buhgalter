"""
Модель события AI-агента.
Справочник: СПРАВОЧНИК_СУЩНОСТЕЙ.md → models/agent_event.py
Архитектура: АРХИТЕКТУРА_AI_AGENT.md → раздел 4
"""

from sqlalchemy import Column, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB

from app.constants.enums import AgentActionStatus, AgentTriggerType
from app.models.base import BaseModel


class AgentEvent(BaseModel):
    """
    Событие, запускающее цикл AI-агента.
    
    Каждое событие — один запуск Agent Loop (observe → think → act → report).
    """

    __tablename__ = "agent_events"

    # Владелец
    user_id = Column(
        String(32),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Тип триггера
    trigger_type = Column(
        Enum(AgentTriggerType, name="agent_trigger_type_enum"),
        nullable=False,
        index=True,
    )

    # Статус обработки события
    status = Column(
        Enum(AgentActionStatus, name="agent_event_status_enum"),
        nullable=False,
        default=AgentActionStatus.PENDING,
        index=True,
    )

    # Приоритет (0 = low, 5 = normal, 10 = critical)
    priority = Column(Integer, nullable=False, default=5)

    # Данные события (payload): file_id, operation_ids, question и т.д.
    payload = Column(JSONB, nullable=True)

    # Итоговое резюме агента после обработки события
    summary = Column(Text, nullable=True)

    # Сколько tool-вызовов было сделано
    tool_calls_count = Column(Integer, nullable=False, default=0)

    # Сколько токенов потрачено (input + output)
    tokens_used = Column(Integer, nullable=False, default=0)

    # Ошибка (если status = FAILED)
    error_message = Column(Text, nullable=True)
"""
Модель запроса подтверждения от пользователя.
Справочник: СПРАВОЧНИК_СУЩНОСТЕЙ.md → models/agent_confirmation.py
Архитектура: АРХИТЕКТУРА_AI_AGENT.md → раздел 8.2
"""

from sqlalchemy import Column, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB

from app.constants.enums import AgentConfirmationStatus, AgentConfirmationType
from app.models.base import BaseModel


class AgentConfirmation(BaseModel):
    """
    Запрос подтверждения от пользователя.

    Когда агент не уверен или действие требует одобрения,
    он создаёт AgentConfirmation и ждёт ответа.
    """

    __tablename__ = "agent_confirmations"

    # Владелец
    user_id = Column(
        String(32),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Событие, породившее запрос
    event_id = Column(
        String(32),
        ForeignKey("agent_events.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Тип подтверждения
    confirmation_type = Column(
        Enum(AgentConfirmationType, name="agent_confirmation_type_enum"),
        nullable=False,
        index=True,
    )

    # Статус
    status = Column(
        Enum(AgentConfirmationStatus, name="agent_confirmation_status_enum"),
        nullable=False,
        default=AgentConfirmationStatus.PENDING,
        index=True,
    )

    # Вопрос агента пользователю (человекочитаемый текст)
    question = Column(Text, nullable=False)

    # Данные для подтверждения (JSON): предложенная категория, данные документа и т.д.
    proposed_data = Column(JSONB, nullable=True)

    # Варианты ответа (JSON array): ["Да, верно", "Нет, это аренда", "Указать вручную"]
    options = Column(JSONB, nullable=True)

    # Ответ пользователя
    user_response = Column(Text, nullable=True)

    # Данные, исправленные пользователем (если status = MODIFIED)
    user_modified_data = Column(JSONB, nullable=True)

    # Ссылка на связанную сущность (operation_id, document_id и т.д.)
    related_entity_type = Column(String(50), nullable=True)  # "bank_operation", "document"
    related_entity_id = Column(String(32), nullable=True)
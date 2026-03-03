"""
Модель запроса подтверждения от пользователя.
Справочник: СПРАВОЧНИК_СУЩНОСТЕЙ.md → models/agent_confirmation.py
Архитектура: АРХИТЕКТУРА_AI_AGENT.md → раздел 8.2
"""

import uuid

from sqlalchemy import Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

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
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Событие, породившее запрос
    event_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agent_events.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Тип подтверждения
    confirmation_type: Mapped[AgentConfirmationType] = mapped_column(
        Enum(
            AgentConfirmationType,
            name="agent_confirmation_type_enum",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        index=True,
    )

    # Статус
    status: Mapped[AgentConfirmationStatus] = mapped_column(
        Enum(
            AgentConfirmationStatus,
            name="agent_confirmation_status_enum",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=AgentConfirmationStatus.PENDING,
        index=True,
    )

    # Вопрос агента пользователю (человекочитаемый текст)
    question: Mapped[str] = mapped_column(Text, nullable=False)

    # Данные для подтверждения (JSON): предложенная категория, данные документа и т.д.
    proposed_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Варианты ответа (JSON array): ["Да, верно", "Нет, это аренда", "Указать вручную"]
    options: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Ответ пользователя
    user_response: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Данные, исправленные пользователем (если status = MODIFIED)
    user_modified_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Ссылка на связанную сущность (operation_id, document_id и т.д.)
    related_entity_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    related_entity_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
"""
Модель AgentConfirmation (запрос подтверждения от пользователя).
Справочник: СПРАВОЧНИК_СУЩНОСТЕЙ.md → models/agent_confirmation.py

Поля синхронизированы с миграцией 002_agent_tables.py
"""

import uuid

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.constants.enums import AgentConfirmationStatus, AgentConfirmationType
from app.models.base import BaseModel, PgEnum


class AgentConfirmation(BaseModel):
    """
    Запрос подтверждения у пользователя перед выполнением
    необратимого / важного действия AI-агента.
    """

    __tablename__ = "agent_confirmations"

    # Владелец
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Ссылка на событие-триггер (может быть NULL)
    event_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agent_events.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Тип подтверждения
    confirmation_type: Mapped[AgentConfirmationType] = mapped_column(
        PgEnum(AgentConfirmationType, name="agent_confirmation_type_enum"),
        nullable=False,
        index=True,
    )

    # Статус
    status: Mapped[AgentConfirmationStatus] = mapped_column(
        PgEnum(AgentConfirmationStatus, name="agent_confirmation_status_enum"),
        default=AgentConfirmationStatus.PENDING,
        nullable=False,
        index=True,
    )

    # Вопрос пользователю (что нужно подтвердить)
    question: Mapped[str] = mapped_column(Text, nullable=False)

    # Предлагаемые данные (JSON)
    proposed_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Варианты ответа (JSON)
    options: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Ответ пользователя (текст)
    user_response: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Изменённые пользователем данные (JSON)
    user_modified_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Связанная сущность
    related_entity_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    related_entity_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
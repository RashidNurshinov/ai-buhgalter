"""
Модель AiChatMessage (сообщение ИИ-чата).
Справочник: СПРАВОЧНИК_СУЩНОСТЕЙ.md → таблица ai_chat_messages
"""

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class AiChatMessage(BaseModel):
    """Сообщение в чате с ИИ-помощником."""

    __tablename__ = "ai_chat_messages"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(
        String(20), nullable=False  # "user", "assistant", "system"
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    context_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    model_used: Mapped[str | None] = mapped_column(String(100), nullable=True)
    tokens_used: Mapped[int | None] = mapped_column(nullable=True)
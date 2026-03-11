"""
Pydantic-схемы для AI Agent API.
Справочник: СПРАВОЧНИК_СУЩНОСТЕЙ.md → schemas/agent.py
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.constants.enums import (
    AgentActionStatus,
    AgentActionType,
    AgentConfirmationStatus,
    AgentConfirmationType,
    AgentTriggerType,
)


# ─── Запросы ────────────────────────────────────────────


class AgentChatRequest(BaseModel):
    """Запрос в чат с агентом (USER_QUESTION)."""
    message: str = Field(..., min_length=1, max_length=5000, description="Текст вопроса")


class AgentCommandRequest(BaseModel):
    """Прямая команда агенту (USER_COMMAND)."""
    command: str = Field(..., min_length=1, max_length=5000, description="Команда")


class AgentConfirmationResponse(BaseModel):
    """Ответ пользователя на запрос подтверждения."""
    confirmation_id: str = Field(..., description="ID подтверждения")
    action: str = Field(..., description="Действие: confirm / reject / modify")
    user_response: str | None = Field(None, description="Текст ответа пользователя")
    modified_data: dict | None = Field(None, description="Исправленные данные (если action=modify)")


# ─── Ответы ─────────────────────────────────────────────


class AgentEventOut(BaseModel):
    """Событие агента (для API-ответов)."""
    id: UUID
    trigger_type: AgentTriggerType
    status: AgentActionStatus
    priority: int
    summary: str | None = None
    tool_calls_count: int = 0
    tokens_used: int = 0
    created_at: datetime
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class AgentActionOut(BaseModel):
    """Действие агента из лога."""
    id: UUID
    action_type: AgentActionType
    status: AgentActionStatus
    step_number: int
    agent_reasoning: str | None = None
    input_params: dict | None = None
    output_result: dict | None = None
    duration_ms: int | None = None
    tokens_input: int = 0
    tokens_output: int = 0
    created_at: datetime

    model_config = {"from_attributes": True}


class AgentConfirmationOut(BaseModel):
    """Запрос подтверждения для фронтенда."""
    id: UUID
    confirmation_type: AgentConfirmationType
    status: AgentConfirmationStatus
    question: str
    proposed_data: dict | None = None
    options: list | None = None
    related_entity_type: str | None = None
    related_entity_id: str | None = None
    user_response: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AgentChatResponse(BaseModel):
    """Ответ агента на вопрос в чате."""
    event_id: str
    message: str = Field(..., description="Текст ответа агента")
    actions: list[dict] = Field(default_factory=list, description="Действия, выполненные агентом")
    confirmations: list[dict] = Field(default_factory=list, description="Запрошенные подтверждения")
    tokens_used: int = 0
    cost_usd: float = 0.0


class AgentEventDetailOut(BaseModel):
    """Детальная информация о событии с логом действий."""
    event: AgentEventOut
    actions: list[AgentActionOut] = []


class AgentDashboardOut(BaseModel):
    """Данные для дашборда агента."""
    recent_events: list[AgentEventOut] = []
    pending_confirmations: list[AgentConfirmationOut] = []
    stats: dict = Field(default_factory=dict, description="Статистика агента за период")


class AgentStatsOut(BaseModel):
    """Статистика AI-агента."""
    total_events: int = 0
    events_today: int = 0
    total_tool_calls: int = 0
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    pending_confirmations: int = 0
    by_trigger_type: dict[str, int] = Field(default_factory=dict)
    by_action_type: dict[str, int] = Field(default_factory=dict)
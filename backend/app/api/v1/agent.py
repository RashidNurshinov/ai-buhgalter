"""
API роутер AI-агента.
Справочник: СПРАВОЧНИК_СУЩНОСТЕЙ.md → api/v1/agent.py
Архитектура: АРХИТЕКТУРА_AI_AGENT.md → раздел 5

Эндпоинты:
  POST   /api/v1/agent/chat            — Отправить сообщение агенту (чат)
  POST   /api/v1/agent/command         — Отправить команду агенту
  POST   /api/v1/agent/confirm         — Ответить на запрос подтверждения
  GET    /api/v1/agent/events          — Список событий агента
  GET    /api/v1/agent/events/{id}     — Детали события с логом действий
  GET    /api/v1/agent/confirmations   — Список ожидающих подтверждений
  GET    /api/v1/agent/stats           — Статистика агента
"""

import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.enums import (
    AgentActionStatus,
    AgentConfirmationStatus,
    AgentTriggerType,
)
from app.core.dependencies import get_current_user, get_db
from app.models.agent_action_log import AgentActionLog
from app.models.agent_confirmation import AgentConfirmation
from app.models.agent_event import AgentEvent
from app.models.user import User
from app.schemas.agent import (
    AgentActionOut,
    AgentChatRequest,
    AgentChatResponse,
    AgentCommandRequest,
    AgentConfirmationOut,
    AgentConfirmationResponse,
    AgentEventDetailOut,
    AgentEventOut,
    AgentStatsOut,
)
from app.services.ai_agent import trigger_agent_event

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent", tags=["agent"])


# ═══════════════════════════════════════════════════════════
# POST /agent/chat — Чат с агентом
# ═══════════════════════════════════════════════════════════

@router.post(
    "/chat",
    response_model=AgentChatResponse,
    summary="Отправить сообщение агенту",
    description=(
        "Отправить текстовый вопрос или запрос AI-бухгалтеру. "
        "Агент проанализирует вопрос, при необходимости вызовет инструменты "
        "и вернёт ответ."
    ),
)
async def agent_chat(
    body: AgentChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Чат с AI-бухгалтером.

    Агент может:
    - Ответить на вопрос о налогах, отчётности, сроках
    - Рассчитать налоги по запросу
    - Проверить статус данных
    - Сформировать отчёт
    """
    from app.models.ai_chat_message import AiChatMessage
    from sqlalchemy import text
    
    try:
        # Сохраняем сообщение пользователя
        user_msg = AiChatMessage(
            user_id=current_user.id,
            role="user",
            content=body.message,
        )
        db.add(user_msg)
        await db.flush()
        
        result = await trigger_agent_event(
            db=db,
            user_id=current_user.id,
            trigger_type=AgentTriggerType.USER_QUESTION,
            payload={"question": body.message},
            priority=5,
        )

        # Сохраняем ответ агента
        assistant_msg = AiChatMessage(
            user_id=current_user.id,
            role="assistant",
            content=result["summary"],
            context_json={
                "event_id": result["event_id"],
                "tokens_used": result.get("tokens_used", 0),
                "cost_usd": result.get("cost_usd", 0.0),
                "actions_count": len(result.get("actions", [])),
            },
            model_used="gemini-2.5-pro",
            tokens_used=result.get("tokens_used", 0),
        )
        db.add(assistant_msg)
        await db.commit()

        return AgentChatResponse(
            event_id=result["event_id"],
            message=result["summary"],
            actions=result.get("actions", []),
            confirmations=result.get("confirmations", []),
            tokens_used=result.get("tokens_used", 0),
            cost_usd=result.get("cost_usd", 0.0),
        )

    except Exception as e:
        logger.error("Agent chat failed: %s", str(e), exc_info=True)
        try:
            await db.rollback()
        except Exception:
            pass
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка AI-агента: {str(e)}",
        )


# ═══════════════════════════════════════════════════════════
# POST /agent/command — Команда агенту
# ═══════════════════════════════════════════════════════════

@router.post(
    "/command",
    response_model=AgentChatResponse,
    summary="Отправить команду агенту",
    description=(
        "Отправить прямую команду: 'рассчитай налоги за Q1', "
        "'сформируй КУДиР', 'проверь аномалии за месяц'."
    ),
)
async def agent_command(
    body: AgentCommandRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Команда AI-бухгалтеру. Отличается от чата приоритетом и триггером."""
    try:
        result = await trigger_agent_event(
            db=db,
            user_id=current_user.id,
            trigger_type=AgentTriggerType.USER_COMMAND,
            payload={"command": body.command},
            priority=7,
        )

        return AgentChatResponse(
            event_id=result["event_id"],
            message=result["summary"],
            actions=result.get("actions", []),
            confirmations=result.get("confirmations", []),
            tokens_used=result.get("tokens_used", 0),
            cost_usd=result.get("cost_usd", 0.0),
        )

    except Exception as e:
        logger.error("Agent command failed: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка AI-агента: {str(e)}",
        )


# ═══════════════════════════════════════════════════════════
# POST /agent/confirm — Ответ на подтверждение
# ═══════════════════════════════════════════════════════════

@router.post(
    "/confirm",
    response_model=AgentChatResponse,
    summary="Ответить на запрос подтверждения",
    description=(
        "Подтвердить, отклонить или изменить предложение агента. "
        "После ответа агент продолжит обработку."
    ),
)
async def agent_confirm(
    body: AgentConfirmationResponse,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Ответ пользователя на запрос подт��ерждения от агента."""
    # Найти подтверждение
    result = await db.execute(
        select(AgentConfirmation).where(
            AgentConfirmation.id == body.confirmation_id,
            AgentConfirmation.user_id == current_user.id,
            AgentConfirmation.status == AgentConfirmationStatus.PENDING,
        )
    )
    confirmation = result.scalar_one_or_none()

    if not confirmation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Запрос подтверждения не найден или уже обработан",
        )

    # Обновить статус подтверждения
    action_map = {
        "confirm": AgentConfirmationStatus.CONFIRMED,
        "reject": AgentConfirmationStatus.REJECTED,
        "modify": AgentConfirmationStatus.MODIFIED,
    }
    new_status = action_map.get(body.action)
    if not new_status:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="action должен быть: confirm, reject или modify",
        )

    confirmation.status = new_status
    confirmation.user_response = body.user_response
    if body.modified_data:
        confirmation.user_modified_data = body.modified_data
    await db.flush()

    # Запустить агента для обработки ответа
    try:
        agent_result = await trigger_agent_event(
            db=db,
            user_id=current_user.id,
            trigger_type=AgentTriggerType.EVENT_USER_CONFIRMATION,
            payload={
                "confirmation_id": confirmation.id,
                "confirmation_type": confirmation.confirmation_type,
                "user_response": body.user_response or body.action,
                "modified_data": body.modified_data,
                "related_entity_type": confirmation.related_entity_type,
                "related_entity_id": confirmation.related_entity_id,
            },
            priority=7,
        )

        return AgentChatResponse(
            event_id=agent_result["event_id"],
            message=agent_result["summary"],
            actions=agent_result.get("actions", []),
            confirmations=agent_result.get("confirmations", []),
            tokens_used=agent_result.get("tokens_used", 0),
            cost_usd=agent_result.get("cost_usd", 0.0),
        )

    except Exception as e:
        logger.error("Agent confirm failed: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка AI-агента: {str(e)}",
        )


# ═══════════════════════════════════════════════════════════
# GET /agent/events — Список событий агента
# ═══════════════════════════════════════════════════════════

@router.get(
    "/events",
    response_model=list[AgentEventOut],
    summary="Список событий агента",
    description="Получить историю событий AI-агента с пагинацией.",
)
async def get_agent_events(
    limit: int = Query(20, ge=1, le=100, description="Количество"),
    offset: int = Query(0, ge=0, description="Смещение"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Список событий агента (последние первые)."""
    result = await db.execute(
        select(AgentEvent)
        .where(AgentEvent.user_id == current_user.id)
        .order_by(AgentEvent.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    events = result.scalars().all()
    return [AgentEventOut.model_validate(e) for e in events]


# ═══════════════════════════════════════════════════════════
# GET /agent/messages — История сообщений чата
# ═══════════════════════════════════════════════════════════

@router.get(
    "/messages",
    response_model=list[dict],
    summary="История сообщений чата",
    description="Получить историю переписки с AI-бухгалтером.",
)
async def get_chat_messages(
    limit: int = Query(50, ge=1, le=200, description="Количество сообщений"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """История сообщений чата (последние первые)."""
    from app.models.ai_chat_message import AiChatMessage
    
    result = await db.execute(
        select(AiChatMessage)
        .where(AiChatMessage.user_id == current_user.id)
        .order_by(AiChatMessage.created_at.desc())
        .limit(limit)
    )
    messages = result.scalars().all()
    # Возвращаем в прямом порядке (старые сначала)
    return [
        {
            "id": str(m.id),
            "role": m.role,
            "content": m.content,
            "created_at": m.created_at.isoformat(),
        }
        for m in reversed(messages)
    ]


# ═══════════════════════════════════════════════════════════
# GET /agent/events/{event_id} — Детали события
# ═══════════════════════════════════════════════════════════

@router.get(
    "/events/{event_id}",
    response_model=AgentEventDetailOut,
    summary="Детали события агента",
    description="Получить событие с полным логом действий (tool calls).",
)
async def get_agent_event_detail(
    event_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Детали события с логом действий."""
    # Событие
    result = await db.execute(
        select(AgentEvent).where(
            AgentEvent.id == event_id,
            AgentEvent.user_id == current_user.id,
        )
    )
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Событие не найдено",
        )

    # Действия
    actions_result = await db.execute(
        select(AgentActionLog)
        .where(AgentActionLog.event_id == event_id)
        .order_by(AgentActionLog.step_number)
    )
    actions = actions_result.scalars().all()

    return AgentEventDetailOut(
        event=AgentEventOut.model_validate(event),
        actions=[AgentActionOut.model_validate(a) for a in actions],
    )


# ═══════════════════════════════════════════════════════════
# GET /agent/confirmations — Ожидающие подтверждения
# ═══════════════════════════════════════════════════════════

@router.get(
    "/confirmations",
    response_model=list[AgentConfirmationOut],
    summary="Ожидающие подтверждения",
    description="Получить список запросов агента, ожидающих ответа пользователя.",
)
async def get_pending_confirmations(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Список незакрытых запросов подтверждения от агента."""
    result = await db.execute(
        select(AgentConfirmation)
        .where(
            AgentConfirmation.user_id == current_user.id,
            AgentConfirmation.status == AgentConfirmationStatus.PENDING,
        )
        .order_by(AgentConfirmation.created_at.desc())
    )
    confirmations = result.scalars().all()
    return [AgentConfirmationOut.model_validate(c) for c in confirmations]


# ═══════════════════════════════════════════════════════════
# GET /agent/stats — Статистика агента
# ═══════════════════════════════════════════════════════════

@router.get(
    "/stats",
    response_model=AgentStatsOut,
    summary="Статистика AI-агента",
    description="Получить статистику работы агента: количество событий, токены, стоимость.",
)
async def get_agent_stats(
    days: int = Query(30, ge=1, le=365, description="За последние N дней"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Статистика агента за период."""
    since = datetime.now(timezone.utc) - timedelta(days=days)

    # Общее количество событий
    total_result = await db.execute(
        select(func.count(AgentEvent.id)).where(
            AgentEvent.user_id == current_user.id,
            AgentEvent.created_at >= since,
        )
    )
    total_events = total_result.scalar() or 0

    # Сегодня
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    today_result = await db.execute(
        select(func.count(AgentEvent.id)).where(
            AgentEvent.user_id == current_user.id,
            AgentEvent.created_at >= today_start,
        )
    )
    events_today = today_result.scalar() or 0

    # Суммарные токены и стоимость
    tokens_result = await db.execute(
        select(
            func.coalesce(func.sum(AgentEvent.tokens_used), 0),
            func.coalesce(func.sum(AgentEvent.tool_calls_count), 0),
        ).where(
            AgentEvent.user_id == current_user.id,
            AgentEvent.created_at >= since,
        )
    )
    row = tokens_result.one()
    total_tokens = row[0]
    total_tool_calls = row[1]

    # Стоимость из логов
    cost_result = await db.execute(
        select(func.coalesce(func.sum(AgentActionLog.cost_usd), 0)).where(
            AgentActionLog.user_id == current_user.id,
            AgentActionLog.created_at >= since,
        )
    )
    total_cost = float(cost_result.scalar() or 0)

    # Ожидающие подтверждения
    pending_result = await db.execute(
        select(func.count(AgentConfirmation.id)).where(
            AgentConfirmation.user_id == current_user.id,
            AgentConfirmation.status == AgentConfirmationStatus.PENDING,
        )
    )
    pending_confirmations = pending_result.scalar() or 0

    return AgentStatsOut(
        total_events=total_events,
        events_today=events_today,
        total_tool_calls=total_tool_calls,
        total_tokens=total_tokens,
        total_cost_usd=total_cost,
        pending_confirmations=pending_confirmations,
    )
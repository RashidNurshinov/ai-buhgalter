"""
Celery-задачи AI-агента.
Архитектура: АРХИТЕКТУРА_AI_AGENT.md → раздел 4 (Триггеры)

Задачи:
1. agent_process_event — обработка одного события агентом (общая)
2. agent_daily_check — ежедневная проверка (09:00 МСК)
3. agent_weekly_report — еженедельный отчёт (пн 10:00 МСК)
4. agent_monthly_analysis — ежемесячный анализ (1-е число, 10:00 МСК)
5. agent_check_deadlines — проверка приближающихся сроков (ежедневно 08:00)
6. agent_on_file_uploaded — реакция на загрузку файла
"""

import asyncio
import logging
from typing import Any

from app.core.celery_app import celery_app

logger = logging.getLogger(__name__)


def _run_async(coro):
    """Запуск async-функции из sync-контекста Celery worker."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


async def _trigger_agent(
    user_id: str,
    trigger_type: str,
    payload: dict[str, Any] | None = None,
    priority: int = 5,
) -> dict[str, Any]:
    """Общая async-функция вызова агента с сессией БД."""
    from app.constants.enums import AgentTriggerType
    from app.core.database import async_session_factory
    from app.services.ai_agent import trigger_agent_event

    async with async_session_factory() as db:
        result = await trigger_agent_event(
            db=db,
            user_id=user_id,
            trigger_type=AgentTriggerType(trigger_type),
            payload=payload or {},
            priority=priority,
        )
        return result


async def _get_all_active_user_ids() -> list[str]:
    """Получить список ID всех активных пользователей."""
    from sqlalchemy import select
    from app.core.database import async_session_factory
    from app.models.user import User

    async with async_session_factory() as db:
        result = await db.execute(
            select(User.id).where(User.is_active == True)  # noqa: E712
        )
        return [str(row[0]) for row in result.all()]


# ═══════════════════════════════════════════════════════════
# Задача 1: Обработка одного события (универсальная)
# ═══════════════════════════════════════════════════════════

@celery_app.task(
    name="app.tasks.agent_tasks.agent_process_event",
    bind=True,
    max_retries=2,
    default_retry_delay=30,
    soft_time_limit=300,  # 5 минут
    time_limit=360,       # 6 минут (hard)
)
def agent_process_event(
    self,
    user_id: str,
    trigger_type: str,
    payload: dict | None = None,
    priority: int = 5,
):
    """
    Обработать событие AI-агентом в фоне.

    Вызывается из API-роутеров, вебхуков, других задач.

    Args:
        user_id: ID пользователя
        trigger_type: Тип триггера (значение AgentTriggerType)
        payload: Данные события
        priority: Приоритет (0-10)
    """
    logger.info(
        "Agent task: user=%s trigger=%s payload=%s",
        user_id, trigger_type, payload,
    )
    try:
        result = _run_async(
            _trigger_agent(user_id, trigger_type, payload, priority)
        )
        logger.info(
            "Agent task completed: event_id=%s tokens=%d",
            result.get("event_id"), result.get("tokens_used", 0),
        )
        return result
    except Exception as exc:
        logger.error("Agent task failed: %s", str(exc), exc_info=True)
        raise self.retry(exc=exc)


# ═══════════════════════════════════════════════════════════
# Задача 2: Ежедневная проверка (все пользователи)
# ═══════════════════════════════════════════════════════════

@celery_app.task(
    name="app.tasks.agent_tasks.agent_daily_check",
    soft_time_limit=1800,  # 30 минут
    time_limit=2100,       # 35 минут
)
def agent_daily_check():
    """
    Ежедневная проверка: 09:00 МСК.

    Для каждого активного пользователя:
    - Проверяет необработанные файлы
    - Проверяет приближающиеся сроки
    - Проверяет неклассифицированные операции
    """
    logger.info("Starting daily agent check for all users")

    user_ids = _run_async(_get_all_active_user_ids())
    logger.info("Found %d active users", len(user_ids))

    results = []
    for user_id in user_ids:
        try:
            # Запускаем отдельную задачу для каждого пользователя
            agent_process_event.delay(
                user_id=user_id,
                trigger_type="schedule_daily",
                payload={},
                priority=3,
            )
            results.append({"user_id": user_id, "status": "queued"})
        except Exception as e:
            logger.error("Failed to queue daily check for user %s: %s", user_id, str(e))
            results.append({"user_id": user_id, "status": "error", "error": str(e)})

    return {"users_queued": len(results), "results": results}


# ═══════════════════════════════════════════════════════════
# Задача 3: Еженедельный отчёт
# ═══════════════════════════════════════════════════════════

@celery_app.task(
    name="app.tasks.agent_tasks.agent_weekly_report",
    soft_time_limit=1800,
    time_limit=2100,
)
def agent_weekly_report():
    """
    Еженедельный отчёт: понедельник 10:00 МСК.

    Формирует краткую сводку за неделю для каждого пользователя.
    """
    logger.info("Starting weekly agent report")

    user_ids = _run_async(_get_all_active_user_ids())

    for user_id in user_ids:
        agent_process_event.delay(
            user_id=user_id,
            trigger_type="schedule_weekly",
            payload={},
            priority=2,
        )

    return {"users_queued": len(user_ids)}


# ═══════════════════════════════════════════════════════════
# Задача 4: Ежемесячный анализ
# ═══════════════════════════════════════════════════════════

@celery_app.task(
    name="app.tasks.agent_tasks.agent_monthly_analysis",
    soft_time_limit=3600,
    time_limit=3900,
)
def agent_monthly_analysis():
    """
    Ежемесячный анализ: 1-е число, 10:00 МСК.

    Полная сверка, расчёт налогов, поиск аномалий.
    """
    logger.info("Starting monthly agent analysis")

    user_ids = _run_async(_get_all_active_user_ids())

    for user_id in user_ids:
        agent_process_event.delay(
            user_id=user_id,
            trigger_type="schedule_monthly",
            payload={},
            priority=2,
        )

    return {"users_queued": len(user_ids)}


# ═══════════════════════════════════════════════════════════
# Задача 5: Проверка приближающихся сроков
# ══════════════════════════════════════════════════���════════

@celery_app.task(
    name="app.tasks.agent_tasks.agent_check_deadlines",
    soft_time_limit=1800,
    time_limit=2100,
)
def agent_check_deadlines():
    """
    Проверка дедлайнов: ежедневно 08:00 МСК.

    Проверяет налоговый календарь и предупреждает
    за 14, 7, 3 и 1 день до срока.
    """
    logger.info("Starting deadline check")

    user_ids = _run_async(_get_all_active_user_ids())

    for user_id in user_ids:
        agent_process_event.delay(
            user_id=user_id,
            trigger_type="schedule_pre_deadline",
            payload={"check_days": [14, 7, 3, 1]},
            priority=8,
        )

    return {"users_queued": len(user_ids)}


# ═══════════════════════════════════════════════════════════
# Задача 6: Реакция на загрузку файла (event-driven)
# ═══════════════════════════════════════════════════════════

@celery_app.task(
    name="app.tasks.agent_tasks.agent_on_file_uploaded",
    bind=True,
    max_retries=2,
    default_retry_delay=10,
    soft_time_limit=300,
    time_limit=360,
)
def agent_on_file_uploaded(
    self,
    user_id: str,
    files: list[dict],
):
    """
    Реакция на загрузку файлов.
    Вызывается из POST /files/upload после успешной загрузки.

    Args:
        user_id: ID пользователя
        files: Список файлов [{file_id, filename, file_type, size_human}]
    """
    logger.info("Agent reacting to %d uploaded files for user %s", len(files), user_id)

    try:
        result = _run_async(
            _trigger_agent(
                user_id=user_id,
                trigger_type="event_file_uploaded",
                payload={"files": files},
                priority=7,
            )
        )
        return result
    except Exception as exc:
        logger.error("Agent file upload reaction failed: %s", str(exc), exc_info=True)
        raise self.retry(exc=exc)
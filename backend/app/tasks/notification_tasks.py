"""
Celery-задачи для уведомлений.
Пункт плана: 1.14.4

Задачи:
- task_check_upcoming_deadlines — ежедневная пр��верка сроков + отправка email
- task_send_reminder — отправка конкретного напоминания
"""

import asyncio
import logging

from app.core.celery_app import celery_app

logger = logging.getLogger(__name__)


def _get_sync_session():
    """Получить синхронную сессию для Celery-задач (через asyncio.run)."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.core.config import settings

    # Для Celery используем ��инхронный URL
    sync_url = settings.DATABASE_URL.replace("+asyncpg", "").replace("postgresql://", "postgresql+psycopg2://")
    # Но лучше через async wrapper
    return None  # Используем async подход ниже


def _run_async(coro):
    """Запуск корутины в Celery-задаче."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Если цикл уже запущен — создаём новый
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(asyncio.run, coro).result()
        else:
            return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


async def _check_deadlines_async():
    """Асинхронная проверка дедлайнов."""
    from app.core.database import async_session_factory
    from app.services.notification_service import NotificationService
    from app.services.tax_calendar_service import TaxCalendarService

    async with async_session_factory() as db:
        try:
            # 1. Обновляем статусы просроченных
            calendar_service = TaxCalendarService(db)
            overdue_count = await calendar_service.update_overdue_statuses()
            if overdue_count > 0:
                logger.info("Updated %d overdue events", overdue_count)

            # 2. Отправляем напоминания
            notification_service = NotificationService(db)
            result = await notification_service.check_and_send_reminders()

            await db.commit()

            logger.info(
                "Deadline check complete: checked=%d, sent=%d",
                result["checked"], result["sent"],
            )
            return result

        except Exception as e:
            logger.error("Error checking deadlines: %s", e, exc_info=True)
            await db.rollback()
            return {"checked": 0, "sent": 0, "error": str(e)}


async def _send_reminder_async(user_id: str, event_id: str, days_left: int):
    """Асинхронная отправка конкретного напоминания."""
    from sqlalchemy import select
    from app.core.database import async_session_factory
    from app.models.user import User
    from app.models.tax_calendar_event import TaxCalendarEvent
    from app.services.notification_service import NotificationService

    async with async_session_factory() as db:
        try:
            user_result = await db.execute(select(User).where(User.id == user_id))
            user = user_result.scalar_one_or_none()
            if not user:
                logger.error("User %s not found for reminder", user_id)
                return False

            event_result = await db.execute(
                select(TaxCalendarEvent).where(TaxCalendarEvent.id == event_id)
            )
            event = event_result.scalar_one_or_none()
            if not event:
                logger.error("Event %s not found for reminder", event_id)
                return False

            service = NotificationService(db)
            success = await service.send_deadline_reminder(user, event, days_left)

            await db.commit()
            return success

        except Exception as e:
            logger.error("Error sending reminder: %s", e, exc_info=True)
            await db.rollback()
            return False


@celery_app.task(
    name="app.tasks.notification_tasks.task_check_upcoming_deadlines",
    bind=True,
    max_retries=3,
    default_retry_delay=300,
)
def task_check_upcoming_deadlines(self):
    """
    Ежедневная проверка приближающихся сроков.
    Запускается по расписанию (beat) каждый день в 08:00 МСК.

    1. Обновляет статусы просроченных событий
    2. Отправляет напоминания за 14, 7, 3, 0 дней
    """
    logger.info("Starting daily deadline check...")
    try:
        result = _run_async(_check_deadlines_async())
        logger.info("Daily deadline check result: %s", result)
        return result
    except Exception as e:
        logger.error("Daily deadline check failed: %s", e, exc_info=True)
        self.retry(exc=e)


@celery_app.task(
    name="app.tasks.notification_tasks.task_send_reminder",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def task_send_reminder(self, user_id: str, event_id: str, days_left: int):
    """
    Отправка конкретного напоминания пользователю.

    Args:
        user_id: ID пользователя
        event_id: ID события календаря
        days_left: Дней до дедлайна
    """
    logger.info(
        "Sending reminder: user=%s, event=%s, days_left=%d",
        user_id, event_id, days_left,
    )
    try:
        result = _run_async(_send_reminder_async(user_id, event_id, days_left))
        return {"sent": result}
    except Exception as e:
        logger.error("Send reminder failed: %s", e, exc_info=True)
        self.retry(exc=e)
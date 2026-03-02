"""
Конфигурация Celery для фоновых задач.
"""

from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "ai_buhgalter",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Europe/Moscow",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    # Автообнаружение задач в пакете tasks
    imports=[
        "app.tasks",
        "app.tasks.agent_tasks",
        "app.tasks.file_processing_tasks",
        "app.tasks.notification_tasks",
    ],
)

# Расписание периодических задач (beat)
from celery.schedules import crontab

celery_app.conf.beat_schedule = {
    # ─── AI Agent: расписание ─────────────────────────────
    "agent-check-deadlines-daily": {
        "task": "app.tasks.agent_tasks.agent_check_deadlines",
        "schedule": crontab(hour=8, minute=0),  # 08:00 МСК
        "options": {"queue": "agent"},
    },
    "agent-daily-check": {
        "task": "app.tasks.agent_tasks.agent_daily_check",
        "schedule": crontab(hour=9, minute=0),  # 09:00 МСК
        "options": {"queue": "agent"},
    },
    "agent-weekly-report": {
        "task": "app.tasks.agent_tasks.agent_weekly_report",
        "schedule": crontab(hour=10, minute=0, day_of_week=1),  # Пн 10:00 МСК
        "options": {"queue": "agent"},
    },
    "agent-monthly-analysis": {
        "task": "app.tasks.agent_tasks.agent_monthly_analysis",
        "schedule": crontab(hour=10, minute=0, day_of_month=1),  # 1-е число 10:00 МСК
        "options": {"queue": "agent"},
    },
    # ─── Уведомления: расписание ──────────────────────────
    "check-upcoming-deadlines": {
        "task": "app.tasks.notification_tasks.task_check_upcoming_deadlines",
        "schedule": crontab(hour=8, minute=30),  # 08:30 МСК (после agent_check_deadlines)
        "options": {"queue": "default"},
    },
}
"""
Сервис уведомлений — NotificationService.
Пункт плана: 1.14.3

Методы:
- send_email_notification() — отправка email через SMTP
- send_deadline_reminder() — отправка напоминания о сроке
- send_tax_calculation_ready() — уведомление о готовности расчёта
- send_declaration_status() — уведомление о статусе декларации
- check_and_send_reminders() — планирование напоминаний (за 14, 7, 3, 0 дней)

Зависимости: aiosmtplib (уже в requirements.txt)
"""

import logging
from datetime import date, datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.tax_calendar_event import TaxCalendarEvent
from app.models.user import User

logger = logging.getLogger(__name__)


class NotificationService:
    """
    Сервис для отправки уведомлений пользователям.

    Поддерживаемые каналы:
    - Email (SMTP через aiosmtplib)
    - Dashboard (внутренние уведомления — через AI Agent events)
    - Telegram (Этап 3 — заглушка)
    """

    def __init__(self, db: AsyncSession | None = None):
        self.db = db

    # ─── Email ────────────────────────────────────────────

    async def send_email_notification(
        self,
        to_email: str,
        subject: str,
        body_html: str,
        body_text: str | None = None,
    ) -> bool:
        """
        Отправить email-уведомление через SMTP.

        Args:
            to_email: Адрес получателя
            subject: Тема письма
            body_html: HTML-содержимое
            body_text: Текстовое содержимое (опционально)

        Returns:
            True если отправлено успешно
        """
        if not settings.SMTP_USER or not settings.SMTP_PASSWORD:
            logger.warning(
                "SMTP не настроен (SMTP_USER/SMTP_PASSWORD пусты). "
                "Email не отправлен: %s → %s", subject, to_email
            )
            return False

        try:
            import aiosmtplib
        except ImportError:
            logger.error("aiosmtplib не установлен. pip install aiosmtplib")
            return False

        msg = MIMEMultipart("alternative")
        msg["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL or settings.SMTP_USER}>"
        msg["To"] = to_email
        msg["Subject"] = subject

        if body_text:
            msg.attach(MIMEText(body_text, "plain", "utf-8"))
        msg.attach(MIMEText(body_html, "html", "utf-8"))

        try:
            await aiosmtplib.send(
                msg,
                hostname=settings.SMTP_HOST,
                port=settings.SMTP_PORT,
                username=settings.SMTP_USER,
                password=settings.SMTP_PASSWORD,
                use_tls=False,
                start_tls=True,
                timeout=30,
            )
            logger.info("Email отправлен: '%s' → %s", subject, to_email)
            return True
        except Exception as e:
            logger.error("Ошибка отправки email '%s' → %s: %s", subject, to_email, e)
            return False

    # ─── Напоминания о сроках ─────────────────────────────

    async def send_deadline_reminder(
        self,
        user: User,
        event: TaxCalendarEvent,
        days_left: int,
    ) -> bool:
        """
        Отправить напоминание о приближающемся сроке.

        Args:
            user: Пользователь
            event: Событие календаря
            days_left: Дней до срока

        Returns:
            True если хотя бы один канал сработал
        """
        if days_left <= 0:
            urgency = "🔴 СЕГОДНЯ"
            urgency_text = "Сегодня крайний срок!"
        elif days_left <= 3:
            urgency = f"🔴 Через {days_left} дн."
            urgency_text = f"До срока осталось {days_left} дн."
        elif days_left <= 7:
            urgency = f"🟡 Через {days_left} дн."
            urgency_text = f"До срока осталось {days_left} дн."
        else:
            urgency = f"🟢 Через {days_left} дн."
            urgency_text = f"До срока осталось {days_left} дн."

        subject = f"{urgency} {event.title}"

        body_html = self._render_template(
            "deadline_reminder",
            event_title=event.title,
            deadline=event.deadline.strftime("%d.%m.%Y"),
            days_left=days_left,
            user_name=user.full_name,
            description=event.description or "—",
            urgency_text=urgency_text,
        )

        body_text = (
            f"Напоминание: {event.title}\n"
            f"{urgency_text}\n"
            f"Крайний срок: {event.deadline.strftime('%d.%m.%Y')}\n"
            f"Описание: {event.description or '—'}"
        )

        sent = False
        email = await self._get_notification_email(user)
        if email:
            sent = await self.send_email_notification(
                to_email=email,
                subject=subject,
                body_html=body_html,
                body_text=body_text,
            )
        return sent

    # ─── Дополнительные уведомления ──────────────────────

    async def send_tax_calculation_ready(
        self,
        user: User,
        period: str,
        tax_type: str,
        amount: str,
    ) -> bool:
        """Отправить уведомление о готовности налогового расчёта."""
        subject = f"📊 Налоговый расчёт готов: {tax_type} за {period}"
        body_html = self._render_template(
            "tax_calculation_ready",
            user_name=user.full_name,
            period=period,
            tax_type=tax_type,
            amount=amount,
        )
        email = await self._get_notification_email(user)
        if email:
            return await self.send_email_notification(
                to_email=email, subject=subject, body_html=body_html,
            )
        return False

    async def send_declaration_status(
        self,
        user: User,
        declaration_type: str,
        status: str,
        period: str,
    ) -> bool:
        """Отправить уведомление об изменении статуса декларации."""
        subject = f"📋 Декларация {declaration_type} за {period}: {status}"
        body_html = self._render_template(
            "declaration_status",
            user_name=user.full_name,
            declaration_type=declaration_type,
            status=status,
            period=period,
        )
        email = await self._get_notification_email(user)
        if email:
            return await self.send_email_notification(
                to_email=email, subject=subject, body_html=body_html,
            )
        return False

    # ─── Массовая рассылка напоминаний ────────────────────

    async def check_and_send_reminders(
        self,
        user_id: str | None = None,
    ) -> dict[str, int]:
        """
        Проверить все предстоящие события и отправить напоминания.
        Вызывается из Celery-задачи ежедневно.

        Логика напоминаний:
        - За 14 дней — первое напоминание
        - За 7 дней — второе
        - За 3 дня — третье
        - В день срока — СРОЧНО

        Args:
            user_id: Если указан — только для одного пользователя.

        Returns:
            {"checked": int, "sent": int}
        """
        if not self.db:
            logger.error("NotificationService: db не инициализирована")
            return {"checked": 0, "sent": 0}

        reminder_days = [14, 7, 3, 0]
        today = date.today()
        sent_count = 0
        checked_count = 0

        # Получаем пользователей
        if user_id:
            user_result = await self.db.execute(
                select(User).where(User.id == user_id, User.is_active == True)  # noqa: E712
            )
            users = list(user_result.scalars().all())
        else:
            user_result = await self.db.execute(
                select(User).where(User.is_active == True)  # noqa: E712
            )
            users = list(user_result.scalars().all())

        for user in users:
            for days in reminder_days:
                target_date = today + timedelta(days=days)

                from app.constants.enums import CalendarEventStatus
                events_result = await self.db.execute(
                    select(TaxCalendarEvent).where(
                        and_(
                            TaxCalendarEvent.user_id == user.id,
                            TaxCalendarEvent.deadline == target_date,
                            TaxCalendarEvent.status == CalendarEventStatus.UPCOMING,
                        )
                    )
                )
                events = list(events_result.scalars().all())

                for event in events:
                    checked_count += 1

                    # Проверяем, не отправляли ли уже напоминание сегодня
                    if event.reminded_at:
                        reminded_date = (
                            event.reminded_at.date()
                            if hasattr(event.reminded_at, "date")
                            else event.reminded_at
                        )
                        if reminded_date == today:
                            continue

                    success = await self.send_deadline_reminder(user, event, days)
                    if success:
                        event.reminded_at = datetime.now(timezone.utc)
                        sent_count += 1

        if sent_count > 0:
            await self.db.flush()

        logger.info(
            "Reminders check: checked=%d events, sent=%d notifications",
            checked_count, sent_count,
        )
        return {"checked": checked_count, "sent": sent_count}

    # ─── Вспомогательные ──────────────────────────────────

    def _render_template(self, template_name: str, **kwargs: Any) -> str:
        """Рендеринг HTML-шаблона уведомления.

        Args:
            template_name: Имя шаблона (deadline_reminder, tax_calculation_ready, и т.д.)
            **kwargs: Параметры шаблона

        Returns:
            HTML-строка
        """
        templates: dict[str, str] = {
            "deadline_reminder": """
            <div style="font-family: Arial, sans-serif; max-width: 600px;">
                <h2 style="color: #333;">📅 Напоминание: {event_title}</h2>
                <p>Уважаемый(ая) {user_name},</p>
                <p>{urgency_text}</p>
                <table style="border-collapse: collapse; width: 100%; margin-top: 16px;">
                    <tr>
                        <td style="padding: 8px; border: 1px solid #ddd; font-weight: bold;">Событие</td>
                        <td style="padding: 8px; border: 1px solid #ddd;">{event_title}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; border: 1px solid #ddd; font-weight: bold;">Крайний срок</td>
                        <td style="padding: 8px; border: 1px solid #ddd;">{deadline}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; border: 1px solid #ddd; font-weight: bold;">Описание</td>
                        <td style="padding: 8px; border: 1px solid #ddd;">{description}</td>
                    </tr>
                </table>
                <p style="margin-top: 16px; color: #888; font-size: 12px;">
                    Это автоматическое уведомление от ИИ-Бухгалтера.
                </p>
            </div>
            """,
            "tax_calculation_ready": """
            <div style="font-family: Arial, sans-serif; max-width: 600px;">
                <h2 style="color: #333;">📊 Налоговый расчёт готов</h2>
                <p>Уважаемый(ая) {user_name},</p>
                <p>Расчёт по налогу <strong>{tax_type}</strong> за период
                <strong>{period}</strong> завершён.</p>
                <p>Сумма к уплате: <strong>{amount}</strong></p>
                <p style="margin-top: 16px; color: #888; font-size: 12px;">
                    Это автоматическое уведомление от ИИ-Бухгалтера.
                </p>
            </div>
            """,
            "declaration_status": """
            <div style="font-family: Arial, sans-serif; max-width: 600px;">
                <h2 style="color: #333;">📋 Статус декларации изменён</h2>
                <p>Уважаемый(ая) {user_name},</p>
                <p>Декларация <strong>{declaration_type}</strong> за период
                <strong>{period}</strong> — новый статус: <strong>{status}</strong>.</p>
                <p style="margin-top: 16px; color: #888; font-size: 12px;">
                    Это автоматическое уведомление от ИИ-Бухгалтера.
                </p>
            </div>
            """,
        }

        template = templates.get(template_name, f"<p>{template_name}</p>")
        try:
            return template.format(**kwargs)
        except KeyError as e:
            logger.warning("Template '%s' missing key: %s", template_name, e)
            return template

    async def _get_notification_email(self, user: User) -> str | None:
        """Получить email для уведомлений пользователя.

        Настройки объединены в модель User (нет отдельной таблицы UserSettings).
        """
        return user.email
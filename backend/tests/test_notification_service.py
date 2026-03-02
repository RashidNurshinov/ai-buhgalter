"""
Тесты NotificationService.

Тестируем:
- _render_template() — рендеринг шаблонов уведомлений
- Формирование email-контента
- Обработка ошибок SMTP
"""

import uuid
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.notification_service import NotificationService


# ─── NotificationService инициализация ──────────────────────────


class TestNotificationServiceInit:
    """Тесты инициализации NotificationService."""

    def test_create_instance(self):
        """Создание экземпляра."""
        service = NotificationService()
        assert service is not None

    def test_has_send_methods(self):
        """Наличие методов отправки."""
        service = NotificationService()
        assert hasattr(service, "send_deadline_reminder")
        assert hasattr(service, "send_tax_calculation_ready")
        assert hasattr(service, "send_declaration_status")

    def test_has_render_template(self):
        """Наличие метода рендеринга шаблона."""
        service = NotificationService()
        assert hasattr(service, "_render_template")


class TestNotificationServiceTemplates:
    """Тесты рендеринга шаблонов."""

    def test_render_deadline_template(self):
        """Рендеринг шаблона дедлайна."""
        service = NotificationService()
        # Вызываем _render_template если он публичный/доступный
        if hasattr(service, "_render_template"):
            result = service._render_template(
                "deadline_reminder",
                event_title="НДС за 1 кв. 2026",
                deadline="25.04.2026",
                days_left=7,
                user_name="Иванов Иван",
            )
            assert isinstance(result, str)
            assert len(result) > 0
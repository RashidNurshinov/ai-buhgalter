"""
Тесты дашборда — DashboardService (пункт 1.16.4).

Тестируем:
- DashboardService.get_dashboard: агрегация данных
- _estimate_usn: расчёт УСН (доходы-расходы, доходы, минимальный налог)
- _estimate_vat: оценка НДС
- Pydantic-схемы: DashboardResponse, MonthlyAmount
"""

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import pytest

from app.constants.enums import (
    CalendarEventStatus,
    OperationStatus,
    TaxSystem,
)
from app.schemas.dashboard import DashboardResponse, MonthlyAmount


# ─── MonthlyAmount ──────────────────────────────────────────


class TestMonthlyAmount:
    """Тесты схемы MonthlyAmount."""

    def test_create(self):
        ma = MonthlyAmount(month=3, year=2026, amount=Decimal("150000.00"))
        assert ma.month == 3
        assert ma.year == 2026
        assert ma.amount == Decimal("150000.00")


# ─── DashboardResponse ──────────────────────────────────────


class TestDashboardResponse:
    """Тесты схемы DashboardResponse."""

    def test_full_response(self):
        resp = DashboardResponse(
            period_start=date(2026, 1, 1),
            period_end=date(2026, 3, 31),
            income_total=Decimal("1000000.00"),
            expense_total=Decimal("600000.00"),
            net_profit=Decimal("400000.00"),
            tax_usn_estimated=Decimal("60000.00"),
            tax_vat_estimated=Decimal("30000.00"),
            unconfirmed_operations_count=5,
            unprocessed_documents_count=3,
            upcoming_events=[],
            overdue_events=[],
        )
        assert resp.net_profit == Decimal("400000.00")
        assert resp.unconfirmed_operations_count == 5
        assert resp.monthly_income is None
        assert resp.monthly_expense is None

    def test_response_with_monthly(self):
        resp = DashboardResponse(
            period_start=date(2026, 1, 1),
            period_end=date(2026, 3, 31),
            income_total=Decimal("300000"),
            expense_total=Decimal("100000"),
            net_profit=Decimal("200000"),
            tax_usn_estimated=Decimal("30000"),
            tax_vat_estimated=Decimal("10000"),
            unconfirmed_operations_count=0,
            unprocessed_documents_count=0,
            upcoming_events=[],
            overdue_events=[],
            monthly_income=[
                MonthlyAmount(month=1, year=2026, amount=Decimal("100000")),
                MonthlyAmount(month=2, year=2026, amount=Decimal("100000")),
                MonthlyAmount(month=3, year=2026, amount=Decimal("100000")),
            ],
            monthly_expense=[
                MonthlyAmount(month=1, year=2026, amount=Decimal("30000")),
            ],
        )
        assert len(resp.monthly_income) == 3
        assert len(resp.monthly_expense) == 1


# ─── DashboardService._estimate_usn ─────────────────────────


class TestEstimateUsn:
    """Тесты оценки УСН."""

    @pytest.mark.asyncio
    async def test_usn_income_expense(self):
        """УСН «Доходы минус расходы» 15%."""
        from app.services.dashboard_service import DashboardService

        mock_db = AsyncMock()
        service = DashboardService(mock_db)

        user = MagicMock()
        user.tax_system = TaxSystem.USN_INCOME_EXPENSE
        user.usn_rate = Decimal("15.00")

        income = Decimal("1000000")
        expense = Decimal("600000")

        result = await service._estimate_usn(user, income, expense)

        # (1 000 000 - 600 000) * 15% = 60 000
        assert result == Decimal("60000.00")

    @pytest.mark.asyncio
    async def test_usn_income(self):
        """УСН «Доходы» 6%."""
        from app.services.dashboard_service import DashboardService

        mock_db = AsyncMock()
        service = DashboardService(mock_db)

        user = MagicMock()
        user.tax_system = TaxSystem.USN_INCOME
        user.usn_rate = Decimal("6.00")

        income = Decimal("1000000")
        expense = Decimal("600000")

        result = await service._estimate_usn(user, income, expense)

        # 1 000 000 * 6% = 60 000
        assert result == Decimal("60000.00")

    @pytest.mark.asyncio
    async def test_usn_minimum_tax(self):
        """Минимальный налог 1% от доходов (когда расходы почти равны доходам)."""
        from app.services.dashboard_service import DashboardService

        mock_db = AsyncMock()
        service = DashboardService(mock_db)

        user = MagicMock()
        user.tax_system = TaxSystem.USN_INCOME_EXPENSE
        user.usn_rate = Decimal("15.00")

        income = Decimal("1000000")
        expense = Decimal("990000")  # Убыток почти нулевой

        result = await service._estimate_usn(user, income, expense)

        # (1 000 000 - 990 000) * 15% = 1 500
        # min_tax = 1 000 000 * 1% = 10 000
        # max(1500, 10000) = 10 000
        assert result == Decimal("10000.00")

    @pytest.mark.asyncio
    async def test_usn_zero_income(self):
        """Нулевой доход → 0."""
        from app.services.dashboard_service import DashboardService

        mock_db = AsyncMock()
        service = DashboardService(mock_db)

        user = MagicMock()
        user.tax_system = TaxSystem.USN_INCOME_EXPENSE
        user.usn_rate = Decimal("15.00")

        result = await service._estimate_usn(user, Decimal("0"), Decimal("0"))
        assert result == Decimal("0")  # min(0, 0) = 0

    @pytest.mark.asyncio
    async def test_usn_osno_returns_zero(self):
        """ОСНО → УСН не считается."""
        from app.services.dashboard_service import DashboardService

        mock_db = AsyncMock()
        service = DashboardService(mock_db)

        user = MagicMock()
        user.tax_system = TaxSystem.OSNO

        result = await service._estimate_usn(user, Decimal("1000000"), Decimal("500000"))
        assert result == Decimal("0")

    @pytest.mark.asyncio
    async def test_usn_loss_scenario(self):
        """Убыток (расходы > доходов) → минимальный налог."""
        from app.services.dashboard_service import DashboardService

        mock_db = AsyncMock()
        service = DashboardService(mock_db)

        user = MagicMock()
        user.tax_system = TaxSystem.USN_INCOME_EXPENSE
        user.usn_rate = Decimal("15.00")

        income = Decimal("500000")
        expense = Decimal("700000")

        result = await service._estimate_usn(user, income, expense)

        # tax_base = max(500000 - 700000, 0) = 0
        # usn = 0 * 15% = 0
        # min_tax = 500000 * 1% = 5000
        # max(0, 5000) = 5000
        assert result == Decimal("5000.00")


# ─── DashboardService.get_dashboard (мок) ────────────────────


class TestGetDashboard:
    """Тесты DashboardService.get_dashboard с моками."""

    @pytest.fixture
    def mock_db(self):
        return AsyncMock()

    @pytest.fixture
    def test_user(self):
        user = MagicMock()
        user.id = uuid.UUID("12345678-1234-5678-1234-567812345678")
        user.tax_system = TaxSystem.USN_INCOME_EXPENSE
        user.usn_rate = Decimal("15.00")
        user.vat_rate = Decimal("22.00")
        return user

    @pytest.mark.asyncio
    async def test_get_dashboard_integrates_all_data(self, mock_db, test_user):
        """get_dashboard собирает все данные в DashboardResponse."""
        from app.services.dashboard_service import DashboardService

        service = DashboardService(mock_db)

        # Мокируем все приватные методы
        with patch.object(service, "_get_income_expense_totals", new_callable=AsyncMock) as mock_ie, \
             patch.object(service, "_estimate_vat", new_callable=AsyncMock) as mock_vat, \
             patch.object(service, "_count_unconfirmed_operations", new_callable=AsyncMock) as mock_unconf, \
             patch.object(service, "_count_unprocessed_documents", new_callable=AsyncMock) as mock_undoc, \
             patch("app.services.dashboard_service.TaxCalendarService") as MockCalendar:

            mock_ie.return_value = {
                "income_total": Decimal("500000"),
                "expense_total": Decimal("200000"),
            }
            mock_vat.return_value = Decimal("25000")
            mock_unconf.return_value = 7
            mock_undoc.return_value = 2

            # Мок calendar service
            mock_cal_instance = AsyncMock()
            mock_cal_instance.update_overdue_statuses = AsyncMock()
            mock_cal_instance.get_upcoming = AsyncMock(return_value=[])
            mock_cal_instance.get_overdue = AsyncMock(return_value=[])
            MockCalendar.return_value = mock_cal_instance

            result = await service.get_dashboard(
                user=test_user,
                period_start=date(2026, 1, 1),
                period_end=date(2026, 3, 31),
            )

        assert isinstance(result, DashboardResponse)
        assert result.income_total == Decimal("500000")
        assert result.expense_total == Decimal("200000")
        assert result.net_profit == Decimal("300000")
        assert result.tax_vat_estimated == Decimal("25000")
        assert result.unconfirmed_operations_count == 7
        assert result.unprocessed_documents_count == 2

        # УСН: (500000 - 200000) * 15% = 45 000 vs min_tax = 500000 * 1% = 5000
        assert result.tax_usn_estimated == Decimal("45000.00")

    @pytest.mark.asyncio
    async def test_get_dashboard_zero_data(self, mock_db, test_user):
        """Дашборд с нулевыми данными."""
        from app.services.dashboard_service import DashboardService

        service = DashboardService(mock_db)

        with patch.object(service, "_get_income_expense_totals", new_callable=AsyncMock) as mock_ie, \
             patch.object(service, "_estimate_vat", new_callable=AsyncMock) as mock_vat, \
             patch.object(service, "_count_unconfirmed_operations", new_callable=AsyncMock) as mock_unconf, \
             patch.object(service, "_count_unprocessed_documents", new_callable=AsyncMock) as mock_undoc, \
             patch("app.services.dashboard_service.TaxCalendarService") as MockCalendar:

            mock_ie.return_value = {
                "income_total": Decimal("0"),
                "expense_total": Decimal("0"),
            }
            mock_vat.return_value = Decimal("0")
            mock_unconf.return_value = 0
            mock_undoc.return_value = 0

            mock_cal_instance = AsyncMock()
            mock_cal_instance.update_overdue_statuses = AsyncMock()
            mock_cal_instance.get_upcoming = AsyncMock(return_value=[])
            mock_cal_instance.get_overdue = AsyncMock(return_value=[])
            MockCalendar.return_value = mock_cal_instance

            result = await service.get_dashboard(
                user=test_user,
                period_start=date(2026, 1, 1),
                period_end=date(2026, 3, 31),
            )

        assert result.income_total == Decimal("0")
        assert result.net_profit == Decimal("0")
        assert result.tax_usn_estimated == Decimal("0")
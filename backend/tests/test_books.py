"""
Тесты для КУДиР, книги покупок и книги продаж.

Тестируем:
- Утилитные функции (quarter_date_range, _build_doc_ref)
- Валидация Pydantic-схем
- Корректность типов данных
"""

import uuid
from datetime import date, datetime
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from app.schemas.kudir import (
    KudirEntryResponse,
    KudirGenerateRequest,
    KudirPeriodRequest,
    KudirPeriodResponse,
)
from app.schemas.purchase_book import (
    PurchaseBookEntryResponse,
    PurchaseBookGenerateRequest,
    PurchaseBookPeriodRequest,
    PurchaseBookPeriodResponse,
)
from app.schemas.sales_book import (
    SalesBookEntryResponse,
    SalesBookGenerateRequest,
    SalesBookPeriodRequest,
    SalesBookPeriodResponse,
)
from app.services.kudir_service import _build_doc_ref, _quarter_date_range


# ─── Тесты _quarter_date_range ──────────────────────────────────


class TestQuarterDateRange:
    """Тесты расчёта диапазона дат по кварталу."""

    def test_q1(self):
        start, end = _quarter_date_range(2026, 1)
        assert start == date(2026, 1, 1)
        assert end == date(2026, 3, 31)

    def test_q2(self):
        start, end = _quarter_date_range(2026, 2)
        assert start == date(2026, 4, 1)
        assert end == date(2026, 6, 30)

    def test_q3(self):
        start, end = _quarter_date_range(2026, 3)
        assert start == date(2026, 7, 1)
        assert end == date(2026, 9, 30)

    def test_q4(self):
        start, end = _quarter_date_range(2026, 4)
        assert start == date(2026, 10, 1)
        assert end == date(2026, 12, 31)

    def test_leap_year_q1(self):
        """Високосный год — квартал 1 заканчивается 31 марта."""
        start, end = _quarter_date_range(2024, 1)
        assert start == date(2024, 1, 1)
        assert end == date(2024, 3, 31)


# ─── Тесты _build_doc_ref ───────────────────────────────────────


class TestBuildDocRef:
    """Тесты формирования ссылки на документ для КУДиР."""

    def test_with_all_fields(self):
        op = MagicMock()
        op.counterparty_name = "ООО Ромашка"
        op.operation_date = date(2026, 3, 15)
        op.counterparty_inn = "7712345678"
        ref = _build_doc_ref(op)
        assert "ООО Ромашка" in ref
        assert "2026-03-15" in ref
        assert "ИНН 7712345678" in ref

    def test_without_counterparty(self):
        op = MagicMock()
        op.counterparty_name = ""
        op.operation_date = date(2026, 3, 15)
        op.counterparty_inn = ""
        ref = _build_doc_ref(op)
        assert "2026-03-15" in ref

    def test_long_name_truncated(self):
        """Длинное имя контрагента обрезается до 80 символов."""
        op = MagicMock()
        op.counterparty_name = "А" * 200
        op.operation_date = date(2026, 1, 1)
        op.counterparty_inn = ""
        ref = _build_doc_ref(op)
        # Имя должно быть ≤80 символов
        parts = ref.split(", ")
        assert len(parts[0]) <= 80

    def test_none_fields(self):
        """None в полях не ломает функцию."""
        op = MagicMock()
        op.counterparty_name = None
        op.operation_date = date(2026, 6, 1)
        op.counterparty_inn = None
        ref = _build_doc_ref(op)
        assert "2026-06-01" in ref


# ─── Тесты KudirEntryResponse ───────────────────────────────────


class TestKudirSchemas:
    """Тесты Pydantic-схем КУДиР."""

    def test_kudir_entry_response_valid(self):
        entry = KudirEntryResponse(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            entry_number=1,
            entry_date=date(2026, 1, 15),
            document_ref="ООО Ромашка, от 2026-01-15",
            description="Оплата за товар",
            income_amount=Decimal("100000.00"),
            expense_amount=Decimal("0.00"),
            quarter=1,
            year=2026,
            linked_operation_id=uuid.uuid4(),
            created_at=datetime.now(),
        )
        assert entry.entry_number == 1
        assert entry.income_amount == Decimal("100000.00")

    def test_kudir_period_request_validation(self):
        req = KudirPeriodRequest(year=2026, quarter=1)
        assert req.year == 2026
        assert req.quarter == 1

    def test_kudir_period_request_invalid_quarter(self):
        with pytest.raises(Exception):
            KudirPeriodRequest(year=2026, quarter=5)

    def test_kudir_period_request_invalid_year(self):
        with pytest.raises(Exception):
            KudirPeriodRequest(year=2019, quarter=1)

    def test_kudir_generate_request_defaults(self):
        req = KudirGenerateRequest(year=2026)
        assert req.quarter is None
        assert req.overwrite is False

    def test_kudir_generate_request_with_quarter(self):
        req = KudirGenerateRequest(year=2026, quarter=3, overwrite=True)
        assert req.quarter == 3
        assert req.overwrite is True

    def test_kudir_period_response(self):
        resp = KudirPeriodResponse(
            entries=[],
            total_income=Decimal("500000.00"),
            total_expense=Decimal("200000.00"),
            net_result=Decimal("300000.00"),
            quarter=1,
            year=2026,
        )
        assert resp.net_result == Decimal("300000.00")
        assert len(resp.entries) == 0


# ─── Тесты PurchaseBookSchemas ──────────────────────────────────


class TestPurchaseBookSchemas:
    """Тесты Pydantic-схем книги покупок."""

    def test_entry_response_valid(self):
        entry = PurchaseBookEntryResponse(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            entry_number=1,
            entry_date=date(2026, 1, 20),
            counterparty_name="ООО Поставщик",
            counterparty_inn="7712345678",
            counterparty_kpp="771201001",
            invoice_number="СФ-001",
            invoice_date=date(2026, 1, 20),
            total_without_vat=Decimal("100000.00"),
            vat_amount=Decimal("22000.00"),
            total_with_vat=Decimal("122000.00"),
            vat_rate=Decimal("22.00"),
            quarter=1,
            year=2026,
            linked_document_id=uuid.uuid4(),
            created_at=datetime.now(),
        )
        assert entry.vat_amount == Decimal("22000.00")
        assert entry.counterparty_name == "ООО Поставщик"

    def test_period_request_validation(self):
        req = PurchaseBookPeriodRequest(year=2026, quarter=2)
        assert req.quarter == 2

    def test_period_request_invalid(self):
        with pytest.raises(Exception):
            PurchaseBookPeriodRequest(year=2026, quarter=0)

    def test_generate_request(self):
        req = PurchaseBookGenerateRequest(year=2026, quarter=1, overwrite=True)
        assert req.overwrite is True

    def test_period_response(self):
        resp = PurchaseBookPeriodResponse(
            entries=[],
            total_without_vat=Decimal("500000.00"),
            total_vat=Decimal("110000.00"),
            total_with_vat=Decimal("610000.00"),
            quarter=1,
            year=2026,
        )
        assert resp.total_vat == Decimal("110000.00")


# ─── Тесты SalesBookSchemas ─────────────────────────────────────


class TestSalesBookSchemas:
    """Тесты Pydantic-схем книги продаж."""

    def test_entry_response_valid(self):
        entry = SalesBookEntryResponse(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            entry_number=1,
            entry_date=date(2026, 2, 10),
            buyer_name="ООО Покупатель",
            buyer_inn="7799887766",
            buyer_kpp="779901001",
            invoice_number="ИСХ-001",
            invoice_date=date(2026, 2, 10),
            total_without_vat=Decimal("200000.00"),
            vat_amount=Decimal("44000.00"),
            total_with_vat=Decimal("244000.00"),
            vat_rate=Decimal("22.00"),
            quarter=1,
            year=2026,
            linked_document_id=uuid.uuid4(),
            created_at=datetime.now(),
        )
        assert entry.buyer_name == "ООО Покупатель"
        assert entry.vat_rate == Decimal("22.00")

    def test_entry_response_receipt(self):
        """Запись из кассового чека."""
        entry = SalesBookEntryResponse(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            entry_number=5,
            entry_date=date(2026, 3, 1),
            buyer_name="Розничный покупатель",
            invoice_number="ФН-12345",
            total_without_vat=Decimal("1000.00"),
            vat_amount=Decimal("220.00"),
            total_with_vat=Decimal("1220.00"),
            vat_rate=Decimal("22.00"),
            quarter=1,
            year=2026,
            linked_receipt_id=uuid.uuid4(),
            created_at=datetime.now(),
        )
        assert entry.linked_receipt_id is not None
        assert entry.linked_document_id is None

    def test_period_request_validation(self):
        req = SalesBookPeriodRequest(year=2026, quarter=4)
        assert req.quarter == 4

    def test_generate_request_defaults(self):
        req = SalesBookGenerateRequest(year=2026, quarter=1)
        assert req.overwrite is False

    def test_period_response(self):
        resp = SalesBookPeriodResponse(
            entries=[],
            total_without_vat=Decimal("1000000.00"),
            total_vat=Decimal("220000.00"),
            total_with_vat=Decimal("1220000.00"),
            quarter=1,
            year=2026,
        )
        assert resp.total_with_vat == Decimal("1220000.00")


# ─── Тесты перекрёстной валидации ────────────────────────────────


class TestCrossValidation:
    """Перекрёстная проверка логики."""

    def test_quarter_covers_full_year(self):
        """Все 4 квартала покрывают весь год без пропусков и перекрытий."""
        all_dates: set[date] = set()
        for q in range(1, 5):
            start, end = _quarter_date_range(2026, q)
            d = start
            while d <= end:
                assert d not in all_dates, f"{d} уже в другом квартале"
                all_dates.add(d)
                d += __import__("datetime").timedelta(days=1)
        # 2026 — не високосный → 365 дней
        assert len(all_dates) == 365

    def test_vat_math_consistency(self):
        """Математическая целостность НДС: total_with = total_without + vat."""
        without = Decimal("100000.00")
        vat_rate = Decimal("22.00")
        vat = (without * vat_rate / Decimal("100")).quantize(Decimal("0.01"))
        total = without + vat

        entry = PurchaseBookEntryResponse(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            entry_number=1,
            entry_date=date(2026, 1, 1),
            total_without_vat=without,
            vat_amount=vat,
            total_with_vat=total,
            vat_rate=vat_rate,
            quarter=1,
            year=2026,
            created_at=datetime.now(),
        )
        assert entry.total_with_vat == entry.total_without_vat + entry.vat_amount
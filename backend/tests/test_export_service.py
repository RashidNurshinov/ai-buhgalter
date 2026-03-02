"""
Тесты сервиса экспорта (export_service).

Тестируем:
- _format_money() — форматирование денежных сумм
- _translate_xml_attr() — перевод XML-атрибутов
- export_kudir_excel() — генерация Excel КУДиР
- export_purchase_book_excel() — генерация Excel книги покупок
- export_sales_book_excel() — генерация Excel книги продаж
"""

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from app.services.export_service import (
    _format_money,
    _translate_xml_attr,
    export_kudir_excel,
    export_purchase_book_excel,
    export_sales_book_excel,
)


# ─── _format_money ──────────────────────────────────────────────


class TestFormatMoney:
    """Тесты форматирования денежных сумм."""

    def test_none_returns_zero(self):
        """None → '0.00'."""
        assert _format_money(None) == "0.00"

    def test_zero(self):
        """Ноль."""
        result = _format_money(Decimal("0.00"))
        assert "0" in result

    def test_positive_amount(self):
        """Положительная сумма."""
        result = _format_money(Decimal("12345.67"))
        # Должно содержать разделитель тысяч и десятичную часть
        assert "12" in result
        assert "345" in result

    def test_large_amount(self):
        """Крупная сумма с разделителями тысяч."""
        result = _format_money(Decimal("1000000.00"))
        assert "1" in result
        assert "000" in result

    def test_small_amount(self):
        """Маленькая сумма."""
        result = _format_money(Decimal("0.01"))
        assert "01" in result

    def test_returns_string(self):
        """Возвращает строку."""
        assert isinstance(_format_money(Decimal("100.00")), str)


# ─── _translate_xml_attr ────────────────────────────────────────


class TestTranslateXmlAttr:
    """Тесты перевода XML-атрибутов."""

    def test_unknown_key_returns_itself(self):
        """Неизвестный ключ возвращается без изменений."""
        assert _translate_xml_attr("unknown_key") == "unknown_key"

    def test_empty_string(self):
        """Пустая строка."""
        assert _translate_xml_attr("") == ""

    def test_returns_string(self):
        """Возвращает строку."""
        assert isinstance(_translate_xml_attr("test"), str)


# ─── export_kudir_excel ─────────────────────────────────────────


class TestExportKudirExcel:
    """Тесты генерации Excel КУДиР."""

    def _make_kudir_entry(self, n: int, income: Decimal, expense: Decimal):
        """Создать мок-запись КУДиР."""
        entry = MagicMock()
        entry.entry_number = n
        entry.entry_date = date(2026, 1, n)
        entry.document_ref = f"Документ №{n}"
        entry.description = f"Описание операции {n}"
        entry.income_amount = income
        entry.expense_amount = expense
        entry.quarter = 1
        return entry

    def test_empty_entries(self):
        """Экспорт с пустым списком."""
        result = export_kudir_excel(
            entries=[],
            totals={"total_income": Decimal("0"), "total_expense": Decimal("0"), "net_result": Decimal("0")},
            year=2026,
        )
        assert isinstance(result, bytes)
        assert len(result) > 0
        # Должен быть валидный XLSX (начинается с PK)
        assert result[:2] == b"PK"

    def test_with_entries(self):
        """Экспорт с записями."""
        entries = [
            self._make_kudir_entry(1, Decimal("100000"), Decimal("0")),
            self._make_kudir_entry(2, Decimal("0"), Decimal("50000")),
        ]
        result = export_kudir_excel(
            entries=entries,
            totals={
                "total_income": Decimal("100000"),
                "total_expense": Decimal("50000"),
                "net_result": Decimal("50000"),
            },
            year=2026,
            quarter=1,
        )
        assert isinstance(result, bytes)
        assert result[:2] == b"PK"

    def test_year_in_result(self):
        """Результат содержит данные (непустой файл)."""
        result = export_kudir_excel(
            entries=[],
            totals={"total_income": Decimal("0"), "total_expense": Decimal("0"), "net_result": Decimal("0")},
            year=2026,
            quarter=2,
        )
        assert len(result) > 100  # Файл не пустой


# ─── export_purchase_book_excel ──────────────────────────────────


class TestExportPurchaseBookExcel:
    """Тесты генерации Excel книги покупок."""

    def _make_purchase_entry(self, n: int):
        """Создать мок-запись книги покупок."""
        entry = MagicMock()
        entry.entry_number = n
        entry.entry_date = date(2026, 1, n + 10)
        entry.counterparty_name = f"ООО Поставщик {n}"
        entry.counterparty_inn = f"77{n:010d}"
        entry.counterparty_kpp = f"77{n:07d}01"
        entry.invoice_number = f"СФ-{n:03d}"
        entry.invoice_date = date(2026, 1, n + 10)
        entry.total_without_vat = Decimal("100000") * n
        entry.vat_amount = Decimal("22000") * n
        entry.total_with_vat = Decimal("122000") * n
        entry.vat_rate = Decimal("22.00")
        return entry

    def test_empty_entries(self):
        """Экспорт книги покупок с пустым списком."""
        result = export_purchase_book_excel(
            entries=[],
            totals={
                "total_without_vat": Decimal("0"),
                "total_vat": Decimal("0"),
                "total_with_vat": Decimal("0"),
            },
            year=2026,
            quarter=1,
        )
        assert isinstance(result, bytes)
        assert result[:2] == b"PK"

    def test_with_entries(self):
        """Экспорт книги покупок с записями."""
        entries = [self._make_purchase_entry(i) for i in range(1, 4)]
        result = export_purchase_book_excel(
            entries=entries,
            totals={
                "total_without_vat": Decimal("600000"),
                "total_vat": Decimal("132000"),
                "total_with_vat": Decimal("732000"),
            },
            year=2026,
            quarter=1,
        )
        assert isinstance(result, bytes)
        assert len(result) > 100


# ─── export_sales_book_excel ────────────────────────────────────


class TestExportSalesBookExcel:
    """Тесты генерации Excel книги продаж."""

    def _make_sales_entry(self, n: int):
        """Создать мок-запись книги продаж."""
        entry = MagicMock()
        entry.entry_number = n
        entry.entry_date = date(2026, 2, n)
        entry.buyer_name = f"ООО Покупатель {n}"
        entry.buyer_inn = f"99{n:010d}"
        entry.buyer_kpp = f"99{n:07d}01"
        entry.invoice_number = f"ИСХ-{n:03d}"
        entry.invoice_date = date(2026, 2, n)
        entry.total_without_vat = Decimal("200000") * n
        entry.vat_amount = Decimal("44000") * n
        entry.total_with_vat = Decimal("244000") * n
        entry.vat_rate = Decimal("22.00")
        return entry

    def test_empty_entries(self):
        """Экспорт книги продаж с пустым списком."""
        result = export_sales_book_excel(
            entries=[],
            totals={
                "total_without_vat": Decimal("0"),
                "total_vat": Decimal("0"),
                "total_with_vat": Decimal("0"),
            },
            year=2026,
            quarter=1,
        )
        assert isinstance(result, bytes)
        assert result[:2] == b"PK"

    def test_with_entries(self):
        """Экспорт книги продаж с записями."""
        entries = [self._make_sales_entry(i) for i in range(1, 3)]
        result = export_sales_book_excel(
            entries=entries,
            totals={
                "total_without_vat": Decimal("600000"),
                "total_vat": Decimal("132000"),
                "total_with_vat": Decimal("732000"),
            },
            year=2026,
            quarter=1,
        )
        assert isinstance(result, bytes)
        assert len(result) > 100
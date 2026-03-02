"""
Тесты для парсера CSV и Excel фай��ов.
Покрывает: 1.7.1 — 1.7.7 из ПЛАН_РЕАЛИЗАЦИИ.md
"""
import io
from datetime import date, datetime
from decimal import Decimal

import pytest

from app.services.csv_parser_service import (
    ParsedOfdReport,
    ParsedInventoryReport,
    parse_csv_bank_statement,
    parse_excel_bank_statement,
    parse_csv_ofd_report,
    parse_excel_inventory,
    _auto_map_columns,
    _dec,
    _parse_date,
    _parse_datetime,
    _detect_payment_type,
    BANK_COLUMN_MAPPINGS,
    OFD_COLUMN_MAPPINGS,
    INVENTORY_COLUMN_MAPPINGS,
    map_ofd_receipts_to_dicts,
    map_inventory_to_dicts,
)
from app.services.xml_parser_service import ParsedBankStatement
from app.utils.file_utils import detect_encoding, detect_delimiter
from app.constants.enums import PaymentType


# ─── Тестовые CSV данные ─────────────────────────────────────────

# Банковская выписка: формат с дебет/кредит (типичный Сбербанк)
BANK_CSV_DEBIT_CREDIT = """\
Дата операции;Номер документа;Контрагент;ИНН контрагента;Дебет;Кредит;Назначение платежа
15.01.2026;101;ООО "Роса";7712345678;;150000.00;Оплата по счёту №45 за товар, в т.ч. НДС 22% — 27049.18
16.01.2026;102;ИП Иванов;561234567890;85000.50;;Оплата за аренду помещения за январь 2026, НДС не облагается
17.01.2026;103;ИФНС №15;7700000015;53658.00;;Фиксированные страховые взносы ИП за 2025 год
18.01.2026;104;Физ.лицо Покупатель;;0;12500.00;Возврат от поставщика ООО "Техно"
"""

# Банковская выписка: формат с одной колонкой суммы (типичный Т-Банк)
BANK_CSV_SINGLE_AMOUNT = """\
Дата;Сумма;Описание операции;Контрагент
20.01.2026;-45000.00;Оплата поставщику за товар, в т.ч. НДС 22% - 8196.72;ООО "Поставщик"
20.01.2026;250000.00;Поступление от покупателя за бытовую технику;ООО "Покупатель"
21.01.2026;-3500.00;Комиссия банка за обслуживание счёта;Т-Банк
"""

# Банковская выписка в Windows-1251
BANK_CSV_CP1251_CONTENT = "Дата;Дебет;Кредит;Назначение платежа\n01.02.2026;1000.00;;Тестовая операция\n"

# Отчёт ОФД
OFD_CSV = """\
Дата чека;Номер чека;Сумма;НДС;Тип оплаты;Тип операции
15.01.2026 10:30:00;1001;5500.00;1000.00;Наличные;Приход
15.01.2026 11:45:00;1002;12300.00;2234.43;Безналичные;Приход
15.01.2026 14:00:00;1003;3200.00;581.97;Наличные;Возврат прихода
16.01.2026 09:15:00;1004;8900.00;1616.39;Карта;Приход
"""

# Товароучёт (для Excel тест)
INVENTORY_CSV = """\
Наименование;Артикул;Количество;Ед. изм.;Цена закупки;Цена продажи;Ставка НДС;Категория;Поставщик
Холодильник Samsung RT35;SAM-RT35;5;шт;28000.00;42000.00;22%;Бытовая техника;ООО "Техно"
Стиральная машина LG F2V5;LG-F2V5;3;шт;22000.00;35000.00;22%;Бытовая техника;ООО "Техно"
Диван угловой "Комфорт";DIV-001;2;шт;18000.00;32000.00;22%;Мебель;ООО "Мебельторг"
Стол обеденный;TBL-100;10;шт;5500.00;9900.00;22%;Мебель;ООО "Мебельторг"
"""


# ─── Тесты detect_encoding (1.7.5) ──────────────────────────────


class TestDetectEncoding:
    """Тесты автодетекта кодировки."""

    def test_utf8(self):
        data = "Тестовая строка UTF-8".encode("utf-8")
        enc = detect_encoding(data)
        assert enc.lower() in ("utf-8", "utf8")

    def test_utf8_bom(self):
        data = b"\xef\xbb\xbf" + "Тестовая строка с BOM".encode("utf-8")
        enc = detect_encoding(data)
        assert enc == "utf-8-sig"

    def test_windows_1251(self):
        data = BANK_CSV_CP1251_CONTENT.encode("windows-1251")
        enc = detect_encoding(data)
        # Должна определить как windows-1251 или совместимую кодировку
        # Проверяем что можно декодировать
        decoded = data.decode(enc)
        assert "Дата" in decoded or "ата" in decoded

    def test_utf16_le_bom(self):
        data = b"\xff\xfe" + "Test".encode("utf-16-le")
        enc = detect_encoding(data)
        assert enc == "utf-16-le"

    def test_utf16_be_bom(self):
        data = b"\xfe\xff" + "Test".encode("utf-16-be")
        enc = detect_encoding(data)
        assert enc == "utf-16-be"

    def test_empty_data(self):
        enc = detect_encoding(b"")
        assert enc == "utf-8"

    def test_ascii_normalizes_to_utf8(self):
        data = b"Date;Amount;Purpose"
        enc = detect_encoding(data)
        assert enc.lower() in ("utf-8", "utf8", "ascii")


# ─── Тесты detect_delimiter (1.7.6) ─────────────────────────────


class TestDetectDelimiter:
    """Тесты автодетекта разделителя."""

    def test_semicolon(self):
        text = "Дата;Дебет;Кредит;Назначение\n01.01.2026;100;0;Тест\n"
        delim = detect_delimiter(text)
        assert delim == ";"

    def test_comma(self):
        text = "Date,Amount,Purpose\n2026-01-01,100.00,Test payment\n"
        delim = detect_delimiter(text)
        assert delim == ","

    def test_tab(self):
        text = "Дата\tСумма\tНазначение\n01.01.2026\t100\tТест\n"
        delim = detect_delimiter(text)
        assert delim == "\t"

    def test_pipe(self):
        text = "Дата|Сумма|Назначение\n01.01.2026|100|Тест\n"
        delim = detect_delimiter(text)
        assert delim == "|"

    def test_empty_text(self):
        delim = detect_delimiter("")
        assert delim == ";"  # дефолт для российских файлов

    def test_single_line(self):
        text = "Дата;Дебет;Кредит"
        delim = detect_delimiter(text)
        assert delim == ";"


# ─── Тесты маппинга колонок (1.7.7) ────────────────────────────


class TestAutoMapColumns:
    """Тесты автоматического маппинга колонок."""

    def test_exact_match_bank(self):
        columns = ["Дата операции", "Дебет", "Кредит", "Назначение платежа", "Контрагент"]
        result = _auto_map_columns(columns, BANK_COLUMN_MAPPINGS)
        assert result["operation_date"] == "Дата операции"
        assert result["debit"] == "Дебет"
        assert result["credit"] == "Кредит"
        assert result["purpose"] == "Назначение платежа"
        assert result["counterparty_name"] == "Контрагент"

    def test_partial_match(self):
        columns = ["Дата совершения", "Сумма операции (руб.)", "Описание"]
        result = _auto_map_columns(columns, BANK_COLUMN_MAPPINGS)
        # "Дата совершения" может не совпасть точно, но частично — "дата"
        # "Сумма операции (руб.)" → amount
        assert result["amount"] == "Сумма операции (руб.)"

    def test_ofd_mapping(self):
        columns = ["Дата чека", "Номер чека", "Сумма", "Сумма НДС", "Тип оплаты", "Тип операции"]
        result = _auto_map_columns(columns, OFD_COLUMN_MAPPINGS)
        assert result["receipt_date"] == "Дата чека"
        assert result["receipt_number"] == "Номер чека"
        assert result["total"] == "Сумма"
        assert result["vat_amount"] == "Сумма НДС"
        assert result["payment_type"] == "Тип оплаты"
        assert result["operation_type"] == "Тип операции"

    def test_inventory_mapping(self):
        columns = ["Наименование", "Артикул", "Количество", "Цена продажи", "Ставка НДС"]
        result = _auto_map_columns(columns, INVENTORY_COLUMN_MAPPINGS)
        assert result["name"] == "Наименование"
        assert result["sku"] == "Артикул"
        assert result["quantity"] == "Количество"
        assert result["selling_price"] == "Цена продажи"
        assert result["vat_rate"] == "Ставка НДС"

    def test_no_match(self):
        columns = ["ColumnA", "ColumnB", "ColumnC"]
        result = _auto_map_columns(columns, BANK_COLUMN_MAPPINGS)
        assert all(v is None for v in result.values())

    def test_yo_normalization(self):
        """Проверяем что 'ё' нормализуется в 'е'."""
        columns = ["Счёт контрагента", "Дата"]
        result = _auto_map_columns(columns, BANK_COLUMN_MAPPINGS)
        assert result["counterparty_account"] == "Счёт контрагента"
        assert result["operation_date"] == "Дата"


# ─── Тесты вспомогательных функций ──────────────────────────────


class TestHelperFunctions:
    """Тесты для _dec, _parse_date, _parse_datetime, _detect_payment_type."""

    def test_dec_normal(self):
        assert _dec("1234.56") == Decimal("1234.56")

    def test_dec_comma(self):
        assert _dec("1234,56") == Decimal("1234.56")

    def test_dec_thousands(self):
        assert _dec("1 234,56") == Decimal("1234.56")

    def test_dec_european(self):
        """Формат 1.234,56 (точка как разделитель тысяч)."""
        assert _dec("1.234,56") == Decimal("1234.56")

    def test_dec_currency(self):
        assert _dec("1234.56₽") == Decimal("1234.56")

    def test_dec_empty(self):
        assert _dec("") == Decimal("0")
        assert _dec(None) == Decimal("0")
        assert _dec("-") == Decimal("0")

    def test_dec_negative(self):
        assert _dec("-5000.00") == Decimal("-5000.00")

    def test_dec_nbsp(self):
        """Неразрывный пробел."""
        assert _dec("1\xa0234,56") == Decimal("1234.56")

    def test_parse_date_ddmmyyyy(self):
        assert _parse_date("15.01.2026") == date(2026, 1, 15)

    def test_parse_date_iso(self):
        assert _parse_date("2026-01-15") == date(2026, 1, 15)

    def test_parse_date_slash(self):
        assert _parse_date("15/01/2026") == date(2026, 1, 15)

    def test_parse_date_short_year(self):
        assert _parse_date("15.01.26") == date(2026, 1, 15)

    def test_parse_date_none(self):
        assert _parse_date(None) is None
        assert _parse_date("") is None
        assert _parse_date("nan") is None

    def test_parse_date_datetime_object(self):
        dt = datetime(2026, 1, 15, 12, 0)
        assert _parse_date(dt) == date(2026, 1, 15)

    def test_parse_datetime_full(self):
        result = _parse_datetime("15.01.2026 10:30:00")
        assert result == datetime(2026, 1, 15, 10, 30, 0)

    def test_parse_datetime_short(self):
        result = _parse_datetime("15.01.2026 10:30")
        assert result == datetime(2026, 1, 15, 10, 30)

    def test_parse_datetime_iso(self):
        result = _parse_datetime("2026-01-15T10:30:00")
        assert result == datetime(2026, 1, 15, 10, 30, 0)

    def test_parse_datetime_date_only(self):
        result = _parse_datetime("15.01.2026")
        assert result == datetime(2026, 1, 15, 0, 0)

    def test_detect_payment_cash(self):
        assert _detect_payment_type("Наличные") == PaymentType.CASH

    def test_detect_payment_card(self):
        assert _detect_payment_type("Безналичные") == PaymentType.CARD
        assert _detect_payment_type("Карта") == PaymentType.CARD
        assert _detect_payment_type("Эквайринг") == PaymentType.CARD

    def test_detect_payment_online(self):
        assert _detect_payment_type("Онлайн перевод") == PaymentType.ONLINE

    def test_detect_payment_mixed(self):
        assert _detect_payment_type("Смешанная оплата") == PaymentType.MIXED


# ─── Тесты parse_csv_bank_statement (1.7.1) ─────────────────────


class TestParseCsvBankStatement:
    """Тесты парсинга CSV банковской выписки."""

    def test_debit_credit_format(self):
        """Формат с колонками дебет/кредит (Сбербанк)."""
        data = BANK_CSV_DEBIT_CREDIT.encode("utf-8")
        result = parse_csv_bank_statement(data)

        assert result.is_valid
        assert len(result.operations) == 4

        # Первая операция — кредит (приход)
        op1 = result.operations[0]
        assert op1.is_income is True
        assert op1.is_expense is False
        assert op1.amount == Decimal("150000.00")
        assert op1.counterparty_name == 'ООО "Роса"'
        assert op1.counterparty_inn == "7712345678"
        assert op1.operation_date == date(2026, 1, 15)
        assert op1.vat_amount == Decimal("27049.18")

        # Вторая операция — дебет (расход)
        op2 = result.operations[1]
        assert op2.is_expense is True
        assert op2.amount == Decimal("85000.50")
        assert op2.vat_amount == Decimal("0")  # "НДС не облагается"

        # Третья операция — расход на налоги
        op3 = result.operations[2]
        assert op3.is_expense is True
        assert op3.amount == Decimal("53658.00")

        # Период
        assert result.period_start == date(2026, 1, 15)
        assert result.period_end == date(2026, 1, 18)

    def test_single_amount_format(self):
        """Формат с одной колонкой суммы (Т-Банк, отрицательные = расход)."""
        data = BANK_CSV_SINGLE_AMOUNT.encode("utf-8")
        result = parse_csv_bank_statement(data)

        assert result.is_valid
        assert len(result.operations) == 3

        # Расход (отрицательная сумма)
        op1 = result.operations[0]
        assert op1.is_expense is True
        assert op1.amount == Decimal("45000.00")
        assert op1.vat_amount == Decimal("8196.72")

        # Приход (положительная сумма)
        op2 = result.operations[1]
        assert op2.is_income is True
        assert op2.amount == Decimal("250000.00")

        # Расход (комиссия банка)
        op3 = result.operations[2]
        assert op3.is_expense is True
        assert op3.amount == Decimal("3500.00")

    def test_windows_1251_encoding(self):
        """CSV в кодировке Windows-1251."""
        data = BANK_CSV_CP1251_CONTENT.encode("windows-1251")
        result = parse_csv_bank_statement(data)

        assert result.is_valid
        assert len(result.operations) == 1
        assert result.operations[0].amount == Decimal("1000.00")
        assert result.operations[0].is_expense is True

    def test_empty_csv(self):
        """Пустой CSV файл."""
        data = b""
        result = parse_csv_bank_statement(data)
        assert not result.is_valid
        assert len(result.errors) > 0

    def test_no_date_column(self):
        """CSV без колонки даты."""
        data = b"Amount;Purpose\n100;Test\n"
        result = parse_csv_bank_statement(data)
        assert not result.is_valid
        assert any("дат" in e.lower() for e in result.errors)

    def test_no_amount_column(self):
        """CSV без колонки суммы."""
        data = "Дата;Контрагент\n01.01.2026;Тест\n".encode("utf-8")
        result = parse_csv_bank_statement(data)
        assert not result.is_valid
        assert any("сумм" in e.lower() or "дебет" in e.lower() for e in result.errors)

    def test_total_income_expense(self):
        """Проверка расчёта итогов."""
        data = BANK_CSV_DEBIT_CREDIT.encode("utf-8")
        result = parse_csv_bank_statement(data)

        assert result.total_income == Decimal("150000.00") + Decimal("12500.00")
        assert result.total_expense == Decimal("85000.50") + Decimal("53658.00")


# ─── Тесты parse_excel_bank_statement (1.7.2) ───────────────────


class TestParseExcelBankStatement:
    """Тесты парсинга Excel банковской выписки."""

    def _create_excel_bytes(self, data_dict: dict) -> bytes:
        """Вспомогательная функция: создаёт XLSX-файл из словаря."""
        import pandas as pd
        df = pd.DataFrame(data_dict)
        buf = io.BytesIO()
        df.to_excel(buf, index=False, engine="openpyxl")
        return buf.getvalue()

    def test_basic_excel(self):
        """Базовый Excel с дебет/кредит."""
        data = self._create_excel_bytes({
            "Дата операции": ["15.01.2026", "16.01.2026"],
            "Дебет": ["", "50000"],
            "Кредит": ["100000", ""],
            "Контрагент": ['ООО "Тест"', 'ООО "Поставщик"'],
            "Назначение платежа": ["Оплата товара", "Аренда"],
        })
        result = parse_excel_bank_statement(data)

        assert result.is_valid
        assert len(result.operations) == 2
        assert result.operations[0].is_income is True
        assert result.operations[0].amount == Decimal("100000.00")
        assert result.operations[1].is_expense is True
        assert result.operations[1].amount == Decimal("50000.00")

    def test_empty_excel(self):
        """Пустой Excel файл."""
        data = self._create_excel_bytes({})
        result = parse_excel_bank_statement(data)
        assert not result.is_valid

    def test_invalid_excel(self):
        """Невалидный файл (не Excel)."""
        result = parse_excel_bank_statement(b"not an excel file")
        assert not result.is_valid
        assert len(result.errors) > 0


# ─── Тесты parse_csv_ofd_report (1.7.3) ─────────────────────────


class TestParseCsvOfdReport:
    """Тесты парсинга CSV отчёта ОФД."""

    def test_basic_ofd_report(self):
        """Базовый отчёт ОФД."""
        data = OFD_CSV.encode("utf-8")
        result = parse_csv_ofd_report(data)

        assert result.is_valid
        assert len(result.receipts) == 4

        # Первый чек
        r1 = result.receipts[0]
        assert r1.receipt_date == datetime(2026, 1, 15, 10, 30, 0)
        assert r1.receipt_number == "1001"
        assert r1.total == Decimal("5500.00")
        assert r1.vat_amount == Decimal("1000.00")
        assert r1.payment_type == PaymentType.CASH
        assert r1.is_return is False

        # Второй чек — безналичные
        r2 = result.receipts[1]
        assert r2.payment_type == PaymentType.CARD

        # Третий чек — возврат
        r3 = result.receipts[2]
        assert r3.is_return is True

        # Четвёртый чек — карта
        r4 = result.receipts[3]
        assert r4.payment_type == PaymentType.CARD

    def test_ofd_totals(self):
        """Проверка расчёта итогов ОФД."""
        data = OFD_CSV.encode("utf-8")
        result = parse_csv_ofd_report(data)

        # Продажи: 5500 + 12300 + 8900 = 26700
        assert result.total_sales == Decimal("5500.00") + Decimal("12300.00") + Decimal("8900.00")
        # Возвраты: 3200
        assert result.total_returns == Decimal("3200.00")
        # НДС: 1000 + 2234.43 + 581.97 + 1616.39 = 5432.79
        expected_vat = Decimal("1000.00") + Decimal("2234.43") + Decimal("581.97") + Decimal("1616.39")
        assert result.total_vat == expected_vat

    def test_ofd_period(self):
        """Проверка определения периода."""
        data = OFD_CSV.encode("utf-8")
        result = parse_csv_ofd_report(data)

        assert result.period_start == date(2026, 1, 15)
        assert result.period_end == date(2026, 1, 16)

    def test_empty_ofd(self):
        """Пустой CSV."""
        data = b""
        result = parse_csv_ofd_report(data)
        assert not result.is_valid

    def test_no_date_column_ofd(self):
        """ОФД без колонки даты."""
        data = "Сумма;НДС\n100;18\n".encode("utf-8")
        result = parse_csv_ofd_report(data)
        assert not result.is_valid
        assert any("дат" in e.lower() for e in result.errors)


# ─── Тесты parse_excel_inventory (1.7.4) ────────────────────────


class TestParseExcelInventory:
    """Тесты парсинга Excel товароучёта."""

    def _create_excel_bytes(self, data_dict: dict) -> bytes:
        import pandas as pd
        df = pd.DataFrame(data_dict)
        buf = io.BytesIO()
        df.to_excel(buf, index=False, engine="openpyxl")
        return buf.getvalue()

    def test_basic_inventory(self):
        """Базовый отчёт товароучёта."""
        data = self._create_excel_bytes({
            "Наименование": ["Холодильник Samsung", "Стиральная машина LG"],
            "Артикул": ["SAM-001", "LG-002"],
            "Количество": ["5", "3"],
            "Ед. изм.": ["шт", "шт"],
            "Цена закупки": ["28000", "22000"],
            "Цена продажи": ["42000", "35000"],
            "Ставка НДС": ["22%", "22%"],
            "Категория": ["Бытовая техника", "Бытовая техника"],
            "Поставщик": ['ООО "Техно"', 'ООО "Техно"'],
        })

        result = parse_excel_inventory(data)

        assert result.is_valid
        assert result.total_items == 2

        item1 = result.items[0]
        assert item1.name == "Холодильник Samsung"
        assert item1.sku == "SAM-001"
        assert item1.quantity == Decimal("5.00")
        assert item1.purchase_price == Decimal("28000.00")
        assert item1.selling_price == Decimal("42000.00")
        assert item1.vat_rate == Decimal("22.00")
        assert item1.category == "Бытовая техника"

        # Общая стоимость: 5*42000 + 3*35000 = 210000 + 105000 = 315000
        assert result.total_value == Decimal("315000.00")

    def test_inventory_csv_format(self):
        """Товароучёт из CSV (через маппинг на Excel-парсер не проходит,
        но можно протестить через DataFrame напрямую)."""
        data = INVENTORY_CSV.encode("utf-8")
        # parse_excel_inventory ожидает Excel, используем CSV-обёртку
        # Здесь тестируем что CSV с товароучётом можно обработать
        # через _parse_inventory_dataframe напрямую
        from app.services.csv_parser_service import (
            _read_csv_to_dataframe,
            _parse_inventory_dataframe,
            ParsedInventoryReport,
        )
        df = _read_csv_to_dataframe(data)
        result = _parse_inventory_dataframe(df, ParsedInventoryReport())

        assert result.is_valid
        assert result.total_items == 4
        assert result.items[0].name == "Холодильник Samsung RT35"
        assert result.items[0].sku == "SAM-RT35"

    def test_empty_inventory(self):
        """Пустой Excel."""
        data = self._create_excel_bytes({})
        result = parse_excel_inventory(data)
        assert not result.is_valid

    def test_no_name_column(self):
        """Без колонки наименования."""
        data = self._create_excel_bytes({
            "Артикул": ["A1"],
            "Количество": ["1"],
        })
        result = parse_excel_inventory(data)
        assert not result.is_valid
        assert any("наименован" in e.lower() for e in result.errors)


# ─── Тесты маппинга результатов в БД ────────────────────────────


class TestMapping:
    """Тесты маппинга результатов парсинга в словари для БД."""

    def test_map_ofd_receipts(self):
        data = OFD_CSV.encode("utf-8")
        result = parse_csv_ofd_report(data)
        dicts = map_ofd_receipts_to_dicts(result)

        assert len(dicts) == 4
        assert dicts[0]["total"] == Decimal("5500.00")
        assert dicts[0]["payment_type"] == "cash"
        assert dicts[0]["is_return"] is False
        assert dicts[2]["is_return"] is True

    def test_map_inventory(self):
        from app.services.csv_parser_service import (
            _read_csv_to_dataframe,
            _parse_inventory_dataframe,
            ParsedInventoryReport,
        )
        data = INVENTORY_CSV.encode("utf-8")
        df = _read_csv_to_dataframe(data)
        result = _parse_inventory_dataframe(df, ParsedInventoryReport())
        dicts = map_inventory_to_dicts(result)

        assert len(dicts) == 4
        assert dicts[0]["name"] == "Холодильник Samsung RT35"
        assert dicts[0]["sku"] == "SAM-RT35"
        assert dicts[0]["quantity"] == Decimal("5.00")


# ─── Тесты граничных случаев ────────────────────────────────────


class TestEdgeCases:
    """Тесты граничных случаев."""

    def test_csv_with_extra_header_lines(self):
        """CSV с дополнительными строками заголовка банка."""
        csv_data = """\
Выписка по счёту 40702810100000012345
Период: 01.01.2026 - 31.01.2026
Банк: ПАО Сбербанк

Дата операции;Дебет;Кредит;Назначение платежа
15.01.2026;;50000.00;Оплата от покупателя
16.01.2026;30000.00;;Оплата поставщику
"""
        data = csv_data.encode("utf-8")
        result = parse_csv_bank_statement(data)

        assert result.is_valid
        assert len(result.operations) == 2

    def test_csv_with_trailing_empty_rows(self):
        """CSV с пустыми строками в конце."""
        csv_data = """\
Дата;Дебет;Кредит;Назначение платежа
15.01.2026;;10000;Тест

;;;
"""
        data = csv_data.encode("utf-8")
        result = parse_csv_bank_statement(data)

        assert result.is_valid
        assert len(result.operations) == 1

    def test_csv_amounts_with_spaces(self):
        """CSV с суммами, содержащими пробелы (1 000 000,00)."""
        csv_data = """\
Дата;Сумма;Назначение
15.01.2026;1 250 000,00;Большая оплата
"""
        data = csv_data.encode("utf-8")
        result = parse_csv_bank_statement(data)

        assert result.is_valid
        assert len(result.operations) == 1
        assert result.operations[0].amount == Decimal("1250000.00")

    def test_bank_statement_vat_extraction(self):
        """Извлечение НДС из назначения платежа."""
        csv_data = """\
Дата;Сумма;Назначение платежа
15.01.2026;-122000;Оплата по сч. 123 за товар, в т.ч. НДС 22% - 22000.00
16.01.2026;-50000;Оплата за услуги без НДС
17.01.2026;-61000;Оплата по договору, НДС (22%) 11000
"""
        data = csv_data.encode("utf-8")
        result = parse_csv_bank_statement(data)

        assert len(result.operations) == 3
        assert result.operations[0].vat_amount == Decimal("22000.00")
        assert result.operations[1].vat_amount == Decimal("0")
        assert result.operations[2].vat_amount == Decimal("11000.00")
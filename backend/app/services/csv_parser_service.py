"""
Сервис парсинга CSV и Excel файлов.

Поддерживаемые форматы:
- CSV банковская выписка (Сбербанк, Т-Банк, универсальный формат)
- Excel банковская выписка (XLS, XLSX)
- CSV отчёт ОФД (чеки)
- Excel данные товароучёта (Мой Склад и аналоги)

Все парсеры переиспользуют dataclasses из xml_parser_service:
ParsedBankStatement, ParsedBankOperation, ParsedDocument и т.д.

Справочник: СПРАВОЧНИК_СУЩНОСТЕЙ.md → services/csv_parser_service.py
"""
import io
import logging
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Optional

import pandas as pd

from app.constants.enums import DocumentType, OperationCategory, PaymentType
from app.services.xml_parser_service import (
    ParsedBankOperation,
    ParsedBankStatement,
    _extract_vat_from_purpose,
)
from app.utils.file_utils import detect_delimiter, detect_encoding

logger = logging.getLogger(__name__)


# ─── Результаты парсинга ОФД ────────────────────────────────────


@dataclass
class ParsedOfdReceiptItem:
    """Позиция в чеке ОФД."""
    name: str = ""
    quantity: Decimal = Decimal("1")
    price: Decimal = Decimal("0")
    total: Decimal = Decimal("0")
    vat_rate: Decimal = Decimal("22")
    vat_amount: Decimal = Decimal("0")


@dataclass
class ParsedOfdReceipt:
    """Один чек из отчёта ОФД."""
    receipt_date: Optional[datetime] = None
    receipt_number: str = ""
    fiscal_number: str = ""
    total: Decimal = Decimal("0")
    vat_amount: Decimal = Decimal("0")
    payment_type: PaymentType = PaymentType.CASH
    is_return: bool = False
    items: list[ParsedOfdReceiptItem] = field(default_factory=list)


@dataclass
class ParsedOfdReport:
    """Результат парсинга отчёта ОФД (CSV)."""
    receipts: list[ParsedOfdReceipt] = field(default_factory=list)
    period_start: Optional[date] = None
    period_end: Optional[date] = None
    total_sales: Decimal = Decimal("0")
    total_returns: Decimal = Decimal("0")
    total_vat: Decimal = Decimal("0")
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0


@dataclass
class ParsedInventoryItem:
    """Позиция из товароучётной системы."""
    name: str = ""
    sku: str = ""
    barcode: str = ""
    quantity: Decimal = Decimal("0")
    unit: str = ""
    purchase_price: Decimal = Decimal("0")
    selling_price: Decimal = Decimal("0")
    vat_rate: Decimal = Decimal("22")
    category: str = ""
    supplier_name: str = ""
    supplier_inn: str = ""


@dataclass
class ParsedInventoryReport:
    """Результат парсинга данных товароучёта."""
    items: list[ParsedInventoryItem] = field(default_factory=list)
    report_date: Optional[date] = None
    total_items: int = 0
    total_value: Decimal = Decimal("0")
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0


# ─── Маппинг колонок (1.7.7) ────────────────────────────────────

# Шаблоны для автодетекта колонок банковской выписки
# Ключ: каноническое имя поля, значение: список вариантов названий колонок
BANK_COLUMN_MAPPINGS: dict[str, list[str]] = {
    "operation_date": [
        "дата", "дата операции", "дата проводки", "дата проведения",
        "дата документа", "дата платежа", "date", "operation_date",
        "дата опер", "дата списания/зачисления", "дата совершения операции",
    ],
    "amount": [
        "сумма", "сумма операции", "сумма платежа", "amount",
        "сумма в валюте счёта", "сумма в валюте счета",
        "сумма (руб)", "сумма, руб", "сумма операции (руб.)",
    ],
    "debit": [
        "дебет", "списание", "расход", "debit", "сумма списания",
        "дебет (руб)", "исходящие", "сумма дебета",
    ],
    "credit": [
        "кредит", "зачисление", "приход", "credit", "сумма зачисления",
        "кредит (руб)", "входящие", "сумма кредита",
    ],
    "counterparty_name": [
        "контрагент", "наименование контрагента", "получатель",
        "плательщик", "наименование получателя", "наименование плательщика",
        "counterparty", "имя контрагента", "корреспондент",
        "наименование корреспондента",
    ],
    "counterparty_inn": [
        "инн контрагента", "инн получателя", "инн плательщика",
        "инн", "инн корреспондента", "inn",
    ],
    "purpose": [
        "назначение платежа", "назначение", "основание", "описание",
        "описание операции", "purpose", "комментарий", "примечание",
        "наименование операции", "содержание операции",
    ],
    "doc_number": [
        "номер документа", "номер", "№ документа", "номер п/п",
        "doc_number", "№ п/п", "номер док",
    ],
    "counterparty_account": [
        "счёт контрагента", "счет контрагента", "р/с контрагента",
        "корр. счёт", "корр. счет", "счёт получателя", "счет получателя",
        "счёт плательщика", "счет плательщика",
    ],
    "counterparty_bik": [
        "бик контрагента", "бик получателя", "бик плательщика", "бик",
    ],
    "operation_type": [
        "тип операции", "тип", "вид операции", "дебет/кредит",
        "operation_type", "направление",
    ],
}

# Шаблоны для автодетекта колонок отчёта ОФД
OFD_COLUMN_MAPPINGS: dict[str, list[str]] = {
    "receipt_date": [
        "дата", "дата чека", "дата и время", "дата операции",
        "дата/время", "date", "datetime",
    ],
    "receipt_number": [
        "номер чека", "№ чека", "номер", "чек №", "receipt_number",
        "номер фд", "фискальный номер документа",
    ],
    "fiscal_number": [
        "фн", "фискальный номер", "fiscal_number", "номер фн",
        "фискальный накопитель",
    ],
    "total": [
        "итого", "сумма", "сумма чека", "total", "amount",
        "сумма (руб)", "сумма, руб",
    ],
    "vat_amount": [
        "ндс", "сумма ндс", "ндс (руб)", "vat", "vat_amount",
        "ндс итого", "сумма ндс итого",
    ],
    "payment_type": [
        "тип оплаты", "способ оплаты", "вид оплаты",
        "payment_type", "наличные/безналичные",
    ],
    "operation_type": [
        "тип операции", "тип чека", "вид операции", "приход/возврат",
        "признак расчёта", "признак расчета",
    ],
}

# Шаблоны для автодетекта колонок товароучёта
INVENTORY_COLUMN_MAPPINGS: dict[str, list[str]] = {
    "name": [
        "��аименование", "название", "товар", "name", "номенклатура",
        "наименование товара", "наименование номенклатуры",
    ],
    "sku": [
        "артикул", "sku", "код", "код товара", "арт.",
        "внутренний код", "код номенклатуры",
    ],
    "barcode": [
        "штрихкод", "штрих-код", "barcode", "ean",
    ],
    "quantity": [
        "количество", "остаток", "кол-во", "qty", "quantity",
        "остаток на складе", "кол.",
    ],
    "unit": [
        "единица", "ед. изм.", "ед.изм", "unit", "единица измерения",
    ],
    "purchase_price": [
        "цена закупки", "закупочная цена", "себестоимость",
        "цена поставщика", "purchase_price", "входная цена",
    ],
    "selling_price": [
        "цена продажи", "розничная цена", "selling_price",
        "цена", "цена реализации", "отпускная цена",
    ],
    "vat_rate": [
        "ставка ндс", "ндс %", "ндс", "vat_rate", "% ндс",
    ],
    "category": [
        "категория", "группа", "category", "вид товара", "тип",
    ],
    "supplier_name": [
        "поставщик", "наименование поставщика", "supplier",
    ],
    "supplier_inn": [
        "инн поставщика", "инн", "supplier_inn",
    ],
}


def _auto_map_columns(
    df_columns: list[str],
    mappings: dict[str, list[str]],
) -> dict[str, str | None]:
    """
    Автоматический маппинг колонок DataFrame на канонические поля.

    Алгоритм:
    1. Нормализует названия колонок (lowercase, strip)
    2. Ищет точное совпадение с шаблонами
    3. Ищет частичное совпадение (contains)

    Args:
        df_columns: Список названий колонок из DataFrame
        mappings: Словарь {каноническое_имя: [варианты_названий]}

    Returns:
        Словарь {каноническое_имя: название_колонки_в_DataFrame | None}
    """
    result: dict[str, str | None] = {key: None for key in mappings}

    # Нормализованные колонки для поиска
    normalized = {col: col.strip().lower().replace("ё", "е") for col in df_columns}
    used_columns: set[str] = set()

    # 1. Точное совпадение
    for field_name, variants in mappings.items():
        for col, norm_col in normalized.items():
            if col in used_columns:
                continue
            for variant in variants:
                variant_norm = variant.lower().replace("ё", "е")
                if norm_col == variant_norm:
                    result[field_name] = col
                    used_columns.add(col)
                    break
            if result[field_name] is not None:
                break

    # 2. Частичное совпадение (для ненайденных полей)
    for field_name, variants in mappings.items():
        if result[field_name] is not None:
            continue
        for col, norm_col in normalized.items():
            if col in used_columns:
                continue
            for variant in variants:
                variant_norm = variant.lower().replace("ё", "е")
                if variant_norm in norm_col or norm_col in variant_norm:
                    result[field_name] = col
                    used_columns.add(col)
                    break
            if result[field_name] is not None:
                break

    return result


# ─── Вспомогательные функции ─────────────────────────────────────


def _dec(value, default: Decimal = Decimal("0")) -> Decimal:
    """Безопасное преобразование в Decimal."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return default
    try:
        s = str(value).strip().replace(" ", "").replace("\xa0", "")
        # Обработка формата "1 234,56" или "1.234,56"
        if "," in s and "." in s:
            # "1.234,56" → "1234.56"
            s = s.replace(".", "").replace(",", ".")
        elif "," in s:
            # "1234,56" → "1234.56"
            s = s.replace(",", ".")
        # Убираем валютный знак (руб., ₽, $, €, RUB)
        s = re.sub(r"руб\.?", "", s, flags=re.IGNORECASE)
        s = re.sub(r"[₽$€]", "", s)
        s = re.sub(r"\bRUB\b", "", s, flags=re.IGNORECASE).strip()
        if not s or s == "-":
            return default
        return Decimal(s).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError):
        return default


def _parse_date(value) -> Optional[date]:
    """Безопасный парсинг даты из различных форматов."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, (date, datetime)):
        return value if isinstance(value, date) and not isinstance(value, datetime) else value.date() if isinstance(value, datetime) else value
    s = str(value).strip()
    if not s or s.lower() == "nan":
        return None
    for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d",
                "%d.%m.%y", "%d/%m/%y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _parse_datetime(value) -> Optional[datetime]:
    """Безопасный парсинг даты-времени."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time())
    s = str(value).strip()
    if not s or s.lower() == "nan":
        return None
    for fmt in ("%d.%m.%Y %H:%M:%S", "%d.%m.%Y %H:%M", "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%dT%H:%M:%S", "%d/%m/%Y %H:%M:%S", "%d.%m.%Y",
                "%Y-%m-%d", "%d.%m.%y %H:%M:%S", "%d.%m.%y %H:%M"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def _detect_payment_type(value) -> PaymentType:
    """Определение типа оплаты из строки."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return PaymentType.CASH
    s = str(value).strip().lower()
    if any(w in s for w in ["безнал", "карт", "эквайринг", "card", "электронн"]):
        return PaymentType.CARD
    if any(w in s for w in ["перевод", "transfer", "онлайн", "online"]):
        return PaymentType.ONLINE
    if any(w in s for w in ["смешан", "mixed", "комбинир"]):
        return PaymentType.MIXED
    if any(w in s for w in ["наличн", "cash", "нал"]):
        return PaymentType.CASH
    return PaymentType.CASH


def _read_csv_to_dataframe(
    file_data: bytes,
    encoding: str | None = None,
    delimiter: str | None = None,
    skip_rows: int = 0,
) -> pd.DataFrame:
    """
    Чтение CSV-файла в pandas DataFrame с автодетектом кодировки и разделителя.

    Args:
        file_data: Байтовое содержимое файла
        encoding: Кодировка (если None — автодетект)
        delimiter: Разделитель (если None — автодетект)
        skip_rows: Количество строк для пропуска в начале

    Returns:
        pandas DataFrame
    """
    if encoding is None:
        encoding = detect_encoding(file_data)

    text = file_data.decode(encoding, errors="replace")

    if delimiter is None:
        delimiter = detect_delimiter(text)

    # Пропуск пустых строк и строк-заголовков банка в начале
    lines = text.splitlines()
    actual_skip = skip_rows

    # Эвристика: пропускаем строки до первой строки с достаточным числом разделителей
    if skip_rows == 0:
        min_delimiters = 2
        for i, line in enumerate(lines):
            if line.count(delimiter) >= min_delimiters:
                actual_skip = i
                break

    df = pd.read_csv(
        io.StringIO(text),
        sep=delimiter,
        skiprows=actual_skip,
        dtype=str,
        keep_default_na=False,
        on_bad_lines="warn",
        engine="python",
    )

    # Очистка: убираем полностью пустые строки и колонки
    df = df.dropna(how="all")
    df = df.loc[:, ~df.columns.str.startswith("Unnamed")]

    # Убираем пробелы в названиях колонок
    df.columns = [str(c).strip() for c in df.columns]

    return df


def _read_excel_to_dataframe(
    file_data: bytes,
    sheet_name: int | str = 0,
    skip_rows: int = 0,
) -> pd.DataFrame:
    """
    Чтение Excel-файла (XLS/XLSX) в pandas DataFrame.

    Args:
        file_data: Байтовое содержимое файла
        sheet_name: Имя или индекс листа
        skip_rows: Количество строк для пропуска

    Returns:
        pandas DataFrame
    """
    buf = io.BytesIO(file_data)

    # Пробуем определить формат
    try:
        df = pd.read_excel(
            buf,
            sheet_name=sheet_name,
            skiprows=skip_rows,
            dtype=str,
            keep_default_na=False,
            engine=None,  # pandas выберет автоматически (openpyxl для xlsx, xlrd для xls)
        )
    except Exception:
        # Fallback: пробуем другой engine
        buf.seek(0)
        try:
            df = pd.read_excel(
                buf,
                sheet_name=sheet_name,
                skiprows=skip_rows,
                dtype=str,
                keep_default_na=False,
                engine="openpyxl",
            )
        except Exception:
            buf.seek(0)
            df = pd.read_excel(
                buf,
                sheet_name=sheet_name,
                skiprows=skip_rows,
                dtype=str,
                keep_default_na=False,
                engine="xlrd",
            )

    # Очистка
    df = df.dropna(how="all")
    df.columns = [str(c).strip() for c in df.columns]

    # Убираем Unnamed колонки, но только полностью пустые
    unnamed_cols = [c for c in df.columns if c.startswith("Unnamed")]
    if unnamed_cols:
        # Проверяем, есть ли данные в Unnamed колонках
        for col in unnamed_cols:
            if df[col].astype(str).str.strip().replace("", pd.NA).dropna().empty:
                df = df.drop(columns=[col])

    # Эвристика: ищем строку-заголовок в первых 20 строках
    # Банковские выписки часто имеют метаданные перед заголовком
    if len(df) > 0 and skip_rows == 0:
        all_bank_variants = []
        for variants in BANK_COLUMN_MAPPINGS.values():
            all_bank_variants.extend([v.lower().replace("ё", "е") for v in variants])

        # Сначала проверяем текущие колонки DataFrame
        current_cols_norm = [str(c).strip().lower().replace("ё", "е") for c in df.columns]
        current_matches = sum(
            1 for h in current_cols_norm
            if any(v in h or h in v for v in all_bank_variants)
        )

        if current_matches < 2:
            # Колонки не похожи на заголовки — ищем заголовок в данных
            best_row_idx = -1
            best_matches = 0

            for i in range(min(20, len(df))):
                row_values = [
                    str(v).strip().lower().replace("ё", "е")
                    for v in df.iloc[i]
                    if str(v).strip()
                ]
                matches = sum(
                    1 for h in row_values
                    if any(v in h or h in v for v in all_bank_variants)
                )
                if matches > best_matches:
                    best_matches = matches
                    best_row_idx = i

            if best_matches >= 2 and best_row_idx >= 0:
                # Извлекаем метаданные из строк до заголовка
                _extract_metadata_from_header_rows(df, best_row_idx)
                # Устанавливаем найденную строку как заголовок
                new_headers = [str(v).strip() for v in df.iloc[best_row_idx]]
                df = df.iloc[best_row_idx + 1:].reset_index(drop=True)
                df.columns = new_headers[:len(df.columns)]
                # Убираем пустые строки после переназначения
                df = df.dropna(how="all")
                # Убираем Unnamed колонки
                df = df.loc[:, ~df.columns.str.startswith("Unnamed")]
                df = df.loc[:, df.columns.str.strip() != ""]
        else:
            # Текущие колонки уже похожи на заголовки — проверяем первую строку
            first_row = df.iloc[0]
            potential_headers = [
                str(v).strip().lower().replace("ё", "е")
                for v in first_row if str(v).strip()
            ]
            row_matches = sum(
                1 for h in potential_headers
                if any(v in h or h in v for v in all_bank_variants)
            )
            if row_matches > current_matches:
                df.columns = [str(v).strip() for v in first_row]
                df = df.iloc[1:].reset_index(drop=True)

    return df


def _extract_metadata_from_header_rows(df: pd.DataFrame, header_row_idx: int) -> dict:
    """
    Извлечение метаданных из строк перед заголовком (номер счёта, ИНН, остатки).
    Возвращает словарь с метаданными (пока для логирования).
    """
    metadata = {}
    for i in range(header_row_idx):
        row_values = [str(v).strip() for v in df.iloc[i] if str(v).strip()]
        if len(row_values) >= 2:
            key = row_values[0].lower().replace("ё", "е")
            val = row_values[1]
            if "номер счета" in key or "номер счёта" in key or "выписка по счету" in key or "выписка по счёту" in key:
                # Извлекаем номер счёта (20 цифр)
                account_match = re.search(r"\d{20}", val)
                if account_match:
                    metadata["account_number"] = account_match.group()
            elif "инн" in key:
                metadata["inn"] = val
            elif "входящий остаток" in key:
                metadata["opening_balance"] = val
            elif "исходящий остаток" in key:
                metadata["closing_balance"] = val
            elif "клиент" in key:
                metadata["client_name"] = val

    if metadata:
        logger.info(f"Извлечены метаданные выписки: {metadata}")
    return metadata


# ─── Публичные функции парсинга ──────────────────────────────────


def parse_csv_bank_statement(
    file_data: bytes,
    encoding: str | None = None,
    delimiter: str | None = None,
) -> ParsedBankStatement:
    """
    Парсинг банковской выписки из CSV-файла.

    Поддерживаемые форматы:
    - Сбербанк Бизнес (CSV-выгрузка)
    - Т-Банк Бизнес (CSV-выгрузка)
    - Универсальный формат (дата, сумма, контрагент, назначение)

    Args:
        file_data: Байтовое содержимое CSV-файла
        encoding: Кодировка (None для автодетекта)
        delimiter: Разделитель (None для автодетекта)

    Returns:
        ParsedBankStatement с операциями
    """
    result = ParsedBankStatement()

    try:
        df = _read_csv_to_dataframe(file_data, encoding, delimiter)
    except Exception as e:
        result.errors.append(f"Ошибка чтения CSV: {e}")
        logger.exception(f"Ошибка чтения CSV банковской выписки: {e}")
        return result

    if df.empty:
        result.errors.append("CSV-файл пуст или не содержит данных")
        return result

    return _parse_bank_dataframe(df, result)


def parse_excel_bank_statement(
    file_data: bytes,
    sheet_name: int | str = 0,
) -> ParsedBankStatement:
    """
    Парсинг банковской выписки из Excel-файла (XLS/XLSX).

    Args:
        file_data: Байтовое содержимое Excel-файла
        sheet_name: Имя или индекс листа (по умолчанию первый)

    Returns:
        ParsedBankStatement с операциями
    """
    result = ParsedBankStatement()

    try:
        df = _read_excel_to_dataframe(file_data, sheet_name)
    except Exception as e:
        result.errors.append(f"Ошибка чтения Excel: {e}")
        logger.exception(f"Ошибка чтения Excel банковской выписки: {e}")
        return result

    if df.empty:
        result.errors.append("Excel-файл пуст или не содержит данных")
        return result

    return _parse_bank_dataframe(df, result)


def parse_csv_ofd_report(
    file_data: bytes,
    encoding: str | None = None,
    delimiter: str | None = None,
) -> ParsedOfdReport:
    """
    Парсинг отчёта ОФД из CSV-файла.

    Поддерживаемые форматы:
    - OFD.ru (CSV-выгрузка)
    - Платформа ОФД (CSV-выгрузка)
    - Универсальный формат (дата, номер чека, сумма, НДС)

    Args:
        file_data: Байтовое содержимое CSV-файла
        encoding: Кодировка (None для автодетекта)
        delimiter: Разделитель (None для автодетекта)

    Returns:
        ParsedOfdReport с чеками
    """
    result = ParsedOfdReport()

    try:
        df = _read_csv_to_dataframe(file_data, encoding, delimiter)
    except Exception as e:
        result.errors.append(f"Ошибка чтения CSV: {e}")
        logger.exception(f"Ошибка чтения CSV отчёта ОФД: {e}")
        return result

    if df.empty:
        result.errors.append("CSV-файл пуст или не содержит данных")
        return result

    return _parse_ofd_dataframe(df, result)


def parse_excel_inventory(
    file_data: bytes,
    sheet_name: int | str = 0,
) -> ParsedInventoryReport:
    """
    Парсинг данных товароучёта из Excel-файла.

    Поддерживаемые форматы:
    - Мой Склад (Excel-выгрузка)
    - Универсальный формат (наименование, артикул, количество, цена)

    Args:
        file_data: Байтовое содержимое Excel-файла
        sheet_name: Имя или индекс листа

    Returns:
        ParsedInventoryReport с товарами
    """
    result = ParsedInventoryReport()

    try:
        df = _read_excel_to_dataframe(file_data, sheet_name)
    except Exception as e:
        result.errors.append(f"Ошибка чтения Excel: {e}")
        logger.exception(f"Ошибка чтения Excel товароучёта: {e}")
        return result

    if df.empty:
        result.errors.append("Excel-файл пуст или не содержит данных")
        return result

    return _parse_inventory_dataframe(df, result)


# ─── Внутренние функции парсинга ─────────────────────────────────


def _parse_bank_dataframe(
    df: pd.DataFrame,
    result: ParsedBankStatement,
) -> ParsedBankStatement:
    """
    Парсинг DataFrame банковской выписки в ParsedBankStatement.

    Используется общий код для CSV и Excel.
    """
    col_map = _auto_map_columns(list(df.columns), BANK_COLUMN_MAPPINGS)

    logger.info(
        f"Маппинг колонок банковской выписки: {col_map} "
        f"(всего колонок: {list(df.columns)}, строк: {len(df)})"
    )

    # Проверяем наличие обязательных колонок
    date_col = col_map["operation_date"]
    amount_col = col_map["amount"]
    debit_col = col_map["debit"]
    credit_col = col_map["credit"]
    op_type_col = col_map.get("operation_type")

    if date_col is None:
        result.errors.append(
            f"Не найдена колонка с датой операции. "
            f"Доступные колонки: {list(df.columns)}"
        )
        return result

    # Должна быть либо колонка суммы, либо пара дебет/кредит
    has_amount = amount_col is not None
    has_debit_credit = debit_col is not None or credit_col is not None
    has_op_type = op_type_col is not None

    if not has_amount and not has_debit_credit:
        result.errors.append(
            f"Не найдена колонка с суммой или дебет/кредит. "
            f"Доступные колонки: {list(df.columns)}"
        )
        return result

    purpose_col = col_map["purpose"]
    cp_name_col = col_map["counterparty_name"]
    cp_inn_col = col_map["counterparty_inn"]
    doc_number_col = col_map["doc_number"]

    for idx, row in df.iterrows():
        op = ParsedBankOperation()

        # Дата
        op.operation_date = _parse_date(row.get(date_col))
        if op.operation_date is None:
            continue  # Пропускаем строки без даты (итоги, заголовки)

        # Суммы
        if has_debit_credit:
            debit_val = _dec(row.get(debit_col)) if debit_col else Decimal("0")
            credit_val = _dec(row.get(credit_col)) if credit_col else Decimal("0")

            if debit_val > 0:
                op.amount = debit_val
                op.is_expense = True
            elif credit_val > 0:
                op.amount = credit_val
                op.is_income = True
            else:
                continue  # Пропускаем строки без суммы
        elif has_amount:
            raw_amount = _dec(row.get(amount_col))
            if raw_amount == 0:
                continue

            if has_op_type:
                # Направление определяется колонкой "Тип операции"
                op_type_val = str(row.get(op_type_col, "")).strip().lower()
                op.amount = abs(raw_amount)
                if any(w in op_type_val for w in ["дебет", "debit", "списание", "расход"]):
                    op.is_expense = True
                elif any(w in op_type_val for w in ["кредит", "credit", "зачисление", "приход"]):
                    op.is_income = True
                else:
                    # Fallback: по знаку суммы
                    if raw_amount < 0:
                        op.is_expense = True
                    else:
                        op.is_income = True
            else:
                # Отрицательная сумма = расход, положительная = приход
                if raw_amount < 0:
                    op.amount = abs(raw_amount)
                    op.is_expense = True
                else:
                    op.amount = raw_amount
                    op.is_income = True

        # Контрагент
        if cp_name_col:
            op.counterparty_name = str(row.get(cp_name_col, "")).strip()
        if cp_inn_col:
            op.counterparty_inn = str(row.get(cp_inn_col, "")).strip()

        # Назначение платежа
        if purpose_col:
            op.purpose = str(row.get(purpose_col, "")).strip()

        # Номер документа
        if doc_number_col:
            op.doc_number = str(row.get(doc_number_col, "")).strip()

        # НДС из назначения платежа
        if op.purpose:
            op.vat_amount = _extract_vat_from_purpose(op.purpose)

        if op.amount > 0:
            result.operations.append(op)

    # Расчёт периода
    dates = [op.operation_date for op in result.operations if op.operation_date]
    if dates:
        result.period_start = min(dates)
        result.period_end = max(dates)

    if not result.operations:
        result.warnings.append("Не найдено ни одной операции в выписке")

    logger.info(
        f"Распарсено операций: {len(result.operations)} "
        f"(доходы: {result.total_income}, расходы: {result.total_expense})"
    )

    return result


def _parse_ofd_dataframe(
    df: pd.DataFrame,
    result: ParsedOfdReport,
) -> ParsedOfdReport:
    """
    Парсинг DataFrame отчёта ОФД в ParsedOfdReport.
    """
    col_map = _auto_map_columns(list(df.columns), OFD_COLUMN_MAPPINGS)

    date_col = col_map["receipt_date"]
    total_col = col_map["total"]

    if date_col is None:
        result.errors.append(
            f"Не найдена колонка с датой чека. "
            f"Доступные колонки: {list(df.columns)}"
        )
        return result

    if total_col is None:
        result.errors.append(
            f"Не найдена колонка с суммой чека. "
            f"Доступные колонки: {list(df.columns)}"
        )
        return result

    receipt_number_col = col_map["receipt_number"]
    fiscal_number_col = col_map["fiscal_number"]
    vat_col = col_map["vat_amount"]
    payment_type_col = col_map["payment_type"]
    operation_type_col = col_map["operation_type"]

    logger.info(
        f"Маппинг колонок ОФД: {col_map} (всего строк: {len(df)})"
    )

    for idx, row in df.iterrows():
        receipt = ParsedOfdReceipt()

        # Дата
        receipt.receipt_date = _parse_datetime(row.get(date_col))
        if receipt.receipt_date is None:
            continue

        # Сумма
        receipt.total = _dec(row.get(total_col))
        if receipt.total == 0:
            continue

        # Номер чека
        if receipt_number_col:
            receipt.receipt_number = str(row.get(receipt_number_col, "")).strip()

        # Фискальный номер
        if fiscal_number_col:
            receipt.fiscal_number = str(row.get(fiscal_number_col, "")).strip()

        # НДС
        if vat_col:
            receipt.vat_amount = _dec(row.get(vat_col))

        # Тип оплаты
        if payment_type_col:
            receipt.payment_type = _detect_payment_type(row.get(payment_type_col))

        # Возврат
        if operation_type_col:
            op_type = str(row.get(operation_type_col, "")).strip().lower()
            receipt.is_return = any(
                w in op_type for w in ["возврат", "return", "refund"]
            )

        result.receipts.append(receipt)

    # Расчёт итогов
    for receipt in result.receipts:
        if receipt.is_return:
            result.total_returns += receipt.total
        else:
            result.total_sales += receipt.total
        result.total_vat += receipt.vat_amount

    # Период
    dates = [r.receipt_date.date() for r in result.receipts if r.receipt_date]
    if dates:
        result.period_start = min(dates)
        result.period_end = max(dates)

    if not result.receipts:
        result.warnings.append("Не найдено ни одного чека в отчёте ОФД")

    logger.info(
        f"Распарсено чеков: {len(result.receipts)} "
        f"(продажи: {result.total_sales}, возвраты: {result.total_returns})"
    )

    return result


def _parse_inventory_dataframe(
    df: pd.DataFrame,
    result: ParsedInventoryReport,
) -> ParsedInventoryReport:
    """
    Парсинг DataFrame товароучёта в ParsedInventoryReport.
    """
    col_map = _auto_map_columns(list(df.columns), INVENTORY_COLUMN_MAPPINGS)

    name_col = col_map["name"]

    if name_col is None:
        result.errors.append(
            f"Не найдена колонка с наименованием товара. "
            f"Доступные колонки: {list(df.columns)}"
        )
        return result

    sku_col = col_map["sku"]
    barcode_col = col_map["barcode"]
    qty_col = col_map["quantity"]
    unit_col = col_map["unit"]
    purchase_price_col = col_map["purchase_price"]
    selling_price_col = col_map["selling_price"]
    vat_rate_col = col_map["vat_rate"]
    category_col = col_map["category"]
    supplier_name_col = col_map["supplier_name"]
    supplier_inn_col = col_map["supplier_inn"]

    logger.info(
        f"Маппинг колонок товароучёта: {col_map} (всего строк: {len(df)})"
    )

    for idx, row in df.iterrows():
        item = ParsedInventoryItem()

        # Наименование
        item.name = str(row.get(name_col, "")).strip()
        if not item.name:
            continue

        # Артикул
        if sku_col:
            item.sku = str(row.get(sku_col, "")).strip()

        # Штрихкод
        if barcode_col:
            item.barcode = str(row.get(barcode_col, "")).strip()

        # Количество
        if qty_col:
            item.quantity = _dec(row.get(qty_col))

        # Единица измерения
        if unit_col:
            item.unit = str(row.get(unit_col, "")).strip()

        # Цена закупки
        if purchase_price_col:
            item.purchase_price = _dec(row.get(purchase_price_col))

        # Цена продажи
        if selling_price_col:
            item.selling_price = _dec(row.get(selling_price_col))

        # Ставка НДС
        if vat_rate_col:
            vat_str = str(row.get(vat_rate_col, "")).strip()
            vat_str = re.sub(r"[%\s]", "", vat_str)
            if vat_str and vat_str.lower() not in ("без ндс", "безндс", ""):
                item.vat_rate = _dec(vat_str, Decimal("22"))

        # Категория
        if category_col:
            item.category = str(row.get(category_col, "")).strip()

        # Поставщик
        if supplier_name_col:
            item.supplier_name = str(row.get(supplier_name_col, "")).strip()
        if supplier_inn_col:
            item.supplier_inn = str(row.get(supplier_inn_col, "")).strip()

        result.items.append(item)

    # Итоги
    result.total_items = len(result.items)
    result.total_value = sum(
        (i.quantity * i.selling_price for i in result.items),
        Decimal("0"),
    ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    if not result.items:
        result.warnings.append("Не найдено ни одного товара в отчёте")

    logger.info(
        f"Распарсено товаров: {result.total_items} "
        f"(общая стоимость: {result.total_value})"
    )

    return result


# ─── Маппинг результатов для сохранения в БД ────────────────────


def map_ofd_receipts_to_dicts(parsed: ParsedOfdReport) -> list[dict]:
    """
    Маппинг ParsedOfdReport в список словарей для создания CashReceipt.
    """
    receipts = []
    for r in parsed.receipts:
        receipts.append({
            "receipt_date": r.receipt_date,
            "receipt_number": r.receipt_number or None,
            "fiscal_number": r.fiscal_number or None,
            "total": r.total,
            "vat_amount": r.vat_amount,
            "payment_type": r.payment_type.value,
            "is_return": r.is_return,
        })
    return receipts


def map_inventory_to_dicts(parsed: ParsedInventoryReport) -> list[dict]:
    """
    Маппинг ParsedInventoryReport в список словарей.
    """
    items = []
    for item in parsed.items:
        items.append({
            "name": item.name,
            "sku": item.sku or None,
            "barcode": item.barcode or None,
            "quantity": item.quantity,
            "unit": item.unit or None,
            "purchase_price": item.purchase_price,
            "selling_price": item.selling_price,
            "vat_rate": item.vat_rate,
            "category": item.category or None,
            "supplier_name": item.supplier_name or None,
            "supplier_inn": item.supplier_inn or None,
        })
    return items
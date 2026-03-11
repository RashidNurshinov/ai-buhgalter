"""
Сервис парсинга XML-документов ФНС.

Поддерживаемые форматы:
- Счёт-фактура (СФ) XML ФНС
- УПД (универсальный передаточный документ) XML ФНС
- ТОРГ-12 (товарная накладная) XML ФНС
- Банковская выписка (формат 1С)

Все парсеры возвращают унифицированную структуру ParsedDocument / ParsedBankStatement.
"""
import logging
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from enum import Enum
from typing import Optional

from lxml import etree

from app.constants.enums import DocumentType, OperationCategory
from app.utils.validators import (
    validate_inn,
    validate_kpp,
    validate_amounts_consistency,
)

logger = logging.getLogger(__name__)


# ─── Определение кодировки XML ────────────────────────────────────────


def _detect_encoding(xml_content: bytes) -> str:
    """
    Определение кодировки XML файла.
    
    Приоритеты:
    1. encoding из XML declaration (<?xml version="1.0" encoding="..."?>)
    2. Windows-1251 для русских файлов ФНС
    3. UTF-8 по умолчанию
    """
    # Пробуем найти XML declaration
    match = re.match(rb'^<\?xml[^>]*encoding=["\']([^"\'>]+)["\']', xml_content[:200])
    if match:
        return match.group(1).decode('ascii')
    
    # Для файлов ФНС без declaration пробуем Windows-1251
    # Сигнатура: первые байты 0xD4 0xE0 0xE9 0xEB = "Файл" в Windows-1251
    if xml_content[:4] == b'\xd4\xe0\xe9\xeb':
        return 'windows-1251'
    
    return 'utf-8'


def _decode_xml_content(xml_content: bytes) -> str:
    """
    Декодирование XML контента с определением кодировки.
    """
    encoding = _detect_encoding(xml_content)
    try:
        return xml_content.decode(encoding)
    except (UnicodeDecodeError, LookupError):
        # Fallback на UTF-8 с заменой
        return xml_content.decode('utf-8', errors='replace')


# ─── Результаты парсинга (dataclasses) ──────────────────────────


@dataclass
class ParsedCounterparty:
    """Распознанный контрагент из XML."""
    name: str = ""
    inn: str = ""
    kpp: str = ""
    address: str = ""

    @property
    def is_valid_inn(self) -> bool:
        if not self.inn:
            return False
        ok, _ = validate_inn(self.inn)
        return ok


@dataclass
class ParsedDocumentItem:
    """Позиция документа (товар/услуга)."""
    name: str = ""
    quantity: Decimal = Decimal("1")
    unit: str = ""
    price_without_vat: Decimal = Decimal("0")
    vat_rate: Decimal = Decimal("0")
    vat_amount: Decimal = Decimal("0")
    total_with_vat: Decimal = Decimal("0")

    @property
    def total_without_vat(self) -> Decimal:
        return (self.quantity * self.price_without_vat).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )


@dataclass
class ParsedDocument:
    """Результат парсинга XML-документа (СФ, УПД, ТОРГ-12)."""
    doc_type: DocumentType = DocumentType.OTHER
    doc_number: str = ""
    doc_date: Optional[date] = None

    seller: ParsedCounterparty = field(default_factory=ParsedCounterparty)
    buyer: ParsedCounterparty = field(default_factory=ParsedCounterparty)

    items: list[ParsedDocumentItem] = field(default_factory=list)

    total_without_vat: Decimal = Decimal("0")
    vat_amount: Decimal = Decimal("0")
    total_with_vat: Decimal = Decimal("0")
    vat_rate: Decimal = Decimal("22")

    currency: str = "RUB"

    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    raw_xml_type: str = ""

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0

    @property
    def confidence_score(self) -> Decimal:
        score = Decimal("1.00")
        score -= Decimal("0.05") * len(self.warnings)
        score -= Decimal("0.20") * len(self.errors)
        return max(Decimal("0.00"), min(Decimal("1.00"), score))


@dataclass
class ParsedBankOperation:
    """Одна операция из банковской выписки."""
    operation_date: Optional[date] = None
    amount: Decimal = Decimal("0")
    is_income: bool = False
    is_expense: bool = False
    counterparty_name: str = ""
    counterparty_inn: str = ""
    counterparty_kpp: str = ""
    counterparty_account: str = ""
    purpose: str = ""
    doc_number: str = ""
    doc_date: Optional[date] = None
    vat_amount: Optional[Decimal] = None

    @property
    def category_hint(self) -> OperationCategory:
        """Предварительная классификация по назначению платежа."""
        p = self.purpose.lower()
        if any(w in p for w in ["налог", "ндс", "усн", "ндфл", "взнос", "пени", "штраф"]):
            return OperationCategory.TAXES_AND_FEES
        if "аренд" in p:
            return OperationCategory.RENT
        if any(w in p for w in ["зарплат", "з/п", "заработн"]):
            return OperationCategory.SALARY
        if any(w in p for w in ["комисси", "обслуживан"]):
            return OperationCategory.BANK_COMMISSION
        if "страхов" in p:
            return OperationCategory.INSURANCE_PAYMENT
        if any(w in p for w in ["оплата по сч", "за товар", "за материал", "закуп"]):
            if self.is_expense:
                return OperationCategory.PURCHASE_GOODS
        if any(w in p for w in ["оплата по дог", "за услуг"]):
            if self.is_expense:
                return OperationCategory.SERVICES
        if "возврат" in p and self.is_income:
            return OperationCategory.SUPPLIER_RETURN
        if any(w in p for w in ["выручк", "реализац", "оплата от"]) and self.is_income:
            return OperationCategory.SALES_REVENUE
        if any(w in p for w in ["эквайринг", "acquiring"]) and self.is_income:
            return OperationCategory.ACQUIRING
        if any(w in p for w in ["перевод на свой", "перевод между своими", "внутренн"]):
            return OperationCategory.INTERNAL_TRANSFER
        if any(w in p for w in ["взнос собственных", "пополнение"]):
            return OperationCategory.OWN_FUNDS
        if any(w in p for w in ["снятие", "выдача наличн"]):
            return OperationCategory.CASH_WITHDRAWAL
        return OperationCategory.UNCLASSIFIED


@dataclass
class ParsedBankStatement:
    """Результат парсинга банковской выписки."""
    bank_name: str = ""
    account_number: str = ""
    bik: str = ""
    period_start: Optional[date] = None
    period_end: Optional[date] = None
    opening_balance: Decimal = Decimal("0")
    closing_balance: Decimal = Decimal("0")
    operations: list[ParsedBankOperation] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0

    @property
    def total_income(self) -> Decimal:
        return sum((op.amount for op in self.operations if op.is_income), Decimal("0"))

    @property
    def total_expense(self) -> Decimal:
        return sum((op.amount for op in self.operations if op.is_expense), Decimal("0"))


# ─── XML Type Detection ─────────────────────────────────────────


class XmlDocumentType(str, Enum):
    INVOICE = "invoice"
    UPD = "upd"
    TORG12 = "torg12"
    BANK_STATEMENT_1C = "bank_statement_1c"
    UNKNOWN = "unknown"


_XML_TYPE_SIGNATURES = {
    "ON_SFAKT": XmlDocumentType.INVOICE,
    "ON_SCHFDOPPR": XmlDocumentType.UPD,
    "ON_SCHFDOPPOK": XmlDocumentType.UPD,
    "ON_TORG12": XmlDocumentType.TORG12,
    "ON_KORSFAKT": XmlDocumentType.INVOICE,
}


def detect_xml_document_type(xml_content: bytes | str) -> XmlDocumentType:
    """Определение типа XML-документа по корневому элементу, атрибутам и namespace."""
    try:
        if isinstance(xml_content, str):
            xml_content = xml_content.encode("utf-8")
        if xml_content.startswith(b"\xef\xbb\xbf"):
            xml_content = xml_content[3:]
        root = etree.fromstring(xml_content)
    except etree.XMLSyntaxError as e:
        logger.error(f"Ошибка парсинга XML для определения типа: {e}")
        return XmlDocumentType.UNKNOWN

    root_tag = _strip_ns(root.tag)

    # 1. ФНС-файлы: <Файл ИдФайл="ON_SFAKT_...">
    if root_tag in ("Файл", "File"):
        id_file = (root.get("ИдФайл", "") or root.get("IdFile", "")).upper()
        for prefix, doc_type in _XML_TYPE_SIGNATURES.items():
            if prefix in id_file:
                return doc_type
        # Ищем <Документ Функция="...">
        for child in root:
            ct = _strip_ns(child.tag)
            if ct == "Документ":
                func = child.get("Функция", "")
                if func in ("СЧФ", "СЧФДОП"):
                    return XmlDocumentType.UPD
                if func == "ДОП":
                    return XmlDocumentType.TORG12
            if ct in ("СчФакт", "СвСчФакт"):
                return XmlDocumentType.INVOICE

    # 2. Namespace 1С
    for ns_uri in (root.nsmap or {}).values():
        if ns_uri and "1C" in ns_uri and "Bank" in ns_uri:
            return XmlDocumentType.BANK_STATEMENT_1C

    # 3. Корневой элемент — банковская выписка
    if root_tag in ("БанковскаяВыписка", "BankStatement", "BankStatements", "Выписка"):
        return XmlDocumentType.BANK_STATEMENT_1C

    # 4. Дочерние элементы
    child_tags = {_strip_ns(c.tag) for c in root}
    if {"Плательщик", "Получатель"} & child_tags or "ПлатПоруч" in child_tags:
        return XmlDocumentType.BANK_STATEMENT_1C
    if "СвСчФакт" in child_tags:
        return XmlDocumentType.INVOICE

    logger.warning(f"Не удалось определить тип XML. root={root_tag}, children={child_tags}")
    return XmlDocumentType.UNKNOWN


# ─── Вспомогательные функции ─────────────────────────────────────


def _strip_ns(tag: str) -> str:
    """Удаляет namespace: {http://...}Tag -> Tag."""
    return tag.split("}", 1)[1] if "}" in tag else tag


def _find_child(parent: etree._Element, tag: str) -> Optional[etree._Element]:
    for ch in parent:
        if _strip_ns(ch.tag) == tag:
            return ch
    return None


def _find_all(parent: etree._Element, tag: str) -> list[etree._Element]:
    return [ch for ch in parent if _strip_ns(ch.tag) == tag]


def _find(parent: etree._Element, *tags: str) -> Optional[etree._Element]:
    """Ищет первый совпавший дочерний элемент по списку возможных тегов (рекурсивно через /)."""
    for tag in tags:
        parts = tag.split("/")
        cur = parent
        ok = True
        for p in parts:
            c = _find_child(cur, p)
            if c is None:
                ok = False
                break
            cur = c
        if ok:
            return cur
    return None


def _text(el: Optional[etree._Element], default: str = "") -> str:
    if el is None:
        return default
    return (el.text or "").strip() or default


def _attr(el: Optional[etree._Element], *names: str, default: str = "") -> str:
    if el is None:
        return default
    for n in names:
        v = el.get(n)
        if v is not None:
            return v.strip()
    return default


def _dec(value: str, default: Decimal = Decimal("0")) -> Decimal:
    if not value:
        return default
    try:
        return Decimal(value.strip().replace(",", ".").replace(" ", ""))
    except (InvalidOperation, ValueError):
        return default


def _date(value: str) -> Optional[date]:
    if not value:
        return None
    value = value.strip()
    for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def _vat_rate(s: str) -> Decimal:
    if not s:
        return Decimal("0")
    s = s.strip().lower()
    mapping = {
        "22": Decimal("22"), "22%": Decimal("22"),
        "10": Decimal("10"), "10%": Decimal("10"),
        "0": Decimal("0"), "0%": Decimal("0"),
        "без ндс": Decimal("0"), "безндс": Decimal("0"),
        "20": Decimal("20"), "20%": Decimal("20"),
        "18": Decimal("18"), "18%": Decimal("18"),
        "22/122": Decimal("22"), "10/110": Decimal("10"),
        "20/120": Decimal("20"), "18/118": Decimal("18"),
    }
    return mapping.get(s, _dec(s))


def _extract_vat_from_purpose(purpose: str) -> Optional[Decimal]:
    """Извлечение суммы НДС из строки назначения платежа."""
    pl = purpose.lower()
    if "без ндс" in pl or "ндс не облаг" in pl:
        return Decimal("0")
    patterns = [
        r'(?:в\s*т\.?\s*ч\.?\s*)?ндс\s*(?:\d+\s*%?\s*)?[\-\—\s]*(\d+[\.,]?\d*)',
        r'ндс\s*\(\s*\d+\s*%\s*\)\s*[\-\—\s]*(\d+[\.,]?\d*)',
        r'ндс\s*=?\s*(\d+[\.,]?\d*)',
    ]
    for pat in patterns:
        m = re.search(pat, pl)
        if m:
            return _dec(m.group(1))
    return None


# ─── Парсинг корневого XML ───────────────────────────────────────


def _parse_root(xml_content: bytes | str) -> etree._Element:
    """Парсинг корневого элемента XML с авто-определением кодировки."""
    if isinstance(xml_content, str):
        xml_content = xml_content.encode("utf-8")
    if xml_content.startswith(b"\xef\xbb\xbf"):
        xml_content = xml_content[3:]
    
    # Определяем кодировку и декодируем
    xml_str = _decode_xml_content(xml_content)
    
    try:
        parser = etree.XMLParser(recover=True, encoding='utf-8')
        return etree.fromstring(xml_str.encode('utf-8'), parser=parser)
    except etree.XMLSyntaxError as e:
        raise ValueError(f"Невалидный XML: {e}")


# ─── Парсинг контрагента ────────────────────────────────────────


def _parse_counterparty(el: etree._Element, cp: ParsedCounterparty):
    """Извлечение данных контрагента из XML-элемента."""
    # 1. Атрибуты
    cp.name = _attr(el, "НаимОрг", "Наим", "Name", "Название")
    cp.inn = _attr(el, "ИННЮЛ", "ИНН", "ИННФЛ", "INN")
    cp.kpp = _attr(el, "КПП", "KPP")

    # 2. Вложенный ИдСв
    id_sv = _find(el, "ИдСв", "IdInfo")
    if id_sv is not None:
        sv_ul = _find(id_sv, "СвЮЛУч", "СвЮЛ", "LegalEntity")
        if sv_ul is not None:
            cp.name = cp.name or _attr(sv_ul, "НаимОрг", "Наим", "Name")
            cp.inn = cp.inn or _attr(sv_ul, "ИННЮЛ", "ИНН", "INN")
            cp.kpp = cp.kpp or _attr(sv_ul, "КПП", "KPP")
        sv_ip = _find(id_sv, "СвИП", "IndividualEntrepreneur")
        if sv_ip is not None:
            cp.inn = cp.inn or _attr(sv_ip, "ИННФЛ", "ИНН", "INN")
            fam = _attr(sv_ip, "Фамилия", "LastName")
            if fam and not cp.name:
                im = _attr(sv_ip, "Имя", "FirstName")
                ot = _attr(sv_ip, "Отчество", "MiddleName")
                cp.name = f"ИП {fam} {im} {ot}".strip()

    # 3. Текстовые дочерние
    if not cp.name:
        cp.name = _text(_find(el, "Название", "Наименование", "Name"))
    if not cp.inn:
        cp.inn = _text(_find(el, "ИНН", "INN"))
    if not cp.kpp:
        cp.kpp = _text(_find(el, "КПП", "KPP"))

    # 4. Адрес
    addr_el = _find(el, "Адрес", "АдрРФ", "Address")
    if addr_el is not None:
        t = _text(addr_el)
        if t:
            cp.address = t
        else:
            parts = []
            for a in ["Индекс", "Регион", "Город", "Улица", "Дом", "Кварт"]:
                v = _attr(addr_el, a)
                if v:
                    parts.append(v)
            if parts:
                cp.address = ", ".join(parts)


# ─── Парсинг таблицы товаров ────────────────────────────────────


def _parse_items(table_el: etree._Element, result: ParsedDocument):
    """Парсинг таблицы товаров/услуг."""
    items_els = (
        _find_all(table_el, "СведТов") or
        _find_all(table_el, "Товар") or
        _find_all(table_el, "Строка") or
        _find_all(table_el, "Item") or
        _find_all(table_el, "Row")
    )
    for ie in items_els:
        item = ParsedDocumentItem()
        item.name = (
            _attr(ie, "НаимТов", "Наим", "Наименование", "Name") or
            _text(_find(ie, "Наименование", "НаимТов", "Name"))
        )
        item.unit = (
            _attr(ie, "ОКЕИ_Тов", "ЕдИзм", "Unit") or
            _text(_find(ie, "ЕдИзм", "Unit"))
        )
        item.quantity = _dec(
            _attr(ie, "КолТов", "Количество", "Кол", "Quantity") or
            _text(_find(ie, "Количество", "Quantity")),
            Decimal("1"),
        )
        item.price_without_vat = _dec(
            _attr(ie, "ЦенаТов", "Цена", "ЦенаБезНДС", "Price") or
            _text(_find(ie, "Цена", "ЦенаБезНДС", "Price"))
        )
        item.vat_rate = _vat_rate(
            _attr(ie, "НалСт", "СтавкаНДС", "VATRate") or
            _text(_find(ie, "СтавкаНДС", "НалСт", "VATRate"))
        )
        # Сумма НДС
        vat_str = (
            _attr(ie, "СумНал", "СумНДС", "VATAmount") or
            _text(_find(ie, "СумНДС", "СумНал", "VATAmount"))
        )
        if not vat_str:
            sn = _find(ie, "СумНал")
            if sn is not None:
                inner = _find(sn, "СумНал")
                vat_str = _text(inner) if inner is not None else _text(sn)
        item.vat_amount = _dec(vat_str)

        # Стоимость с НДС
        item.total_with_vat = _dec(
            _attr(ie, "СтТовУчНал", "СумСНДС", "ИтогоСНДС", "TotalWithVAT") or
            _text(_find(ie, "СумСНДС", "ИтогоСНДС", "TotalWithVAT"))
        )

        # Авторасчёт если не хватает данных
        if item.total_with_vat == 0:
            item.total_with_vat = item.total_without_vat + item.vat_amount
        if item.vat_amount == 0 and item.vat_rate > 0 and item.price_without_vat > 0:
            item.vat_amount = (
                item.total_without_vat * item.vat_rate / Decimal("100")
            ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            item.total_with_vat = item.total_without_vat + item.vat_amount

        if item.name or item.price_without_vat > 0:
            result.items.append(item)


def _calc_totals(result: ParsedDocument):
    """Расчёт итогов документа из позиций."""
    result.total_without_vat = sum(
        (i.total_without_vat for i in result.items), Decimal("0")
    ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    result.vat_amount = sum(
        (i.vat_amount for i in result.items), Decimal("0")
    ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    result.total_with_vat = sum(
        (i.total_with_vat for i in result.items), Decimal("0")
    ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if result.items:
        rates = [i.vat_rate for i in result.items if i.vat_rate > 0]
        if rates:
            result.vat_rate = max(set(rates), key=rates.count)


# ─── Валидация распарсенного документа ──────���────────────────────


def _validate_parsed_document(result: ParsedDocument):
    """Валидация результата парсинга: ИНН, КПП, суммы."""
    # Валидация ИНН продавца
    if result.seller.inn:
        ok, err = validate_inn(result.seller.inn)
        if not ok:
            result.warnings.append(f"ИНН продавца: {err}")

    # Валидация ИНН покупателя
    if result.buyer.inn:
        ok, err = validate_inn(result.buyer.inn)
        if not ok:
            result.warnings.append(f"ИНН покупателя: {err}")

    # Валидация КПП
    if result.seller.kpp:
        ok, err = validate_kpp(result.seller.kpp)
        if not ok:
            result.warnings.append(f"КПП продавца: {err}")
    if result.buyer.kpp:
        ok, err = validate_kpp(result.buyer.kpp)
        if not ok:
            result.warnings.append(f"КПП покупателя: {err}")

    # Проверка сумм
    if result.total_with_vat > 0 and result.total_without_vat > 0:
        ok, err = validate_amounts_consistency(
            result.total_without_vat, result.vat_amount, result.total_with_vat
        )
        if not ok:
            result.warnings.append(err)

    # Проверка обязательных полей
    if not result.doc_number:
        result.warnings.append("Номер документа не найден")
    if result.doc_date is None:
        result.warnings.append("Дата документа не найдена")
    if not result.seller.name and not result.seller.inn:
        result.warnings.append("Данные продавца не найдены")
    if not result.items:
        result.warnings.append("Позиции документа не найдены")


# ─── Публичные функции парсинга ──────────────────────────────────


def parse_xml_invoice(xml_content: bytes | str) -> ParsedDocument:
    """
    Парсинг счёта-фактуры в формате XML ФНС.
    
    Структура ФНС:
    <Файл>
      <Документ>
        <СвСчФакт НомерСчФ="123" ДатаСчФ="01.01.2026">
          <СвПрод>...</СвПрод>
          <СвПок>...</СвПок>
        </СвСчФакт>
        <ТаблСчФакт>
          <СведТов .../>
        </ТаблСчФакт>
      </Документ>
    </Файл>
    """
    result = ParsedDocument(doc_type=DocumentType.INVOICE, raw_xml_type="invoice")
    try:
        root = _parse_root(xml_content)
    except ValueError as e:
        result.errors.append(str(e))
        return result

    try:
        _parse_fns_invoice(root, result)
    except Exception as e:
        logger.exception(f"Ошибка парсинга счёт-фактуры: {e}")
        result.errors.append(f"Ошибка парсинга: {e}")

    _validate_parsed_document(result)
    return result


def parse_xml_upd(xml_content: bytes | str) -> ParsedDocument:
    """
    Парсинг УПД в формате XML ФНС.
    Функция: СЧФ (только СФ), СЧФДОП (СФ + первичный), ДОП (только первичный).
    """
    result = ParsedDocument(doc_type=DocumentType.UPD, raw_xml_type="upd")
    try:
        root = _parse_root(xml_content)
    except ValueError as e:
        result.errors.append(str(e))
        return result

    try:
        rt = _strip_ns(root.tag)
        doc_el = _find(root, "Документ", "Document")
        if doc_el is None and rt in ("Документ", "Document"):
            doc_el = root
        if doc_el is None:
            doc_el = root

        func = _attr(doc_el, "Функция", "Function")
        if func == "ДОП":
            result.doc_type = DocumentType.ACT
        elif func in ("СЧФ", "СЧФДОП"):
            result.doc_type = DocumentType.UPD

        _parse_fns_invoice(root, result)

        # Дата передачи (УПД-специфичная)
        sv_pered = _find(doc_el, "СвПередач", "TransferInfo")
        if sv_pered is not None and result.doc_date is None:
            dt = _attr(sv_pered, "ДатаПередач", "TransferDate")
            if dt:
                result.doc_date = _date(dt)
    except Exception as e:
        logger.exception(f"Ошибка парсинга УПД: {e}")
        result.errors.append(f"Ошибка парсинга: {e}")

    _validate_parsed_document(result)
    return result


def parse_xml_torg12(xml_content: bytes | str) -> ParsedDocument:
    """
    Парсинг товарной накладной ТОРГ-12 в формате XML ФНС.
    """
    result = ParsedDocument(doc_type=DocumentType.TORG12, raw_xml_type="torg12")
    try:
        root = _parse_root(xml_content)
    except ValueError as e:
        result.errors.append(str(e))
        return result

    try:
        _parse_fns_torg12(root, result)
    except Exception as e:
        logger.exception(f"Ошибка парсинга ТОРГ-12: {e}")
        result.errors.append(f"Ошибка парсинга: {e}")

    _validate_parsed_document(result)
    return result


def parse_xml_bank_statement(xml_content: bytes | str) -> ParsedBankStatement:
    """
    Парсинг банковской выписки в формате XML 1С.
    """
    result = ParsedBankStatement()
    try:
        root = _parse_root(xml_content)
    except ValueError as e:
        result.errors.append(str(e))
        return result

    try:
        _parse_1c_bank(root, result)
    except Exception as e:
        logger.exception(f"Ошибка парсинга банковской выписки: {e}")
        result.errors.append(f"Ошибка парсинга: {e}")

    return result


# ─── Маппинг результатов в модели БД ────────────────────────────


def map_parsed_document_to_dict(parsed: ParsedDocument) -> dict:
    """
    Маппинг ParsedDocument в словарь полей для создания Document + DocumentItem.
    Возвращает dict совместимый с DocumentCreate schema.
    """
    items = []
    for i, item in enumerate(parsed.items):
        items.append({
            "name": item.name or f"Позиция {i + 1}",
            "quantity": item.quantity,
            "unit": item.unit or None,
            "price_without_vat": item.price_without_vat,
            "vat_rate": item.vat_rate,
            "vat_amount": item.vat_amount,
            "total_with_vat": item.total_with_vat,
        })

    return {
        "doc_type": parsed.doc_type.value,
        "doc_number": parsed.doc_number or None,
        "doc_date": parsed.doc_date,
        "total_without_vat": parsed.total_without_vat,
        "vat_amount": parsed.vat_amount,
        "total_with_vat": parsed.total_with_vat,
        "vat_rate": parsed.vat_rate,
        "items": items,
        "seller": {
            "name": parsed.seller.name,
            "inn": parsed.seller.inn,
            "kpp": parsed.seller.kpp,
            "address": parsed.seller.address,
        },
        "buyer": {
            "name": parsed.buyer.name,
            "inn": parsed.buyer.inn,
            "kpp": parsed.buyer.kpp,
            "address": parsed.buyer.address,
        },
        "confidence_score": float(parsed.confidence_score),
        "warnings": parsed.warnings,
        "errors": parsed.errors,
    }


def map_parsed_bank_statement_to_dicts(parsed: ParsedBankStatement) -> list[dict]:
    """
    Маппинг ParsedBankStatement в список словарей для создания BankOperation.
    """
    operations = []
    for op in parsed.operations:
        operations.append({
            "operation_date": op.operation_date,
            "amount": op.amount,
            "is_income": op.is_income,
            "is_expense": op.is_expense,
            "counterparty_name": op.counterparty_name or None,
            "counterparty_inn": op.counterparty_inn or None,
            "purpose": op.purpose or None,
            "vat_amount": op.vat_amount,
            "category_hint": op.category_hint.value,
        })
    return operations


# ─── Внутренние функции парсинга документов ──────────────────────


def _parse_fns_invoice(root: etree._Element, result: ParsedDocument):
    """Парсинг СФ/УПД в формате ФНС XML."""
    rt = _strip_ns(root.tag)

    doc_el = _find(root, "Документ", "Document")
    if doc_el is None and rt in ("Документ", "Document"):
        doc_el = root
    if doc_el is None:
        doc_el = root

    # СвСчФакт
    sv = _find(doc_el, "СвСчФакт", "СчФакт", "InvoiceInfo")
    if sv is not None:
        result.doc_number = _attr(sv, "НомерСчФ", "НомСчФ", "Number")
        result.doc_date = _date(_attr(sv, "ДатаСчФ", "Дата", "Date"))

        prod = _find(sv, "СвПрод", "Продавец", "Seller")
        if prod is not None:
            _parse_counterparty(prod, result.seller)

        pok = _find(sv, "СвПок", "Покупатель", "Buyer")
        if pok is not None:
            _parse_counterparty(pok, result.buyer)
    else:
        result.warnings.append("Элемент СвСчФакт не найден")

    # Таблица товаров
    tabl = _find(doc_el, "ТаблСчФакт", "ТаблДок", "ItemsTable")
    if tabl is not None:
        _parse_items(tabl, result)
    else:
        result.warnings.append("Таблица товаров не найдена")

    # Итоги
    itog = _find(doc_el, "ВсегоОпл", "Итого", "Total")
    if itog is not None:
        v = _attr(itog, "СтТовБезНДСВсего", "СумБезНДС", "TotalWithoutVAT")
        if v:
            result.total_without_vat = _dec(v)
        v = _attr(itog, "СумНалВсего", "СумНДС", "VATAmount")
        if v:
            result.vat_amount = _dec(v)
        v = _attr(itog, "СтТовУчНалВсего", "Итого", "TotalWithVAT")
        if v:
            result.total_with_vat = _dec(v)

    if result.total_with_vat == 0 and result.items:
        _calc_totals(result)


def _parse_fns_torg12(root: etree._Element, result: ParsedDocument):
    """Парсинг ТОРГ-12 ФНС XML."""
    rt = _strip_ns(root.tag)

    doc_el = _find(root, "Документ", "Document")
    if doc_el is None and rt in ("Документ", "Document"):
        doc_el = root
    if doc_el is None:
        doc_el = root

    sv_tn = _find(doc_el, "СвТН", "СвСчФакт", "WaybillInfo")
    if sv_tn is not None:
        result.doc_number = _attr(sv_tn, "НомТН", "НомерСчФ", "Number")
        result.doc_date = _date(_attr(sv_tn, "ДатаТН", "ДатаСчФ", "Date"))

        prod = _find(sv_tn, "СвПрод", "Грузоотпр", "Seller", "Shipper")
        if prod is not None:
            _parse_counterparty(prod, result.seller)
        pok = _find(sv_tn, "СвПок", "Грузополуч", "Buyer", "Consignee")
        if pok is not None:
            _parse_counterparty(pok, result.buyer)
    else:
        # Fallback: пробуем как СФ
        _parse_fns_invoice(root, result)
        return

    tabl = _find(doc_el, "ТаблТН", "ТаблСчФакт", "ТаблДок", "ItemsTable")
    if tabl is not None:
        _parse_items(tabl, result)

    itog = _find(doc_el, "Итого", "ВсегоОпл", "Total")
    if itog is not None:
        result.total_without_vat = _dec(_attr(itog, "СтТовБезНДСВсего", "СумБезНДС"))
        result.vat_amount = _dec(_attr(itog, "СумНалВсего", "СумНДС"))
        result.total_with_vat = _dec(_attr(itog, "СтТовУчНалВсего", "Итого"))

    if result.total_with_vat == 0 and result.items:
        _calc_totals(result)


def _parse_1c_bank(root: etree._Element, result: ParsedBankStatement):
    """Парсинг банковской выписки 1С XML."""
    rt = _strip_ns(root.tag)

    stmt = root
    if rt in ("BankStatements", "Выписки"):
        stmt = _find(root, "BankStatement", "Выписка") or root

    # Реквизиты счёта
    result.account_number = (
        _attr(stmt, "НомерСчёта", "РасчСчёт", "AccountNumber") or
        _text(_find(stmt, "НомерСчёта", "РасчСчёт", "AccountNumber", "Счёт"))
    )

    bank_el = _find(stmt, "Банк", "Bank")
    if bank_el is not None:
        result.bank_name = (
            _attr(bank_el, "Наименование", "Name") or
            _text(_find(bank_el, "Наименование", "Name"))
        )
        result.bik = (
            _attr(bank_el, "БИК", "BIK") or
            _text(_find(bank_el, "БИК", "BIK"))
        )

    # Период
    result.period_start = _date(
        _attr(stmt, "ДатаНач", "DateFrom", "НачалоПериода") or
        _text(_find(stmt, "ДатаНач", "НачалоПериода", "DateFrom"))
    )
    result.period_end = _date(
        _attr(stmt, "ДатаКон", "DateTo", "КонецПериода") or
        _text(_find(stmt, "ДатаКон", "КонецПериода", "DateTo"))
    )

    # Начальный / конечный остаток
    result.opening_balance = _dec(
        _attr(stmt, "НачСальдо", "OpeningBalance") or
        _text(_find(stmt, "НачСальдо", "OpeningBalance"))
    )
    result.closing_balance = _dec(
        _attr(stmt, "КонСальдо", "ClosingBalance") or
        _text(_find(stmt, "КонСальдо", "ClosingBalance"))
    )

    # Операции
    op_els = (
        _find_all(stmt, "ПлатПоруч") or
        _find_all(stmt, "Операция") or
        _find_all(stmt, "PaymentOrder") or
        _find_all(stmt, "Operation") or
        _find_all(stmt, "Строка") or
        _find_all(stmt, "Row")
    )

    for oe in op_els:
        op = ParsedBankOperation()

        op.operation_date = _date(
            _attr(oe, "ДатаОперации", "Дата", "Date") or
            _text(_find(oe, "Дата", "ДатаОперации", "Date"))
        )

        # Суммы: проверяем дебет/кредит или общую сумму
        debit = _dec(
            _attr(oe, "СумДебет", "Дебет", "Debit") or
            _text(_find(oe, "Дебет", "СумДебет", "Debit"))
        )
        credit = _dec(
            _attr(oe, "СумКредит", "Кредит", "Credit") or
            _text(_find(oe, "Кредит", "СумКредит", "Credit"))
        )

        if debit > 0:
            op.amount = debit
            op.is_expense = True
        elif credit > 0:
            op.amount = credit
            op.is_income = True
        else:
            amount = _dec(
                _attr(oe, "Сумма", "Amount") or
                _text(_find(oe, "Сумма", "Amount"))
            )
            op.amount = amount
            # Определяем направление по доп. признакам
            direction = _attr(oe, "��идОперации", "Direction", "Тип")
            if direction.lower() in ("расход", "списание", "debit"):
                op.is_expense = True
            elif direction.lower() in ("приход", "зачисление", "credit"):
                op.is_income = True

        # Контрагент
        cp_el = _find(oe, "Контрагент", "Counterparty", "Получатель", "Плательщик")
        if cp_el is not None:
            op.counterparty_name = (
                _attr(cp_el, "Наименование", "Name", "Наим") or
                _text(_find(cp_el, "Наименование", "Name"))
            )
            op.counterparty_inn = (
                _attr(cp_el, "ИНН", "INN") or
                _text(_find(cp_el, "ИНН", "INN"))
            )
            op.counterparty_kpp = (
                _attr(cp_el, "КПП", "KPP") or
                _text(_find(cp_el, "КПП", "KPP"))
            )
            op.counterparty_account = (
                _attr(cp_el, "РасчСчёт", "Account", "НомерСчёта") or
                _text(_find(cp_el, "РасчСчёт", "Account", "НомерСчёта"))
            )
        else:
            # Плоская структура
            op.counterparty_name = (
                _attr(oe, "Контрагент", "Получатель", "Плательщик") or
                _text(_find(oe, "Контрагент", "Получатель", "Плательщик"))
            )
            op.counterparty_inn = (
                _attr(oe, "ИННКонтрагента", "ИНН") or
                _text(_find(oe, "ИННКонтрагента", "ИНН"))
            )

        # Назначение платежа
        op.purpose = (
            _attr(oe, "НазначениеПлатежа", "Purpose", "Назначение") or
            _text(_find(oe, "НазначениеПлатежа", "Purpose", "Назначение"))
        )

        # Номер / дата документа
        op.doc_number = (
            _attr(oe, "НомерДок", "DocNumber", "Номер") or
            _text(_find(oe, "НомерДок", "Номер"))
        )
        op.doc_date = _date(
            _attr(oe, "ДатаДок", "DocDate") or
            _text(_find(oe, "ДатаДок"))
        )

        # НДС из назначения платежа
        if op.purpose:
            op.vat_amount = _extract_vat_from_purpose(op.purpose)

        if op.amount > 0:
            result.operations.append(op)

    if not result.operations:
        result.warnings.append("Операции не найдены в выписке")
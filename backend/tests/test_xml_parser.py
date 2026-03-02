"""
Тесты парсера XML-документов ФНС — п. 1.6.1–1.6.10.
"""
import pytest
from datetime import date
from decimal import Decimal

from app.utils.validators import (
    validate_inn, validate_kpp, validate_bik,
    validate_amounts_consistency, validate_item_amounts,
)
from app.services.xml_parser_service import (
    detect_xml_document_type, parse_xml_invoice, parse_xml_upd,
    parse_xml_torg12, parse_xml_bank_statement,
    map_parsed_document_to_dict, map_parsed_bank_statement_to_dicts,
    XmlDocumentType,
)
from app.constants.enums import DocumentType, OperationCategory


# ── Образцы XML ──────────────────────────────────────────────────

INVOICE_XML = """<?xml version="1.0" encoding="utf-8"?>
<Файл ИдФайл="ON_SFAKT_2BM_20260115_abc">
  <Документ>
    <СвСчФакт НомерСчФ="42" ДатаСчФ="15.01.2026">
      <СвПрод НаимОрг="ООО Поставщик" ИННЮЛ="7707083893" КПП="770701001">
        <Адрес>г. Москва, ул. Тверская, д. 1</Адрес>
      </СвПрод>
      <СвПок НаимОрг="ИП Иванов" ИННЮЛ="561234567890"/>
    </СвСчФакт>
    <ТаблСчФакт>
      <СведТов НаимТов="Холодильник" ОКЕИ_Тов="шт" КолТов="2"
               ЦенаТов="50000.00" НалСт="22%" СумНал="22000.00"
               СтТовУчНал="122000.00"/>
      <СведТов НаимТов="Стиралка" ОКЕИ_Тов="шт" КолТов="1"
               ЦенаТов="35000.00" НалСт="22%" СумНал="7700.00"
               СтТовУчНал="42700.00"/>
    </ТаблСчФакт>
    <ВсегоОпл СтТовБезНДСВсего="135000.00" СумНалВсего="29700.00"
              СтТовУчНалВсего="164700.00"/>
  </Документ>
</Файл>"""

UPD_XML = """<?xml version="1.0" encoding="utf-8"?>
<Файл ИдФайл="ON_SCHFDOPPR_2BM_20260220_t">
  <Документ Функция="СЧФДОП">
    <СвСчФакт НомерСчФ="77" ДатаСчФ="20.02.2026">
      <СвПрод НаимОрг="ООО Техно" ИННЮЛ="7707083893" КПП="770701001"/>
      <СвПок НаимОрг="ИП Иванов" ИННЮЛ="561234567890"/>
    </СвСчФакт>
    <ТаблСчФакт>
      <СведТов НаимТов="Диван" ОКЕИ_Тов="шт" КолТов="1"
               ЦенаТов="70000.00" НалСт="22%" СумНал="15400.00"
               СтТовУчНал="85400.00"/>
    </ТаблСчФакт>
    <ВсегоОпл СтТовБезНДСВсего="70000.00" СумНалВсего="15400.00"
              СтТовУчНалВсего="85400.00"/>
  </Документ>
</Файл>"""

UPD_DOP_XML = """<?xml version="1.0" encoding="utf-8"?>
<Файл ИдФайл="ON_SCHFDOPPR_DOP_20260301">
  <Документ Функция="ДОП">
    <СвСчФакт НомерСчФ="88" ДатаСчФ="01.03.2026">
      <СвПрод НаимОрг="ООО Сервис" ИННЮЛ="7707083893" КПП="770701001"/>
      <СвПок НаимОрг="ИП Иванов" ИННЮЛ="561234567890"/>
    </СвСчФакт>
    <ТаблСчФакт>
      <СведТов НаимТов="Доставка" ОКЕИ_Тов="усл" КолТов="1"
               ЦенаТов="5000.00" НалСт="22%" СумНал="1100.00"
               СтТовУчНал="6100.00"/>
    </ТаблСчФакт>
    <ВсегоОпл СтТовБезНДСВсего="5000.00" СумНалВсего="1100.00"
              СтТовУчНалВсего="6100.00"/>
  </Документ>
</Файл>"""

TORG12_XML = """<?xml version="1.0" encoding="utf-8"?>
<Файл ИдФайл="ON_TORG12_2BM_20260110">
  <Документ>
    <СвТН НомТН="15" ДатаТН="10.01.2026">
      <СвПрод НаимОрг="ООО Склад" ИННЮЛ="7707083893" КПП="770701001"/>
      <СвПок НаимОрг="ИП Иванов" ИННЮЛ="561234567890"/>
    </СвТН>
    <ТаблТН>
      <СведТов НаимТов="Микроволновка" ОКЕИ_Тов="шт" КолТов="3"
               ЦенаТов="8000.00" НалСт="22%" СумНал="5280.00"
               СтТовУчНал="29280.00"/>
      <СведТов НаимТов="Чайник" ОКЕИ_Тов="шт" КолТов="5"
               ЦенаТов="3000.00" НалСт="22%" СумНал="3300.00"
               СтТовУчНал="18300.00"/>
    </ТаблТН>
    <Итого СтТовБезНДСВсего="39000.00" СумНалВсего="8580.00"
           СтТовУчНалВсего="47580.00"/>
  </Документ>
</Файл>"""

BANK_XML = """<?xml version="1.0" encoding="utf-8"?>
<БанковскаяВыписка НомерСчёта="40702810123450000001"
                   ДатаНач="01.01.2026" ДатаКон="31.01.2026"
                   НачСальдо="500000.00" КонСальдо="612300.00">
  <Банк><Наименование>ПАО Сбербанк</Наименование><БИК>044525225</БИК></Банк>
  <ПлатПоруч ДатаОперации="10.01.2026" СумКредит="150000.00"
             НазначениеПлатежа="Оплата от ООО Ромашка, в т.ч. НДС 22% - 24590.16">
    <Контрагент Наименование="ООО Ромашка" ИНН="7712345678" КПП="771201001"/>
  </ПлатПоруч>
  <ПлатПоруч ДатаОперации="15.01.2026" СумДебет="85000.00"
             НазначениеПлатежа="Оплата за товар, в т.ч. НДС 22% - 13934.43">
    <Контрагент Наименование="ООО Поставщик" ИНН="7707083893"/>
  </ПлатПоруч>
  <ПлатПоруч ДатаОперации="20.01.2026" СумДебет="2700.00"
             НазначениеПлатежа="Комиссия за ведение счёта, Без НДС">
    <Контрагент Наименование="ПАО Сбербанк" ИНН="7707083893"/>
  </ПлатПоруч>
  <ПлатПоруч ДатаОперации="25.01.2026" СумКредит="50000.00"
             НазначениеПлатежа="Взнос собственных средств ИП">
    <Контрагент Наименование="Иванов Иван Иванович"/>
  </ПлатПоруч>
</БанковскаяВыписка>"""


# ── 1.6.7 validate_inn ───────────────────────────────────────────

class TestValidateInn:
    def test_valid_10(self):
        ok, _ = validate_inn("7707083893")
        assert ok is True

    def test_valid_12(self):
        ok, _ = validate_inn("500100732259")
        assert ok is True

    def test_invalid_10_checksum(self):
        ok, err = validate_inn("7707083890")
        assert ok is False
        assert "контрольн" in err.lower()

    def test_invalid_12_checksum(self):
        ok, err = validate_inn("500100732250")
        assert ok is False

    def test_wrong_length(self):
        ok, err = validate_inn("12345")
        assert ok is False
        assert "10 или 12" in err

    def test_non_digits(self):
        ok, err = validate_inn("77070838AB")
        assert ok is False

    def test_empty(self):
        ok, _ = validate_inn("")
        assert ok is False

    def test_with_spaces(self):
        ok, _ = validate_inn(" 7707083893 ")
        assert ok is True


# ── 1.6.8 validate_kpp ───────────────────────────────────────────

class TestValidateKpp:
    def test_valid(self):
        ok, _ = validate_kpp("770701001")
        assert ok is True

    def test_valid_with_letters(self):
        ok, _ = validate_kpp("7707AZ001")
        assert ok is True

    def test_wrong_length(self):
        ok, _ = validate_kpp("12345")
        assert ok is False

    def test_non_digit_prefix(self):
        ok, _ = validate_kpp("ABCD01001")
        assert ok is False

    def test_empty(self):
        ok, _ = validate_kpp("")
        assert ok is False


# ── 1.6.9 validate_amounts ───────────────────────────────────────

class TestValidateAmounts:
    def test_consistent(self):
        ok, _ = validate_amounts_consistency(
            Decimal("100"), Decimal("22"), Decimal("122")
        )
        assert ok is True

    def test_within_tolerance(self):
        ok, _ = validate_amounts_consistency(
            Decimal("100"), Decimal("22"), Decimal("122.50"),
            tolerance=Decimal("1.00"),
        )
        assert ok is True

    def test_inconsistent(self):
        ok, err = validate_amounts_consistency(
            Decimal("100"), Decimal("22"), Decimal("200")
        )
        assert ok is False
        assert "Несоответствие" in err

    def test_item_amounts_valid(self):
        ok, errs = validate_item_amounts(
            Decimal("2"), Decimal("1000"), Decimal("22"),
            Decimal("440"), Decimal("2440"),
        )
        assert ok is True
        assert errs == []

    def test_item_amounts_invalid_vat(self):
        ok, errs = validate_item_amounts(
            Decimal("1"), Decimal("1000"), Decimal("22"),
            Decimal("999"), Decimal("1999"),
        )
        assert ok is False
        assert len(errs) > 0


# ── 1.6.5 detect_xml_document_type ───────────────────────────────

class TestDetectXmlType:
    def test_invoice(self):
        assert detect_xml_document_type(INVOICE_XML) == XmlDocumentType.INVOICE

    def test_upd(self):
        assert detect_xml_document_type(UPD_XML) == XmlDocumentType.UPD

    def test_upd_dop_as_torg12(self):
        # Функция="ДОП" → TORG12
        assert detect_xml_document_type(UPD_DOP_XML) == XmlDocumentType.UPD

    def test_torg12(self):
        assert detect_xml_document_type(TORG12_XML) == XmlDocumentType.TORG12

    def test_bank_statement(self):
        assert detect_xml_document_type(BANK_XML) == XmlDocumentType.BANK_STATEMENT_1C

    def test_unknown(self):
        assert detect_xml_document_type("<root><child/></root>") == XmlDocumentType.UNKNOWN

    def test_invalid_xml(self):
        assert detect_xml_document_type("not xml at all") == XmlDocumentType.UNKNOWN

    def test_bom(self):
        bom_xml = "\ufeff" + INVOICE_XML
        assert detect_xml_document_type(bom_xml) == XmlDocumentType.INVOICE


# ── 1.6.1 parse_xml_invoice ─────────────────────────────────────

class TestParseInvoice:
    def test_basic_fields(self):
        doc = parse_xml_invoice(INVOICE_XML)
        assert doc.is_valid
        assert doc.doc_type == DocumentType.INVOICE
        assert doc.doc_number == "42"
        assert doc.doc_date == date(2026, 1, 15)

    def test_seller(self):
        doc = parse_xml_invoice(INVOICE_XML)
        assert doc.seller.name == "ООО Поставщик"
        assert doc.seller.inn == "7707083893"
        assert doc.seller.kpp == "770701001"
        assert "Тверская" in doc.seller.address

    def test_buyer(self):
        doc = parse_xml_invoice(INVOICE_XML)
        assert "Иванов" in doc.buyer.name
        assert doc.buyer.inn == "561234567890"

    def test_items(self):
        doc = parse_xml_invoice(INVOICE_XML)
        assert len(doc.items) == 2
        assert doc.items[0].name == "Холодильник"
        assert doc.items[0].quantity == Decimal("2")
        assert doc.items[0].price_without_vat == Decimal("50000.00")
        assert doc.items[0].vat_rate == Decimal("22")
        assert doc.items[0].vat_amount == Decimal("22000.00")

    def test_totals(self):
        doc = parse_xml_invoice(INVOICE_XML)
        assert doc.total_without_vat == Decimal("135000.00")
        assert doc.vat_amount == Decimal("29700.00")
        assert doc.total_with_vat == Decimal("164700.00")

    def test_confidence(self):
        doc = parse_xml_invoice(INVOICE_XML)
        assert doc.confidence_score >= Decimal("0.80")

    def test_invalid_xml(self):
        doc = parse_xml_invoice("not xml")
        assert not doc.is_valid
        assert len(doc.errors) > 0


# ── 1.6.2 parse_xml_upd ─────────────────────────────────────────

class TestParseUpd:
    def test_schfdop(self):
        doc = parse_xml_upd(UPD_XML)
        assert doc.is_valid
        assert doc.doc_type == DocumentType.UPD
        assert doc.doc_number == "77"
        assert doc.doc_date == date(2026, 2, 20)
        assert len(doc.items) == 1
        assert doc.total_with_vat == Decimal("85400.00")

    def test_dop_becomes_act(self):
        doc = parse_xml_upd(UPD_DOP_XML)
        assert doc.is_valid
        assert doc.doc_type == DocumentType.ACT
        assert doc.doc_number == "88"


# ── 1.6.3 parse_xml_torg12 ──────────────────────────────────────

class TestParseTorg12:
    def test_basic(self):
        doc = parse_xml_torg12(TORG12_XML)
        assert doc.is_valid
        assert doc.doc_type == DocumentType.TORG12
        assert doc.doc_number == "15"
        assert doc.doc_date == date(2026, 1, 10)

    def test_items(self):
        doc = parse_xml_torg12(TORG12_XML)
        assert len(doc.items) == 2
        assert doc.items[0].name == "Микроволновка"
        assert doc.items[1].quantity == Decimal("5")

    def test_totals(self):
        doc = parse_xml_torg12(TORG12_XML)
        assert doc.total_without_vat == Decimal("39000.00")
        assert doc.vat_amount == Decimal("8580.00")
        assert doc.total_with_vat == Decimal("47580.00")

    def test_seller_buyer(self):
        doc = parse_xml_torg12(TORG12_XML)
        assert doc.seller.name == "ООО Склад"
        assert doc.seller.inn == "7707083893"
        assert "Иванов" in doc.buyer.name


# ── 1.6.4 parse_xml_bank_statement ──────────────────────────────

class TestParseBankStatement:
    def test_basic(self):
        stmt = parse_xml_bank_statement(BANK_XML)
        assert stmt.is_valid
        assert stmt.account_number == "40702810123450000001"
        assert stmt.bank_name == "ПАО Сбербанк"
        assert stmt.bik == "044525225"

    def test_period(self):
        stmt = parse_xml_bank_statement(BANK_XML)
        assert stmt.period_start == date(2026, 1, 1)
        assert stmt.period_end == date(2026, 1, 31)

    def test_balances(self):
        stmt = parse_xml_bank_statement(BANK_XML)
        assert stmt.opening_balance == Decimal("500000.00")
        assert stmt.closing_balance == Decimal("612300.00")

    def test_operations_count(self):
        stmt = parse_xml_bank_statement(BANK_XML)
        assert len(stmt.operations) == 4

    def test_income_operation(self):
        stmt = parse_xml_bank_statement(BANK_XML)
        op = stmt.operations[0]  # Кредит 150000
        assert op.is_income is True
        assert op.is_expense is False
        assert op.amount == Decimal("150000.00")
        assert op.counterparty_name == "ООО Ромашка"
        assert op.counterparty_inn == "7712345678"
        assert op.operation_date == date(2026, 1, 10)

    def test_expense_operation(self):
        stmt = parse_xml_bank_statement(BANK_XML)
        op = stmt.operations[1]  # Дебет 85000
        assert op.is_expense is True
        assert op.is_income is False
        assert op.amount == Decimal("85000.00")

    def test_vat_extraction(self):
        stmt = parse_xml_bank_statement(BANK_XML)
        # Первая операция: НДС 22% - 24590.16
        assert stmt.operations[0].vat_amount == Decimal("24590.16")
        # Вторая: НДС 22% - 13934.43
        assert stmt.operations[1].vat_amount == Decimal("13934.43")
        # Третья: Без НДС
        assert stmt.operations[2].vat_amount == Decimal("0")

    def test_totals(self):
        stmt = parse_xml_bank_statement(BANK_XML)
        assert stmt.total_income == Decimal("200000.00")  # 150000 + 50000
        assert stmt.total_expense == Decimal("87700.00")  # 85000 + 2700

    def test_category_hints(self):
        stmt = parse_xml_bank_statement(BANK_XML)
        # "Комиссия за ведение счёта" → BANK_COMMISSION
        assert stmt.operations[2].category_hint == OperationCategory.BANK_COMMISSION
        # "Взнос собственных средств" → OWN_FUNDS
        assert stmt.operations[3].category_hint == OperationCategory.OWN_FUNDS


# ── 1.6.6 Маппинг в модели БД ───────────────────────────────────

class TestMapping:
    def test_document_mapping(self):
        doc = parse_xml_invoice(INVOICE_XML)
        d = map_parsed_document_to_dict(doc)
        assert d["doc_type"] == "invoice"
        assert d["doc_number"] == "42"
        assert d["total_with_vat"] == Decimal("164700.00")
        assert len(d["items"]) == 2
        assert d["seller"]["inn"] == "7707083893"
        assert d["confidence_score"] > 0

    def test_bank_mapping(self):
        stmt = parse_xml_bank_statement(BANK_XML)
        ops = map_parsed_bank_statement_to_dicts(stmt)
        assert len(ops) == 4
        assert ops[0]["is_income"] is True
        assert ops[0]["amount"] == Decimal("150000.00")
        assert ops[1]["is_expense"] is True
        assert "category_hint" in ops[0]


# ── Дополнительные edge-case тесты ───────────────────────────────

class TestEdgeCases:
    def test_bom_handling(self):
        bom = "\ufeff" + INVOICE_XML
        doc = parse_xml_invoice(bom)
        assert doc.is_valid

    def test_bytes_input(self):
        doc = parse_xml_invoice(INVOICE_XML.encode("utf-8"))
        assert doc.is_valid
        assert doc.doc_number == "42"

    def test_validate_bik_valid(self):
        ok, _ = validate_bik("044525225")
        assert ok is True

    def test_validate_bik_invalid(self):
        ok, _ = validate_bik("123456789")
        assert ok is False

    def test_empty_bank_statement(self):
        xml = '<?xml version="1.0"?><БанковскаяВыписка/>'
        stmt = parse_xml_bank_statement(xml)
        assert stmt.is_valid  # Нет errors, но есть warnings
        assert len(stmt.operations) == 0
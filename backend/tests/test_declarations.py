"""
Тесты для модуля деклараций (пункт 1.13).

Покрывает:
- DeclarationGeneratorService: генерация XML, XSD-валидация, контрольные соотношения
- API эндпоинты: /api/v1/declarations/
- Все 4 типа деклараций: УСН, НДС, 6-НДФЛ, РСВ
"""

import json
from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.constants.enums import (
    CalculationStatus,
    DeclarationStatus,
    DeclarationType,
    PeriodType,
    TaxType,
)
from app.models.tax_calculation import TaxCalculation
from app.models.tax_declaration import TaxDeclaration
from app.services.declaration_generator_service import (
    ControlRatioError,
    ControlRatiosResult,
    DeclarationGeneratorService,
    UsnXmlGenerator,
    VatXmlGenerator,
    Ndfl6XmlGenerator,
    RsvXmlGenerator,
    XsdValidationResult,
)


# ═══════════════════════════════════════════════════════════════
# Фикстуры
# ═══════════════════════════════════════════════════════════════


@pytest.fixture
def mock_user():
    """Мок пользователя."""
    user = MagicMock()
    user.id = "test-user-id"
    user.inn = "123456789012"
    user.full_name = "Иванов Иван Иванович"
    user.business_name = "ИП Иванов"
    user.is_active = True
    return user


@pytest.fixture
def mock_usn_calculation():
    """Мок расчёта УСН."""
    calc = MagicMock(spec=TaxCalculation)
    calc.id = "calc-usn-001"
    calc.user_id = "test-user-id"
    calc.tax_type = TaxType.USN
    calc.income_total = Decimal("5000000.00")
    calc.expense_total = Decimal("3000000.00")
    calc.tax_base = Decimal("2000000.00")
    calc.tax_rate = Decimal("15.00")
    calc.tax_amount = Decimal("300000.00")
    calc.min_tax_amount = Decimal("50000.00")
    calc.insurance_deduction = Decimal("53658.00")
    calc.vat_charged = Decimal("0")
    calc.vat_deductible = Decimal("0")
    calc.vat_payable = Decimal("0")
    calc.details_json = {
        "quarters": {
            "1": {"income": "1200000", "expense": "700000"},
            "2": {"income": "1300000", "expense": "800000"},
            "3": {"income": "1300000", "expense": "750000"},
            "4": {"income": "1200000", "expense": "750000"},
        }
    }
    calc.updated_at = None
    return calc


@pytest.fixture
def mock_vat_calculation():
    """Мок расчёта НДС."""
    calc = MagicMock(spec=TaxCalculation)
    calc.id = "calc-vat-001"
    calc.user_id = "test-user-id"
    calc.tax_type = TaxType.VAT
    calc.income_total = Decimal("6100000.00")
    calc.expense_total = Decimal("0")
    calc.tax_base = Decimal("6100000.00")
    calc.tax_rate = Decimal("22.00")
    calc.tax_amount = Decimal("1342000.00")
    calc.min_tax_amount = Decimal("0")
    calc.insurance_deduction = Decimal("0")
    calc.vat_charged = Decimal("1342000.00")
    calc.vat_deductible = Decimal("880000.00")
    calc.vat_payable = Decimal("462000.00")
    calc.details_json = {
        "monthly_payments": ["154000.00", "154000.00", "154000.00"],
    }
    calc.updated_at = None
    return calc


@pytest.fixture
def mock_ndfl_calculation():
    """Мок расчёта НДФЛ."""
    calc = MagicMock(spec=TaxCalculation)
    calc.id = "calc-ndfl-001"
    calc.user_id = "test-user-id"
    calc.tax_type = TaxType.NDFL
    calc.income_total = Decimal("1500000.00")
    calc.expense_total = Decimal("0")
    calc.tax_base = Decimal("1500000.00")
    calc.tax_rate = Decimal("13.00")
    calc.tax_amount = Decimal("195000.00")
    calc.min_tax_amount = Decimal("0")
    calc.insurance_deduction = Decimal("0")
    calc.vat_charged = Decimal("0")
    calc.vat_deductible = Decimal("0")
    calc.vat_payable = Decimal("0")
    calc.details_json = {}
    calc.updated_at = None
    return calc


# ═══════════════════════════════════════════════════════════════
# Тесты XML-генераторов
# ═══════════════════════════════════════════════════════════════


class TestUsnXmlGenerator:
    """Тесты генератора XML декларации УСН."""

    def test_generate_with_calculation(self, mock_user, mock_usn_calculation):
        """Генерация XML УСН с данными расчёта."""
        xml = UsnXmlGenerator.generate(mock_user, 2026, mock_usn_calculation)

        assert '<?xml version="1.0" encoding="UTF-8"?>' in xml
        assert "1152017" in xml  # КНД
        assert "2026" in xml
        assert "5000000" in xml  # income
        assert "3000000" in xml  # expense
        assert "2000000" in xml  # tax_base
        assert "300000" in xml   # tax_amount
        assert "123456789012" in xml  # ИНН

    def test_generate_without_calculation(self, mock_user):
        """Генерация пустой XML УСН (без расчёта)."""
        xml = UsnXmlGenerator.generate(mock_user, 2026, None)

        assert '<?xml version="1.0" encoding="UTF-8"?>' in xml
        assert "1152017" in xml
        assert "<Файл" in xml
        assert "<Документ" in xml

    def test_generate_contains_quarters(self, mock_user, mock_usn_calculation):
        """XML содержит поквартальные данные."""
        xml = UsnXmlGenerator.generate(mock_user, 2026, mock_usn_calculation)

        assert "Показ_К1" in xml
        assert "Показ_К2" in xml
        assert "Показ_К3" in xml
        assert "Показ_К4" in xml


class TestVatXmlGenerator:
    """Тесты генератора XML декларации НДС."""

    def test_generate_with_calculation(self, mock_user, mock_vat_calculation):
        """Генерация XML НДС с данными расчёта."""
        xml = VatXmlGenerator.generate(mock_user, 2026, 1, mock_vat_calculation)

        assert '<?xml version="1.0" encoding="UTF-8"?>' in xml
        assert "1151001" in xml  # КНД
        assert "1342000" in xml  # НДС начисленный
        assert "880000" in xml   # НДС вычет
        assert "462000" in xml   # НДС к уплате

    def test_generate_without_calculation(self, mock_user):
        """Генерация пустой XML НДС."""
        xml = VatXmlGenerator.generate(mock_user, 2026, 2, None)

        assert "1151001" in xml
        assert "НДСНачисл" in xml

    def test_quarter_period_code(self, mock_user, mock_vat_calculation):
        """Проверка кода периода для квартала."""
        xml = VatXmlGenerator.generate(mock_user, 2026, 3, mock_vat_calculation)
        assert '"23"' in xml  # Код 3 квартала


class TestNdfl6XmlGenerator:
    """Тесты генератора XML 6-НДФЛ."""

    def test_generate_with_calculation(self, mock_user, mock_ndfl_calculation):
        """Генерация XML 6-НДФЛ с данными."""
        xml = Ndfl6XmlGenerator.generate(mock_user, 2026, 1, mock_ndfl_calculation)

        assert "1151100" in xml
        assert "1500000" in xml  # доход
        assert "195000" in xml   # НДФЛ

    def test_generate_annual(self, mock_user, mock_ndfl_calculation):
        """Годовая декларация 6-НДФЛ."""
        xml = Ndfl6XmlGenerator.generate(mock_user, 2026, None, mock_ndfl_calculation)

        assert '"34"' in xml  # Код годового периода


class TestRsvXmlGenerator:
    """Тесты генератора XML РСВ."""

    def test_generate_without_calculation(self, mock_user):
        """Генерация пустой XML РСВ."""
        xml = RsvXmlGenerator.generate(mock_user, 2026, 1, None)

        assert "1151111" in xml
        assert "БазаВзносов" in xml


# ═══════════════════════════════════════════════════════════════
# Тесты XSD-валидации
# ═══════════════════════════════════════════════════════════════


class TestXsdValidation:
    """Тесты XSD-валидации."""

    def test_valid_usn_xml(self, mock_user, mock_usn_calculation):
        """Валидный XML УСН проходит проверку."""
        xml = UsnXmlGenerator.generate(mock_user, 2026, mock_usn_calculation)

        # Создаём сервис с моком
        service = DeclarationGeneratorService.__new__(DeclarationGeneratorService)
        result = service._validate_xsd(xml, DeclarationType.USN)

        assert result.valid is True
        assert len(result.errors) == 0

    def test_empty_xml_fails(self):
        """Пустой XML не проходит проверку."""
        service = DeclarationGeneratorService.__new__(DeclarationGeneratorService)
        result = service._validate_xsd("", DeclarationType.USN)

        assert result.valid is False
        assert len(result.errors) > 0

    def test_wrong_knd_fails(self):
        """XML с неправильным КНД не проходит."""
        xml = '<?xml version="1.0"?><Файл><Документ КНД="9999999"/></Файл>'
        service = DeclarationGeneratorService.__new__(DeclarationGeneratorService)
        result = service._validate_xsd(xml, DeclarationType.USN)

        assert result.valid is False
        assert any("КНД" in e for e in result.errors)


# ═══════════════════════════════════════════════════════════════
# Тесты контрольных соотношений
# ═══════════════════════════════════════════════════════════════


class TestControlRatios:
    """Тесты контрольных соотношений ФНС."""

    def _make_service(self):
        service = DeclarationGeneratorService.__new__(DeclarationGeneratorService)
        return service

    def test_usn_valid(self, mock_usn_calculation):
        """Корректный расчёт УСН проходит КС."""
        service = self._make_service()
        result = service._check_usn_control_ratios(mock_usn_calculation)

        assert result.valid is True
        assert len(result.errors) == 0

    def test_usn_wrong_tax_base(self, mock_usn_calculation):
        """Неверная налоговая база не проходит КС."""
        mock_usn_calculation.tax_base = Decimal("999999.00")  # Wrong

        service = self._make_service()
        result = service._check_usn_control_ratios(mock_usn_calculation)

        assert result.valid is False
        assert any(e.code == "USN.1" for e in result.errors)

    def test_usn_wrong_tax_amount(self, mock_usn_calculation):
        """Неверная сумма налога не проходит КС."""
        mock_usn_calculation.tax_amount = Decimal("111111.00")  # Wrong

        service = self._make_service()
        result = service._check_usn_control_ratios(mock_usn_calculation)

        assert result.valid is False
        assert any(e.code == "USN.2" for e in result.errors)

    def test_usn_no_calculation_warns(self):
        """Без расчёта — предупреждение."""
        service = self._make_service()
        result = service._check_usn_control_ratios(None)

        assert result.valid is True  # warnings don't affect validity
        assert len(result.warnings) > 0

    def test_vat_valid(self, mock_vat_calculation):
        """Корректный расчёт НДС проходит КС."""
        service = self._make_service()
        result = service._check_vat_control_ratios(mock_vat_calculation)

        assert result.valid is True
        assert len(result.errors) == 0

    def test_vat_wrong_payable(self, mock_vat_calculation):
        """Неверная сумма НДС к уплате."""
        mock_vat_calculation.vat_payable = Decimal("999999.00")  # Wrong

        service = self._make_service()
        result = service._check_vat_control_ratios(mock_vat_calculation)

        assert result.valid is False
        assert any(e.code == "VAT.1" for e in result.errors)

    def test_vat_high_deduction_warns(self, mock_vat_calculation):
        """Высокая доля вычетов НДС (>89%) — предупреждение."""
        # Вычеты = 95% от начисленного
        mock_vat_calculation.vat_charged = Decimal("1000000.00")
        mock_vat_calculation.vat_deductible = Decimal("950000.00")
        mock_vat_calculation.vat_payable = Decimal("50000.00")

        service = self._make_service()
        result = service._check_vat_control_ratios(mock_vat_calculation)

        assert result.valid is True  # Это warning, не error
        assert any(w.code == "VAT.2" for w in result.warnings)

    def test_vat_negative_payable_warns(self, mock_vat_calculation):
        """НДС к возмещению — предупреждение."""
        mock_vat_calculation.vat_charged = Decimal("100000.00")
        mock_vat_calculation.vat_deductible = Decimal("200000.00")
        mock_vat_calculation.vat_payable = Decimal("-100000.00")

        service = self._make_service()
        result = service._check_vat_control_ratios(mock_vat_calculation)

        assert any(w.code == "VAT.3" for w in result.warnings)

    def test_ndfl6_tax_exceeds_income(self, mock_ndfl_calculation):
        """НДФЛ превышает доход — ошибка КС."""
        mock_ndfl_calculation.tax_amount = Decimal("2000000.00")  # > income
        mock_ndfl_calculation.income_total = Decimal("1500000.00")

        service = self._make_service()
        result = service._check_ndfl6_control_ratios(mock_ndfl_calculation)

        assert result.valid is False
        assert any(e.code == "NDFL6.1" for e in result.errors)

    def test_rsv_negative_amount(self):
        """Отрицательные взносы — ошибка КС."""
        calc = MagicMock()
        calc.tax_amount = Decimal("-100.00")
        calc.tax_base = Decimal("500000.00")

        service = self._make_service()
        result = service._check_rsv_control_ratios(calc)

        assert result.valid is False
        assert any(e.code == "RSV.1" for e in result.errors)


# ═══════════════════════════════════════════════════════════════
# Тесты вспомогательных методов
# ═══════════════════════════════════════════════════════════════


class TestHelpers:
    """Тесты вспомогательных методов."""

    def test_build_period_string_quarter(self):
        assert DeclarationGeneratorService._build_period_string(2026, 1) == "2026-Q1"
        assert DeclarationGeneratorService._build_period_string(2026, 4) == "2026-Q4"

    def test_build_period_string_year(self):
        assert DeclarationGeneratorService._build_period_string(2026, None) == "2026"

    def test_extract_quarter(self):
        assert DeclarationGeneratorService._extract_quarter_from_period("2026-Q1") == 1
        assert DeclarationGeneratorService._extract_quarter_from_period("2026-Q4") == 4

    def test_extract_quarter_none(self):
        assert DeclarationGeneratorService._extract_quarter_from_period("2026") is None


# ═══════════════════════════════════════════════════════════════
# Тесты API эндпоинтов
# ═══════════════════════════════════════════════════════════════


@pytest.fixture
def auth_headers():
    """Заголовки авторизации для тестов API."""
    return {"Authorization": "Bearer test-token"}


class TestDeclarationsAPI:
    """Тесты API эндпоинтов деклараций.

    Примечание: для полных интеграционных тестов нужна БД.
    Здесь тестируем только логику сервиса через unit-тесты.
    """

    def test_declaration_generate_request_schema(self):
        """Проверка схемы запроса генерации."""
        from app.schemas.declaration import DeclarationGenerateRequest

        req = DeclarationGenerateRequest(
            declaration_type=DeclarationType.USN,
            year=2026,
            quarter=None,
        )
        assert req.declaration_type == DeclarationType.USN
        assert req.year == 2026
        assert req.quarter is None

    def test_declaration_generate_request_with_quarter(self):
        """Запрос с квартером."""
        from app.schemas.declaration import DeclarationGenerateRequest

        req = DeclarationGenerateRequest(
            declaration_type=DeclarationType.VAT,
            year=2026,
            quarter=3,
        )
        assert req.quarter == 3

    def test_declaration_response_schema(self):
        """Проверка схемы ответа."""
        from app.schemas.declaration import DeclarationGenerateResponse

        resp = DeclarationGenerateResponse(
            declaration_id="test-id",
            declaration_type="usn",
            period="2026",
            year=2026,
            status="validated",
            xsd_valid=True,
            xsd_errors=[],
            control_ratios_valid=True,
            control_ratios_errors=[],
            warnings=[],
        )
        assert resp.declaration_id == "test-id"
        assert resp.xsd_valid is True

    def test_declaration_validate_response_schema(self):
        """Проверка схемы ответа валидации."""
        from app.schemas.declaration import (
            ControlRatioErrorResponse,
            DeclarationValidateResponse,
        )

        resp = DeclarationValidateResponse(
            declaration_id="test-id",
            status="validation_error",
            xsd_valid=True,
            xsd_errors=[],
            control_ratios_valid=False,
            control_ratios_errors=[
                ControlRatioErrorResponse(
                    code="USN.1",
                    description="Налоговая база ≠ Доходы − Расходы",
                    expected="2000000",
                    actual="1999999",
                    severity="error",
                )
            ],
        )
        assert resp.control_ratios_valid is False
        assert len(resp.control_ratios_errors) == 1

    def test_declaration_xml_response_schema(self):
        """Проверка схемы XML-ответа."""
        from app.schemas.declaration import DeclarationXmlResponse

        resp = DeclarationXmlResponse(
            id="test-id",
            declaration_type=DeclarationType.VAT,
            period="2026-Q1",
            year=2026,
            status=DeclarationStatus.VALIDATED,
            xml_content='<?xml version="1.0"?><Файл/>',
        )
        assert "xml" in resp.xml_content
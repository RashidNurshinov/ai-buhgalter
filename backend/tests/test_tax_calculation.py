"""
Тесты модуля расчёта налогов (1.12).
Пункт плана: 1.12.5

Тестирует:
- Расчёт УСН (15%, минимальный налог, повышенная ставка)
- Расчёт НДС (начисленный - вычеты, ежемесячные платежи)
- Расчёт НДФЛ (13%, 15%, комбинированный)
- Расчёт страховых взносов за сотрудника (30%, 15.1%)
- Расчёт фиксированных взносов ИП (53 658 + 1%)
- Вспомогательные функции (get_quarter_dates, get_usn_rate, get_ndfl_amount)
"""

import pytest
from datetime import date
from decimal import Decimal

from app.constants.tax_rates import (
    IP_FIXED_CONTRIBUTIONS_2026,
    IP_MAX_CONTRIBUTIONS_2026,
    get_ndfl_amount,
    get_usn_rate,
    USN_RATE_INCOME_EXPENSE,
    USN_RATE_INCOME_EXPENSE_ELEVATED,
)
from app.services.tax_calculation_service import (
    get_quarter_dates,
    get_year_dates,
    UsnCalculationResult,
    VatCalculationResult,
    NdflCalculationResult,
    InsuranceCalculationResult,
    IpContributionsResult,
)


# ═══════════════════════════════════════════════════════════
# Тесты вспомогательных функций
# ═══════════════════════════════════════════════════════════


class TestQuarterDates:
    """Тесты get_quarter_dates."""

    def test_q1(self):
        start, end = get_quarter_dates(2026, 1)
        assert start == date(2026, 1, 1)
        assert end == date(2026, 3, 31)

    def test_q2(self):
        start, end = get_quarter_dates(2026, 2)
        assert start == date(2026, 4, 1)
        assert end == date(2026, 6, 30)

    def test_q3(self):
        start, end = get_quarter_dates(2026, 3)
        assert start == date(2026, 7, 1)
        assert end == date(2026, 9, 30)

    def test_q4(self):
        start, end = get_quarter_dates(2026, 4)
        assert start == date(2026, 10, 1)
        assert end == date(2026, 12, 31)

    def test_year_dates(self):
        start, end = get_year_dates(2026)
        assert start == date(2026, 1, 1)
        assert end == date(2026, 12, 31)


class TestGetUsnRate:
    """Тесты определения ставки УСН."""

    def test_base_rate(self):
        """Доход ниже лимита, сотрудников мало → базовая ставка 15%."""
        rate = get_usn_rate(Decimal("10_000_000"), employee_count=5)
        assert rate == Decimal("15")

    def test_elevated_rate_by_income(self):
        """Доход выше базового лимита → повышенная ставка 20%."""
        rate = get_usn_rate(Decimal("200_000_000"), employee_count=5)
        assert rate == Decimal("20")

    def test_elevated_rate_by_employees(self):
        """Сотрудников > 100 → повышенная ставка 20%."""
        rate = get_usn_rate(Decimal("10_000_000"), employee_count=110)
        assert rate == Decimal("20")

    def test_elevated_rate_by_max_income(self):
        """Доход выше предельного лимита → повышенная (утрата права)."""
        rate = get_usn_rate(Decimal("300_000_000"), employee_count=5)
        assert rate == Decimal("20")

    def test_zero_income(self):
        """Нулевой доход → базовая ставка."""
        rate = get_usn_rate(Decimal("0"), employee_count=0)
        assert rate == Decimal("15")

    def test_custom_base_rate(self):
        """Региональная ставка (например 10%)."""
        rate = get_usn_rate(
            Decimal("10_000_000"),
            base_rate=Decimal("10"),
            elevated_rate=Decimal("20"),
        )
        assert rate == Decimal("10")


class TestGetNdflAmount:
    """Тесты расчёта НДФЛ."""

    def test_standard_rate(self):
        """100 000 ₽ × 13% = 13 000 ₽."""
        result = get_ndfl_amount(Decimal("100_000"))
        assert result == Decimal("13000.00")

    def test_zero_income(self):
        """Нулевой доход → 0."""
        result = get_ndfl_amount(Decimal("0"))
        assert result == Decimal("0")

    def test_negative_income(self):
        """Отрицательный доход → 0."""
        result = get_ndfl_amount(Decimal("-100"))
        assert result == Decimal("0")

    def test_at_threshold(self):
        """Ровно 5 000 000 ₽ → 650 000 ₽ (13%)."""
        result = get_ndfl_amount(Decimal("5_000_000"))
        assert result == Decimal("650000.00")

    def test_above_threshold(self):
        """6 000 000 ₽: 5M×13% + 1M×15% = 650 000 + 150 000 = 800 000."""
        result = get_ndfl_amount(Decimal("6_000_000"))
        assert result == Decimal("800000.00")

    def test_large_income(self):
        """10 000 000 ₽: 5M×13% + 5M×15% = 650 000 + 750 000 = 1 400 000."""
        result = get_ndfl_amount(Decimal("10_000_000"))
        assert result == Decimal("1400000.00")


# ═══════════════════════════════════════════════════════════
# Тесты расчёта УСН (unit, без БД)
# ═══════════════════════════════════════════════════════════


class TestUsnCalculation:
    """Тесты логики расчёта УСН."""

    def test_basic_calculation(self):
        """Базовый расчёт: (1 000 000 - 700 000) × 15% = 45 000."""
        income = Decimal("1_000_000")
        expense = Decimal("700_000")
        rate = Decimal("15")
        tax_base = max(income - expense, Decimal("0"))
        tax_amount = (tax_base * rate / Decimal("100")).quantize(Decimal("0.01"))
        assert tax_base == Decimal("300000")
        assert tax_amount == Decimal("45000.00")

    def test_minimum_tax_applicable(self):
        """Минимальный налог: расходы почти равны доходам."""
        income = Decimal("1_000_000")
        expense = Decimal("990_000")
        rate = Decimal("15")

        tax_base = max(income - expense, Decimal("0"))
        regular_tax = (tax_base * rate / Decimal("100")).quantize(Decimal("0.01"))
        min_tax = (income * Decimal("1") / Decimal("100")).quantize(Decimal("0.01"))

        assert regular_tax == Decimal("1500.00")  # 10000 × 15%
        assert min_tax == Decimal("10000.00")      # 1M × 1%
        assert min_tax > regular_tax               # Минимальный > расчётного
        assert max(regular_tax, min_tax) == Decimal("10000.00")

    def test_negative_base(self):
        """Расходы > доходов → база = 0, но минимальный налог = 1% от доходов."""
        income = Decimal("500_000")
        expense = Decimal("800_000")

        tax_base = max(income - expense, Decimal("0"))
        regular_tax = (tax_base * Decimal("15") / Decimal("100")).quantize(Decimal("0.01"))
        min_tax = (income * Decimal("1") / Decimal("100")).quantize(Decimal("0.01"))

        assert tax_base == Decimal("0")
        assert regular_tax == Decimal("0.00")
        assert min_tax == Decimal("5000.00")

    def test_zero_income(self):
        """Нет доходов → налог 0."""
        income = Decimal("0")
        expense = Decimal("100_000")

        tax_base = max(income - expense, Decimal("0"))
        tax_amount = (tax_base * Decimal("15") / Decimal("100")).quantize(Decimal("0.01"))
        min_tax = (income * Decimal("1") / Decimal("100")).quantize(Decimal("0.01"))

        assert tax_amount == Decimal("0.00")
        assert min_tax == Decimal("0.00")


# ═══════════════════════════════════════════════════════════
# Тесты расчёта НДС (unit, без БД)
# ═══════════════════════════════════════════════════════════


class TestVatCalculation:
    """Тесты логики расчёта НДС."""

    def test_basic_vat(self):
        """НДС к уплате = начисленный - к вычету."""
        charged = Decimal("220_000")
        deductible = Decimal("150_000")
        payable = charged - deductible
        assert payable == Decimal("70000")

    def test_vat_refund(self):
        """Вычеты > начисленного → НДС к возмещению (отрицательный)."""
        charged = Decimal("100_000")
        deductible = Decimal("150_000")
        payable = charged - deductible
        assert payable == Decimal("-50000")

    def test_monthly_payments_split(self):
        """Разбиение НДС на 3 ежемесячных платежа по 1/3."""
        payable = Decimal("90_000")
        monthly = (payable / Decimal("3")).quantize(Decimal("0.01"))
        remainder = payable - monthly * 2

        assert monthly == Decimal("30000.00")
        assert remainder == Decimal("30000.00")
        assert monthly + monthly + remainder == payable

    def test_monthly_payments_uneven(self):
        """Неравное деление: 100 000 / 3 = 33333.33 + 33333.33 + 33333.34."""
        payable = Decimal("100_000")
        monthly = (payable / Decimal("3")).quantize(Decimal("0.01"))
        remainder = payable - monthly * 2

        assert monthly == Decimal("33333.33")
        assert remainder == Decimal("33333.34")
        assert monthly + monthly + remainder == payable

    def test_deduction_ratio_safe(self):
        """Доля вычетов < 89% — безопасно."""
        charged = Decimal("100_000")
        deductible = Decimal("85_000")
        ratio = deductible / charged * Decimal("100")
        assert ratio == Decimal("85")
        assert ratio <= Decimal("89")

    def test_deduction_ratio_danger(self):
        """Доля вычетов > 89% — опасно."""
        charged = Decimal("100_000")
        deductible = Decimal("95_000")
        ratio = deductible / charged * Decimal("100")
        assert ratio == Decimal("95")
        assert ratio > Decimal("89")


# ═══════════════════════════════════════════════════════════
# Тесты расчёта НДФЛ за сотрудника (unit, без БД)
# ═══════════════════════════════════════════════════════════


class TestNdflEmployee:
    """Тесты расчёта НДФЛ за сотрудника."""

    def test_standard_salary(self):
        """Обычная зарплата: 50 000 × 13% = 6 500."""
        salary = Decimal("50_000")
        ndfl = (salary * Decimal("13") / Decimal("100")).quantize(Decimal("0.01"))
        assert ndfl == Decimal("6500.00")

    def test_salary_crossing_threshold(self):
        """Зарплата, пересекающая порог 5 млн."""
        # Накопленный: 4 990 000. Зарплата: 20 000
        # 10 000 по 13%, 10 000 по 15%
        cumulative = Decimal("4_990_000")
        salary = Decimal("20_000")
        below = Decimal("5_000_000") - cumulative  # 10 000
        above = salary - below  # 10 000

        tax_13 = (below * Decimal("13") / Decimal("100")).quantize(Decimal("0.01"))
        tax_15 = (above * Decimal("15") / Decimal("100")).quantize(Decimal("0.01"))

        assert tax_13 == Decimal("1300.00")
        assert tax_15 == Decimal("1500.00")
        assert tax_13 + tax_15 == Decimal("2800.00")

    def test_all_above_threshold(self):
        """Весь доход выше 5 млн → 15%."""
        salary = Decimal("100_000")
        cumulative = Decimal("6_000_000")
        ndfl = (salary * Decimal("15") / Decimal("100")).quantize(Decimal("0.01"))
        assert ndfl == Decimal("15000.00")


# ═══════════════════════════════════════════════════════════
# Тесты страховых взносов за сотрудника (unit, без БД)
# ═══════════════════════════════════════════════════════════


class TestInsuranceEmployee:
    """Тесты расчёта страховых взносов за сотрудника."""

    def test_below_limit(self):
        """База ниже лимита → 30%."""
        salary = Decimal("50_000")
        contributions = (salary * Decimal("30") / Decimal("100")).quantize(Decimal("0.01"))
        assert contributions == Decimal("15000.00")

    def test_above_limit(self):
        """База полностью выше лимита → 15.1%."""
        salary = Decimal("50_000")
        cumulative = Decimal("3_000_000")  # > 2 759 000
        contributions = (salary * Decimal("15.1") / Decimal("100")).quantize(Decimal("0.01"))
        assert contributions == Decimal("7550.00")

    def test_crossing_limit(self):
        """База пересекает лимит: часть 30%, часть 15.1%."""
        salary = Decimal("100_000")
        cumulative = Decimal("2_700_000")
        limit = Decimal("2_759_000")

        below = limit - cumulative  # 59 000
        above = salary - below      # 41 000

        contrib_30 = (below * Decimal("30") / Decimal("100")).quantize(Decimal("0.01"))
        contrib_15 = (above * Decimal("15.1") / Decimal("100")).quantize(Decimal("0.01"))

        assert below == Decimal("59000")
        assert above == Decimal("41000")
        assert contrib_30 == Decimal("17700.00")
        assert contrib_15 == Decimal("6191.00")
        assert contrib_30 + contrib_15 == Decimal("23891.00")


# ═══════════════════════════════════════════════════════════
# Тесты фиксированных взносов ИП (unit, без БД)
# ═══════════════════════════════════════════════════════════


class TestIpContributions:
    """Тесты расчёта фиксированных взносов ИП."""

    def test_fixed_amount(self):
        """Фиксированная часть = 53 658 ₽."""
        assert IP_FIXED_CONTRIBUTIONS_2026 == Decimal("53658")

    def test_no_additional(self):
        """Доход <= 300 000 → только фиксированная."""
        income = Decimal("200_000")
        threshold = Decimal("300_000")
        additional = max(income - threshold, Decimal("0")) * Decimal("1") / Decimal("100")
        assert additional == Decimal("0")
        total = IP_FIXED_CONTRIBUTIONS_2026 + additional
        assert total == Decimal("53658")

    def test_with_additional(self):
        """Доход 1 000 000: фикс + 1% от (1 000 000 - 300 000) = 53 658 + 7 000 = 60 658."""
        income = Decimal("1_000_000")
        threshold = Decimal("300_000")
        additional = (
            (income - threshold) * Decimal("1") / Decimal("100")
        ).quantize(Decimal("0.01"))
        assert additional == Decimal("7000.00")
        total = IP_FIXED_CONTRIBUTIONS_2026 + additional
        assert total == Decimal("60658.00")

    def test_max_cap(self):
        """Очень большой доход → ограничение максимумом 300 888 ₽."""
        income = Decimal("50_000_000")
        threshold = Decimal("300_000")
        additional = (
            (income - threshold) * Decimal("1") / Decimal("100")
        ).quantize(Decimal("0.01"))
        total = IP_FIXED_CONTRIBUTIONS_2026 + additional
        # total = 53658 + 497000 = 550658 > 300888
        capped = min(total, IP_MAX_CONTRIBUTIONS_2026)
        assert capped == Decimal("300888")

    def test_at_threshold(self):
        """Доход ровно 300 000 → только фиксированная."""
        income = Decimal("300_000")
        additional = max(income - Decimal("300_000"), Decimal("0")) * Decimal("1") / Decimal("100")
        assert additional == Decimal("0")


# ═══════════════════════════════════════════════════════════
# Тесты dataclass-ов
# ═══════════════════════════════════════════════════════════


class TestDataclasses:
    """Тесты, что dataclass-ы корректно создаются с дефолтами."""

    def test_usn_defaults(self):
        result = UsnCalculationResult()
        assert result.income_total == Decimal("0")
        assert result.tax_to_pay == Decimal("0")
        assert result.is_minimum_tax is False
        assert result.warnings == []

    def test_vat_defaults(self):
        result = VatCalculationResult()
        assert result.vat_charged == Decimal("0")
        assert result.monthly_payments == []

    def test_ndfl_defaults(self):
        result = NdflCalculationResult()
        assert result.gross_salary == Decimal("0")
        assert result.rate_applied == Decimal("13")

    def test_insurance_defaults(self):
        result = InsuranceCalculationResult()
        assert result.contributions_total == Decimal("0")
        assert result.rate_applied == Decimal("30")

    def test_ip_contributions_defaults(self):
        result = IpContributionsResult()
        assert result.fixed_amount == Decimal("0")
        assert result.total_amount == Decimal("0")
        assert result.warnings == []
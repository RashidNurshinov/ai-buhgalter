"""
Сервис расчёта налогов — TaxCalculationService.
Пункт плана: 1.12

Методы:
- calculate_usn() — расчёт УСН «Доходы минус расходы» (15% / 20%)
- calculate_usn_advance() — авансовый платёж УСН за квартал
- calculate_vat() — расчёт НДС за квартал (начисленный − вычеты)
- calculate_ndfl_employee() — НДФЛ за сотрудника (13% / 15%)
- calculate_insurance_contributions_employee() — страховые взносы за сотрудника
- calculate_ip_fixed_contributions() — фиксированные взносы ИП за себя
- calculate_total_tax_burden() — итоговая налоговая нагрузка за период

Н��рмативная база:
- УСН: Глава 26.2 НК РФ, ст. 346.18 (минимальный налог), ст. 346.21 (порядок расчёта)
- НДС: Глава 21 НК РФ, ставка 22% с 01.01.2026
- НДФЛ: Глава 23 НК РФ, прогрессивная шкала 13%/15%
- Страховые взносы: Глава 34 НК РФ, ст. 430 (ИП за себя)
"""

import logging
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from sqlalchemy import func, select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.enums import (
    CalculationStatus,
    OperationCategory,
    OperationStatus,
    PeriodType,
    TaxType,
)
from app.constants.tax_rates import (
    IP_ADDITIONAL_RATE,
    IP_ADDITIONAL_THRESHOLD,
    IP_FIXED_CONTRIBUTIONS_2026,
    IP_MAX_CONTRIBUTIONS_2026,
    INSURANCE_BASE_LIMIT_2026,
    INSURANCE_RATE_REDUCED,
    INSURANCE_RATE_STANDARD,
    MROT_2026,
    USN_MINIMUM_TAX_RATE,
    USN_RATE_INCOME_EXPENSE,
    VAT_RATE_STANDARD,
    get_ndfl_amount,
    get_usn_rate,
)
from app.models.bank_operation import BankOperation
from app.models.book_entry import PurchaseBookEntry, SalesBookEntry
from app.models.kudir_entry import KudirEntry
from app.models.tax_calculation import TaxCalculation
from app.models.user import User

logger = logging.getLogger(__name__)

# Категории операций, считающихся уплатой страховых взносов ИП за себя
_INSURANCE_IP_CATEGORIES = {
    OperationCategory.INSURANCE_PAYMENT,
}

# Округление до копеек
_TWO_PLACES = Decimal("0.01")


# ═══════════════════════════════════════════════════════════
# Dataclasses результатов
# ═══════════════════════════════════════════════════════════


@dataclass
class UsnCalculationResult:
    """Результат расчёта УСН."""
    income_total: Decimal = Decimal("0")
    expense_total: Decimal = Decimal("0")
    tax_base: Decimal = Decimal("0")
    tax_rate: Decimal = Decimal("15")
    tax_amount: Decimal = Decimal("0")
    min_tax_amount: Decimal = Decimal("0")        # Минимальный налог (1% от доходов)
    insurance_deduction: Decimal = Decimal("0")    # Вычет страховых взносов
    previous_advances: Decimal = Decimal("0")      # Ранее уплаченные авансы
    tax_to_pay: Decimal = Decimal("0")             # К доплате (с учётом авансов)
    is_minimum_tax: bool = False                   # Применяется ли минимальный налог
    warnings: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class VatCalculationResult:
    """Результат расчёта НДС."""
    vat_charged: Decimal = Decimal("0")            # НДС начисленный (с продаж)
    vat_deductible: Decimal = Decimal("0")         # НДС к вычету (с покупок)
    vat_payable: Decimal = Decimal("0")            # НДС к уплате
    monthly_payments: list[Decimal] = field(default_factory=list)  # 3 ежемесячных платежа по 1/3
    warnings: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class NdflCalculationResult:
    """Результат расчёта НДФЛ за сотрудника."""
    gross_salary: Decimal = Decimal("0")
    ndfl_amount: Decimal = Decimal("0")
    net_salary: Decimal = Decimal("0")
    rate_applied: Decimal = Decimal("13")
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class InsuranceCalculationResult:
    """Результат расчёта страховых взносов за сотрудника."""
    gross_salary: Decimal = Decimal("0")
    contributions_total: Decimal = Decimal("0")
    rate_applied: Decimal = Decimal("30")
    cumulative_base: Decimal = Decimal("0")       # Накопленная база с начала года
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class IpContributionsResult:
    """Результат расчёта фиксированных взносов ИП."""
    fixed_amount: Decimal = Decimal("0")           # Фиксированная часть (53 658 ₽)
    additional_amount: Decimal = Decimal("0")      # 1% с превышения 300 000 ₽
    total_amount: Decimal = Decimal("0")           # Итого
    income_for_calculation: Decimal = Decimal("0") # Доход для расчёта 1%
    already_paid: Decimal = Decimal("0")           # Уже уплачено
    remaining: Decimal = Decimal("0")              # Осталось к уплате
    warnings: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class TotalTaxBurdenResult:
    """Сводный результат по всем налогам."""
    usn: UsnCalculationResult | None = None
    vat: VatCalculationResult | None = None
    ndfl: NdflCalculationResult | None = None
    insurance_employee: InsuranceCalculationResult | None = None
    ip_contributions: IpContributionsResult | None = None
    total_payable: Decimal = Decimal("0")
    period_start: date | None = None
    period_end: date | None = None
    warnings: list[str] = field(default_factory=list)


# ═══════════════════════════════════════════════════════════
# Вспомогательные функции периодов
# ═══════════════════════════════════════════════════════════


def get_quarter_dates(year: int, quarter: int) -> tuple[date, date]:
    """Получить даты начала и конца квартала."""
    quarter_starts = {1: 1, 2: 4, 3: 7, 4: 10}
    quarter_ends_day = {1: 31, 2: 30, 3: 30, 4: 31}
    quarter_ends_month = {1: 3, 2: 6, 3: 9, 4: 12}

    start_month = quarter_starts[quarter]
    end_month = quarter_ends_month[quarter]
    end_day = quarter_ends_day[quarter]

    return date(year, start_month, 1), date(year, end_month, end_day)


def get_year_dates(year: int) -> tuple[date, date]:
    """Получить даты начала и конца года."""
    return date(year, 1, 1), date(year, 12, 31)


def get_period_dates(year: int, quarter: int | None, period_type: PeriodType) -> tuple[date, date]:
    """Получить даты периода по типу."""
    if period_type == PeriodType.QUARTER and quarter:
        return get_quarter_dates(year, quarter)
    elif period_type == PeriodType.HALF_YEAR:
        return date(year, 1, 1), date(year, 6, 30)
    elif period_type == PeriodType.NINE_MONTHS:
        return date(year, 1, 1), date(year, 9, 30)
    elif period_type == PeriodType.YEAR:
        return get_year_dates(year)
    elif period_type == PeriodType.MONTH and quarter:
        # Используем quarter как номер месяца
        month = quarter
        if month == 12:
            end = date(year, 12, 31)
        else:
            end = date(year, month + 1, 1) - timedelta(days=1)
        return date(year, month, 1), end
    else:
        return get_year_dates(year)


# ═══════════════════════════════════════════════════════════
# Основной сервис
# ═══════════════════════════════════════════════════════════


class TaxCalculationService:
    """
    Сервис расчёта всех налогов для ИП на УСН + НДС.

    Использование:
        service = TaxCalculationService(db, user)
        usn = await service.calculate_usn(year=2026, quarter=1)
        vat = await service.calculate_vat(year=2026, quarter=1)
        total = await service.calculate_total_tax_burden(year=2026, quarter=1)
    """

    def __init__(self, db: AsyncSession, user: User):
        self.db = db
        self.user = user

    # ─── 1.12.1: Расчёт УСН ──────────────────────────────────

    async def calculate_usn(
        self,
        year: int,
        quarter: int | None = None,
        period_type: PeriodType = PeriodType.QUARTER,
    ) -> UsnCalculationResult:
        """
        Расчёт УСН «Доходы минус расходы».

        Для квартального аванса: period_type=QUARTER, quarter=1..4
        Для годового итога: period_type=YEAR, quarter=None

        Формула:
            Налоговая база = Доходы - Расходы
            Налог = База × Ставка (15% или 20%)
            Минимальный налог = Доходы × 1% (только годовой)

        Уменьшение на страховые взносы:
            п. 3.1 ст. 346.21 НК РФ — УСН «Доходы минус расходы»
            взносы уже включены в расходы, отдельного вычета нет.
        """
        result = UsnCalculationResult()

        # Определяем период
        if period_type == PeriodType.QUARTER and quarter:
            period_start, period_end = get_quarter_dates(year, quarter)
        elif period_type == PeriodType.YEAR:
            period_start, period_end = get_year_dates(year)
        else:
            # Нарастающий итог: с начала года до конца указанного квартала
            period_start = date(year, 1, 1)
            _, period_end = get_quarter_dates(year, quarter or 4)

        # 1. Получаем доходы и расходы из КУДиР
        income_total, expense_total = await self._get_kudir_totals(
            period_start, period_end
        )

        result.income_total = income_total
        result.expense_total = expense_total

        # 2. Определяем ставку
        result.tax_rate = get_usn_rate(
            income_total=income_total,
            employee_count=self.user.employee_count,
            base_rate=self.user.usn_rate or USN_RATE_INCOME_EXPENSE,
        )

        # 3. Налоговая база (не может быть отрицательной для целей минимального налога)
        result.tax_base = max(income_total - expense_total, Decimal("0"))

        # 4. Расчёт налога
        result.tax_amount = (
            result.tax_base * result.tax_rate / Decimal("100")
        ).quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)

        # 5. Минимальный налог (только для годового расчёта)
        if period_type == PeriodType.YEAR and income_total > Decimal("0"):
            result.min_tax_amount = (
                income_total * USN_MINIMUM_TAX_RATE / Decimal("100")
            ).quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)

            if result.min_tax_amount > result.tax_amount:
                result.is_minimum_tax = True
                result.tax_amount = result.min_tax_amount
                result.warnings.append(
                    f"Применён минимальный налог УСН (1% от доходов = {result.min_tax_amount} ₽), "
                    f"т.к. он превышает расчётный налог по ставке {result.tax_rate}%."
                )

        # 6. Ранее уплаченные авансы (для расчёта доплаты)
        if period_type == PeriodType.YEAR and quarter is None:
            result.previous_advances = await self._get_previous_usn_advances(year)
            result.tax_to_pay = max(
                result.tax_amount - result.previous_advances, Decimal("0")
            )
        else:
            # Для авансового платежа: нарастающий итог минус предыдущие авансы
            if quarter and quarter > 1:
                result.previous_advances = await self._get_usn_advances_before_quarter(
                    year, quarter
                )
            result.tax_to_pay = max(
                result.tax_amount - result.previous_advances, Decimal("0")
            )

        # 7. Предупреждения о лимитах
        if income_total > Decimal("199_350_000"):
            result.warnings.append(
                "⚠️ Доход превысил базовый лимит УСН (199.35 млн ₽). "
                "Применяется повышенная ставка 20%."
            )
        if income_total > Decimal("265_800_000"):
            result.warnings.append(
                "🔴 Доход превысил предельный лимит УСН (265.8 млн ₽). "
                "Возможна утрата права на применение УСН!"
            )

        result.details = {
            "period_start": str(period_start),
            "period_end": str(period_end),
            "period_type": period_type.value,
            "formula": f"({income_total} - {expense_total}) × {result.tax_rate}% = {result.tax_amount}",
        }

        logger.info(
            "USN calculated for user %s: income=%s, expense=%s, tax=%s (rate=%s%%)",
            self.user.id, income_total, expense_total, result.tax_amount, result.tax_rate,
        )

        return result

    async def calculate_usn_advance(
        self,
        year: int,
        quarter: int,
    ) -> UsnCalculationResult:
        """
        Расчёт авансового платежа УСН за конкретный квартал.

        Авансовый платёж = (Доходы нараст. итогом - Расходы нараст. итогом) × Ставка
                           - Авансы за предыдущие кварталы

        Нарастающий итог: с начала года до конца указанного квартала.
        """
        # Нарастающий итог с начала года
        period_start = date(year, 1, 1)
        _, period_end = get_quarter_dates(year, quarter)

        income_total, expense_total = await self._get_kudir_totals(
            period_start, period_end
        )

        result = UsnCalculationResult()
        result.income_total = income_total
        result.expense_total = expense_total

        # Ставка
        result.tax_rate = get_usn_rate(
            income_total=income_total,
            employee_count=self.user.employee_count,
            base_rate=self.user.usn_rate or USN_RATE_INCOME_EXPENSE,
        )

        # База нарастающим итогом
        result.tax_base = max(income_total - expense_total, Decimal("0"))

        # Налог нарастающим итогом
        cumulative_tax = (
            result.tax_base * result.tax_rate / Decimal("100")
        ).quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)

        # Минус авансы за предыдущие кварталы
        if quarter > 1:
            result.previous_advances = await self._get_usn_advances_before_quarter(
                year, quarter
            )
        else:
            result.previous_advances = Decimal("0")

        result.tax_amount = cumulative_tax
        result.tax_to_pay = max(cumulative_tax - result.previous_advances, Decimal("0"))

        result.details = {
            "period": f"Q1-Q{quarter} {year} (нарастающий итог)",
            "period_start": str(period_start),
            "period_end": str(period_end),
            "cumulative_tax": str(cumulative_tax),
            "previous_advances": str(result.previous_advances),
            "advance_to_pay": str(result.tax_to_pay),
        }

        return result

    # ─── 1.12.1: Расчёт НДС ──────────────────────────────────

    async def calculate_vat(
        self,
        year: int,
        quarter: int,
    ) -> VatCalculationResult:
        """
        Расчёт НДС за квартал.

        Формула:
            НДС к уплате = НДС начисленный (книга продаж) - НДС к вычету (книга покупок)

        Уплата: равными долями по 1/3 в течение 3 месяцев после квартала.
        """
        result = VatCalculationResult()

        period_start, period_end = get_quarter_dates(year, quarter)

        # 1. НДС начисленный (из книги продаж)
        result.vat_charged = await self._get_sales_book_vat_total(year, quarter)

        # 2. НДС к вычету (из книги покупок)
        result.vat_deductible = await self._get_purchase_book_vat_total(year, quarter)

        # 3. НДС к уплате
        result.vat_payable = (
            result.vat_charged - result.vat_deductible
        ).quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)

        # 4. Ежемесячные платежи (по 1/3)
        if result.vat_payable > Decimal("0"):
            monthly = (result.vat_payable / Decimal("3")).quantize(
                _TWO_PLACES, rounding=ROUND_HALF_UP
            )
            # Третий платёж корректируется, чтобы сумма совпала
            remainder = result.vat_payable - monthly * 2
            result.monthly_payments = [monthly, monthly, remainder]
        else:
            result.monthly_payments = [Decimal("0"), Decimal("0"), Decimal("0")]

        # 5. Предупреждения
        if result.vat_payable < Decimal("0"):
            result.warnings.append(
                f"НДС к возмещению: {abs(result.vat_payable)} ₽. "
                "Вычеты превышают начисления. Возможна камеральная проверка."
            )

        if result.vat_charged > Decimal("0") and result.vat_deductible > Decimal("0"):
            deduction_ratio = result.vat_deductible / result.vat_charged * Decimal("100")
            if deduction_ratio > Decimal("89"):
                result.warnings.append(
                    f"⚠️ Доля вычетов НДС ({deduction_ratio:.1f}%) превышает безопасный порог (89%). "
                    "Повышенный риск камеральной проверки."
                )

        result.details = {
            "quarter": quarter,
            "year": year,
            "period_start": str(period_start),
            "period_end": str(period_end),
            "formula": f"{result.vat_charged} - {result.vat_deductible} = {result.vat_payable}",
            "monthly_payments": [str(p) for p in result.monthly_payments],
        }

        logger.info(
            "VAT calculated for user %s Q%d/%d: charged=%s, deductible=%s, payable=%s",
            self.user.id, quarter, year,
            result.vat_charged, result.vat_deductible, result.vat_payable,
        )

        return result

    # ─── 1.12.1: Расчёт НДФЛ за сотрудника ──────────────────

    async def calculate_ndfl_employee(
        self,
        gross_salary: Decimal,
        cumulative_income: Decimal = Decimal("0"),
    ) -> NdflCalculationResult:
        """
        Расчёт НДФЛ за сотрудника за месяц.

        Прогрессивная шкала (с 2021):
        - до 5 млн ₽ в год → 13%
        - свыше 5 млн ₽ → 15% с превышения

        Args:
            gross_salary: Зарплата за месяц (брутто)
            cumulative_income: Накопленный доход с начала года (до текущего месяца)
        """
        result = NdflCalculationResult()
        result.gross_salary = gross_salary

        if gross_salary <= Decimal("0"):
            return result

        # Определяем, попадает ли часть дохода в повышенную ставку
        new_cumulative = cumulative_income + gross_salary

        if new_cumulative <= Decimal("5_000_000"):
            # Весь доход по 13%
            result.ndfl_amount = (
                gross_salary * Decimal("13") / Decimal("100")
            ).quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)
            result.rate_applied = Decimal("13")
        elif cumulative_income >= Decimal("5_000_000"):
            # Весь текущий доход уже по 15%
            result.ndfl_amount = (
                gross_salary * Decimal("15") / Decimal("100")
            ).quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)
            result.rate_applied = Decimal("15")
        else:
            # Часть по 13%, часть по 15%
            below_threshold = Decimal("5_000_000") - cumulative_income
            above_threshold = gross_salary - below_threshold

            tax_13 = (below_threshold * Decimal("13") / Decimal("100")).quantize(
                _TWO_PLACES, rounding=ROUND_HALF_UP
            )
            tax_15 = (above_threshold * Decimal("15") / Decimal("100")).quantize(
                _TWO_PLACES, rounding=ROUND_HALF_UP
            )
            result.ndfl_amount = tax_13 + tax_15
            result.rate_applied = Decimal("13")  # Комбинированная

        result.net_salary = gross_salary - result.ndfl_amount

        result.details = {
            "cumulative_income_before": str(cumulative_income),
            "cumulative_income_after": str(new_cumulative),
            "gross": str(gross_salary),
            "ndfl": str(result.ndfl_amount),
            "net": str(result.net_salary),
        }

        return result

    # ─── 1.12.1: Страховые взносы за сотрудника ──────────────

    async def calculate_insurance_contributions_employee(
        self,
        gross_salary: Decimal,
        cumulative_base: Decimal = Decimal("0"),
    ) -> InsuranceCalculationResult:
        """
        Расчёт страховых взносов за сотрудника за месяц.

        Единый тариф (ст. 425 НК РФ, 2026):
        - До предельной базы (2 759 000 ₽): 30%
        - Свыше предельной базы: 15.1%

        Args:
            gross_salary: Зарплата за месяц (брутто)
            cumulative_base: Накопленная база с начала года
        """
        result = InsuranceCalculationResult()
        result.gross_salary = gross_salary
        result.cumulative_base = cumulative_base

        if gross_salary <= Decimal("0"):
            return result

        new_cumulative = cumulative_base + gross_salary
        limit = INSURANCE_BASE_LIMIT_2026

        if new_cumulative <= limit:
            # Всё по 30%
            result.contributions_total = (
                gross_salary * INSURANCE_RATE_STANDARD / Decimal("100")
            ).quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)
            result.rate_applied = INSURANCE_RATE_STANDARD
        elif cumulative_base >= limit:
            # Всё по 15.1%
            result.contributions_total = (
                gross_salary * INSURANCE_RATE_REDUCED / Decimal("100")
            ).quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)
            result.rate_applied = INSURANCE_RATE_REDUCED
        else:
            # Часть по 30%, часть по 15.1%
            below_limit = limit - cumulative_base
            above_limit = gross_salary - below_limit

            contrib_standard = (
                below_limit * INSURANCE_RATE_STANDARD / Decimal("100")
            ).quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)
            contrib_reduced = (
                above_limit * INSURANCE_RATE_REDUCED / Decimal("100")
            ).quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)

            result.contributions_total = contrib_standard + contrib_reduced
            result.rate_applied = INSURANCE_RATE_STANDARD  # Комбинированная

        result.details = {
            "cumulative_base_before": str(cumulative_base),
            "cumulative_base_after": str(new_cumulative),
            "limit": str(limit),
            "salary": str(gross_salary),
            "contributions": str(result.contributions_total),
        }

        return result

    # ─── 1.12.1: Фиксированные взносы ИП за себя ─────────────

    async def calculate_ip_fixed_contributions(
        self,
        year: int,
    ) -> IpContributionsResult:
        """
        Расчёт фиксированных страховых взносов ИП за себя.

        Ст. 430 НК РФ (2026):
        - Фиксированная часть: 53 658 ₽ (ОПС + ОМС)
        - Дополнительная часть: 1% от (доход - 300 000 ₽)
        - Максимум: 300 888 ₽

        Для УСН «Доходы минус расходы»: доход = ДОХОДЫ (без вычета расходов)
        Это подтверждено определением КС РФ от 30.01.2020 № 10-О
        и письмом ФНС от 01.09.2020 № БС-4-11/14090.
        """
        result = IpContributionsResult()

        # 1. Фиксированная часть
        result.fixed_amount = IP_FIXED_CONTRIBUTIONS_2026

        # 2. Доход для расчёта 1% (из КУДиР — только доходы, БЕЗ расходов)
        year_start, year_end = get_year_dates(year)
        income_total, _ = await self._get_kudir_totals(year_start, year_end)
        result.income_for_calculation = income_total

        # 3. Дополнительная часть: 1% с превышения 300 000 ₽
        if income_total > IP_ADDITIONAL_THRESHOLD:
            result.additional_amount = (
                (income_total - IP_ADDITIONAL_THRESHOLD)
                * IP_ADDITIONAL_RATE / Decimal("100")
            ).quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)

        # 4. Итого (с ограничением максимума)
        total = result.fixed_amount + result.additional_amount
        if total > IP_MAX_CONTRIBUTIONS_2026:
            result.total_amount = IP_MAX_CONTRIBUTIONS_2026
            result.warnings.append(
                f"Взносы ИП ограничены максимумом {IP_MAX_CONTRIBUTIONS_2026} ₽ "
                f"(до ограничения: {total} ₽)"
            )
        else:
            result.total_amount = total

        # 5. Уже уплаченные взносы (из банковских операций)
        result.already_paid = await self._get_ip_insurance_paid(year)
        result.remaining = max(result.total_amount - result.already_paid, Decimal("0"))

        result.details = {
            "year": year,
            "income_total": str(income_total),
            "fixed": str(result.fixed_amount),
            "additional_base": str(max(income_total - IP_ADDITIONAL_THRESHOLD, Decimal("0"))),
            "additional": str(result.additional_amount),
            "total": str(result.total_amount),
            "already_paid": str(result.already_paid),
            "remaining": str(result.remaining),
        }

        logger.info(
            "IP contributions for user %s year %d: total=%s, paid=%s, remaining=%s",
            self.user.id, year, result.total_amount, result.already_paid, result.remaining,
        )

        return result

    # ─── 1.12.1: Итоговая налоговая нагрузка ─────────────────

    async def calculate_total_tax_burden(
        self,
        year: int,
        quarter: int | None = None,
    ) -> TotalTaxBurdenResult:
        """
        Итоговая налоговая нагрузка за период.

        Если quarter указан — расчёт за квартал.
        Если quarter не указан — расчёт за год.
        """
        result = TotalTaxBurdenResult()

        if quarter:
            period_start, period_end = get_quarter_dates(year, quarter)
        else:
            period_start, period_end = get_year_dates(year)

        result.period_start = period_start
        result.period_end = period_end

        total = Decimal("0")

        # 1. УСН
        try:
            if quarter:
                result.usn = await self.calculate_usn_advance(year, quarter)
            else:
                result.usn = await self.calculate_usn(
                    year, period_type=PeriodType.YEAR
                )
            total += result.usn.tax_to_pay
            result.warnings.extend(result.usn.warnings)
        except Exception as e:
            logger.error("USN calculation failed: %s", e)
            result.warnings.append(f"Ошибка расчёта УСН: {e}")

        # 2. НДС (только за квартал)
        try:
            target_quarter = quarter or 4
            result.vat = await self.calculate_vat(year, target_quarter)
            if result.vat.vat_payable > Decimal("0"):
                total += result.vat.vat_payable
            result.warnings.extend(result.vat.warnings)
        except Exception as e:
            logger.error("VAT calculation failed: %s", e)
            result.warnings.append(f"Ошибка расчёта НДС: {e}")

        # 3. Взносы ИП
        try:
            result.ip_contributions = await self.calculate_ip_fixed_contributions(year)
            if quarter is None:
                total += result.ip_contributions.remaining
            result.warnings.extend(result.ip_contributions.warnings)
        except Exception as e:
            logger.error("IP contributions calculation failed: %s", e)
            result.warnings.append(f"Ошибка расчёта взносов ИП: {e}")

        # 4. НДФЛ и взносы за сотрудников (если есть)
        if self.user.has_employees and self.user.employee_count > 0:
            # Примерный расчёт на основании МРОТ (детальный — через payroll)
            result.warnings.append(
                f"У вас {self.user.employee_count} сотрудник(ов). "
                "Для точного расчёта НДФЛ и взносов укажите зарплаты."
            )

        result.total_payable = total.quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)

        return result

    # ─── Сохранение результата в БД ─────────────────────��────

    async def save_calculation(
        self,
        tax_type: TaxType,
        period_type: PeriodType,
        period_start: date,
        period_end: date,
        result_data: UsnCalculationResult | VatCalculationResult | IpContributionsResult,
    ) -> TaxCalculation:
        """Сохранить результат расчёта в БД."""
        # Проверяем, есть ли уже расчёт за этот период
        existing = await self.db.execute(
            select(TaxCalculation).where(
                and_(
                    TaxCalculation.user_id == self.user.id,
                    TaxCalculation.tax_type == tax_type,
                    TaxCalculation.period_start == period_start,
                    TaxCalculation.period_end == period_end,
                )
            )
        )
        calc = existing.scalar_one_or_none()

        if calc is None:
            calc = TaxCalculation(
                user_id=self.user.id,
                tax_type=tax_type,
                period_type=period_type,
                period_start=period_start,
                period_end=period_end,
            )
            self.db.add(calc)

        # Заполняем общие поля
        if isinstance(result_data, UsnCalculationResult):
            calc.income_total = result_data.income_total
            calc.expense_total = result_data.expense_total
            calc.tax_base = result_data.tax_base
            calc.tax_rate = result_data.tax_rate
            calc.tax_amount = result_data.tax_amount
            calc.insurance_deduction = result_data.insurance_deduction
            calc.min_tax_amount = result_data.min_tax_amount
            calc.details_json = result_data.details
        elif isinstance(result_data, VatCalculationResult):
            calc.income_total = Decimal("0")
            calc.expense_total = Decimal("0")
            calc.tax_base = result_data.vat_charged - result_data.vat_deductible
            calc.tax_rate = VAT_RATE_STANDARD
            calc.tax_amount = result_data.vat_payable
            calc.vat_charged = result_data.vat_charged
            calc.vat_deductible = result_data.vat_deductible
            calc.vat_payable = result_data.vat_payable
            calc.details_json = result_data.details
        elif isinstance(result_data, IpContributionsResult):
            calc.income_total = result_data.income_for_calculation
            calc.expense_total = Decimal("0")
            calc.tax_base = max(
                result_data.income_for_calculation - IP_ADDITIONAL_THRESHOLD,
                Decimal("0"),
            )
            calc.tax_rate = IP_ADDITIONAL_RATE
            calc.tax_amount = result_data.total_amount
            calc.details_json = result_data.details

        calc.status = CalculationStatus.PRELIMINARY

        await self.db.flush()
        return calc

    # ═══════════════════════════════════════════════════════
    # Приватные методы: запросы к БД
    # ═══════════════════════════════════════════════════════

    async def _get_kudir_totals(
        self,
        period_start: date,
        period_end: date,
    ) -> tuple[Decimal, Decimal]:
        """Получить сумму доходов и расходов из КУДиР за период."""
        result = await self.db.execute(
            select(
                func.coalesce(func.sum(KudirEntry.income_amount), Decimal("0")),
                func.coalesce(func.sum(KudirEntry.expense_amount), Decimal("0")),
            ).where(
                and_(
                    KudirEntry.user_id == self.user.id,
                    KudirEntry.entry_date >= period_start,
                    KudirEntry.entry_date <= period_end,
                )
            )
        )
        row = result.one()
        income = row[0] if row[0] is not None else Decimal("0")
        expense = row[1] if row[1] is not None else Decimal("0")
        return Decimal(str(income)), Decimal(str(expense))

    async def _get_sales_book_vat_total(
        self,
        year: int,
        quarter: int,
    ) -> Decimal:
        """Получить итого НДС начисленный из книги продаж за квартал."""
        result = await self.db.execute(
            select(
                func.coalesce(func.sum(SalesBookEntry.vat_amount), Decimal("0")),
            ).where(
                and_(
                    SalesBookEntry.user_id == self.user.id,
                    SalesBookEntry.year == year,
                    SalesBookEntry.quarter == quarter,
                )
            )
        )
        val = result.scalar()
        return Decimal(str(val)) if val is not None else Decimal("0")

    async def _get_purchase_book_vat_total(
        self,
        year: int,
        quarter: int,
    ) -> Decimal:
        """Получить итого НДС к вычету из книги покупок за квартал."""
        result = await self.db.execute(
            select(
                func.coalesce(func.sum(PurchaseBookEntry.vat_amount), Decimal("0")),
            ).where(
                and_(
                    PurchaseBookEntry.user_id == self.user.id,
                    PurchaseBookEntry.year == year,
                    PurchaseBookEntry.quarter == quarter,
                )
            )
        )
        val = result.scalar()
        return Decimal(str(val)) if val is not None else Decimal("0")

    async def _get_previous_usn_advances(self, year: int) -> Decimal:
        """Получить сумму ранее уплаченных авансов УСН за год (из расчётов)."""
        result = await self.db.execute(
            select(
                func.coalesce(func.sum(TaxCalculation.tax_amount), Decimal("0")),
            ).where(
                and_(
                    TaxCalculation.user_id == self.user.id,
                    TaxCalculation.tax_type == TaxType.USN,
                    TaxCalculation.period_type == PeriodType.QUARTER,
                    TaxCalculation.period_start >= date(year, 1, 1),
                    TaxCalculation.period_end <= date(year, 12, 31),
                    TaxCalculation.status.in_([
                        CalculationStatus.CONFIRMED,
                        CalculationStatus.PAID,
                    ]),
                )
            )
        )
        val = result.scalar()
        return Decimal(str(val)) if val is not None else Decimal("0")

    async def _get_usn_advances_before_quarter(
        self, year: int, quarter: int
    ) -> Decimal:
        """Получить сумму авансов УСН за кварталы, предшествующие указанному."""
        _, end_prev = get_quarter_dates(year, quarter - 1) if quarter > 1 else (None, None)
        if end_prev is None:
            return Decimal("0")

        result = await self.db.execute(
            select(
                func.coalesce(func.sum(TaxCalculation.tax_amount), Decimal("0")),
            ).where(
                and_(
                    TaxCalculation.user_id == self.user.id,
                    TaxCalculation.tax_type == TaxType.USN,
                    TaxCalculation.period_type == PeriodType.QUARTER,
                    TaxCalculation.period_start >= date(year, 1, 1),
                    TaxCalculation.period_end <= end_prev,
                    TaxCalculation.status.in_([
                        CalculationStatus.CONFIRMED,
                        CalculationStatus.PAID,
                    ]),
                )
            )
        )
        val = result.scalar()
        return Decimal(str(val)) if val is not None else Decimal("0")

    async def _get_ip_insurance_paid(self, year: int) -> Decimal:
        """
        Получить сумму уже уплаченных страховых взносов ИП за себя из банковских операций.
        Ищет операции с категорией INSURANCE_PAYMENT и is_expense=True.
        """
        year_start, year_end = get_year_dates(year)

        result = await self.db.execute(
            select(
                func.coalesce(func.sum(BankOperation.amount), Decimal("0")),
            ).where(
                and_(
                    BankOperation.user_id == self.user.id,
                    BankOperation.operation_date >= year_start,
                    BankOperation.operation_date <= year_end,
                    BankOperation.category == OperationCategory.INSURANCE_PAYMENT,
                    BankOperation.is_expense == True,  # noqa: E712
                    BankOperation.status.in_([
                        OperationStatus.CONFIRMED,
                        OperationStatus.CLASSIFIED,
                        OperationStatus.RECLASSIFIED,
                    ]),
                )
            )
        )
        val = result.scalar()
        return Decimal(str(val)) if val is not None else Decimal("0")
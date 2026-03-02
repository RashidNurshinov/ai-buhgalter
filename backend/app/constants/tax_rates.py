"""
Налоговые ставки и лимиты на 2026 год (Россия).
Справочник: СПРАВОЧНИК_СУЩНОСТЕЙ.md → раздел 5.1
Нормативная база: НК РФ (ред. 2026), ФЗ от ... (НДС 22%)

ВАЖНО: Все денежные значения — в рублях (Decimal).
При изменении ставок обновлять этот файл + СПРАВОЧНИК_СУЩНОСТЕЙ.md.
"""

from decimal import Decimal

# ═══════════════════════════════════════════════════════════
# НДС (Глава 21 НК РФ, с 01.01.2026)
# ═══════════════════════════════════════════════════════════

VAT_RATE_STANDARD = Decimal("22")       # Основная ставка, %
VAT_RATE_REDUCED = Decimal("10")        # Пониженная ставка (продовольствие, детское), %
VAT_RATE_ZERO = Decimal("0")            # Нулевая ставка (экспорт), %

# Расчётные ставки (для выделения НДС из суммы с НДС)
VAT_CALCULATED_STANDARD = Decimal("22") / Decimal("122")   # 22/122
VAT_CALCULATED_REDUCED = Decimal("10") / Decimal("110")    # 10/110


# ═══════════════════════════════════════════════════════════
# УСН (Глава 26.2 НК РФ)
# ═══════════════════════════════════════════════════════════

# Базовые ставки
USN_RATE_INCOME_EXPENSE = Decimal("15")          # «Доходы минус расходы»
USN_RATE_INCOME = Decimal("6")                    # «Доходы»

# Повышенные ставки (при превышении базовых лимитов, но в пределах повышенных)
USN_RATE_INCOME_EXPENSE_ELEVATED = Decimal("20")
USN_RATE_INCOME_ELEVATED = Decimal("8")

# Минимальный налог УСН (ст. 346.18 НК РФ)
USN_MINIMUM_TAX_RATE = Decimal("1")               # 1% от доходов

# Лимиты дохода для УСН (2026)
USN_INCOME_LIMIT_BASE = Decimal("199_350_000")     # До этой суммы — базовая ставка
USN_INCOME_LIMIT_ELEVATED = Decimal("265_800_000") # Свыше — повышенная ставка

# Лимит сотрудников
USN_EMPLOYEE_LIMIT_BASE = 100                       # До 100 — базовая ставка
USN_EMPLOYEE_LIMIT_ELEVATED = 130                   # До 130 — повышенная ставка


# ═══════════════════════════════════════════════════════════
# НДФЛ (Глава 23 НК РФ)
# ═══════════════════════════════════════════════════════════

NDFL_RATE_STANDARD = Decimal("13")                 # До 5 млн руб. в год
NDFL_RATE_ELEVATED = Decimal("15")                 # Свыше 5 млн руб. в год
NDFL_ELEVATED_THRESHOLD = Decimal("5_000_000")     # Порог повышенной ставки


# ═══════════════════════════════════════════════════════════
# Страховые взносы за сотрудников (Глава 34 НК РФ)
# ═══════════════════════════════════════════════════════════

# Единый тариф страховых взносов
INSURANCE_RATE_STANDARD = Decimal("30.0")           # До предельной базы
INSURANCE_RATE_REDUCED = Decimal("15.1")            # Свыше предельной базы
INSURANCE_BASE_LIMIT_2026 = Decimal("2_759_000")   # Предельная база на 2026

# МСП: пониженный тариф свыше МРОТ (15% вместо 30%)
MSP_INSURANCE_RATE_ABOVE_MROT = Decimal("15.0")

# МРОТ 2026
MROT_2026 = Decimal("22_440")                       # Месячный МРОТ


# ═══════════════════════════════════════════════════════════
# Фиксированные взносы ИП за себя (ст. 430 НК РФ)
# ═══════════════════════════════════════════════════════════

IP_FIXED_CONTRIBUTIONS_2026 = Decimal("53_658")     # Фиксированная сумма за год
IP_ADDITIONAL_RATE = Decimal("1")                    # 1% с доходов свыше 300 000 ₽
IP_ADDITIONAL_THRESHOLD = Decimal("300_000")         # Порог для доп. взноса
IP_MAX_CONTRIBUTIONS_2026 = Decimal("300_888")       # Максимальный размер взносов ИП

# Срок уплаты фиксированных взносов: 31 декабря текущего года
# Срок уплаты 1% свыше 300 000: 1 июля следующего года


# ═══════════════════════════════════════════════════════════
# Вспомогательные функции
# ═══════════════════════════════════════════════════════════

def get_usn_rate(
    income_total: Decimal,
    employee_count: int = 0,
    base_rate: Decimal = USN_RATE_INCOME_EXPENSE,
    elevated_rate: Decimal = USN_RATE_INCOME_EXPENSE_ELEVATED,
) -> Decimal:
    """
    Определить применимую ставку УСН на основе дохода и числа сотрудников.

    Если доход > базового лимита ИЛИ сотрудников > 100 → повышенная ставка.
    Если доход > повышенного лимита ИЛИ сотрудников > 130 → утрата права на УСН.
    """
    if income_total > USN_INCOME_LIMIT_ELEVATED or employee_count > USN_EMPLOYEE_LIMIT_ELEVATED:
        # Утрата права на УСН (возвращаем повышенную, но нужно уведомить)
        return elevated_rate

    if income_total > USN_INCOME_LIMIT_BASE or employee_count > USN_EMPLOYEE_LIMIT_BASE:
        return elevated_rate

    return base_rate


def get_ndfl_amount(income: Decimal) -> Decimal:
    """
    Рассчитать НДФЛ с учётом прогрессивной шкалы.

    До 5 млн → 13%, свыше → 15% с превышения.
    """
    if income <= Decimal("0"):
        return Decimal("0")

    if income <= NDFL_ELEVATED_THRESHOLD:
        return (income * NDFL_RATE_STANDARD / Decimal("100")).quantize(Decimal("0.01"))

    # Базовая часть: 5 000 000 × 13%
    base_tax = NDFL_ELEVATED_THRESHOLD * NDFL_RATE_STANDARD / Decimal("100")
    # Повышенная часть: (доход - 5 000 000) × 15%
    elevated_tax = (income - NDFL_ELEVATED_THRESHOLD) * NDFL_RATE_ELEVATED / Decimal("100")

    return (base_tax + elevated_tax).quantize(Decimal("0.01"))
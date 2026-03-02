"""
Валидаторы данных: ИНН, КПП, БИК, суммы.
"""
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional


def validate_inn(inn: str) -> tuple[bool, str]:
    """
    Валидация ИНН по контрольной сумме.
    Поддерживает ИНН юрлиц (10 цифр) и физлиц/ИП (12 цифр).
    
    Returns:
        (is_valid, error_message)
    """
    if not inn:
        return False, "ИНН не указан"
    
    # Убираем пробелы
    inn = inn.strip()
    
    if not inn.isdigit():
        return False, f"ИНН должен содержать только цифры, получено: '{inn}'"
    
    if len(inn) == 10:
        return _validate_inn_10(inn)
    elif len(inn) == 12:
        return _validate_inn_12(inn)
    else:
        return False, f"ИНН должен содержать 10 или 12 цифр, получено: {len(inn)}"


def _validate_inn_10(inn: str) -> tuple[bool, str]:
    """Валидация ИНН юридического лица (10 цифр)."""
    weights = [2, 4, 10, 3, 5, 9, 4, 6, 8]
    check_sum = sum(int(inn[i]) * weights[i] for i in range(9)) % 11 % 10
    
    if check_sum == int(inn[9]):
        return True, ""
    else:
        return False, f"Неверная контрольная сумма ИНН (10 цифр): {inn}"


def _validate_inn_12(inn: str) -> tuple[bool, str]:
    """Валидация ИНН физического лица / ИП (12 цифр)."""
    # Проверка первой контрольной цифры (11-й символ)
    weights_11 = [7, 2, 4, 10, 3, 5, 9, 4, 6, 8]
    check_sum_11 = sum(int(inn[i]) * weights_11[i] for i in range(10)) % 11 % 10
    
    if check_sum_11 != int(inn[10]):
        return False, f"Неверная первая контрольная цифра ИНН (12 цифр): {inn}"
    
    # Проверка второй контрольной цифры (12-й символ)
    weights_12 = [3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8]
    check_sum_12 = sum(int(inn[i]) * weights_12[i] for i in range(11)) % 11 % 10
    
    if check_sum_12 != int(inn[11]):
        return False, f"Неверная вторая контрольная цифра ИНН (12 цифр): {inn}"
    
    return True, ""


def validate_kpp(kpp: str) -> tuple[bool, str]:
    """
    Валидация КПП (код причины постановки на учёт).
    Формат: NNNNPPXXX, где:
    - NNNN — код налоговой (4 цифры)
    - PP — причина постановки (2 цифры или буквы A-Z)
    - XXX — порядковый номер (3 цифры)
    
    Returns:
        (is_valid, error_message)
    """
    if not kpp:
        return False, "КПП не указан"
    
    kpp = kpp.strip()
    
    if len(kpp) != 9:
        return False, f"КПП должен содержать 9 символов, получено: {len(kpp)}"
    
    # Первые 4 символа — цифры (код налоговой)
    if not kpp[:4].isdigit():
        return False, f"Первые 4 символа КПП должны быть цифрами: {kpp[:4]}"
    
    # 5-6 символы — цифры или заглавные латинские буквы
    for i in range(4, 6):
        if not (kpp[i].isdigit() or (kpp[i].isalpha() and kpp[i].isupper() and kpp[i].isascii())):
            return False, f"Символы 5-6 КПП должны быть цифрами или заглавными латинскими буквами: {kpp[4:6]}"
    
    # Последние 3 символа — цифры
    if not kpp[6:].isdigit():
        return False, f"Последние 3 символа КПП должны быть цифрами: {kpp[6:]}"
    
    return True, ""


def validate_bik(bik: str) -> tuple[bool, str]:
    """
    Валидация БИК (банковский идентификационный код).
    Формат: 9 цифр, начинается с «04» (Россия).
    
    Returns:
        (is_valid, error_message)
    """
    if not bik:
        return False, "БИК не указан"
    
    bik = bik.strip()
    
    if not bik.isdigit():
        return False, f"БИК должен содержать только цифры: '{bik}'"
    
    if len(bik) != 9:
        return False, f"БИК должен содержать 9 цифр, получено: {len(bik)}"
    
    if not bik.startswith("04"):
        return False, f"БИК должен начинаться с '04': {bik}"
    
    return True, ""


def validate_amounts_consistency(
    total_without_vat: Decimal,
    vat_amount: Decimal,
    total_with_vat: Decimal,
    tolerance: Decimal = Decimal("1.00"),
) -> tuple[bool, str]:
    """
    Проверка соответствия сумм: total_with_vat ≈ total_without_vat + vat_amount.
    Допускается погрешность округления.
    
    Args:
        total_without_vat: Сумма без НДС
        vat_amount: Сумма НДС
        total_with_vat: Сумма с НДС
        tolerance: Допустимая погрешность (по умолчанию 1 рубль)
    
    Returns:
        (is_valid, error_message)
    """
    expected = total_without_vat + vat_amount
    diff = abs(total_with_vat - expected)
    
    if diff <= tolerance:
        return True, ""
    else:
        return False, (
            f"Несоответствие сумм: {total_without_vat} + {vat_amount} = {expected}, "
            f"но указано {total_with_vat} (разница: {diff})"
        )


def validate_item_amounts(
    quantity: Decimal,
    price_without_vat: Decimal,
    vat_rate: Decimal,
    vat_amount: Decimal,
    total_with_vat: Decimal,
    tolerance: Decimal = Decimal("1.00"),
) -> tuple[bool, list[str]]:
    """
    Проверка корректности расчётов по позиции документа.
    
    Returns:
        (is_valid, list_of_errors)
    """
    errors = []
    
    # Расчёт суммы без НДС
    expected_sum_without_vat = (quantity * price_without_vat).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    
    # Расчёт ожидаемого НДС
    if vat_rate > 0:
        expected_vat = (expected_sum_without_vat * vat_rate / Decimal("100")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        if abs(vat_amount - expected_vat) > tolerance:
            errors.append(
                f"НДС: ожидалось {expected_vat} ({vat_rate}% от {expected_sum_without_vat}), "
                f"получено {vat_amount}"
            )
    
    # Расчёт ожидаемого итого
    expected_total = expected_sum_without_vat + vat_amount
    if abs(total_with_vat - expected_total) > tolerance:
        errors.append(
            f"Итого: ожидалось {expected_total} ({expected_sum_without_vat} + {vat_amount}), "
            f"получено {total_with_vat}"
        )
    
    return len(errors) == 0, errors
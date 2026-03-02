"""
Сервис генерации и валидации налоговых деклараций.
Пункт плана: 1.13.2

Поддерживаемые декларации:
- УСН (ст. 346.23 НК РФ) — годовая
- НДС (ст. 174 НК РФ) — квартальная
- 6-НДФЛ (ст. 230 НК РФ) — квартальная / годовая
- РСВ (ст. 431 НК РФ) — квартальная / годовая

Генерирует XML в формате ФНС, проводит XSD-валидацию
и проверку контрольных соотношений.
"""

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from io import BytesIO
from typing import Any
from xml.etree.ElementTree import Element, SubElement, tostring, indent

from sqlalchemy import select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.enums import (
    CalculationStatus,
    DeclarationStatus,
    DeclarationType,
    PeriodType,
    TaxType,
)
from app.models.tax_calculation import TaxCalculation
from app.models.tax_declaration import TaxDeclaration
from app.models.user import User

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# Dataclass-ы результатов
# ═══════════════════════════════════════════════════════════════


@dataclass
class XsdValidationResult:
    """Результат XSD-валидации."""
    valid: bool = True
    errors: list[str] = field(default_factory=list)


@dataclass
class ControlRatioError:
    """Ошибка контрольного соотношения."""
    code: str = ""           # Код КС (например «1.1»)
    description: str = ""    # Описание
    expected: str = ""       # Ожидаемое значение
    actual: str = ""         # Фактическое значение
    severity: str = "error"  # error / warning


@dataclass
class ControlRatiosResult:
    """Результат проверки контрольных соотношений."""
    valid: bool = True
    errors: list[ControlRatioError] = field(default_factory=list)
    warnings: list[ControlRatioError] = field(default_factory=list)


@dataclass
class DeclarationGenerationResult:
    """Результат генерации декларации."""
    declaration_id: str = ""
    declaration_type: str = ""
    period: str = ""
    year: int = 0
    xml_content: str = ""
    xsd_valid: bool = False
    xsd_errors: list[str] = field(default_factory=list)
    control_ratios_valid: bool = False
    control_ratios_errors: list[dict[str, Any]] = field(default_factory=list)
    status: str = "draft"
    warnings: list[str] = field(default_factory=list)


# ═══════════════════════════════════════════════════════════════
# XML-генераторы деклараций
# ═══════════════════════════════════════════════════════════════


class UsnXmlGenerator:
    """Генератор XML декларации по УСН."""

    @staticmethod
    def generate(
        user: User,
        year: int,
        calculation: TaxCalculation | None,
    ) -> str:
        """
        Сгенерировать XML декларации УСН.

        Формат: упрощённый XML, приближённый к формату ФНС.
        В реальной системе используется полная XSD-схема.
        """
        root = Element("Файл")
        root.set("ИдФайл", f"NO_USN_26.2-2_{year}_{uuid.uuid4().hex[:8]}")
        root.set("ВерсФорм", "5.09")
        root.set("ВерсПрог", "AI-Buhgalter 1.0")

        # Документ
        doc = SubElement(root, "Документ")
        doc.set("КНД", "1152017")  # КНД декларации УСН
        doc.set("ДатаДок", datetime.now().strftime("%d.%m.%Y"))
        doc.set("Период", "34")    # 34 = год
        doc.set("ОтчетГод", str(year))

        # Сведения о налогоплательщике
        np = SubElement(doc, "СвНП")
        np_fl = SubElement(np, "НПФЛ")
        np_fl.set("ИННФЛ", user.inn or "000000000000")
        np_fl.set("ФИО", user.full_name or "")

        # Раздел 2.2 — расчёт налога (доходы минус расходы)
        section = SubElement(doc, "Расч_УСН_ДР")

        if calculation:
            details = calculation.details_json or {}

            # Доходы и расходы по кварталам (из details)
            quarters = details.get("quarters", {})
            for q_num in range(1, 5):
                q_key = str(q_num)
                q_data = quarters.get(q_key, {})

                q_el = SubElement(section, f"Показ_К{q_num}")
                q_el.set("Доход", str(q_data.get("income", "0")))
                q_el.set("Расход", str(q_data.get("expense", "0")))

            # Итоги
            totals = SubElement(section, "Итого")
            totals.set("ДоходВсего", str(calculation.income_total))
            totals.set("РасходВсего", str(calculation.expense_total))
            totals.set("НалБаза", str(calculation.tax_base))
            totals.set("Ставка", str(calculation.tax_rate))
            totals.set("НалИсчисл", str(calculation.tax_amount))
            totals.set("МинНалог", str(calculation.min_tax_amount))
            totals.set("СтрахВзносВычет", str(calculation.insurance_deduction))
        else:
            # Пустая декларация
            totals = SubElement(section, "Итого")
            totals.set("ДоходВсего", "0")
            totals.set("РасходВсего", "0")
            totals.set("НалБаза", "0")
            totals.set("Ставка", "15")
            totals.set("НалИсчисл", "0")
            totals.set("МинНалог", "0")

        indent(root)
        return '<?xml version="1.0" encoding="UTF-8"?>\n' + tostring(
            root, encoding="unicode"
        )


class VatXmlGenerator:
    """Генератор XML декларации по НДС."""

    @staticmethod
    def generate(
        user: User,
        year: int,
        quarter: int,
        calculation: TaxCalculation | None,
    ) -> str:
        """Сгенерировать XML декларации НДС."""
        root = Element("Файл")
        root.set("ИдФайл", f"NO_NDS_{year}_Q{quarter}_{uuid.uuid4().hex[:8]}")
        root.set("ВерсФорм", "5.08")
        root.set("ВерсПрог", "AI-Buhgalter 1.0")

        doc = SubElement(root, "Документ")
        doc.set("КНД", "1151001")  # КНД декларации НДС
        doc.set("ДатаДок", datetime.now().strftime("%d.%m.%Y"))
        doc.set("Период", _quarter_to_period_code(quarter))
        doc.set("ОтчетГод", str(year))

        # Налогоплательщик
        np = SubElement(doc, "СвНП")
        np.set("ИНН", user.inn or "000000000000")
        np.set("НаимОрг", user.business_name or user.full_name or "")

        # Раздел 3 — расчёт суммы НДС
        section3 = SubElement(doc, "Разд3")

        if calculation:
            details = calculation.details_json or {}

            section3.set("НДСНачисл", str(calculation.vat_charged))
            section3.set("НДСВычет", str(calculation.vat_deductible))
            section3.set("НДСУплате", str(calculation.vat_payable))

            # Ежемесячные платежи
            monthly = details.get("monthly_payments", [])
            for i, amount in enumerate(monthly):
                mp = SubElement(section3, f"ЕжМесПл_{i + 1}")
                mp.set("Сумма", str(amount))
        else:
            section3.set("НДСНачисл", "0")
            section3.set("НДСВычет", "0")
            section3.set("НДСУплате", "0")

        indent(root)
        return '<?xml version="1.0" encoding="UTF-8"?>\n' + tostring(
            root, encoding="unicode"
        )


class Ndfl6XmlGenerator:
    """Генератор XML расчёта 6-НДФЛ."""

    @staticmethod
    def generate(
        user: User,
        year: int,
        quarter: int | None,
        calculation: TaxCalculation | None,
    ) -> str:
        """Сгенерировать XML расчёта 6-НДФЛ."""
        root = Element("Файл")
        root.set("ИдФайл", f"NO_NDFL6_{year}_{uuid.uuid4().hex[:8]}")
        root.set("ВерсФорм", "5.06")
        root.set("ВерсПрог", "AI-Buhgalter 1.0")

        doc = SubElement(root, "Документ")
        doc.set("КНД", "1151100")  # КНД формы 6-НДФЛ
        doc.set("ДатаДок", datetime.now().strftime("%d.%m.%Y"))
        if quarter:
            doc.set("Период", _quarter_to_period_code(quarter))
        else:
            doc.set("Период", "34")  # Год
        doc.set("ОтчетГод", str(year))

        # Налогоплательщик
        np = SubElement(doc, "СвНП")
        np.set("ИНН", user.inn or "000000000000")
        np.set("НаимОрг", user.business_name or user.full_name or "")

        # Раздел 1 — обобщённые данные
        section1 = SubElement(doc, "Разд1")

        if calculation:
            section1.set("НачислДоход", str(calculation.income_total))
            section1.set("ИсчислНДФЛ", str(calculation.tax_amount))
            section1.set("Ставка", str(calculation.tax_rate))
        else:
            section1.set("НачислДоход", "0")
            section1.set("ИсчислНДФЛ", "0")
            section1.set("Ставка", "13")

        indent(root)
        return '<?xml version="1.0" encoding="UTF-8"?>\n' + tostring(
            root, encoding="unicode"
        )


class RsvXmlGenerator:
    """Генератор XML расчёта по страховым взносам (РСВ)."""

    @staticmethod
    def generate(
        user: User,
        year: int,
        quarter: int | None,
        calculation: TaxCalculation | None,
    ) -> str:
        """Сгенерировать XML РСВ."""
        root = Element("Файл")
        root.set("ИдФайл", f"NO_RSV_{year}_{uuid.uuid4().hex[:8]}")
        root.set("ВерсФорм", "1.02")
        root.set("ВерсПрог", "AI-Buhgalter 1.0")

        doc = SubElement(root, "Документ")
        doc.set("КНД", "1151111")  # КНД формы РСВ
        doc.set("ДатаДок", datetime.now().strftime("%d.%m.%Y"))
        if quarter:
            doc.set("Период", _quarter_to_period_code(quarter))
        else:
            doc.set("Период", "34")
        doc.set("ОтчетГод", str(year))

        np = SubElement(doc, "СвНП")
        np.set("ИНН", user.inn or "000000000000")
        np.set("НаимОрг", user.business_name or user.full_name or "")

        section1 = SubElement(doc, "Разд1")

        if calculation:
            section1.set("БазаВзносов", str(calculation.tax_base))
            section1.set("ИсчислВзнос", str(calculation.tax_amount))
            section1.set("Ставка", str(calculation.tax_rate))
        else:
            section1.set("БазаВзносов", "0")
            section1.set("ИсчислВзнос", "0")
            section1.set("Ставка", "30")

        indent(root)
        return '<?xml version="1.0" encoding="UTF-8"?>\n' + tostring(
            root, encoding="unicode"
        )


# ═══════════════════════════════════════════════════════════════
# Сервис генерации деклараций
# ═══════════════════════════════════════════════════════════════


class DeclarationGeneratorService:
    """
    Сервис генерации и валидации налоговых деклараций.

    Основные обязанности:
    1. Формирование XML в формате ФНС
    2. XSD-валидация сгенерированного XML
    3. Проверка контрольных соотношений (КС)
    4. Сохранение декларации в БД
    """

    # Маппинг типа декларации → тип налога для поиска расчёта
    _TYPE_TO_TAX: dict[DeclarationType, TaxType] = {
        DeclarationType.USN: TaxType.USN,
        DeclarationType.VAT: TaxType.VAT,
        DeclarationType.NDFL_6: TaxType.NDFL,
        DeclarationType.RSV: TaxType.INSURANCE_EMPLOYEE,
    }

    def __init__(self, db: AsyncSession, user: User):
        self.db = db
        self.user = user

    # ─── Основной метод генерации ──────────────────────────

    async def generate(
        self,
        declaration_type: DeclarationType,
        year: int,
        quarter: int | None = None,
    ) -> DeclarationGenerationResult:
        """
        Сгенерировать налоговую декларацию.

        1. Находит последний расчёт налога за период
        2. Генерирует XML
        3. Валидирует XSD + контрольные соотношения
        4. Сохраняет в БД
        5. Возвращает результат
        """
        logger.info(
            "Generating %s declaration for year=%d quarter=%s user=%s",
            declaration_type.value, year, quarter, self.user.id,
        )

        # 1. Определяем период
        period = self._build_period_string(year, quarter)

        # 2. Ищем расчёт налога
        calculation = await self._find_calculation(declaration_type, year, quarter)

        # 3. Генерируем XML
        xml_content = self._generate_xml(declaration_type, year, quarter, calculation)

        # 4. Валидация XSD
        xsd_result = self._validate_xsd(xml_content, declaration_type)

        # 5. Контрольные соотношения
        cr_result = self._check_control_ratios(
            declaration_type, year, quarter, calculation
        )

        # 6. Определяем статус
        if xsd_result.valid and cr_result.valid:
            status = DeclarationStatus.VALIDATED
        elif xsd_result.valid and not cr_result.valid:
            status = DeclarationStatus.VALIDATION_ERROR
        else:
            status = DeclarationStatus.GENERATED

        # 7. Сохраняем в БД
        declaration = TaxDeclaration(
            user_id=self.user.id,
            declaration_type=declaration_type,
            period=period,
            year=year,
            xml_content=xml_content,
            status=status,
            validation_errors=json.dumps(
                {
                    "xsd_errors": xsd_result.errors,
                    "control_ratios_errors": [
                        {
                            "code": e.code,
                            "description": e.description,
                            "expected": e.expected,
                            "actual": e.actual,
                            "severity": e.severity,
                        }
                        for e in cr_result.errors
                    ],
                },
                ensure_ascii=False,
            ) if not (xsd_result.valid and cr_result.valid) else None,
            linked_calculation_id=calculation.id if calculation else None,
        )
        self.db.add(declaration)
        await self.db.flush()

        # 8. Формируем результат
        warnings: list[str] = []
        if calculation is None:
            warnings.append(
                f"Расчёт {declaration_type.value} за {period} не найден. "
                f"Декларация сформирована с нулевыми значениями."
            )
        for w in cr_result.warnings:
            warnings.append(f"КС {w.code}: {w.description}")

        return DeclarationGenerationResult(
            declaration_id=declaration.id,
            declaration_type=declaration_type.value,
            period=period,
            year=year,
            xml_content=xml_content,
            xsd_valid=xsd_result.valid,
            xsd_errors=xsd_result.errors,
            control_ratios_valid=cr_result.valid,
            control_ratios_errors=[
                {
                    "code": e.code,
                    "description": e.description,
                    "expected": e.expected,
                    "actual": e.actual,
                    "severity": e.severity,
                }
                for e in cr_result.errors
            ],
            status=status.value,
            warnings=warnings,
        )

    # ─── Валидация существующей декларации ─────────────────

    async def validate(
        self, declaration_id: str
    ) -> dict[str, Any]:
        """
        Валидировать существующую декларацию по ID.

        Выполняет XSD-валидацию и проверку контрольных соотношений.
        Обновляет статус декларации в БД.
        """
        result = await self.db.execute(
            select(TaxDeclaration).where(
                and_(
                    TaxDeclaration.id == declaration_id,
                    TaxDeclaration.user_id == self.user.id,
                )
            )
        )
        declaration = result.scalar_one_or_none()
        if not declaration:
            raise ValueError(f"Декларация {declaration_id} не найдена")

        xml_content = declaration.xml_content or ""

        # XSD-валидация
        xsd_result = self._validate_xsd(xml_content, declaration.declaration_type)

        # Ищем связанный расчёт для контрольных соотношений
        calculation = None
        if declaration.linked_calculation_id:
            calc_result = await self.db.execute(
                select(TaxCalculation).where(
                    TaxCalculation.id == declaration.linked_calculation_id
                )
            )
            calculation = calc_result.scalar_one_or_none()

        # Контрольные соотношения
        quarter = self._extract_quarter_from_period(declaration.period)
        cr_result = self._check_control_ratios(
            declaration.declaration_type, declaration.year, quarter, calculation
        )

        # Обновляем статус
        if xsd_result.valid and cr_result.valid:
            declaration.status = DeclarationStatus.VALIDATED
        else:
            declaration.status = DeclarationStatus.VALIDATION_ERROR

        declaration.validation_errors = json.dumps(
            {
                "xsd_errors": xsd_result.errors,
                "control_ratios_errors": [
                    {
                        "code": e.code,
                        "description": e.description,
                        "expected": e.expected,
                        "actual": e.actual,
                        "severity": e.severity,
                    }
                    for e in cr_result.errors
                ],
            },
            ensure_ascii=False,
        ) if not (xsd_result.valid and cr_result.valid) else None

        await self.db.flush()

        return {
            "declaration_id": declaration.id,
            "xsd_valid": xsd_result.valid,
            "xsd_errors": xsd_result.errors,
            "control_ratios_valid": cr_result.valid,
            "control_ratios_errors": [
                {
                    "code": e.code,
                    "description": e.description,
                    "expected": e.expected,
                    "actual": e.actual,
                    "severity": e.severity,
                }
                for e in cr_result.errors
            ],
            "status": declaration.status.value,
        }

    # ─── Получение списка деклараций ───────────────────────

    async def get_list(
        self,
        year: int | None = None,
        declaration_type: DeclarationType | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[TaxDeclaration]:
        """Получить список деклараций пользователя."""
        query = select(TaxDeclaration).where(
            TaxDeclaration.user_id == self.user.id
        )

        if year:
            query = query.where(TaxDeclaration.year == year)
        if declaration_type:
            query = query.where(TaxDeclaration.declaration_type == declaration_type)

        query = query.order_by(desc(TaxDeclaration.created_at)).offset(skip).limit(limit)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    # ─── Получение одной декларации ────────────────────────

    async def get_by_id(self, declaration_id: str) -> TaxDeclaration | None:
        """Получить декларацию по ID."""
        result = await self.db.execute(
            select(TaxDeclaration).where(
                and_(
                    TaxDeclaration.id == declaration_id,
                    TaxDeclaration.user_id == self.user.id,
                )
            )
        )
        return result.scalar_one_or_none()

    # ─── Приватные методы ──────────────────────────────────

    async def _find_calculation(
        self,
        declaration_type: DeclarationType,
        year: int,
        quarter: int | None,
    ) -> TaxCalculation | None:
        """Найти последний расчёт налога за период."""
        tax_type = self._TYPE_TO_TAX.get(declaration_type)
        if not tax_type:
            logger.warning("No tax type mapping for %s", declaration_type)
            return None

        # Определяем границы периода
        if quarter:
            from app.services.tax_calculation_service import get_quarter_dates
            period_start, period_end = get_quarter_dates(year, quarter)
        else:
            from app.services.tax_calculation_service import get_year_dates
            period_start, period_end = get_year_dates(year)

        result = await self.db.execute(
            select(TaxCalculation)
            .where(
                and_(
                    TaxCalculation.user_id == self.user.id,
                    TaxCalculation.tax_type == tax_type,
                    TaxCalculation.period_start == period_start,
                    TaxCalculation.period_end == period_end,
                )
            )
            .order_by(desc(TaxCalculation.updated_at))
            .limit(1)
        )
        return result.scalar_one_or_none()

    def _generate_xml(
        self,
        declaration_type: DeclarationType,
        year: int,
        quarter: int | None,
        calculation: TaxCalculation | None,
    ) -> str:
        """Сгенерировать XML нужного типа."""
        if declaration_type == DeclarationType.USN:
            return UsnXmlGenerator.generate(self.user, year, calculation)
        elif declaration_type == DeclarationType.VAT:
            q = quarter or 4
            return VatXmlGenerator.generate(self.user, year, q, calculation)
        elif declaration_type == DeclarationType.NDFL_6:
            return Ndfl6XmlGenerator.generate(self.user, year, quarter, calculation)
        elif declaration_type == DeclarationType.RSV:
            return RsvXmlGenerator.generate(self.user, year, quarter, calculation)
        else:
            raise ValueError(f"Неподдерживаемый тип декларации: {declaration_type}")

    def _validate_xsd(
        self, xml_content: str, declaration_type: DeclarationType
    ) -> XsdValidationResult:
        """
        XSD-валидация XML.

        Примечание: полная XSD-валидация требует наличия XSD-схем ФНС.
        Сейчас выполняется базовая структурная проверка.
        В production-версии подключаются реальные XSD-файлы.
        """
        result = XsdValidationResult()
        errors: list[str] = []

        # Базовые проверки структуры
        if not xml_content or not xml_content.strip():
            errors.append("XML-документ пуст")
            result.valid = False
            result.errors = errors
            return result

        if '<?xml' not in xml_content:
            errors.append("Отсутствует XML-заголовок")

        if '<Файл' not in xml_content:
            errors.append("Отсутствует корневой элемент <Файл>")

        if '<Документ' not in xml_content:
            errors.append("Отсутствует элемент <Документ>")

        # Проверяем КНД соответствие
        knd_map = {
            DeclarationType.USN: "1152017",
            DeclarationType.VAT: "1151001",
            DeclarationType.NDFL_6: "1151100",
            DeclarationType.RSV: "1151111",
        }
        expected_knd = knd_map.get(declaration_type, "")
        if expected_knd and expected_knd not in xml_content:
            errors.append(
                f"Несоответствие КНД: ожидается {expected_knd} "
                f"для декларации {declaration_type.value}"
            )

        if errors:
            result.valid = False
            result.errors = errors

        return result

    def _check_control_ratios(
        self,
        declaration_type: DeclarationType,
        year: int,
        quarter: int | None,
        calculation: TaxCalculation | None,
    ) -> ControlRatiosResult:
        """
        Проверка контрольных соотношений (КС) ФНС.

        Реализованы основные КС для каждого типа декларации.
        Полный перечень КС — в письмах ФНС.
        """
        if declaration_type == DeclarationType.USN:
            return self._check_usn_control_ratios(calculation)
        elif declaration_type == DeclarationType.VAT:
            return self._check_vat_control_ratios(calculation)
        elif declaration_type == DeclarationType.NDFL_6:
            return self._check_ndfl6_control_ratios(calculation)
        elif declaration_type == DeclarationType.RSV:
            return self._check_rsv_control_ratios(calculation)
        else:
            return ControlRatiosResult()

    def _check_usn_control_ratios(
        self, calculation: TaxCalculation | None
    ) -> ControlRatiosResult:
        """Контрольные соотношения для УСН."""
        result = ControlRatiosResult()

        if not calculation:
            result.warnings.append(ControlRatioError(
                code="USN.0",
                description="Расчёт УСН не найден — проверка КС невозможна",
                severity="warning",
            ))
            return result

        # КС 1: Налоговая база = Доходы - Расходы (при >= 0)
        expected_base = max(
            calculation.income_total - calculation.expense_total,
            Decimal("0"),
        )
        if calculation.tax_base != expected_base:
            result.errors.append(ControlRatioError(
                code="USN.1",
                description="Налоговая база ≠ Доходы − Расходы",
                expected=str(expected_base),
                actual=str(calculation.tax_base),
            ))
            result.valid = False

        # КС 2: Сумма налога = База × Ставка / 100
        expected_tax = (
            calculation.tax_base * calculation.tax_rate / Decimal("100")
        ).quantize(Decimal("0.01"))
        if calculation.tax_amount != expected_tax:
            # Допускаем расхождение, если применён минимальный налог
            if calculation.min_tax_amount <= Decimal("0") or calculation.tax_amount != calculation.min_tax_amount:
                result.errors.append(ControlRatioError(
                    code="USN.2",
                    description="Исчисленный налог ≠ База × Ставка",
                    expected=str(expected_tax),
                    actual=str(calculation.tax_amount),
                ))
                result.valid = False

        # КС 3 (warning): Ставка должна быть 15% или 20%
        valid_rates = [Decimal("15"), Decimal("20"), Decimal("6"), Decimal("8")]
        if calculation.tax_rate not in valid_rates:
            result.warnings.append(ControlRatioError(
                code="USN.3",
                description=f"Нестандартная ставка УСН: {calculation.tax_rate}%",
                expected="15 или 20 (доходы-расходы) / 6 или 8 (доходы)",
                actual=str(calculation.tax_rate),
                severity="warning",
            ))

        return result

    def _check_vat_control_ratios(
        self, calculation: TaxCalculation | None
    ) -> ControlRatiosResult:
        """Контрольные соотношения для НДС."""
        result = ControlRatiosResult()

        if not calculation:
            result.warnings.append(ControlRatioError(
                code="VAT.0",
                description="Расчёт НДС не найден — проверка КС невозможна",
                severity="warning",
            ))
            return result

        # КС 1: НДС к уплате = Начисленный - Вычеты
        expected_payable = calculation.vat_charged - calculation.vat_deductible
        if calculation.vat_payable != expected_payable:
            result.errors.append(ControlRatioError(
                code="VAT.1",
                description="НДС к уплате ≠ Начисленный − Вычеты",
                expected=str(expected_payable),
                actual=str(calculation.vat_payable),
            ))
            result.valid = False

        # КС 2 (warning): Доля вычетов > 89%
        if calculation.vat_charged > Decimal("0"):
            deduction_ratio = (
                calculation.vat_deductible / calculation.vat_charged * Decimal("100")
            )
            if deduction_ratio > Decimal("89"):
                result.warnings.append(ControlRatioError(
                    code="VAT.2",
                    description=(
                        f"Доля вычетов НДС ({deduction_ratio:.1f}%) превышает "
                        f"безопасный порог 89%. Высокий риск камеральной проверки."
                    ),
                    expected="≤ 89%",
                    actual=f"{deduction_ratio:.1f}%",
                    severity="warning",
                ))

        # КС 3 (warning): Отрицательный НДС (к возмещению)
        if calculation.vat_payable < Decimal("0"):
            result.warnings.append(ControlRatioError(
                code="VAT.3",
                description="НДС к возмещению — будет камеральная проверка",
                expected=">= 0",
                actual=str(calculation.vat_payable),
                severity="warning",
            ))

        return result

    def _check_ndfl6_control_ratios(
        self, calculation: TaxCalculation | None
    ) -> ControlRatiosResult:
        """Контрольные соотношения для 6-НДФЛ."""
        result = ControlRatiosResult()

        if not calculation:
            result.warnings.append(ControlRatioError(
                code="NDFL6.0",
                description="Расчёт НДФЛ не найден — проверка КС невозможна",
                severity="warning",
            ))
            return result

        # КС 1: Сумма НДФЛ не может превышать доход
        if calculation.tax_amount > calculation.income_total:
            result.errors.append(ControlRatioError(
                code="NDFL6.1",
                description="Исчисленный НДФЛ превышает начисленный доход",
                expected=f"≤ {calculation.income_total}",
                actual=str(calculation.tax_amount),
            ))
            result.valid = False

        # КС 2 (warning): Ставка
        valid_rates = [Decimal("13"), Decimal("15"), Decimal("30"), Decimal("35")]
        if calculation.tax_rate not in valid_rates:
            result.warnings.append(ControlRatioError(
                code="NDFL6.2",
                description=f"Нестандартная ставка НДФЛ: {calculation.tax_rate}%",
                expected="13, 15, 30 или 35",
                actual=str(calculation.tax_rate),
                severity="warning",
            ))

        return result

    def _check_rsv_control_ratios(
        self, calculation: TaxCalculation | None
    ) -> ControlRatiosResult:
        """Контрольные соотношения для РСВ."""
        result = ControlRatiosResult()

        if not calculation:
            result.warnings.append(ControlRatioError(
                code="RSV.0",
                description="Расчёт страховых взносов не найден — проверка КС невозможна",
                severity="warning",
            ))
            return result

        # КС 1: Взносы не отрицательные
        if calculation.tax_amount < Decimal("0"):
            result.errors.append(ControlRatioError(
                code="RSV.1",
                description="Исчисленные взносы не могут быть отрицательными",
                expected=">= 0",
                actual=str(calculation.tax_amount),
            ))
            result.valid = False

        # КС 2: База не отрицательная
        if calculation.tax_base < Decimal("0"):
            result.errors.append(ControlRatioError(
                code="RSV.2",
                description="База для начисления взносов не может быть отрицательной",
                expected=">= 0",
                actual=str(calculation.tax_base),
            ))
            result.valid = False

        return result

    @staticmethod
    def _build_period_string(year: int, quarter: int | None) -> str:
        """Построить строку периода: '2026-Q1' или '2026'."""
        if quarter:
            return f"{year}-Q{quarter}"
        return str(year)

    @staticmethod
    def _extract_quarter_from_period(period: str) -> int | None:
        """Извлечь квартал из строки периода."""
        if "-Q" in period:
            try:
                return int(period.split("-Q")[1])
            except (ValueError, IndexError):
                return None
        return None


# ═══════════════════════════════════════════════════════════════
# Всп��могательные функции
# ═══════════════════════════════════════════════════════════════


def _quarter_to_period_code(quarter: int) -> str:
    """Код периода ФНС для квартала: 21, 22, 23, 24."""
    codes = {1: "21", 2: "22", 3: "23", 4: "24"}
    return codes.get(quarter, "21")
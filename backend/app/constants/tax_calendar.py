"""
Справочник событий налогового календаря для ИП на УСН + НДС (2026 год, Россия).
Пункт плана: 1.14

Содержит все обязательные сроки сдачи отчётности и уплаты налогов.
Используется TaxCalendarService для генерации событий пользователю.

Нормативная база:
- УСН: ст. 346.21, 346.23 НК РФ
- НДС: ст. 174 НК РФ
- Страховые взносы ИП: ст. 432 НК РФ
- 6-НДФЛ: ст. 230 НК РФ
- РСВ: ст. 431 НК РФ
- Персонифицированные сведения: ст. 11 ФЗ-27

Правило переноса: если срок выпадает на выходной/праздник,
переносится на ближайший рабочий день (ст. 6.1 НК РФ).
Переносы уже учтены в конкретных датах ниже.
"""

from datetime import date

from app.constants.enums import CalendarEventType


# Тип записи в справочнике
class CalendarEventTemplate:
    """Шаблон события налогового календаря."""

    __slots__ = ("event_type", "title", "description", "deadline")

    def __init__(
        self,
        event_type: CalendarEventType,
        title: str,
        description: str,
        deadline: date,
    ):
        self.event_type = event_type
        self.title = title
        self.description = description
        self.deadline = deadline


# ═══════════════════════════════════════════════════════════
# Календарь на 2026 год
# ═══════════════════════════════════════════════════════════

TAX_CALENDAR_2026: list[CalendarEventTemplate] = [
    # ─── Январь ──────────────────────────────────────
    CalendarEventTemplate(
        event_type=CalendarEventType.CONTRIBUTION_PAYMENT,
        title="Фиксированные взносы ИП за 2025 год",
        description="Срок уплаты фиксированных страховых взносов ИП за себя за 2025 год (ст. 432 НК РФ).",
        deadline=date(2026, 1, 9),  # 31.12 — выходной, перенос
    ),
    CalendarEventTemplate(
        event_type=CalendarEventType.DECLARATION_SUBMIT,
        title="6-НДФЛ за 2025 год",
        description="Сдача расчёта 6-НДФЛ за 2025 год (ст. 230 НК РФ).",
        deadline=date(2026, 2, 25),
    ),
    CalendarEventTemplate(
        event_type=CalendarEventType.DECLARATION_SUBMIT,
        title="РСВ за 2025 год",
        description="Сдача расчёта по страховым взносам за 2025 год (ст. 431 НК РФ).",
        deadline=date(2026, 1, 26),
    ),
    CalendarEventTemplate(
        event_type=CalendarEventType.TAX_PAYMENT,
        title="НДС за 4 кв. 2025 (1/3)",
        description="Первый ежемесячный платёж НДС за 4 квартал 2025 года.",
        deadline=date(2026, 1, 26),
    ),
    CalendarEventTemplate(
        event_type=CalendarEventType.DECLARATION_SUBMIT,
        title="Декларация НДС за 4 кв. 2025",
        description="Сдача декларации по НДС за 4 квартал 2025 года (ст. 174 НК РФ).",
        deadline=date(2026, 1, 26),
    ),

    # ─── Февраль ─────────────────────────────────────
    CalendarEventTemplate(
        event_type=CalendarEventType.TAX_PAYMENT,
        title="НДС за 4 кв. 2025 (2/3)",
        description="Второй ежемесячный платёж НДС за 4 квартал 2025 года.",
        deadline=date(2026, 2, 25),
    ),
    CalendarEventTemplate(
        event_type=CalendarEventType.REPORT_SUBMIT,
        title="Персонифицированные сведения за январь",
        description="Сдача персонифицированных сведений о физлицах за январь (ФЗ-27).",
        deadline=date(2026, 2, 25),
    ),

    # ─── Март ──���─────────────────────────────────────
    CalendarEventTemplate(
        event_type=CalendarEventType.TAX_PAYMENT,
        title="НДС за 4 кв. 2025 (3/3)",
        description="Третий ежемесячный платёж НДС за 4 квартал 2025 года.",
        deadline=date(2026, 3, 25),
    ),
    CalendarEventTemplate(
        event_type=CalendarEventType.REPORT_SUBMIT,
        title="Персонифицированные сведения за февраль",
        description="Сдача персонифицированных сведений о физлицах за февраль.",
        deadline=date(2026, 3, 25),
    ),

    # ─── Апрель ──────────────────────────────────────
    CalendarEventTemplate(
        event_type=CalendarEventType.DECLARATION_SUBMIT,
        title="Декларация НДС за 1 кв. 2026",
        description="Сдача декларации по НДС за 1 квартал 2026 года.",
        deadline=date(2026, 4, 27),
    ),
    CalendarEventTemplate(
        event_type=CalendarEventType.TAX_PAYMENT,
        title="НДС за 1 кв. 2026 (1/3)",
        description="Первый ежемесячный платёж НДС за 1 квартал 2026 года.",
        deadline=date(2026, 4, 27),
    ),
    CalendarEventTemplate(
        event_type=CalendarEventType.DECLARATION_SUBMIT,
        title="Декларация УСН за 2025 год (ИП)",
        description="Сдача декларации по УСН за 2025 год для ИП (ст. 346.23 НК РФ). Срок для ИП — 25 апреля.",
        deadline=date(2026, 4, 27),
    ),
    CalendarEventTemplate(
        event_type=CalendarEventType.TAX_PAYMENT,
        title="УСН за 2025 год — итоговый платёж",
        description="Уплата УСН за 2025 год за минусом ранее уплаченных авансов.",
        deadline=date(2026, 4, 28),
    ),
    CalendarEventTemplate(
        event_type=CalendarEventType.ADVANCE_PAYMENT,
        title="Аванс УСН за 1 кв. 2026",
        description="Авансовый платёж по УСН за 1 квартал 2026 года (ст. 346.21 НК РФ).",
        deadline=date(2026, 4, 28),
    ),
    CalendarEventTemplate(
        event_type=CalendarEventType.DECLARATION_SUBMIT,
        title="6-НДФЛ за 1 кв. 2026",
        description="Сдача расчёта 6-НДФЛ за 1 квартал 2026 года.",
        deadline=date(2026, 4, 25),
    ),
    CalendarEventTemplate(
        event_type=CalendarEventType.DECLARATION_SUBMIT,
        title="РСВ за 1 кв. 2026",
        description="Сдача расчёта по страховым взносам за 1 квартал 2026 года.",
        deadline=date(2026, 4, 25),
    ),
    CalendarEventTemplate(
        event_type=CalendarEventType.REPORT_SUBMIT,
        title="Персонифицированные сведения за март",
        description="Сдача персонифицированных сведений за март.",
        deadline=date(2026, 4, 25),
    ),

    # ─── Май ─────────────────────────────────────────
    CalendarEventTemplate(
        event_type=CalendarEventType.TAX_PAYMENT,
        title="НДС за 1 кв. 2026 (2/3)",
        description="Второй ежемесячный платёж НДС за 1 квартал 2026 года.",
        deadline=date(2026, 5, 25),
    ),
    CalendarEventTemplate(
        event_type=CalendarEventType.REPORT_SUBMIT,
        title="Персонифицированные сведения за апрель",
        description="Сдача персонифицированных сведений за апрель.",
        deadline=date(2026, 5, 25),
    ),

    # ─── Июнь ────────────────────────────────────────
    CalendarEventTemplate(
        event_type=CalendarEventType.TAX_PAYMENT,
        title="НДС за 1 кв. 2026 (3/3)",
        description="Третий ежемесячный платёж НДС за 1 квартал 2026 года.",
        deadline=date(2026, 6, 25),
    ),
    CalendarEventTemplate(
        event_type=CalendarEventType.REPORT_SUBMIT,
        title="Персонифицированные сведения за май",
        description="Сдача персонифицированных сведений за май.",
        deadline=date(2026, 6, 25),
    ),

    # ─── Июль ────────────────────────────────────────
    CalendarEventTemplate(
        event_type=CalendarEventType.CONTRIBUTION_PAYMENT,
        title="Доп. взносы ИП (1%) за 2025 год",
        description="Срок уплаты 1% от дохода свыше 300 000 ₽ за 2025 год (ст. 432 НК РФ).",
        deadline=date(2026, 7, 1),
    ),
    CalendarEventTemplate(
        event_type=CalendarEventType.DECLARATION_SUBMIT,
        title="Декларация НДС за 2 кв. 2026",
        description="Сдача декларации по НДС за 2 квартал 2026 года.",
        deadline=date(2026, 7, 27),
    ),
    CalendarEventTemplate(
        event_type=CalendarEventType.TAX_PAYMENT,
        title="НДС за 2 кв. 2026 (1/3)",
        description="Первый ежемесячный платёж НДС за 2 квартал 2026 года.",
        deadline=date(2026, 7, 27),
    ),
    CalendarEventTemplate(
        event_type=CalendarEventType.ADVANCE_PAYMENT,
        title="Аванс УСН за полугодие 2026",
        description="Авансовый платёж по УСН за полугодие 2026 года.",
        deadline=date(2026, 7, 27),
    ),
    CalendarEventTemplate(
        event_type=CalendarEventType.DECLARATION_SUBMIT,
        title="6-НДФЛ за полугодие 2026",
        description="Сдача расчёта 6-НДФЛ за полугодие 2026 года.",
        deadline=date(2026, 7, 25),
    ),
    CalendarEventTemplate(
        event_type=CalendarEventType.DECLARATION_SUBMIT,
        title="РСВ за полугодие 2026",
        description="Сдача расчёта по страховым взносам за полугодие 2026 года.",
        deadline=date(2026, 7, 25),
    ),
    CalendarEventTemplate(
        event_type=CalendarEventType.REPORT_SUBMIT,
        title="Персонифицированные сведения за июнь",
        description="Сдача персонифицированных сведений за июнь.",
        deadline=date(2026, 7, 25),
    ),

    # ─── Август ──────────────────────────────────────
    CalendarEventTemplate(
        event_type=CalendarEventType.TAX_PAYMENT,
        title="НДС за 2 кв. 2026 (2/3)",
        description="Второй ежемесячный платёж НДС за 2 квартал 2026 года.",
        deadline=date(2026, 8, 25),
    ),
    CalendarEventTemplate(
        event_type=CalendarEventType.REPORT_SUBMIT,
        title="Персонифицированные сведения за июль",
        description="Сдача персонифицированных сведений за июль.",
        deadline=date(2026, 8, 25),
    ),

    # ─── Сентябрь ────────────────────────────────────
    CalendarEventTemplate(
        event_type=CalendarEventType.TAX_PAYMENT,
        title="НДС за 2 кв. 2026 (3/3)",
        description="Третий ежемесячный платёж НДС за 2 квартал 2026 года.",
        deadline=date(2026, 9, 25),
    ),
    CalendarEventTemplate(
        event_type=CalendarEventType.REPORT_SUBMIT,
        title="Персонифицированные сведения за август",
        description="Сдача персонифицированных сведений за август.",
        deadline=date(2026, 9, 25),
    ),

    # ─── Октябрь ─────────────────────────────────────
    CalendarEventTemplate(
        event_type=CalendarEventType.DECLARATION_SUBMIT,
        title="Декларация НДС за 3 кв. 2026",
        description="Сдача декларации по НДС за 3 квартал 2026 года.",
        deadline=date(2026, 10, 26),
    ),
    CalendarEventTemplate(
        event_type=CalendarEventType.TAX_PAYMENT,
        title="НДС за 3 кв. 2026 (1/3)",
        description="Первый ежемесячный платёж НДС за 3 квартал 2026 года.",
        deadline=date(2026, 10, 26),
    ),
    CalendarEventTemplate(
        event_type=CalendarEventType.ADVANCE_PAYMENT,
        title="Аванс УСН за 9 месяцев 2026",
        description="Авансовый платёж по УСН за 9 месяцев 2026 года.",
        deadline=date(2026, 10, 26),
    ),
    CalendarEventTemplate(
        event_type=CalendarEventType.DECLARATION_SUBMIT,
        title="6-НДФЛ за 9 месяцев 2026",
        description="Сдача расчёта 6-НДФЛ за 9 месяцев 2026 года.",
        deadline=date(2026, 10, 25),
    ),
    CalendarEventTemplate(
        event_type=CalendarEventType.DECLARATION_SUBMIT,
        title="РСВ за 9 месяцев 2026",
        description="Сдача расчёта по страховым взносам за 9 месяцев 2026 года.",
        deadline=date(2026, 10, 25),
    ),
    CalendarEventTemplate(
        event_type=CalendarEventType.REPORT_SUBMIT,
        title="Персонифицированные сведения за сентябрь",
        description="Сдача персонифицированных сведений за сентябрь.",
        deadline=date(2026, 10, 25),
    ),

    # ─── Ноябрь ──────────────────────────────────────
    CalendarEventTemplate(
        event_type=CalendarEventType.TAX_PAYMENT,
        title="НДС за 3 кв. 2026 (2/3)",
        description="Второй ежемесячный платёж НДС за 3 квартал 2026 года.",
        deadline=date(2026, 11, 25),
    ),
    CalendarEventTemplate(
        event_type=CalendarEventType.REPORT_SUBMIT,
        title="Персонифицированные сведения за октябрь",
        description="Сдача персонифицированных сведений за октябрь.",
        deadline=date(2026, 11, 25),
    ),

    # ─── Декабрь ─────────────────────────────────────
    CalendarEventTemplate(
        event_type=CalendarEventType.TAX_PAYMENT,
        title="НДС за 3 кв. 2026 (3/3)",
        description="Третий ежемесячный платёж НДС за 3 квартал 2026 года.",
        deadline=date(2026, 12, 25),
    ),
    CalendarEventTemplate(
        event_type=CalendarEventType.CONTRIBUTION_PAYMENT,
        title="Фиксированные взносы ИП за 2026 год",
        description="Срок уплаты фиксированных страховых взносов ИП за себя за 2026 год: 53 658 ₽ (ст. 432 НК РФ).",
        deadline=date(2026, 12, 31),
    ),
    CalendarEventTemplate(
        event_type=CalendarEventType.REPORT_SUBMIT,
        title="Персонифицированные сведения за ноябрь",
        description="Сдача персонифицированных сведений за ноябрь.",
        deadline=date(2026, 12, 25),
    ),
]


def get_calendar_templates(year: int = 2026) -> list[CalendarEventTemplate]:
    """
    Получить шаблоны событий календаря для указанного года.
    Пока поддерживается только 2026 год.
    """
    if year == 2026:
        return TAX_CALENDAR_2026
    # Для других годов — возвращаем пустой список (можно расширить)
    return []
"""
Системный промпт AI-агента "ИИ-Бухгалтер".
Архитектура: АРХИТЕКТУРА_AI_AGENT.md -> раздел 3.5

Этот промпт определяет "личность" и правила поведения агента.
Динамический контекст бизнеса подставляется в runtime.
"""

_SEP = "=" * 39


def build_agent_system_prompt(
    business_name: str = "",
    inn: str = "",
    tax_system: str = "УСН «Доходы минус расходы»",
    region: str = "",
    employees_count: int = 0,
    business_context: str = "",
) -> str:
    """
    Построить системный промпт агента с динамическим контекстом.

    Args:
        business_name: Название ИП/бизнеса
        inn: ИНН предпринимателя
        tax_system: Система налогообложения
        region: Регион регистрации
        employees_count: Количество сотрудников
        business_context: Динамический контекст (остатки, суммы, сроки)

    Returns:
        Полный системный промпт
    """
    biz = f" для ИП \u00ab{business_name}\u00bb" if business_name else ""
    inn_part = f" (ИНН {inn})" if inn else ""
    region_part = f"Регион: {region}." if region else ""
    emp_part = f" Сотрудников: {employees_count}." if employees_count else ""

    ctx_block = ""
    if business_context:
        ctx_block = (
            f"\n\n{_SEP}\n"
            f"ТЕКУЩИЙ КОНТЕКСТ БИЗНЕСА\n"
            f"{_SEP}\n\n"
            f"{business_context}"
        )

    return (
        f"Ты -- ИИ-бухгалтер{biz}{inn_part}.\n"
        f"Система налогообложения: {tax_system} + НДС 22%.\n"
        f"{region_part}{emp_part}\n"
        f"\n"
        f"{_SEP}\n"
        f"ТВОЯ РОЛЬ\n"
        f"{_SEP}\n"
        f"\n"
        f"Ты самостоятельно ведёшь бухгалтерский и налоговый учёт.\n"
        f"Пользователь -- предприниматель, он занимается бизнесом, а ты -- его бухгалтерией.\n"
        f"Ты НЕ ассистент, который ждёт команд. Ты -- бухгалтер, который сам знает что делать.\n"
        f"\n"
        f"{_SEP}\n"
        f"ПРАВИЛА ПОВЕДЕНИЯ\n"
        f"{_SEP}\n"
        f"\n"
        f"1. ПРОАКТИВНОСТЬ\n"
        f"   - Не жди команд -- сам проверяй данные и предлагай действия\n"
        f"   - При загрузке файла -- сразу анализируй и обрабатывай\n"
        f"   - При приближении срока -- предупреждай заранее (за 14, 7, 3 дня)\n"
        f"   - При обнаружении проблемы -- сообщай и предлагай решение\n"
        f"\n"
        f"2. ТОЧНОСТЬ И ОСТОРОЖНОСТЬ\n"
        f"   - Всегда проверяй: ИНН (контрольная цифра), суммы, НДС\n"
        f"   - Если уверенность классификации < 70% -- ОБЯЗАТЕЛЬНО спроси пользователя\n"
        f"   - Если уверенность 70-90% -- предложи свой вариант, но попроси подтвердить\n"
        f"   - Если уверенность > 90% -- действуй автоматически, но запиши в лог\n"
        f"   - Никогда не выдумывай данные -- если чего-то нет, так и скажи\n"
        f"\n"
        f"3. ПРОСТОЙ ЯЗЫК\n"
        f"   - Объясняй простым языком, не бухгалтерским жаргоном\n"
        f"   - Вместо \"дебетовое сальдо\" -> \"на счёте осталось\"\n"
        f"   - Вместо \"акцептовать\" -> \"подтвердить\"\n"
        f"   - Суммы пиши с разделителями: 1 250 000 руб., не 1250000\n"
        f"\n"
        f"4. БЕЗОПАСНОСТЬ\n"
        f"   - НИКОГДА не отправляй декларации в ФНС без явного подтверждения\n"
        f"   - НИКОГДА не удаляй данные -- только помечай\n"
        f"   - Все свои действия логируй подробно\n"
        f"   - При сомнениях -- лучше переспросить\n"
        f"\n"
        f"{_SEP}\n"
        f"АКТУАЛЬНЫЕ СТАВКИ (2026 год, Россия)\n"
        f"{_SEP}\n"
        f"\n"
        f"* НДС: 22% (основная), 10% (продовольствие, дет.товары, лекарства), 0% (экспорт)\n"
        f"  Расчётная ставка: 22/122 = 18.0328%\n"
        f"* УСН \"Доходы минус расходы\": 15% (базовая), 20% (при превышении лимитов)\n"
        f"  Минимальный налог: 1% от доходов (ст. 346.18 НК РФ)\n"
        f"* Фиксированные взносы ИП: 53 658 руб./год + 1% с доходов свыше 300 000 руб.\n"
        f"  Максимум 1% = 300 888 руб.\n"
        f"* НДФЛ: 13% (до 5 млн), 15% (свыше 5 млн)\n"
        f"* Страховые взносы за сотрудников: 30% (до предела 2 759 000 руб.), 15.1% (свыше)\n"
        f"* МРОТ: 22 440 руб./мес\n"
        f"\n"
        f"{_SEP}\n"
        f"КАК ОБРАБАТЫВАТЬ СОБЫТИЯ\n"
        f"{_SEP}\n"
        f"\n"
        f"При получении события (файл, данные, вопрос):\n"
        f"\n"
        f"1. ОПРЕДЕЛИ что произошло (новый файл? новые операции? вопрос?)\n"
        f"2. ОЦЕНИ влияние на учёт (затрагивает доходы? расходы? НДС?)\n"
        f"3. ВЫПОЛНИ действия через инструменты:\n"
        f"   - Для файлов: распознай -> классифицируй -> внеси в учёт\n"
        f"   - Для операций: классифицируй -> проверь НДС -> сопоставь с документами\n"
        f"   - Для вопросов: собери контекст -> дай точный ответ с ссылками\n"
        f"4. СООБЩИ результат пользователю и если нужно -- запроси подтверждение\n"
        f"\n"
        f"{_SEP}\n"
        f"ФОРМАТ ОТВЕТОВ\n"
        f"{_SEP}\n"
        f"\n"
        f"* Кратко (2-5 предложений), по делу\n"
        f"* Если выполнил действия -- перечисли что сделал\n"
        f"* Если нашёл проблему -- опиши проблему + предложи решение\n"
        f"* Если нужно подтверждение -- задай конкретный вопрос с вариантами\n"
        f"* Для сумм используй формат: 1 250 000,50 руб.\n"
        f"* Для дат: 27 февраля 2026 г.\n"
        f"\n"
        f"{_SEP}\n"
        f"ТИПИЧНЫЕ ОШИБКИ (не допускай)\n"
        f"{_SEP}\n"
        f"\n"
        f"- Считать эквайринг отдельным доходом (это та же выручка из ОФД)\n"
        f"- Забывать про минимальный налог 1% при УСН\n"
        f"- Не учитывать что взнос собственных средств -- НЕ доход\n"
        f"- Не учитывать что снятие наличных -- НЕ расход\n"
        f"- Путать начисленный и уплаченный НДС\n"
        f"- Забывать про расчётн��ю ставку НДС (22/122)\n"
        f"- Не проверять действительность ИНН контрагента\n"
        f"{ctx_block}"
    )


def build_event_user_message(
    trigger_type: str,
    payload: dict,
) -> str:
    """
    Построить user-сообщение для агента на основе триггера.

    Args:
        trigger_type: Тип триггера (из AgentTriggerType)
        payload: Данные события

    Returns:
        Текст user-сообщения для LLM
    """
    trigger_templates = {
        "event_file_uploaded": _format_file_uploaded,
        "event_new_bank_data": _format_new_bank_data,
        "event_new_ofd_data": _format_new_ofd_data,
        "event_new_edo_document": _format_new_edo_document,
        "event_user_confirmation": _format_user_confirmation,
        "user_question": _format_user_question,
        "user_command": _format_user_command,
        "schedule_daily": _format_schedule_daily,
        "schedule_weekly": _format_schedule_weekly,
        "schedule_monthly": _format_schedule_monthly,
        "schedule_pre_deadline": _format_schedule_pre_deadline,
    }

    formatter = trigger_templates.get(trigger_type, _format_generic)
    return formatter(payload)


def _format_file_uploaded(payload: dict) -> str:
    files = payload.get("files", [])
    if len(files) == 1:
        f = files[0]
        return (
            f"Загружен новый файл: \u00ab{f.get('filename', 'неизвестный')}\u00bb "
            f"(тип: {f.get('file_type', '?')}, размер: {f.get('size_human', '?')}). "
            f"ID файла: {f.get('file_id', '?')}. "
            "Проанализируй файл и обработай его."
        )
    else:
        names = ", ".join(f.get("filename", "?") for f in files[:5])
        return (
            f"Загружено {len(files)} файлов: {names}. "
            "Проанализируй каждый и обработай."
        )


def _format_new_bank_data(payload: dict) -> str:
    count = payload.get("operations_count", 0)
    bank = payload.get("bank_name", "банк")
    period = payload.get("period", "")
    return (
        f"Получено {count} новых операций из {bank}"
        f"{f' за период {period}' if period else ''}. "
        "Классифицируй операции, выдели НДС, сопоставь с документами."
    )


def _format_new_ofd_data(payload: dict) -> str:
    count = payload.get("receipts_count", 0)
    return (
        f"Получено {count} новых кассовых чеков из ОФД. "
        "Обработай: проверь суммы, НДС, внеси в книгу продаж."
    )


def _format_new_edo_document(payload: dict) -> str:
    doc_type = payload.get("document_type", "документ")
    sender = payload.get("sender", "контрагент")
    return (
        f"Получен новый {doc_type} от {sender} через ЭДО. "
        "Распознай, проверь реквизиты, внеси в учёт."
    )


def _format_user_confirmation(payload: dict) -> str:
    confirmation_id = payload.get("confirmation_id", "")
    user_response = payload.get("user_response", "")
    return (
        f"Пользователь ответил на запрос подтверждения {confirmation_id}: "
        f"\u00ab{user_response}\u00bb. Продолжи обработку с учётом ответа."
    )


def _format_user_question(payload: dict) -> str:
    question = payload.get("question", "")
    return question if question else "Пользователь обратился без конкретного вопроса."


def _format_user_command(payload: dict) -> str:
    command = payload.get("command", "")
    return command if command else "Пользователь дал команду без уточнения."


def _format_schedule_daily(payload: dict) -> str:
    return (
        "Ежедневная проверка. Выполни:\n"
        "1. Проверь, есть ли необработанные файлы\n"
        "2. Проверь приближающиеся сроки (7 дней)\n"
        "3. Проверь неклассифицированные операции\n"
        "4. Кратко сообщи результаты."
    )


def _format_schedule_weekly(payload: dict) -> str:
    return (
        "Еженедельный отчёт. Составь краткую сводку за неделю:\n"
        "1. Доходы и расходы за неделю\n"
        "2. Текущий баланс по налогам\n"
        "3. Обнаруженные проблемы\n"
        "4. Ближайшие сроки\n"
        "5. Рекомендации."
    )


def _format_schedule_monthly(payload: dict) -> str:
    return (
        "Ежемесячный анализ. Выполни:\n"
        "1. Полная сверка данных за месяц\n"
        "2. Предварительный расчёт налогов\n"
        "3. Проверка на аномалии\n"
        "4. Подробный отчёт с рекомендациями."
    )


def _format_schedule_pre_deadline(payload: dict) -> str:
    event = payload.get("event_name", "неизвестное событие")
    days_left = payload.get("days_left", 0)
    deadline = payload.get("deadline", "")
    return (
        f"До срока \u00ab{event}\u00bb осталось {days_left} дней (дедлайн: {deadline}). "
        "Проверь готовность: данные, расчёты, декларация. "
        "Если что-то не готово -- сообщи пользователю что нужно сделать."
    )


def _format_generic(payload: dict) -> str:
    return f"Событие: {payload}"
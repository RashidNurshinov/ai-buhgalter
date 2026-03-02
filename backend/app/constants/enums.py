"""
Все Enum-классы проекта «ИИ-Бухгалтер».
Справочник: СПРАВОЧНИК_СУЩНОСТЕЙ.md → раздел «Перечисления (Enum)»

ВАЖНО: Это единственный источник правды для enum-значений.
Миграции, модели и схемы ОБЯЗАНЫ ссылаться на этот файл.
"""

import enum


# ─── User ───────────────────────────────────────────────
class TaxSystem(str, enum.Enum):
    """Система налогообложения."""
    USN_INCOME_EXPENSE = "usn_income_expense"  # УСН «Доходы − Расходы» 15 %
    USN_INCOME = "usn_income"                  # УСН «Доходы» 6 %
    OSNO = "osno"                              # ОСНО (общая)
    PATENT = "patent"                          # Патент (ПСН)
    ESHN = "eshn"                              # ЕСХН


class UserRole(str, enum.Enum):
    """Роль пользователя."""
    OWNER = "owner"
    ACCOUNTANT = "accountant"
    VIEWER = "viewer"


# ─── Document ───────────────────────────────────────────
class DocumentType(str, enum.Enum):
    """Тип первичного документа."""
    INVOICE = "invoice"                # Счёт-фактура
    UPD = "upd"                        # Универсальный передаточный документ
    TORG12 = "torg12"                  # ТОРГ-12
    ACT = "act"                        # Акт выполненных работ
    BILL = "bill"                      # Счёт на оплату
    CASH_RECEIPT = "cash_receipt"      # Кассовый чек
    BANK_STATEMENT = "bank_statement"  # Банковская выписка
    CONTRACT = "contract"              # Договор
    PAYMENT_ORDER = "payment_order"    # Платёжное поручение
    OTHER = "other"                    # Прочее


class DocumentStatus(str, enum.Enum):
    """Статус обработки документа."""
    UPLOADING = "uploading"            # Загружается
    PROCESSING = "processing"          # Обрабатывается (OCR/парсинг)
    RECOGNIZED = "recognized"          # Распознан, ждёт подтверждения
    CONFIRMED = "confirmed"            # Подтверждён пользователем
    REJECTED = "rejected"              # Отклонён
    ERROR = "error"                    # Ошибка обработки


class DocumentSource(str, enum.Enum):
    """Источник документа."""
    MANUAL_UPLOAD = "manual_upload"    # Ручная загрузка
    EDO = "edo"                        # ЭДО (Сфера, СБИС, Диадок)
    OFD = "ofd"                        # ОФД
    EMAIL = "email"                    # Получено по email
    BANK_SYNC = "bank_sync"           # Синхронизация с банком
    MOYSKLAD = "moysklad"             # Мой Склад


# ─── Bank Operation ────────────────────────────────────
class OperationCategory(str, enum.Enum):
    """Категория банковской операции."""
    # Доходы
    SALES_REVENUE = "sales_revenue"               # Выручка от продаж
    ACQUIRING = "acquiring"                       # Поступление по эквайрингу
    SUPPLIER_RETURN = "supplier_return"           # Возврат от поставщика
    OTHER_INCOME = "other_income"                 # Прочие доходы
    # Не доходы
    OWN_FUNDS = "own_funds"                       # Взнос собственных средств
    INTERNAL_TRANSFER = "internal_transfer"       # Перевод между своими счетами
    LOAN_RECEIVED = "loan_received"               # Получение кредита/займа
    # Расходы
    PURCHASE_GOODS = "purchase_goods"             # Закупка товара
    RENT = "rent"                                 # Аренда
    SALARY = "salary"                             # Зарплата
    TAXES_AND_FEES = "taxes_and_fees"             # Налоги и взносы
    INSURANCE_PAYMENT = "insurance_payment"       # Страховые взносы
    BANK_COMMISSION = "bank_commission"           # Комиссия банка
    UTILITIES = "utilities"                       # Коммунальные услуги
    TRANSPORT = "transport"                       # Транспорт/доставка
    ADVERTISING = "advertising"                   # Реклама
    SERVICES = "services"                         # Услуги (связь, интернет и т.п.)
    LOAN_REPAYMENT = "loan_repayment"             # Погашение кредита
    OTHER_EXPENSE = "other_expense"               # Прочие расходы
    # Не расходы
    PERSONAL_WITHDRAWAL = "personal_withdrawal"   # Снятие на личные нужды
    CASH_WITHDRAWAL = "cash_withdrawal"           # Снятие наличных
    # Неклассифицировано
    UNCLASSIFIED = "unclassified"                 # Не классифицировано


class OperationStatus(str, enum.Enum):
    """Статус банковской операции."""
    PENDING = "pending"                # Ожидает классификации
    CLASSIFIED = "classified"          # Классифицировано ИИ
    CONFIRMED = "confirmed"            # Подтверждено пользователем
    RECLASSIFIED = "reclassified"      # Переклассифицировано вручную


# ─── Cash Receipt ──────────────────────────────────────
class PaymentType(str, enum.Enum):
    """Тип оплаты кассового чека."""
    CASH = "cash"                      # Наличные
    CARD = "card"                      # Карта (эквайринг)
    TRANSFER = "transfer"              # Безналичный перевод
    ONLINE = "online"                  # Онлайн-оплата
    MIXED = "mixed"                    # Смешанная


# ─── Tax Calculation ───────────────────────────────────
class TaxType(str, enum.Enum):
    """Тип налога."""
    USN = "usn"                                  # УСН
    VAT = "vat"                                  # НДС
    NDFL = "ndfl"                                # НДФЛ
    INSURANCE_EMPLOYEE = "insurance_employee"    # Страх. взносы за сотрудников
    INSURANCE_IP = "insurance_ip"                # Фиксированные взносы ИП


class PeriodType(str, enum.Enum):
    """Тип налогового периода."""
    MONTH = "month"
    QUARTER = "quarter"
    HALF_YEAR = "half_year"
    NINE_MONTHS = "nine_months"
    YEAR = "year"


class CalculationStatus(str, enum.Enum):
    """Статус расчёта налога."""
    PRELIMINARY = "preliminary"        # Предварительный
    FINAL = "final"                    # Итоговый
    CONFIRMED = "confirmed"            # Подтверждён
    PAID = "paid"                      # Оплачен


# ─── Tax Declaration ──────────────────────────────────
class DeclarationType(str, enum.Enum):
    """Тип налоговой декларации."""
    VAT = "vat"                        # Декларация НДС
    USN = "usn"                        # Декларация УСН
    NDFL_6 = "ndfl_6"                  # 6-НДФЛ
    RSV = "rsv"                        # РСВ
    PERSONIFIED = "personified"        # Персонифицированные сведения


class DeclarationStatus(str, enum.Enum):
    """Статус декларации."""
    DRAFT = "draft"                    # Черновик
    GENERATED = "generated"            # Сформирована
    VALIDATED = "validated"            # Прошла проверку
    VALIDATION_ERROR = "validation_error"  # Ошибка проверки
    SIGNED = "signed"                  # Подписана ЭЦП
    SUBMITTED = "submitted"            # Отправлена в ФНС
    ACCEPTED = "accepted"              # Принята ФНС
    REJECTED = "rejected"              # Отклонена ФНС


# ─── Tax Calendar ─────────────────────────────────────
class CalendarEventType(str, enum.Enum):
    """Тип события налогового календаря."""
    TAX_PAYMENT = "tax_payment"                       # Оплата налога
    DECLARATION_SUBMIT = "declaration_submit"          # Сдача декларации
    ADVANCE_PAYMENT = "advance_payment"               # Авансовый платёж
    CONTRIBUTION_PAYMENT = "contribution_payment"     # Оплата взносов
    REPORT_SUBMIT = "report_submit"                   # Сдача отчёта


class CalendarEventStatus(str, enum.Enum):
    """Статус события календаря."""
    UPCOMING = "upcoming"              # Предстоит
    OVERDUE = "overdue"                # Просрочено
    COMPLETED = "completed"            # Выполнено


# ─── Uploaded File ────────────────────────────────────
class FileType(str, enum.Enum):
    """Тип загруженного файла."""
    PDF = "pdf"
    XML = "xml"
    CSV = "csv"
    XLS = "xls"
    XLSX = "xlsx"
    JPG = "jpg"
    JPEG = "jpeg"
    PNG = "png"
    TIFF = "tiff"
    HEIC = "heic"
    OTHER = "other"


class ProcessingStatus(str, enum.Enum):
    """Статус обработки файла."""
    QUEUED = "queued"                  # В очереди
    PROCESSING = "processing"          # Обрабатывается
    COMPLETED = "completed"            # Завершено
    ERROR = "error"                    # Ошибка


# ─── Chat Role ────────────────────────────────────────
class ChatRole(str, enum.Enum):
    """Роль в чате с ИИ-помощником."""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


# ─── AI Agent ─────────────────────────────────────────
class AgentTriggerType(str, enum.Enum):
    """Тип триггера, запускающего цикл AI-агента."""
    # Событийные триггеры (event-driven)
    EVENT_FILE_UPLOADED = "event_file_uploaded"          # Загружен новый файл
    EVENT_NEW_BANK_DATA = "event_new_bank_data"          # Получены данные из банка
    EVENT_NEW_OFD_DATA = "event_new_ofd_data"            # Получены чеки из ОФД
    EVENT_NEW_EDO_DOCUMENT = "event_new_edo_document"    # Получен документ из ЭДО
    EVENT_USER_CONFIRMATION = "event_user_confirmation"  # Пользователь подтвердил/исправил
    # Пользовательские триггеры
    USER_QUESTION = "user_question"                      # Вопрос в чате
    USER_COMMAND = "user_command"                         # Прямая команда (рассчитай, сформируй)
    # Триггеры по расписанию (scheduled)
    SCHEDULE_DAILY = "schedule_daily"                    # Ежедневная проверка
    SCHEDULE_WEEKLY = "schedule_weekly"                  # Еженедельный отчёт
    SCHEDULE_MONTHLY = "schedule_monthly"                # Ежемесячный анализ
    SCHEDULE_PRE_DEADLINE = "schedule_pre_deadline"      # За N дней до срока сдачи


class AgentActionStatus(str, enum.Enum):
    """Статус действия AI-агента."""
    PENDING = "pending"              # Ожидает выполнения
    RUNNING = "running"              # Выполняется
    COMPLETED = "completed"          # Завершено успешно
    FAILED = "failed"                # Ошибка выполнения
    AWAITING_USER = "awaiting_user"  # Ожидает подтверждения пользователя
    CANCELLED = "cancelled"          # Отменено


class AgentActionType(str, enum.Enum):
    """Тип действия, выполненного агентом (для лога)."""
    # Получение данных
    TOOL_FETCH_BANK = "tool_fetch_bank"
    TOOL_FETCH_OFD = "tool_fetch_ofd"
    TOOL_FETCH_EDO = "tool_fetch_edo"
    TOOL_GET_FILES = "tool_get_files"
    TOOL_QUERY_EGRUL = "tool_query_egrul"
    TOOL_GET_CONTEXT = "tool_get_context"
    # Анализ и распознавание
    TOOL_RECOGNIZE_DOCUMENT = "tool_recognize_document"
    TOOL_PARSE_XML = "tool_parse_xml"
    TOOL_PARSE_TABLE = "tool_parse_table"
    TOOL_CLASSIFY_OPERATION = "tool_classify_operation"
    TOOL_CLASSIFY_BATCH = "tool_classify_batch"
    TOOL_MATCH_OPERATION = "tool_match_operation"
    TOOL_DETECT_DUPLICATES = "tool_detect_duplicates"
    TOOL_DETECT_ANOMALIES = "tool_detect_anomalies"
    # Расчёты и учёт
    TOOL_CALCULATE_TAXES = "tool_calculate_taxes"
    TOOL_GENERATE_KUDIR = "tool_generate_kudir"
    TOOL_GENERATE_PURCHASE_BOOK = "tool_generate_purchase_book"
    TOOL_GENERATE_SALES_BOOK = "tool_generate_sales_book"
    TOOL_RECONCILE = "tool_reconcile"
    # Отчётность
    TOOL_GENERATE_DECLARATION = "tool_generate_declaration"
    TOOL_VALIDATE_DECLARATION = "tool_validate_declaration"
    TOOL_EXPORT = "tool_export"
    # Уведомления
    TOOL_SEND_NOTIFICATION = "tool_send_notification"
    TOOL_REQUEST_CONFIRMATION = "tool_request_confirmation"
    TOOL_CREATE_REPORT = "tool_create_report"
    # Мета
    AGENT_THINKING = "agent_thinking"       # Агент рассуждает (LLM-вызов без tool)
    AGENT_ERROR = "agent_error"             # Ошибка агента
    AGENT_SUMMARY = "agent_summary"         # Итоговое резюме цикла


class AgentConfirmationType(str, enum.Enum):
    """Тип запроса подтверждения от пользователя."""
    OPERATION_CLASSIFICATION = "operation_classification"  # Подтвердить категорию операции
    DOCUMENT_RECOGNITION = "document_recognition"          # Подтвердить данные документа
    TAX_CALCULATION = "tax_calculation"                     # Подтвердить расчёт налога
    DECLARATION_SUBMIT = "declaration_submit"               # Подтвердить отправку декларации
    ANOMALY_RESOLUTION = "anomaly_resolution"               # Разрешить обнаруженную аномалию
    GENERAL = "general"                                     # Общий вопрос


class AgentConfirmationStatus(str, enum.Enum):
    """Статус подтверждения от пользователя."""
    PENDING = "pending"        # Ожидает ответа
    CONFIRMED = "confirmed"    # Подтверждено
    REJECTED = "rejected"      # Отклонено
    MODIFIED = "modified"      # Изменено и подтверждено
    EXPIRED = "expired"        # Истекло (не ответил)

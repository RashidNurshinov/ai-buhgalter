"""
Тесты перечислений (Enum).

Тестируем:
- Полноту значений каждого enum
- Строковое представление (str enum)
- Отсутствие дублей
- Совместимость с Pydantic
"""

import pytest

from app.constants.enums import (
    AgentActionStatus,
    AgentActionType,
    AgentConfirmationStatus,
    AgentConfirmationType,
    AgentTriggerType,
    CalculationStatus,
    CalendarEventStatus,
    CalendarEventType,
    ChatRole,
    DeclarationStatus,
    DeclarationType,
    DocumentSource,
    DocumentStatus,
    DocumentType,
    FileType,
    OperationCategory,
    OperationStatus,
    PaymentType,
    PeriodType,
    ProcessingStatus,
    TaxSystem,
    TaxType,
    UserRole,
)


class TestTaxSystem:
    """Тесты TaxSystem enum."""

    def test_all_values(self):
        """Все системы налогообложения присутствуют."""
        expected = {"usn_income_expense", "usn_income", "osno", "patent", "eshn"}
        actual = {ts.value for ts in TaxSystem}
        assert actual == expected

    def test_str_enum(self):
        """TaxSystem — строковый enum."""
        assert isinstance(TaxSystem.USN_INCOME_EXPENSE.value, str)
        assert str(TaxSystem.USN_INCOME_EXPENSE) == "TaxSystem.USN_INCOME_EXPENSE"

    def test_from_value(self):
        """Создание из строкового значения."""
        ts = TaxSystem("usn_income")
        assert ts == TaxSystem.USN_INCOME

    def test_invalid_value(self):
        """Невалидное значение вызывает ValueError."""
        with pytest.raises(ValueError):
            TaxSystem("invalid_system")


class TestOperationCategory:
    """Тесты OperationCategory enum."""

    def test_count(self):
        """Общее количество категорий."""
        assert len(OperationCategory) >= 20  # Достаточно категорий

    def test_income_categories_exist(self):
        """Категории доходов присутствуют."""
        income = {
            OperationCategory.SALES_REVENUE,
            OperationCategory.ACQUIRING,
            OperationCategory.SUPPLIER_RETURN,
            OperationCategory.OTHER_INCOME,
        }
        for cat in income:
            assert cat in OperationCategory

    def test_expense_categories_exist(self):
        """Категории расходов присутствуют."""
        expense = {
            OperationCategory.PURCHASE_GOODS,
            OperationCategory.RENT,
            OperationCategory.SALARY,
            OperationCategory.TAXES_AND_FEES,
        }
        for cat in expense:
            assert cat in OperationCategory

    def test_neutral_categories_exist(self):
        """Нейтральные категории (не доход и не расход)."""
        neutral = {
            OperationCategory.OWN_FUNDS,
            OperationCategory.INTERNAL_TRANSFER,
            OperationCategory.PERSONAL_WITHDRAWAL,
        }
        for cat in neutral:
            assert cat in OperationCategory

    def test_unclassified_exists(self):
        """Категория 'не классифицировано' есть."""
        assert OperationCategory.UNCLASSIFIED.value == "unclassified"

    def test_no_duplicate_values(self):
        """Нет дубликатов значений."""
        values = [c.value for c in OperationCategory]
        assert len(values) == len(set(values))


class TestOperationStatus:
    """Тесты OperationStatus enum."""

    def test_all_statuses(self):
        """Все статусы операций."""
        expected = {"pending", "classified", "confirmed", "reclassified"}
        actual = {s.value for s in OperationStatus}
        assert actual == expected

    def test_lifecycle_order(self):
        """Жизненный цикл: pending → classified → confirmed."""
        assert OperationStatus.PENDING.value == "pending"
        assert OperationStatus.CLASSIFIED.value == "classified"
        assert OperationStatus.CONFIRMED.value == "confirmed"


class TestTaxType:
    """Тесты TaxType enum."""

    def test_all_types(self):
        """Все типы налогов."""
        expected = {"usn", "vat", "ndfl", "insurance_employee", "insurance_ip"}
        actual = {t.value for t in TaxType}
        assert actual == expected


class TestPeriodType:
    """Тесты PeriodType enum."""

    def test_all_periods(self):
        """Все типы периодов."""
        expected = {"month", "quarter", "half_year", "nine_months", "year"}
        actual = {p.value for p in PeriodType}
        assert actual == expected


class TestDeclarationType:
    """Тесты DeclarationType enum."""

    def test_all_types(self):
        """Все типы деклараций."""
        expected = {"vat", "usn", "ndfl_6", "rsv", "personified"}
        actual = {d.value for d in DeclarationType}
        assert actual == expected


class TestDeclarationStatus:
    """Тесты DeclarationStatus enum."""

    def test_lifecycle(self):
        """Жизненный цикл декларации."""
        statuses = [s.value for s in DeclarationStatus]
        assert "draft" in statuses
        assert "generated" in statuses
        assert "submitted" in statuses
        assert "accepted" in statuses

    def test_count(self):
        """Количество статусов декларации."""
        assert len(DeclarationStatus) == 8


class TestDocumentType:
    """Тесты DocumentType enum."""

    def test_common_types(self):
        """Основные типы документов."""
        assert DocumentType.INVOICE.value == "invoice"
        assert DocumentType.UPD.value == "upd"
        assert DocumentType.TORG12.value == "torg12"
        assert DocumentType.BANK_STATEMENT.value == "bank_statement"
        assert DocumentType.OTHER.value == "other"


class TestCalendarEventType:
    """Тесты CalendarEventType enum."""

    def test_all_event_types(self):
        """Все типы событий календаря."""
        expected = {
            "tax_payment",
            "declaration_submit",
            "advance_payment",
            "contribution_payment",
            "report_submit",
        }
        actual = {e.value for e in CalendarEventType}
        assert actual == expected


class TestCalendarEventStatus:
    """Тесты CalendarEventStatus enum."""

    def test_all_statuses(self):
        """Все статусы событий."""
        expected = {"upcoming", "overdue", "completed"}
        actual = {s.value for s in CalendarEventStatus}
        assert actual == expected


class TestFileType:
    """Тесты FileType enum."""

    def test_image_types(self):
        """Типы изображений."""
        image_types = {FileType.JPG, FileType.JPEG, FileType.PNG, FileType.TIFF, FileType.HEIC}
        assert len(image_types) == 5

    def test_document_types(self):
        """Типы документов."""
        doc_types = {FileType.PDF, FileType.XML, FileType.CSV, FileType.XLS, FileType.XLSX}
        assert len(doc_types) == 5


class TestChatRole:
    """Тесты ChatRole enum."""

    def test_all_roles(self):
        """Все роли чата."""
        expected = {"user", "assistant", "system"}
        actual = {r.value for r in ChatRole}
        assert actual == expected


class TestAllEnumsNoDuplicates:
    """Проверка отсутствия дублей во всех enum."""

    @pytest.mark.parametrize("enum_cls", [
        TaxSystem, UserRole, DocumentType, DocumentStatus, DocumentSource,
        OperationCategory, OperationStatus, PaymentType, TaxType, PeriodType,
        CalculationStatus, DeclarationType, DeclarationStatus,
        CalendarEventType, CalendarEventStatus, FileType, ProcessingStatus,
        ChatRole, AgentTriggerType, AgentActionStatus, AgentActionType,
        AgentConfirmationType, AgentConfirmationStatus,
    ])
    def test_no_duplicate_values(self, enum_cls):
        """Нет дублей значений в enum {enum_cls.__name__}."""
        values = [member.value for member in enum_cls]
        assert len(values) == len(set(values)), (
            f"Дубликаты в {enum_cls.__name__}: "
            f"{[v for v in values if values.count(v) > 1]}"
        )

    @pytest.mark.parametrize("enum_cls", [
        TaxSystem, UserRole, DocumentType, DocumentStatus, DocumentSource,
        OperationCategory, OperationStatus, PaymentType, TaxType, PeriodType,
        CalculationStatus, DeclarationType, DeclarationStatus,
        CalendarEventType, CalendarEventStatus, FileType, ProcessingStatus,
        ChatRole,
    ])
    def test_is_str_enum(self, enum_cls):
        """Все enum наследуют str."""
        for member in enum_cls:
            assert isinstance(member.value, str)
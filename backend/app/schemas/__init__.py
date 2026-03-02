"""
Pydantic-схемы приложения.
Реэкспорт всех схем для удобного импорта.
"""

from app.schemas.bank_account import (
    BankAccountCreate,
    BankAccountResponse,
    BankAccountUpdate,
)
from app.schemas.bank_operation import (
    BankOperationFilter,
    BankOperationResponse,
    OperationConfirmRequest,
    OperationReclassifyRequest,
)
from app.schemas.cash_receipt import CashReceiptResponse
from app.schemas.common import (
    ErrorResponse,
    FileUploadResponse,
    PaginatedResponse,
    PaginationParams,
    StatusResponse,
)
from app.schemas.counterparty import (
    CounterpartyCreate,
    CounterpartyResponse,
    CounterpartyUpdate,
)
from app.schemas.dashboard import DashboardResponse, MonthlyAmount
from app.schemas.declaration import (
    DeclarationGenerateRequest,
    DeclarationResponse,
    DeclarationValidateResponse,
)
from app.schemas.document import (
    DocumentConfirmRequest,
    DocumentCreate,
    DocumentItemCreate,
    DocumentItemResponse,
    DocumentResponse,
    DocumentUpdate,
)
from app.schemas.kudir import KudirEntryResponse, KudirPeriodRequest, KudirPeriodResponse
from app.schemas.purchase_book import (
    PurchaseBookEntryResponse,
    PurchaseBookPeriodRequest,
    PurchaseBookPeriodResponse,
)
from app.schemas.reconciliation import (
    DiscrepancyItem,
    ReconciliationReportResponse,
    ReconciliationRunRequest,
)
from app.schemas.sales_book import (
    SalesBookEntryResponse,
    SalesBookPeriodRequest,
    SalesBookPeriodResponse,
)
from app.schemas.tax import (
    TaxCalculationRequest,
    TaxCalculationResponse,
    TaxSummaryResponse,
    VatSummaryResponse,
)
from app.schemas.tax_calendar import (
    TaxCalendarCompleteRequest,
    TaxCalendarEventResponse,
    TaxCalendarListResponse,
)
from app.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    RefreshTokenRequest,
    TokenResponse,
)
from app.schemas.user import (
    UserBriefResponse,
    UserResponse,
    UserUpdate,
)

__all__ = [
    # Auth
    "LoginRequest",
    "RegisterRequest",
    "RefreshTokenRequest",
    "TokenResponse",
    # User
    "UserResponse",
    "UserUpdate",
    "UserBriefResponse",
    # Counterparty
    "CounterpartyCreate",
    "CounterpartyUpdate",
    "CounterpartyResponse",
    # Bank Account
    "BankAccountCreate",
    "BankAccountUpdate",
    "BankAccountResponse",
    # Document
    "DocumentCreate",
    "DocumentUpdate",
    "DocumentResponse",
    "DocumentItemCreate",
    "DocumentItemResponse",
    "DocumentConfirmRequest",
    # Bank Operation
    "BankOperationResponse",
    "BankOperationFilter",
    "OperationConfirmRequest",
    "OperationReclassifyRequest",
    # Cash Receipt
    "CashReceiptResponse",
    # KUDiR
    "KudirEntryResponse",
    "KudirPeriodResponse",
    "KudirPeriodRequest",
    # Purchase Book
    "PurchaseBookEntryResponse",
    "PurchaseBookPeriodRequest",
    "PurchaseBookPeriodResponse",
    # Sales Book
    "SalesBookEntryResponse",
    "SalesBookPeriodRequest",
    "SalesBookPeriodResponse",
    # Tax
    "TaxCalculationRequest",
    "TaxCalculationResponse",
    "TaxSummaryResponse",
    "VatSummaryResponse",
    # Declaration
    "DeclarationGenerateRequest",
    "DeclarationResponse",
    "DeclarationValidateResponse",
    # Tax Calendar
    "TaxCalendarEventResponse",
    "TaxCalendarListResponse",
    "TaxCalendarCompleteRequest",
    # Reconciliation
    "ReconciliationReportResponse",
    "ReconciliationRunRequest",
    "DiscrepancyItem",
    # Dashboard
    "DashboardResponse",
    "MonthlyAmount",
    # Common
    "PaginationParams",
    "PaginatedResponse",
    "StatusResponse",
    "ErrorResponse",
    "FileUploadResponse",
]
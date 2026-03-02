"""
Реестр всех SQLAlchemy-моделей.
Импортируется в Alembic env.py для автогенерации миграций.
"""

from app.models.base import BaseModel  # noqa: F401
from app.models.user import User  # noqa: F401
from app.models.counterparty import Counterparty  # noqa: F401
from app.models.bank_account import BankAccount  # noqa: F401
from app.models.document import Document, DocumentItem  # noqa: F401
from app.models.bank_operation import BankOperation  # noqa: F401
from app.models.cash_receipt import CashReceipt  # noqa: F401
from app.models.kudir_entry import KudirEntry  # noqa: F401
from app.models.book_entry import PurchaseBookEntry, SalesBookEntry  # noqa: F401
from app.models.tax_calculation import TaxCalculation  # noqa: F401
from app.models.tax_declaration import TaxDeclaration  # noqa: F401
from app.models.tax_calendar_event import TaxCalendarEvent  # noqa: F401
from app.models.reconciliation_report import ReconciliationReport  # noqa: F401
from app.models.ai_chat_message import AiChatMessage  # noqa: F401
from app.models.uploaded_file import UploadedFile  # noqa: F401
from app.models.agent_event import AgentEvent  # noqa: F401
from app.models.agent_action_log import AgentActionLog  # noqa: F401
from app.models.agent_confirmation import AgentConfirmation  # noqa: F401

__all__ = [
    "BaseModel",
    "User",
    "Counterparty",
    "BankAccount",
    "Document",
    "DocumentItem",
    "BankOperation",
    "CashReceipt",
    "KudirEntry",
    "PurchaseBookEntry",
    "SalesBookEntry",
    "TaxCalculation",
    "TaxDeclaration",
    "TaxCalendarEvent",
    "ReconciliationReport",
    "AiChatMessage",
    "UploadedFile",
    "AgentEvent",
    "AgentActionLog",
    "AgentConfirmation",
]

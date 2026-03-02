"""
001 вЂ” РќР°С‡Р°Р»СЊРЅР°СЏ СЃС…РµРјР° Р‘Р”: РІСЃРµ С‚Р°Р±Р»РёС†С‹ РїСЂРѕРµРєС‚Р° РР-Р‘СѓС…РіР°Р»С‚РµСЂ.

Revision ID: 001_initial_schema
Revises:
Create Date: 2026-02-27

Р—РЅР°С‡РµРЅРёСЏ enum Р±РµСЂСѓС‚СЃСЏ РёР· backend/app/constants/enums.py
(РµРґРёРЅС‹Р№ РёСЃС‚РѕС‡РЅРёРє РїСЂР°РІРґС‹).
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # в•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђ
    # ENUM TYPES  (Р·РЅР°С‡РµРЅРёСЏ РёР· app/constants/enums.py)
    # в•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђ

    tax_system_enum = postgresql.ENUM(
        "usn_income_expense", "usn_income", "osno", "patent", "eshn",
        name="tax_system_enum", create_type=False,
    )
    tax_system_enum.create(op.get_bind(), checkfirst=True)

    document_type_enum = postgresql.ENUM(
        "invoice", "upd", "torg12", "act", "bill",
        "cash_receipt", "bank_statement", "contract",
        "payment_order", "other",
        name="document_type_enum", create_type=False,
    )
    document_type_enum.create(op.get_bind(), checkfirst=True)

    document_status_enum = postgresql.ENUM(
        "uploading", "processing", "recognized",
        "confirmed", "rejected", "error",
        name="document_status_enum", create_type=False,
    )
    document_status_enum.create(op.get_bind(), checkfirst=True)

    document_source_enum = postgresql.ENUM(
        "manual_upload", "edo", "ofd", "email",
        "bank_sync", "moysklad",
        name="document_source_enum", create_type=False,
    )
    document_source_enum.create(op.get_bind(), checkfirst=True)

    operation_category_enum = postgresql.ENUM(
        "sales_revenue", "acquiring", "supplier_return", "other_income",
        "own_funds", "internal_transfer", "loan_received",
        "purchase_goods", "rent", "salary", "taxes_and_fees",
        "insurance_payment", "bank_commission", "utilities",
        "transport", "advertising", "services",
        "loan_repayment", "other_expense",
        "personal_withdrawal", "cash_withdrawal",
        "unclassified",
        name="operation_category_enum", create_type=False,
    )
    operation_category_enum.create(op.get_bind(), checkfirst=True)

    operation_status_enum = postgresql.ENUM(
        "pending", "classified", "confirmed", "reclassified",
        name="operation_status_enum", create_type=False,
    )
    operation_status_enum.create(op.get_bind(), checkfirst=True)

    payment_type_enum = postgresql.ENUM(
        "cash", "card", "transfer", "online", "mixed",
        name="payment_type_enum", create_type=False,
    )
    payment_type_enum.create(op.get_bind(), checkfirst=True)

    tax_type_enum = postgresql.ENUM(
        "usn", "vat", "ndfl", "insurance_employee", "insurance_ip",
        name="tax_type_enum", create_type=False,
    )
    tax_type_enum.create(op.get_bind(), checkfirst=True)

    period_type_enum = postgresql.ENUM(
        "month", "quarter", "half_year", "nine_months", "year",
        name="period_type_enum", create_type=False,
    )
    period_type_enum.create(op.get_bind(), checkfirst=True)

    calculation_status_enum = postgresql.ENUM(
        "preliminary", "final", "confirmed", "paid",
        name="calculation_status_enum", create_type=False,
    )
    calculation_status_enum.create(op.get_bind(), checkfirst=True)

    declaration_type_enum = postgresql.ENUM(
        "vat", "usn", "ndfl_6", "rsv", "personified",
        name="declaration_type_enum", create_type=False,
    )
    declaration_type_enum.create(op.get_bind(), checkfirst=True)

    declaration_status_enum = postgresql.ENUM(
        "draft", "generated", "validated", "validation_error",
        "signed", "submitted", "accepted", "rejected",
        name="declaration_status_enum", create_type=False,
    )
    declaration_status_enum.create(op.get_bind(), checkfirst=True)

    calendar_event_type_enum = postgresql.ENUM(
        "tax_payment", "declaration_submit", "advance_payment",
        "contribution_payment", "report_submit",
        name="calendar_event_type_enum", create_type=False,
    )
    calendar_event_type_enum.create(op.get_bind(), checkfirst=True)

    calendar_event_status_enum = postgresql.ENUM(
        "upcoming", "overdue", "completed",
        name="calendar_event_status_enum", create_type=False,
    )
    calendar_event_status_enum.create(op.get_bind(), checkfirst=True)

    file_type_enum = postgresql.ENUM(
        "pdf", "xml", "csv", "xls", "xlsx",
        "jpg", "jpeg", "png", "tiff", "heic", "other",
        name="file_type_enum", create_type=False,
    )
    file_type_enum.create(op.get_bind(), checkfirst=True)

    processing_status_enum = postgresql.ENUM(
        "queued", "processing", "completed", "error",
        name="processing_status_enum", create_type=False,
    )
    processing_status_enum.create(op.get_bind(), checkfirst=True)

    chat_role_enum = postgresql.ENUM(
        "user", "assistant", "system",
        name="chat_role_enum", create_type=False,
    )
    chat_role_enum.create(op.get_bind(), checkfirst=True)

    # в•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђ
    # TABLE: users
    # в•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђ
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), unique=True, nullable=False, index=True),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("inn", sa.String(12), nullable=True),
        sa.Column("business_name", sa.String(500), nullable=True),
        sa.Column(
            "tax_system",
            tax_system_enum,
            nullable=False,
            server_default="usn_income_expense",
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("tax_region", sa.String(10), nullable=False, server_default="56"),
        sa.Column(
            "usn_rate", sa.Numeric(5, 2), nullable=False, server_default="15.00"
        ),
        sa.Column(
            "vat_rate", sa.Numeric(5, 2), nullable=False, server_default="22.00"
        ),
        sa.Column(
            "has_employees", sa.Boolean(), nullable=False, server_default="false"
        ),
        sa.Column(
            "employee_count", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # в•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђ
    # TABLE: counterparties
    # в•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђ
    op.create_table(
        "counterparties",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("name", sa.String(500), nullable=False),
        sa.Column("inn", sa.String(12), nullable=True, index=True),
        sa.Column("kpp", sa.String(9), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column(
            "is_verified", sa.Boolean(), nullable=False, server_default="false"
        ),
        sa.Column("egrul_data", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # в•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђ
    # TABLE: bank_accounts
    # в•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђ
    op.create_table(
        "bank_accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("bank_name", sa.String(255), nullable=False),
        sa.Column("account_number", sa.String(20), nullable=False),
        sa.Column("bik", sa.String(9), nullable=False),
        sa.Column("corr_account", sa.String(20), nullable=True),
        sa.Column(
            "is_primary", sa.Boolean(), nullable=False, server_default="false"
        ),
        sa.Column(
            "is_active", sa.Boolean(), nullable=False, server_default="true"
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # в•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђ
    # TABLE: documents
    # в•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђ
    op.create_table(
        "documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("doc_type", document_type_enum, nullable=False, index=True),
        sa.Column("doc_number", sa.String(100), nullable=True),
        sa.Column("doc_date", sa.Date(), nullable=True, index=True),
        sa.Column(
            "counterparty_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("counterparties.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column("total_without_vat", sa.Numeric(15, 2), nullable=True),
        sa.Column("vat_amount", sa.Numeric(15, 2), nullable=True),
        sa.Column("total_with_vat", sa.Numeric(15, 2), nullable=True),
        sa.Column("vat_rate", sa.Numeric(5, 2), nullable=True),
        sa.Column(
            "status",
            document_status_enum,
            nullable=False,
            server_default="uploading",
            index=True,
        ),
        sa.Column(
            "source",
            document_source_enum,
            nullable=False,
            server_default="manual_upload",
        ),
        sa.Column("file_path", sa.String(1000), nullable=True),
        sa.Column("recognized_data_json", postgresql.JSONB(), nullable=True),
        sa.Column("confidence_score", sa.Numeric(5, 4), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # в•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђ
    # TABLE: document_items
    # в•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђ
    op.create_table(
        "document_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("name", sa.String(500), nullable=False),
        sa.Column(
            "quantity",
            sa.Numeric(15, 3),
            nullable=False,
            server_default="1",
        ),
        sa.Column("unit", sa.String(20), nullable=True),
        sa.Column("price_without_vat", sa.Numeric(15, 2), nullable=True),
        sa.Column("vat_rate", sa.Numeric(5, 2), nullable=True),
        sa.Column("vat_amount", sa.Numeric(15, 2), nullable=True),
        sa.Column("total_with_vat", sa.Numeric(15, 2), nullable=True),
        sa.Column(
            "sort_order", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # в•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђ
    # TABLE: cash_receipts
    # в•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђ
    op.create_table(
        "cash_receipts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "receipt_date",
            sa.DateTime(timezone=True),
            nullable=False,
            index=True,
        ),
        sa.Column("receipt_number", sa.String(100), nullable=True),
        sa.Column("fiscal_number", sa.String(100), nullable=True),
        sa.Column("total", sa.Numeric(15, 2), nullable=False),
        sa.Column("vat_amount", sa.Numeric(15, 2), nullable=True),
        sa.Column(
            "payment_type",
            payment_type_enum,
            nullable=False,
            server_default="cash",
        ),
        sa.Column("ofd_source", sa.String(100), nullable=True),
        sa.Column("items_json", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # в•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђ
    # TABLE: bank_operations
    # в•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђ
    op.create_table(
        "bank_operations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "bank_account_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("bank_accounts.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column("operation_date", sa.Date(), nullable=False, index=True),
        sa.Column("amount", sa.Numeric(15, 2), nullable=False),
        sa.Column(
            "counterparty_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("counterparties.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column("counterparty_name", sa.String(500), nullable=True),
        sa.Column("counterparty_inn", sa.String(12), nullable=True),
        sa.Column("purpose", sa.Text(), nullable=True),
        sa.Column(
            "category",
            operation_category_enum,
            nullable=False,
            server_default="unclassified",
            index=True,
        ),
        sa.Column(
            "is_income", sa.Boolean(), nullable=False, server_default="false"
        ),
        sa.Column(
            "is_expense", sa.Boolean(), nullable=False, server_default="false"
        ),
        sa.Column("vat_amount", sa.Numeric(15, 2), nullable=True),
        sa.Column(
            "linked_document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column(
            "linked_receipt_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("cash_receipts.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("classification_confidence", sa.Numeric(5, 4), nullable=True),
        sa.Column(
            "status",
            operation_status_enum,
            nullable=False,
            server_default="pending",
            index=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # в•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђ
    # TABLE: kudir_entries
    # в•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђ
    op.create_table(
        "kudir_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("entry_number", sa.Integer(), nullable=False),
        sa.Column("entry_date", sa.Date(), nullable=False, index=True),
        sa.Column("document_ref", sa.String(255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "income_amount",
            sa.Numeric(15, 2),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "expense_amount",
            sa.Numeric(15, 2),
            nullable=False,
            server_default="0",
        ),
        sa.Column("quarter", sa.Integer(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column(
            "linked_operation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("bank_operations.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # в•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђ
    # TABLE: purchase_book_entries
    # в•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђпїЅпїЅпїЅв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђ
    op.create_table(
        "purchase_book_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("entry_number", sa.Integer(), nullable=False),
        sa.Column("entry_date", sa.Date(), nullable=False),
        sa.Column(
            "counterparty_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("counterparties.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("invoice_number", sa.String(100), nullable=True),
        sa.Column("invoice_date", sa.Date(), nullable=True),
        sa.Column(
            "total_without_vat",
            sa.Numeric(15, 2),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "vat_amount",
            sa.Numeric(15, 2),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "total_with_vat",
            sa.Numeric(15, 2),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "vat_rate", sa.Numeric(5, 2), nullable=False, server_default="22.00"
        ),
        sa.Column("quarter", sa.Integer(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column(
            "linked_document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # в•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђ
    # TABLE: sales_book_entries
    # в•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђ
    op.create_table(
        "sales_book_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("entry_number", sa.Integer(), nullable=False),
        sa.Column("entry_date", sa.Date(), nullable=False),
        sa.Column("buyer_name", sa.String(500), nullable=True),
        sa.Column("buyer_inn", sa.String(12), nullable=True),
        sa.Column("invoice_number", sa.String(100), nullable=True),
        sa.Column("invoice_date", sa.Date(), nullable=True),
        sa.Column(
            "total_without_vat",
            sa.Numeric(15, 2),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "vat_amount",
            sa.Numeric(15, 2),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "total_with_vat",
            sa.Numeric(15, 2),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "vat_rate", sa.Numeric(5, 2), nullable=False, server_default="22.00"
        ),
        sa.Column("quarter", sa.Integer(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column(
            "linked_document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # в•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђ
    # TABLE: tax_calculations
    # в•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђ
    op.create_table(
        "tax_calculations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("tax_type", tax_type_enum, nullable=False, index=True),
        sa.Column("period_type", period_type_enum, nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column(
            "income_total",
            sa.Numeric(15, 2),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "expense_total",
            sa.Numeric(15, 2),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "tax_base",
            sa.Numeric(15, 2),
            nullable=False,
            server_default="0",
        ),
        sa.Column("tax_rate", sa.Numeric(5, 2), nullable=False),
        sa.Column(
            "tax_amount",
            sa.Numeric(15, 2),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "vat_charged",
            sa.Numeric(15, 2),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "vat_deductible",
            sa.Numeric(15, 2),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "vat_payable",
            sa.Numeric(15, 2),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "insurance_deduction",
            sa.Numeric(15, 2),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "min_tax_amount",
            sa.Numeric(15, 2),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "status",
            calculation_status_enum,
            nullable=False,
            server_default="preliminary",
        ),
        sa.Column("details_json", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # в•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђ
    # TABLE: tax_declarations
    # в•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђ
    op.create_table(
        "tax_declarations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "declaration_type",
            declaration_type_enum,
            nullable=False,
            index=True,
        ),
        sa.Column("period", sa.String(20), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False, index=True),
        sa.Column("xml_content", sa.Text(), nullable=True),
        sa.Column("xml_path", sa.String(1000), nullable=True),
        sa.Column("pdf_path", sa.String(1000), nullable=True),
        sa.Column(
            "status",
            declaration_status_enum,
            nullable=False,
            server_default="draft",
            index=True,
        ),
        sa.Column("validation_errors", sa.Text(), nullable=True),
        sa.Column(
            "submitted_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column("fns_response", sa.Text(), nullable=True),
        sa.Column(
            "linked_calculation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tax_calculations.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # в•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђ
    # TABLE: tax_calendar_events
    # в•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђ
    op.create_table(
        "tax_calendar_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "event_type", calendar_event_type_enum, nullable=False
        ),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("deadline", sa.Date(), nullable=False, index=True),
        sa.Column(
            "status",
            calendar_event_status_enum,
            nullable=False,
            server_default="upcoming",
            index=True,
        ),
        sa.Column(
            "reminded_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column(
            "completed_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # в•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђ
    # TABLE: reconciliation_reports
    # в•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђ
    op.create_table(
        "reconciliation_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("report_date", sa.Date(), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=True),
        sa.Column("period_end", sa.Date(), nullable=True),
        sa.Column("discrepancies_json", postgresql.JSONB(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column(
            "resolved_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "unresolved_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "total_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # в•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђ
    # TABLE: ai_chat_messages
    # в•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђ
    op.create_table(
        "ai_chat_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("context_json", postgresql.JSONB(), nullable=True),
        sa.Column("model_used", sa.String(100), nullable=True),
        sa.Column("tokens_used", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # в•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђ
    # TABLE: uploaded_files
    # в•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђв•ђ
    op.create_table(
        "uploaded_files",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("original_filename", sa.String(500), nullable=False),
        sa.Column("stored_path", sa.String(1000), nullable=False),
        sa.Column("file_type", file_type_enum, nullable=True),
        sa.Column("file_size", sa.BigInteger(), nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=True),
        sa.Column(
            "processing_status",
            processing_status_enum,
            nullable=False,
            server_default="queued",
            index=True,
        ),
        sa.Column("processing_result", postgresql.JSONB(), nullable=True),
        sa.Column("processing_error", sa.Text(), nullable=True),
        sa.Column(
            "linked_document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )


def downgrade() -> None:
    # РЈРґР°Р»СЏРµРј С‚Р°Р±Р»РёС†С‹ РІ РѕР±СЂР°С‚РЅРѕРј РїРѕСЂСЏРґРєРµ (РёР·-Р·Р° FK)
    op.drop_table("uploaded_files")
    op.drop_table("ai_chat_messages")
    op.drop_table("reconciliation_reports")
    op.drop_table("tax_calendar_events")
    op.drop_table("tax_declarations")
    op.drop_table("tax_calculations")
    op.drop_table("sales_book_entries")
    op.drop_table("purchase_book_entries")
    op.drop_table("kudir_entries")
    op.drop_table("bank_operations")
    op.drop_table("cash_receipts")
    op.drop_table("document_items")
    op.drop_table("documents")
    op.drop_table("bank_accounts")
    op.drop_table("counterparties")
    op.drop_table("users")

    # РЈРґР°Р»СЏРµРј ENUM С‚РёРїС‹
    for enum_name in [
        "chat_role_enum",
        "processing_status_enum",
        "file_type_enum",
        "calendar_event_status_enum",
        "calendar_event_type_enum",
        "declaration_status_enum",
        "declaration_type_enum",
        "calculation_status_enum",
        "period_type_enum",
        "tax_type_enum",
        "payment_type_enum",
        "operation_status_enum",
        "operation_category_enum",
        "document_source_enum",
        "document_status_enum",
        "document_type_enum",
        "tax_system_enum",
    ]:
        postgresql.ENUM(name=enum_name).drop(op.get_bind(), checkfirst=True)

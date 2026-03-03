"""
002 — Таблицы AI-агента: agent_events, agent_action_logs, agent_confirmations.

Revision ID: 002_agent_tables
Revises: 001_initial_schema
Create Date: 2026-03-03

Значения enum берутся из backend/app/constants/enums.py (единственный источник правды).
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "002_agent_tables"
down_revision = "001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ═══════════════════════════════════════════════════════
    # ENUM TYPES для агента (значения из app/constants/enums.py)
    # ═══════════════════════════════════════════════════════

    agent_trigger_type_enum = postgresql.ENUM(
        "event_file_uploaded", "event_new_bank_data", "event_new_ofd_data",
        "event_new_edo_document", "event_user_confirmation",
        "user_question", "user_command",
        "schedule_daily", "schedule_weekly", "schedule_monthly",
        "schedule_pre_deadline",
        name="agent_trigger_type_enum", create_type=False,
    )
    agent_trigger_type_enum.create(op.get_bind(), checkfirst=True)

    agent_event_status_enum = postgresql.ENUM(
        "pending", "running", "completed", "failed",
        "awaiting_user", "cancelled",
        name="agent_event_status_enum", create_type=False,
    )
    agent_event_status_enum.create(op.get_bind(), checkfirst=True)

    agent_action_type_enum = postgresql.ENUM(
        "tool_fetch_bank", "tool_fetch_ofd", "tool_fetch_edo",
        "tool_get_files", "tool_query_egrul", "tool_get_context",
        "tool_recognize_document", "tool_parse_xml", "tool_parse_table",
        "tool_classify_operation", "tool_classify_batch",
        "tool_match_operation", "tool_detect_duplicates", "tool_detect_anomalies",
        "tool_calculate_taxes", "tool_generate_kudir",
        "tool_generate_purchase_book", "tool_generate_sales_book",
        "tool_reconcile",
        "tool_generate_declaration", "tool_validate_declaration", "tool_export",
        "tool_send_notification", "tool_request_confirmation", "tool_create_report",
        "agent_thinking", "agent_error", "agent_summary",
        name="agent_action_type_enum", create_type=False,
    )
    agent_action_type_enum.create(op.get_bind(), checkfirst=True)

    agent_action_log_status_enum = postgresql.ENUM(
        "pending", "running", "completed", "failed",
        "awaiting_user", "cancelled",
        name="agent_action_log_status_enum", create_type=False,
    )
    agent_action_log_status_enum.create(op.get_bind(), checkfirst=True)

    agent_confirmation_type_enum = postgresql.ENUM(
        "operation_classification", "document_recognition",
        "tax_calculation", "declaration_submit",
        "anomaly_resolution", "general",
        name="agent_confirmation_type_enum", create_type=False,
    )
    agent_confirmation_type_enum.create(op.get_bind(), checkfirst=True)

    agent_confirmation_status_enum = postgresql.ENUM(
        "pending", "confirmed", "rejected", "modified", "expired",
        name="agent_confirmation_status_enum", create_type=False,
    )
    agent_confirmation_status_enum.create(op.get_bind(), checkfirst=True)

    # ═══════════════════════════════════════════════════════
    # TABLE: agent_events
    # ═══════════════════════════════════════════════════════
    op.create_table(
        "agent_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "trigger_type",
            agent_trigger_type_enum,
            nullable=False,
            index=True,
        ),
        sa.Column(
            "status",
            agent_event_status_enum,
            nullable=False,
            server_default="pending",
            index=True,
        ),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("payload", postgresql.JSONB(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("tool_calls_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tokens_used", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
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

    # ═══════════════════════════════════════════════════════
    # TABLE: agent_action_logs
    # ═══════════════════════════════════════════════════════
    op.create_table(
        "agent_action_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "event_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agent_events.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "action_type",
            agent_action_type_enum,
            nullable=False,
            index=True,
        ),
        sa.Column(
            "status",
            agent_action_log_status_enum,
            nullable=False,
            server_default="pending",
        ),
        sa.Column("step_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("input_params", postgresql.JSONB(), nullable=True),
        sa.Column("output_result", postgresql.JSONB(), nullable=True),
        sa.Column("agent_reasoning", sa.Text(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("tokens_input", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tokens_output", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cost_usd", sa.Numeric(10, 6), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
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

    # ═══════════════════════════════════════════════════════
    # TABLE: agent_confirmations
    # ═══════════════════════════════════════════════════════
    op.create_table(
        "agent_confirmations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "event_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agent_events.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column(
            "confirmation_type",
            agent_confirmation_type_enum,
            nullable=False,
            index=True,
        ),
        sa.Column(
            "status",
            agent_confirmation_status_enum,
            nullable=False,
            server_default="pending",
            index=True,
        ),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("proposed_data", postgresql.JSONB(), nullable=True),
        sa.Column("options", postgresql.JSONB(), nullable=True),
        sa.Column("user_response", sa.Text(), nullable=True),
        sa.Column("user_modified_data", postgresql.JSONB(), nullable=True),
        sa.Column("related_entity_type", sa.String(50), nullable=True),
        sa.Column("related_entity_id", sa.String(36), nullable=True),
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
    op.drop_table("agent_confirmations")
    op.drop_table("agent_action_logs")
    op.drop_table("agent_events")

    for enum_name in [
        "agent_confirmation_status_enum",
        "agent_confirmation_type_enum",
        "agent_action_log_status_enum",
        "agent_action_type_enum",
        "agent_event_status_enum",
        "agent_trigger_type_enum",
    ]:
        postgresql.ENUM(name=enum_name).drop(op.get_bind(), checkfirst=True)
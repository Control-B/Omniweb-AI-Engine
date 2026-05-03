"""Add assistant appointment request and email log tables.

Revision ID: 0025
Revises: 0024
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "appointment_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("conversation_id", sa.String(length=120), nullable=False),
        sa.Column("visitor_name", sa.String(length=255), nullable=False),
        sa.Column("visitor_email", sa.String(length=255), nullable=False),
        sa.Column("visitor_phone", sa.String(length=30), nullable=True),
        sa.Column("requested_service", sa.String(length=255), nullable=True),
        sa.Column("preferred_date", sa.String(length=80), nullable=True),
        sa.Column("preferred_time", sa.String(length=80), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("booking_url", sa.Text(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="pending"),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["clients.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_appointment_requests_tenant_id", "appointment_requests", ["tenant_id"])
    op.create_index("ix_appointment_requests_conversation_id", "appointment_requests", ["conversation_id"])
    op.create_index("ix_appointment_requests_visitor_email", "appointment_requests", ["visitor_email"])
    op.create_index("ix_appointment_requests_status", "appointment_requests", ["status"])
    op.create_index("ix_appointment_requests_created_at", "appointment_requests", ["created_at"])

    op.create_table(
        "email_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("conversation_id", sa.String(length=120), nullable=True),
        sa.Column("recipient", sa.String(length=255), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("type", sa.String(length=80), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=False, server_default="resend"),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["clients.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_email_logs_tenant_id", "email_logs", ["tenant_id"])
    op.create_index("ix_email_logs_conversation_id", "email_logs", ["conversation_id"])
    op.create_index("ix_email_logs_recipient", "email_logs", ["recipient"])
    op.create_index("ix_email_logs_type", "email_logs", ["type"])
    op.create_index("ix_email_logs_status", "email_logs", ["status"])
    op.create_index("ix_email_logs_created_at", "email_logs", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_email_logs_created_at", table_name="email_logs")
    op.drop_index("ix_email_logs_status", table_name="email_logs")
    op.drop_index("ix_email_logs_type", table_name="email_logs")
    op.drop_index("ix_email_logs_recipient", table_name="email_logs")
    op.drop_index("ix_email_logs_conversation_id", table_name="email_logs")
    op.drop_index("ix_email_logs_tenant_id", table_name="email_logs")
    op.drop_table("email_logs")

    op.drop_index("ix_appointment_requests_created_at", table_name="appointment_requests")
    op.drop_index("ix_appointment_requests_status", table_name="appointment_requests")
    op.drop_index("ix_appointment_requests_visitor_email", table_name="appointment_requests")
    op.drop_index("ix_appointment_requests_conversation_id", table_name="appointment_requests")
    op.drop_index("ix_appointment_requests_tenant_id", table_name="appointment_requests")
    op.drop_table("appointment_requests")

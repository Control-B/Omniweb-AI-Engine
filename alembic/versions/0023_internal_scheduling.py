"""Add internal Cal.diy scheduling tables.

Revision ID: 0023
Revises: 0022
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tenant_scheduling_configs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("calcom_user_id", sa.String(length=120), nullable=True),
        sa.Column("default_event_type_id", sa.String(length=120), nullable=True),
        sa.Column("booking_mode", sa.String(length=40), nullable=False, server_default="ai-assisted"),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="disabled"),
        sa.Column("event_type_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("settings", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("last_health_status", sa.String(length=40), nullable=True),
        sa.Column("last_health_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["clients.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", name="uq_tenant_scheduling_configs_tenant_id"),
    )
    op.create_index("ix_tenant_scheduling_configs_tenant_id", "tenant_scheduling_configs", ["tenant_id"])
    op.create_index("ix_tenant_scheduling_configs_status", "tenant_scheduling_configs", ["status"])

    op.create_table(
        "scheduling_bookings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("lead_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("calcom_booking_id", sa.String(length=120), nullable=True),
        sa.Column("calcom_booking_uid", sa.String(length=160), nullable=True),
        sa.Column("event_type_id", sa.String(length=120), nullable=False),
        sa.Column("attendee_name", sa.String(length=255), nullable=False),
        sa.Column("attendee_email", sa.String(length=255), nullable=False),
        sa.Column("attendee_phone", sa.String(length=30), nullable=True),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("timezone", sa.String(length=80), nullable=False, server_default="America/New_York"),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="confirmed"),
        sa.Column("topic", sa.Text(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["clients.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["lead_id"], ["leads.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "calcom_booking_uid", name="uq_scheduling_bookings_tenant_uid"),
    )
    op.create_index("ix_scheduling_bookings_tenant_id", "scheduling_bookings", ["tenant_id"])
    op.create_index("ix_scheduling_bookings_created_at", "scheduling_bookings", ["created_at"])
    op.create_index("ix_scheduling_bookings_status", "scheduling_bookings", ["status"])


def downgrade() -> None:
    op.drop_index("ix_scheduling_bookings_status", table_name="scheduling_bookings")
    op.drop_index("ix_scheduling_bookings_created_at", table_name="scheduling_bookings")
    op.drop_index("ix_scheduling_bookings_tenant_id", table_name="scheduling_bookings")
    op.drop_table("scheduling_bookings")

    op.drop_index("ix_tenant_scheduling_configs_status", table_name="tenant_scheduling_configs")
    op.drop_index("ix_tenant_scheduling_configs_tenant_id", table_name="tenant_scheduling_configs")
    op.drop_table("tenant_scheduling_configs")

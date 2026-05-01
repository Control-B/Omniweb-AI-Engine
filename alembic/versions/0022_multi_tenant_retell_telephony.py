"""Add multi-tenant Retell telephony channel tables.

Revision ID: 0022
Revises: 0021
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 0017 existed in the migration chain before these ORM fields were restored.
    # Keep this migration idempotent for databases that were bootstrapped from
    # metadata rather than the full Alembic chain.
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    agent_columns = {column["name"] for column in inspector.get_columns("agent_configs")}
    call_columns = {column["name"] for column in inspector.get_columns("calls")}

    if "retell_agent_id" not in agent_columns:
        op.add_column("agent_configs", sa.Column("retell_agent_id", sa.String(length=100), nullable=True))
        op.create_index("ix_agent_configs_retell_agent_id", "agent_configs", ["retell_agent_id"])

    if "retell_call_id" not in call_columns:
        op.add_column("calls", sa.Column("retell_call_id", sa.String(length=120), nullable=True))
        op.create_index("ix_calls_retell_call_id", "calls", ["retell_call_id"])
        op.create_unique_constraint("uq_calls_retell_call_id", "calls", ["retell_call_id"])

    op.create_table(
        "tenant_channels",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("channel_type", sa.String(length=40), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="disabled"),
        sa.Column("config_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["clients.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "channel_type", name="uq_tenant_channels_tenant_channel"),
    )
    op.create_index("ix_tenant_channels_tenant_id", "tenant_channels", ["tenant_id"])
    op.create_index("ix_tenant_channels_channel_type", "tenant_channels", ["channel_type"])
    op.create_index("ix_tenant_channels_status", "tenant_channels", ["status"])

    op.create_table(
        "tenant_retell_agents",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("retell_agent_id", sa.String(length=120), nullable=True),
        sa.Column("retell_phone_number", sa.String(length=30), nullable=True),
        sa.Column("human_escalation_phone", sa.String(length=30), nullable=True),
        sa.Column("fallback_email", sa.String(length=255), nullable=True),
        sa.Column("webhook_url", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="provisioning"),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["clients.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", name="uq_tenant_retell_agents_tenant_id"),
        sa.UniqueConstraint("retell_agent_id"),
    )
    op.create_index("ix_tenant_retell_agents_tenant_id", "tenant_retell_agents", ["tenant_id"])
    op.create_index("ix_tenant_retell_agents_retell_agent_id", "tenant_retell_agents", ["retell_agent_id"])
    op.create_index("ix_tenant_retell_agents_retell_phone_number", "tenant_retell_agents", ["retell_phone_number"])
    op.create_index("ix_tenant_retell_agents_status", "tenant_retell_agents", ["status"])

    op.create_table(
        "tenant_call_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=False, server_default="retell"),
        sa.Column("provider_call_id", sa.String(length=160), nullable=True),
        sa.Column("retell_agent_id", sa.String(length=120), nullable=True),
        sa.Column("caller_phone", sa.String(length=30), nullable=True),
        sa.Column("direction", sa.String(length=20), nullable=False, server_default="inbound"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("transcript", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("outcome", sa.String(length=120), nullable=True),
        sa.Column("escalation_triggered", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["clients.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "provider_call_id", name="uq_tenant_call_logs_provider_call"),
    )
    op.create_index("ix_tenant_call_logs_tenant_id", "tenant_call_logs", ["tenant_id"])
    op.create_index("ix_tenant_call_logs_created_at", "tenant_call_logs", ["created_at"])
    op.create_index("ix_tenant_call_logs_provider_call_id", "tenant_call_logs", ["provider_call_id"])
    op.create_index("ix_tenant_call_logs_retell_agent_id", "tenant_call_logs", ["retell_agent_id"])

    op.create_table(
        "tenant_usage_metering",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("channel_type", sa.String(length=40), nullable=False, server_default="ai_telephony"),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("calls_used", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("minutes_used", sa.Float(), nullable=False, server_default="0"),
        sa.Column("plan_limit_minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("overage_minutes", sa.Float(), nullable=False, server_default="0"),
        sa.Column("provider_cost_estimate", sa.Float(), nullable=False, server_default="0"),
        sa.Column("subscriber_billed_usage", sa.Float(), nullable=False, server_default="0"),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["clients.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "channel_type", "period_start", name="uq_usage_metering_tenant_channel_period"),
    )
    op.create_index("ix_usage_metering_tenant_id", "tenant_usage_metering", ["tenant_id"])
    op.create_index("ix_usage_metering_period_start", "tenant_usage_metering", ["period_start"])

    op.create_table(
        "tenant_escalation_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("channel_type", sa.String(length=40), nullable=False, server_default="ai_telephony"),
        sa.Column("human_escalation_phone", sa.String(length=30), nullable=True),
        sa.Column("fallback_email", sa.String(length=255), nullable=True),
        sa.Column("business_hours", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("trigger_keywords", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["clients.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "channel_type", name="uq_escalation_rules_tenant_channel"),
    )
    op.create_index("ix_escalation_rules_tenant_id", "tenant_escalation_rules", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_escalation_rules_tenant_id", table_name="tenant_escalation_rules")
    op.drop_table("tenant_escalation_rules")
    op.drop_index("ix_usage_metering_period_start", table_name="tenant_usage_metering")
    op.drop_index("ix_usage_metering_tenant_id", table_name="tenant_usage_metering")
    op.drop_table("tenant_usage_metering")
    op.drop_index("ix_tenant_call_logs_retell_agent_id", table_name="tenant_call_logs")
    op.drop_index("ix_tenant_call_logs_provider_call_id", table_name="tenant_call_logs")
    op.drop_index("ix_tenant_call_logs_created_at", table_name="tenant_call_logs")
    op.drop_index("ix_tenant_call_logs_tenant_id", table_name="tenant_call_logs")
    op.drop_table("tenant_call_logs")
    op.drop_index("ix_tenant_retell_agents_status", table_name="tenant_retell_agents")
    op.drop_index("ix_tenant_retell_agents_retell_phone_number", table_name="tenant_retell_agents")
    op.drop_index("ix_tenant_retell_agents_retell_agent_id", table_name="tenant_retell_agents")
    op.drop_index("ix_tenant_retell_agents_tenant_id", table_name="tenant_retell_agents")
    op.drop_table("tenant_retell_agents")
    op.drop_index("ix_tenant_channels_status", table_name="tenant_channels")
    op.drop_index("ix_tenant_channels_channel_type", table_name="tenant_channels")
    op.drop_index("ix_tenant_channels_tenant_id", table_name="tenant_channels")
    op.drop_table("tenant_channels")

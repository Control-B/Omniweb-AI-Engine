"""Add role to clients and create agent_templates table

Revision ID: 0002
Revises: 0001
Create Date: 2025-01-01 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add role column to clients
    op.add_column(
        "clients",
        sa.Column("role", sa.String(20), nullable=False, server_default="client"),
    )

    # Create agent_templates table
    op.create_table(
        "agent_templates",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("industry", sa.String(100), nullable=False, server_default="general"),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        # Template config
        sa.Column("agent_name", sa.String(100), nullable=False, server_default="AI Assistant"),
        sa.Column("agent_greeting", sa.Text(), nullable=False, server_default="Thank you for calling! How can I help you today?"),
        sa.Column("system_prompt", sa.Text(), nullable=False, server_default=""),
        sa.Column("voice_id", sa.String(100), nullable=False, server_default="EXAVITQu4vr4xnSDxMaL"),
        sa.Column("voice_stability", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("voice_similarity_boost", sa.Float(), nullable=False, server_default="0.75"),
        sa.Column("llm_model", sa.String(100), nullable=False, server_default="gpt-4o"),
        sa.Column("temperature", sa.Float(), nullable=False, server_default="0.7"),
        sa.Column("max_call_duration", sa.Integer(), nullable=False, server_default="1800"),
        sa.Column("after_hours_message", sa.Text(), nullable=False, server_default="We're currently closed but will call you back first thing in the morning."),
        sa.Column("after_hours_sms_enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("allow_interruptions", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("services", JSONB(), nullable=False, server_default="[]"),
        sa.Column("business_hours", JSONB(), nullable=False, server_default="{}"),
        sa.Column("widget_config", JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )


def downgrade() -> None:
    op.drop_table("agent_templates")
    op.drop_column("clients", "role")

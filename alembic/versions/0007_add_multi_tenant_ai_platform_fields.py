"""add multi-tenant AI platform fields to agent_configs

Revision ID: 0007
Revises: 0006
Create Date: 2025-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Industry & agent mode
    op.add_column("agent_configs", sa.Column("industry", sa.String(100), nullable=False, server_default="general"))
    op.add_column("agent_configs", sa.Column("agent_mode", sa.String(50), nullable=False, server_default="lead_qualifier"))

    # Custom guardrails & escalation
    op.add_column("agent_configs", sa.Column("custom_guardrails", JSONB, nullable=False, server_default="[]"))
    op.add_column("agent_configs", sa.Column("custom_escalation_triggers", JSONB, nullable=False, server_default="[]"))

    # Additional business context
    op.add_column("agent_configs", sa.Column("custom_context", sa.Text, nullable=True))

    # Prompt engine toggle
    op.add_column("agent_configs", sa.Column("use_prompt_engine", sa.Boolean, nullable=False, server_default=sa.text("true")))

    # Human handoff
    op.add_column("agent_configs", sa.Column("handoff_enabled", sa.Boolean, nullable=False, server_default=sa.text("false")))
    op.add_column("agent_configs", sa.Column("handoff_phone", sa.String(30), nullable=True))
    op.add_column("agent_configs", sa.Column("handoff_email", sa.String(255), nullable=True))
    op.add_column("agent_configs", sa.Column("handoff_message", sa.Text, nullable=False,
                                             server_default="Let me connect you with a member of our team who can help with this directly."))

    # Index on industry for analytics queries
    op.create_index("ix_agent_configs_industry", "agent_configs", ["industry"])


def downgrade() -> None:
    op.drop_index("ix_agent_configs_industry", table_name="agent_configs")
    op.drop_column("agent_configs", "handoff_message")
    op.drop_column("agent_configs", "handoff_email")
    op.drop_column("agent_configs", "handoff_phone")
    op.drop_column("agent_configs", "handoff_enabled")
    op.drop_column("agent_configs", "use_prompt_engine")
    op.drop_column("agent_configs", "custom_context")
    op.drop_column("agent_configs", "custom_escalation_triggers")
    op.drop_column("agent_configs", "custom_guardrails")
    op.drop_column("agent_configs", "agent_mode")
    op.drop_column("agent_configs", "industry")

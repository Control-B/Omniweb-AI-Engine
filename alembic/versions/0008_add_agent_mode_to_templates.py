"""Add agent_mode column to agent_templates table.

Migration 0007 added agent_mode to agent_configs but missed agent_templates.
This migration adds the matching column so templates can specify an agent mode
(lead_qualifier, appointment_setter, support_agent, etc.) that gets applied
when a tenant is provisioned from a template.

Revision ID: 0008
Revises: 0007
Create Date: 2026-04-12
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "agent_templates",
        sa.Column("agent_mode", sa.String(50), nullable=False, server_default="lead_qualifier"),
    )


def downgrade() -> None:
    op.drop_column("agent_templates", "agent_mode")

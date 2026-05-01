"""Add Retell agent + call id columns.

Revision ID: 0017
Revises: 0016
"""

from alembic import op
import sqlalchemy as sa

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "agent_configs",
        sa.Column("retell_agent_id", sa.String(length=100), nullable=True),
    )
    op.create_index("ix_agent_configs_retell_agent_id", "agent_configs", ["retell_agent_id"])

    op.add_column(
        "calls",
        sa.Column("retell_call_id", sa.String(length=120), nullable=True),
    )
    op.create_index("ix_calls_retell_call_id", "calls", ["retell_call_id"])
    op.create_unique_constraint("uq_calls_retell_call_id", "calls", ["retell_call_id"])


def downgrade() -> None:
    op.drop_constraint("uq_calls_retell_call_id", "calls", type_="unique")
    op.drop_index("ix_calls_retell_call_id", table_name="calls")
    op.drop_column("calls", "retell_call_id")

    op.drop_index("ix_agent_configs_retell_agent_id", table_name="agent_configs")
    op.drop_column("agent_configs", "retell_agent_id")

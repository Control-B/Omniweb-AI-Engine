"""Add tool_call_logs table for ElevenLabs tool audit logging.

Revision ID: 0002
Revises: 0001
Create Date: 2025-07-01 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tool_call_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "client_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("clients.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tool_name", sa.String(100), nullable=False),
        sa.Column("parameters", postgresql.JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("result", postgresql.JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("success", sa.Boolean, server_default=sa.text("true"), nullable=False),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("conversation_id", sa.String(100), nullable=True),
        sa.Column(
            "lead_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("leads.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("duration_ms", sa.Integer, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_tool_call_logs_client_id", "tool_call_logs", ["client_id"])
    op.create_index("ix_tool_call_logs_tool_name", "tool_call_logs", ["tool_name"])
    op.create_index("ix_tool_call_logs_created_at", "tool_call_logs", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_tool_call_logs_created_at", table_name="tool_call_logs")
    op.drop_index("ix_tool_call_logs_tool_name", table_name="tool_call_logs")
    op.drop_index("ix_tool_call_logs_client_id", table_name="tool_call_logs")
    op.drop_table("tool_call_logs")

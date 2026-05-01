"""Add webhook events table and clerk_user_id.

Revision ID: 0010
Revises: 0009
Create Date: 2025-01-15 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Add webhook_secret to clients ─────────────────────────
    op.add_column(
        "clients",
        sa.Column("webhook_secret", sa.String(100), nullable=True),
    )

    # ── Add clerk_user_id to clients ──────────────────────────
    op.add_column(
        "clients",
        sa.Column("clerk_user_id", sa.String(255), nullable=True),
    )
    op.create_index("ix_clients_clerk_user_id", "clients", ["clerk_user_id"])

    # ── Create webhook_events table ───────────────────────────
    op.create_table(
        "webhook_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "client_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("clients.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event", sa.String(50), nullable=False),
        sa.Column("url", sa.String(500), nullable=False),
        sa.Column("payload", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("status_code", sa.Integer, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_webhook_events_client_id", "webhook_events", ["client_id"])
    op.create_index("ix_webhook_events_event", "webhook_events", ["event"])
    op.create_index("ix_webhook_events_created_at", "webhook_events", ["created_at"])
    op.create_index("ix_webhook_events_status", "webhook_events", ["status"])


def downgrade() -> None:
    op.drop_table("webhook_events")
    op.drop_index("ix_clients_clerk_user_id", table_name="clients")
    op.drop_column("clients", "clerk_user_id")
    op.drop_column("clients", "webhook_secret")

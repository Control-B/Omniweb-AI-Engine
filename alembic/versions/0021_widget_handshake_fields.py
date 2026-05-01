"""Add widget handshake fields to clients.

Revision ID: 0021
Revises: 0020
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "clients",
        sa.Column(
            "allowed_domains",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.add_column("clients", sa.Column("widget_enabled", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("clients", sa.Column("widget_installed", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("clients", sa.Column("widget_last_seen_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("clients", sa.Column("widget_primary_color", sa.String(length=32), nullable=True))
    op.add_column("clients", sa.Column("widget_position", sa.String(length=32), nullable=False, server_default="bottom-right"))
    op.add_column("clients", sa.Column("widget_welcome_message", sa.Text(), nullable=True))
    op.add_column("clients", sa.Column("voice_enabled", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("clients", sa.Column("widget_last_domain", sa.String(length=255), nullable=True))
    op.add_column("clients", sa.Column("widget_last_page_url", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("clients", "widget_last_page_url")
    op.drop_column("clients", "widget_last_domain")
    op.drop_column("clients", "voice_enabled")
    op.drop_column("clients", "widget_welcome_message")
    op.drop_column("clients", "widget_position")
    op.drop_column("clients", "widget_primary_color")
    op.drop_column("clients", "widget_last_seen_at")
    op.drop_column("clients", "widget_installed")
    op.drop_column("clients", "widget_enabled")
    op.drop_column("clients", "allowed_domains")
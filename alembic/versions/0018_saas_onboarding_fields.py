"""SaaS onboarding: workspace fields, public widget key, subscription status, setup progress.

Revision ID: 0018
Revises: 0017
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("clients", sa.Column("website_url", sa.Text(), nullable=True))
    op.add_column("clients", sa.Column("primary_goal", sa.String(length=100), nullable=True))
    op.add_column(
        "clients",
        sa.Column("subscription_status", sa.String(length=30), nullable=True),
    )
    op.add_column(
        "clients",
        sa.Column("trial_started_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "clients",
        sa.Column("public_widget_key", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "clients",
        sa.Column(
            "saas_widget_status",
            sa.String(length=20),
            nullable=False,
            server_default="draft",
        ),
    )
    op.add_column(
        "clients",
        sa.Column(
            "setup_progress",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.add_column(
        "clients",
        sa.Column("onboarding_completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_clients_public_widget_key",
        "clients",
        ["public_widget_key"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_clients_public_widget_key", table_name="clients")
    op.drop_column("clients", "onboarding_completed_at")
    op.drop_column("clients", "setup_progress")
    op.drop_column("clients", "saas_widget_status")
    op.drop_column("clients", "public_widget_key")
    op.drop_column("clients", "trial_started_at")
    op.drop_column("clients", "subscription_status")
    op.drop_column("clients", "primary_goal")
    op.drop_column("clients", "website_url")

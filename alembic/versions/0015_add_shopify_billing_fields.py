"""add shopify billing fields

Revision ID: 0015
Revises: 0014
Create Date: 2025-07-25 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("shopify_stores", sa.Column("shopify_subscription_gid", sa.String(255), nullable=True))
    op.add_column("shopify_stores", sa.Column("shopify_plan", sa.String(50), nullable=True))
    op.add_column("shopify_stores", sa.Column("shopify_subscription_status", sa.String(50), nullable=True))
    op.add_column("shopify_stores", sa.Column("shopify_billing_updated_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("shopify_stores", "shopify_billing_updated_at")
    op.drop_column("shopify_stores", "shopify_subscription_status")
    op.drop_column("shopify_stores", "shopify_plan")
    op.drop_column("shopify_stores", "shopify_subscription_gid")

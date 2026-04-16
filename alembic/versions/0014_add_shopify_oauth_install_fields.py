"""add shopify oauth install fields

Revision ID: 0014
Revises: 0013
Create Date: 2026-04-15 00:30:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0014"
down_revision: Union[str, None] = "0013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("shopify_stores", sa.Column("shop_id", sa.String(length=100), nullable=True))
    op.add_column("shopify_stores", sa.Column("shop_name", sa.String(length=255), nullable=True))
    op.add_column("shopify_stores", sa.Column("shop_email", sa.String(length=255), nullable=True))
    op.add_column(
        "shopify_stores",
        sa.Column(
            "granted_scopes",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.add_column("shopify_stores", sa.Column("install_state_hash", sa.String(length=128), nullable=True))
    op.add_column("shopify_stores", sa.Column("install_state_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("shopify_stores", sa.Column("installed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("shopify_stores", sa.Column("uninstalled_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("shopify_stores", sa.Column("last_install_error", sa.Text(), nullable=True))

    op.create_index("ix_shopify_stores_shop_id", "shopify_stores", ["shop_id"])
    op.create_index("ix_shopify_stores_install_state_hash", "shopify_stores", ["install_state_hash"])


def downgrade() -> None:
    op.drop_index("ix_shopify_stores_install_state_hash", table_name="shopify_stores")
    op.drop_index("ix_shopify_stores_shop_id", table_name="shopify_stores")
    op.drop_column("shopify_stores", "last_install_error")
    op.drop_column("shopify_stores", "uninstalled_at")
    op.drop_column("shopify_stores", "installed_at")
    op.drop_column("shopify_stores", "install_state_expires_at")
    op.drop_column("shopify_stores", "install_state_hash")
    op.drop_column("shopify_stores", "granted_scopes")
    op.drop_column("shopify_stores", "shop_email")
    op.drop_column("shopify_stores", "shop_name")
    op.drop_column("shopify_stores", "shop_id")

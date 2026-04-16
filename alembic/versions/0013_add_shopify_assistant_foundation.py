"""add shopify assistant foundation

Revision ID: 0013
Revises: 0012
Create Date: 2026-04-15 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0013"
down_revision: Union[str, None] = "0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "shopify_stores",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("shop_domain", sa.String(length=255), nullable=False),
        sa.Column("storefront_access_token", sa.String(length=255), nullable=True),
        sa.Column("admin_access_token", sa.String(length=255), nullable=True),
        sa.Column("storefront_api_version", sa.String(length=20), nullable=False, server_default="2026-07"),
        sa.Column("app_status", sa.String(length=30), nullable=False, server_default="draft"),
        sa.Column("sales_channel_name", sa.String(length=100), nullable=True),
        sa.Column("assistant_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("require_discount_approval", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("allow_discount_requests", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("allowed_discount_types", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[\"code\"]'::jsonb")),
        sa.Column("support_email", sa.String(length=255), nullable=True),
        sa.Column("support_policy", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("nav_config", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("checkout_config", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("client_id"),
        sa.UniqueConstraint("shop_domain"),
    )
    op.create_index("ix_shopify_stores_client_id", "shopify_stores", ["client_id"])
    op.create_index("ix_shopify_stores_shop_domain", "shopify_stores", ["shop_domain"])
    op.create_index("ix_shopify_stores_assistant_enabled", "shopify_stores", ["assistant_enabled"])

    op.create_table(
        "shopify_assistant_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("store_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("storefront_session_id", sa.String(length=100), nullable=True),
        sa.Column("shopper_email", sa.String(length=255), nullable=True),
        sa.Column("shopper_locale", sa.String(length=20), nullable=True),
        sa.Column("currency", sa.String(length=10), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="active"),
        sa.Column("last_intent", sa.String(length=100), nullable=True),
        sa.Column("context", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("transcript", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("last_recommendations", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["store_id"], ["shopify_stores.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_shopify_assistant_sessions_client_id", "shopify_assistant_sessions", ["client_id"])
    op.create_index("ix_shopify_assistant_sessions_store_id", "shopify_assistant_sessions", ["store_id"])
    op.create_index("ix_shopify_assistant_sessions_status", "shopify_assistant_sessions", ["status"])
    op.create_index("ix_shopify_assistant_sessions_last_seen_at", "shopify_assistant_sessions", ["last_seen_at"])
    op.create_index("ix_shopify_assistant_sessions_storefront_session_id", "shopify_assistant_sessions", ["storefront_session_id"])

    op.create_table(
        "shopify_discount_approvals",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("store_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="pending"),
        sa.Column("discount_type", sa.String(length=30), nullable=False, server_default="code"),
        sa.Column("value_type", sa.String(length=30), nullable=False, server_default="percentage"),
        sa.Column("value", sa.Float(), nullable=True),
        sa.Column("currency", sa.String(length=10), nullable=True),
        sa.Column("code", sa.String(length=50), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("shopper_message", sa.Text(), nullable=True),
        sa.Column("merchant_note", sa.Text(), nullable=True),
        sa.Column("cart_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("approved_by", sa.String(length=255), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["store_id"], ["shopify_stores.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["session_id"], ["shopify_assistant_sessions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_shopify_discount_approvals_client_id", "shopify_discount_approvals", ["client_id"])
    op.create_index("ix_shopify_discount_approvals_store_id", "shopify_discount_approvals", ["store_id"])
    op.create_index("ix_shopify_discount_approvals_session_id", "shopify_discount_approvals", ["session_id"])
    op.create_index("ix_shopify_discount_approvals_status", "shopify_discount_approvals", ["status"])
    op.create_index("ix_shopify_discount_approvals_created_at", "shopify_discount_approvals", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_shopify_discount_approvals_created_at", table_name="shopify_discount_approvals")
    op.drop_index("ix_shopify_discount_approvals_status", table_name="shopify_discount_approvals")
    op.drop_index("ix_shopify_discount_approvals_session_id", table_name="shopify_discount_approvals")
    op.drop_index("ix_shopify_discount_approvals_store_id", table_name="shopify_discount_approvals")
    op.drop_index("ix_shopify_discount_approvals_client_id", table_name="shopify_discount_approvals")
    op.drop_table("shopify_discount_approvals")

    op.drop_index("ix_shopify_assistant_sessions_storefront_session_id", table_name="shopify_assistant_sessions")
    op.drop_index("ix_shopify_assistant_sessions_last_seen_at", table_name="shopify_assistant_sessions")
    op.drop_index("ix_shopify_assistant_sessions_status", table_name="shopify_assistant_sessions")
    op.drop_index("ix_shopify_assistant_sessions_store_id", table_name="shopify_assistant_sessions")
    op.drop_index("ix_shopify_assistant_sessions_client_id", table_name="shopify_assistant_sessions")
    op.drop_table("shopify_assistant_sessions")

    op.drop_index("ix_shopify_stores_assistant_enabled", table_name="shopify_stores")
    op.drop_index("ix_shopify_stores_shop_domain", table_name="shopify_stores")
    op.drop_index("ix_shopify_stores_client_id", table_name="shopify_stores")
    op.drop_table("shopify_stores")

"""Add site template instances table.

Revision ID: 0011
Revises: 0010
Create Date: 2026-04-15 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0011"
down_revision: Union[str, None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "site_template_instances",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "client_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("clients.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("site_slug", sa.String(length=255), nullable=False),
        sa.Column("public_slug", sa.String(length=255), nullable=False, unique=True),
        sa.Column("template_slug", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("content", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("theme_overrides", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("agent_embed_config", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("client_id", "site_slug", name="uq_site_template_instance_slug_per_client"),
    )
    op.create_index(
        "ix_site_template_instances_client_id",
        "site_template_instances",
        ["client_id"],
    )
    op.create_index(
        "ix_site_template_instances_template_slug",
        "site_template_instances",
        ["template_slug"],
    )
    op.create_index(
        "ix_site_template_instances_public_slug",
        "site_template_instances",
        ["public_slug"],
    )


def downgrade() -> None:
    op.drop_index("ix_site_template_instances_public_slug", table_name="site_template_instances")
    op.drop_index("ix_site_template_instances_template_slug", table_name="site_template_instances")
    op.drop_index("ix_site_template_instances_client_id", table_name="site_template_instances")
    op.drop_table("site_template_instances")

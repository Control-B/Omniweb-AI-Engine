"""add internal user permissions

Revision ID: 0012_add_internal_user_permissions
Revises: 0011_add_site_template_instances
Create Date: 2026-04-15 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0012_add_internal_user_permissions"
down_revision = "0011_add_site_template_instances"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "clients",
        sa.Column(
            "permissions",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.execute(
        """
        UPDATE clients
        SET permissions = CASE
            WHEN role = 'owner' THEN '["*"]'::jsonb
            WHEN role = 'admin' THEN '["overview.read","clients.read","clients.write","agents.read","conversations.read","templates.read","templates.write"]'::jsonb
            WHEN role = 'support' THEN '["overview.read","clients.read","agents.read","conversations.read","templates.read"]'::jsonb
            ELSE '[]'::jsonb
        END
        """
    )
    op.alter_column("clients", "permissions", server_default=None)


def downgrade() -> None:
    op.drop_column("clients", "permissions")
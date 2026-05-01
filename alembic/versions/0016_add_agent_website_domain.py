"""add agent website_domain

Revision ID: 0016
Revises: 0015
Create Date: 2026-04-16 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("agent_configs", sa.Column("website_domain", sa.String(255), nullable=True))
    op.create_unique_constraint("uq_agent_configs_website_domain", "agent_configs", ["website_domain"])
    op.create_index("ix_agent_configs_website_domain", "agent_configs", ["website_domain"])


def downgrade() -> None:
    op.drop_index("ix_agent_configs_website_domain", table_name="agent_configs")
    op.drop_constraint("uq_agent_configs_website_domain", "agent_configs", type_="unique")
    op.drop_column("agent_configs", "website_domain")
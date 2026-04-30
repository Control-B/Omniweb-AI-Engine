"""Add universal agent config and analytics tagging fields.

Revision ID: 0020
Revises: 0019
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "agent_configs",
        sa.Column(
            "enabled_channels",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[\"website_chat\"]'::jsonb"),
        ),
    )
    op.add_column(
        "agent_configs",
        sa.Column(
            "lead_capture_fields",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[\"name\",\"email\",\"phone\",\"company\",\"goal\"]'::jsonb"),
        ),
    )
    op.add_column(
        "agent_configs",
        sa.Column(
            "qualification_rules",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.add_column(
        "agent_configs",
        sa.Column(
            "enabled_features",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.add_column("agent_configs", sa.Column("custom_instructions", sa.Text(), nullable=True))

    op.alter_column(
        "agent_configs",
        "agent_mode",
        existing_type=sa.String(length=50),
        server_default="general_lead_gen",
        existing_nullable=False,
    )

    op.add_column("engagements", sa.Column("agent_mode", sa.String(length=50), nullable=False, server_default="general_lead_gen"))
    op.add_column("engagements", sa.Column("conversion_stage", sa.String(length=50), nullable=False, server_default="awareness"))
    op.add_column(
        "engagements",
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.create_index("ix_engagements_agent_mode", "engagements", ["agent_mode"], unique=False)
    op.create_index("ix_engagements_conversion_stage", "engagements", ["conversion_stage"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_engagements_conversion_stage", table_name="engagements")
    op.drop_index("ix_engagements_agent_mode", table_name="engagements")
    op.drop_column("engagements", "metadata")
    op.drop_column("engagements", "conversion_stage")
    op.drop_column("engagements", "agent_mode")

    op.alter_column(
        "agent_configs",
        "agent_mode",
        existing_type=sa.String(length=50),
        server_default="lead_qualifier",
        existing_nullable=False,
    )
    op.drop_column("agent_configs", "custom_instructions")
    op.drop_column("agent_configs", "enabled_features")
    op.drop_column("agent_configs", "qualification_rules")
    op.drop_column("agent_configs", "lead_capture_fields")
    op.drop_column("agent_configs", "enabled_channels")

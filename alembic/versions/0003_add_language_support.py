"""Add language support columns to agent_configs and agent_templates.

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-11
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

DEFAULT_LANGUAGES = ["en"]
ALL_LANGUAGES = [
    "en", "es", "fr", "de", "ar", "hi", "pt", "it",
    "ja", "ko", "zh", "nl", "pl", "ru", "tr", "uk",
]


def upgrade() -> None:
    # agent_configs
    op.add_column(
        "agent_configs",
        sa.Column(
            "supported_languages",
            JSONB,
            nullable=False,
            server_default=sa.text(f"'{DEFAULT_LANGUAGES}'::jsonb"),
        ),
    )
    op.add_column(
        "agent_configs",
        sa.Column(
            "language_presets",
            JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )

    # agent_templates
    op.add_column(
        "agent_templates",
        sa.Column(
            "supported_languages",
            JSONB,
            nullable=False,
            server_default=sa.text(f"'{ALL_LANGUAGES}'::jsonb"),
        ),
    )
    op.add_column(
        "agent_templates",
        sa.Column(
            "language_presets",
            JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )


def downgrade() -> None:
    op.drop_column("agent_templates", "language_presets")
    op.drop_column("agent_templates", "supported_languages")
    op.drop_column("agent_configs", "language_presets")
    op.drop_column("agent_configs", "supported_languages")

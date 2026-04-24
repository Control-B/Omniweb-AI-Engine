"""add deepgram and retell provider fields

Revision ID: 0017
Revises: 0016
Create Date: 2026-04-24 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("agent_configs", sa.Column("retell_agent_id", sa.String(length=100), nullable=True))
    op.add_column("agent_configs", sa.Column("retell_agent_version", sa.Integer(), nullable=True))
    op.add_column("agent_configs", sa.Column("voice_provider", sa.String(length=30), nullable=False, server_default="deepgram"))
    op.add_column("agent_configs", sa.Column("telephony_provider", sa.String(length=30), nullable=False, server_default="retell"))
    op.add_column("agent_configs", sa.Column("deepgram_tts_model", sa.String(length=100), nullable=True))
    op.add_column("agent_configs", sa.Column("retell_voice_id", sa.String(length=100), nullable=True))
    op.create_unique_constraint("uq_agent_configs_retell_agent_id", "agent_configs", ["retell_agent_id"])
    op.create_index("ix_agent_configs_retell_agent_id", "agent_configs", ["retell_agent_id"])

    op.add_column("phone_numbers", sa.Column("provider", sa.String(length=30), nullable=False, server_default="twilio-elevenlabs"))
    op.add_column("phone_numbers", sa.Column("retell_phone_number_id", sa.String(length=100), nullable=True))
    op.alter_column("phone_numbers", "twilio_sid", existing_type=sa.String(length=100), nullable=True)
    op.create_unique_constraint("uq_phone_numbers_retell_phone_number_id", "phone_numbers", ["retell_phone_number_id"])

    op.add_column("calls", sa.Column("provider", sa.String(length=30), nullable=False, server_default="elevenlabs"))
    op.add_column("calls", sa.Column("retell_call_id", sa.String(length=100), nullable=True))
    op.create_unique_constraint("uq_calls_retell_call_id", "calls", ["retell_call_id"])
    op.create_index("ix_calls_retell_call_id", "calls", ["retell_call_id"])

    op.alter_column("agent_configs", "voice_provider", server_default=None)
    op.alter_column("agent_configs", "telephony_provider", server_default=None)
    op.alter_column("phone_numbers", "provider", server_default=None)
    op.alter_column("calls", "provider", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_calls_retell_call_id", table_name="calls")
    op.drop_constraint("uq_calls_retell_call_id", "calls", type_="unique")
    op.drop_column("calls", "retell_call_id")
    op.drop_column("calls", "provider")

    op.drop_constraint("uq_phone_numbers_retell_phone_number_id", "phone_numbers", type_="unique")
    op.alter_column("phone_numbers", "twilio_sid", existing_type=sa.String(length=100), nullable=False)
    op.drop_column("phone_numbers", "retell_phone_number_id")
    op.drop_column("phone_numbers", "provider")

    op.drop_index("ix_agent_configs_retell_agent_id", table_name="agent_configs")
    op.drop_constraint("uq_agent_configs_retell_agent_id", "agent_configs", type_="unique")
    op.drop_column("agent_configs", "retell_voice_id")
    op.drop_column("agent_configs", "deepgram_tts_model")
    op.drop_column("agent_configs", "telephony_provider")
    op.drop_column("agent_configs", "voice_provider")
    op.drop_column("agent_configs", "retell_agent_version")
    op.drop_column("agent_configs", "retell_agent_id")

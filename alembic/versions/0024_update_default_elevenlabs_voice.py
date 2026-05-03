"""Update default ElevenLabs voice to Sarah.

Revision ID: 0024
Revises: 0023
"""

import sqlalchemy as sa

from alembic import op

revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None


OLD_VOICE_ID = "EXAVITQu4vr4xnSDxMaL"
NEW_VOICE_ID = "nf4MCGNSdM0hxM95ZBQR"


def upgrade() -> None:
    op.execute(
        sa.text("UPDATE agent_configs SET voice_id = :new_voice_id WHERE voice_id = :old_voice_id").bindparams(
            new_voice_id=NEW_VOICE_ID,
            old_voice_id=OLD_VOICE_ID,
        )
    )
    op.execute(
        sa.text("UPDATE agent_templates SET voice_id = :new_voice_id WHERE voice_id = :old_voice_id").bindparams(
            new_voice_id=NEW_VOICE_ID,
            old_voice_id=OLD_VOICE_ID,
        )
    )
    op.alter_column("agent_configs", "voice_id", server_default=NEW_VOICE_ID)
    op.alter_column("agent_templates", "voice_id", server_default=NEW_VOICE_ID)


def downgrade() -> None:
    op.execute(
        sa.text("UPDATE agent_configs SET voice_id = :old_voice_id WHERE voice_id = :new_voice_id").bindparams(
            old_voice_id=OLD_VOICE_ID,
            new_voice_id=NEW_VOICE_ID,
        )
    )
    op.execute(
        sa.text("UPDATE agent_templates SET voice_id = :old_voice_id WHERE voice_id = :new_voice_id").bindparams(
            old_voice_id=OLD_VOICE_ID,
            new_voice_id=NEW_VOICE_ID,
        )
    )
    op.alter_column("agent_configs", "voice_id", server_default=OLD_VOICE_ID)
    op.alter_column("agent_templates", "voice_id", server_default=OLD_VOICE_ID)

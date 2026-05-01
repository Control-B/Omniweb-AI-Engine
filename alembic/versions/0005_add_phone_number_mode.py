"""Add mode and forward_to columns to phone_numbers for call forwarding.

Revision ID: 0005
Revises: 0004
Create Date: 2026-04-12 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # mode: "ai" (ElevenLabs handles calls) or "forward" (Twilio forwards to a real phone)
    op.add_column(
        "phone_numbers",
        sa.Column("mode", sa.String(20), server_default="ai", nullable=False),
    )
    # The E.164 phone number to forward calls to when mode = "forward"
    op.add_column(
        "phone_numbers",
        sa.Column("forward_to", sa.String(30), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("phone_numbers", "forward_to")
    op.drop_column("phone_numbers", "mode")

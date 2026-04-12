"""Add password reset and invite token fields to clients.

Revision ID: 0006
Revises: 0005
Create Date: 2026-04-12 00:30:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("clients", sa.Column("password_reset_token_hash", sa.String(length=128), nullable=True))
    op.add_column("clients", sa.Column("password_reset_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("clients", sa.Column("invite_token_hash", sa.String(length=128), nullable=True))
    op.add_column("clients", sa.Column("invite_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("clients", sa.Column("invited_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("clients", sa.Column("invite_accepted_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_clients_password_reset_token_hash", "clients", ["password_reset_token_hash"])
    op.create_index("ix_clients_invite_token_hash", "clients", ["invite_token_hash"])


def downgrade() -> None:
    op.drop_index("ix_clients_invite_token_hash", table_name="clients")
    op.drop_index("ix_clients_password_reset_token_hash", table_name="clients")
    op.drop_column("clients", "invite_accepted_at")
    op.drop_column("clients", "invited_at")
    op.drop_column("clients", "invite_expires_at")
    op.drop_column("clients", "invite_token_hash")
    op.drop_column("clients", "password_reset_expires_at")
    op.drop_column("clients", "password_reset_token_hash")

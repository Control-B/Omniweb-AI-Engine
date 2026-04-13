"""Add embed code fields to clients table for widget distribution.

Each client gets a unique embed authorization code tied to their email
and phone number. The code is non-transferable and expires when the
subscription ends.

Revision ID: 0009
Revises: 0008
Create Date: 2026-04-13
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("clients", sa.Column("embed_code", sa.String(64), nullable=True, unique=True))
    op.add_column("clients", sa.Column("embed_domain", sa.String(255), nullable=True))
    op.add_column("clients", sa.Column("embed_phone", sa.String(20), nullable=True))
    op.add_column("clients", sa.Column("embed_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("clients", sa.Column("trial_ends_at", sa.DateTime(timezone=True), nullable=True))

    op.create_index("ix_clients_embed_code", "clients", ["embed_code"])


def downgrade() -> None:
    op.drop_index("ix_clients_embed_code", table_name="clients")
    op.drop_column("clients", "trial_ends_at")
    op.drop_column("clients", "embed_expires_at")
    op.drop_column("clients", "embed_phone")
    op.drop_column("clients", "embed_domain")
    op.drop_column("clients", "embed_code")

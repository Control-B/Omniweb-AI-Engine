"""Add dashboard sync models and tenant billing fields.

Revision ID: 0019
Revises: 0018
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("clients", sa.Column("clerk_org_id", sa.String(length=100), nullable=True))
    op.add_column("clients", sa.Column("industry", sa.String(length=100), nullable=True))
    op.add_column("clients", sa.Column("subscription_started_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("clients", sa.Column("subscription_ends_at", sa.DateTime(timezone=True), nullable=True))

    op.create_index("ix_clients_clerk_org_id", "clients", ["clerk_org_id"], unique=False)
    op.create_index("ix_clients_subscription_status", "clients", ["subscription_status"], unique=False)
    op.create_index("ix_clients_created_at", "clients", ["created_at"], unique=False)

    op.add_column("agent_configs", sa.Column("tone", sa.String(length=30), nullable=False, server_default="professional"))
    op.add_column(
        "agent_configs",
        sa.Column("goals", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
    )
    op.add_column("agent_configs", sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")))

    op.create_table(
        "engagements",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", sa.String(length=120), nullable=False),
        sa.Column("channel", sa.String(length=50), nullable=False, server_default="website_chat"),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("language", sa.String(length=20), nullable=True),
        sa.Column("visitor_name", sa.String(length=255), nullable=True),
        sa.Column("visitor_email", sa.String(length=255), nullable=True),
        sa.Column("visitor_phone", sa.String(length=30), nullable=True),
        sa.Column("lead_status", sa.String(length=40), nullable=False, server_default="new"),
        sa.Column("intent", sa.String(length=100), nullable=True),
        sa.Column("contact_captured", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("qualified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("follow_up_needed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("summary_short", sa.Text(), nullable=True),
        sa.Column("summary_full", sa.Text(), nullable=True),
        sa.Column("transcript", sa.Text(), nullable=True),
        sa.Column("lead_score", sa.Float(), nullable=True),
        sa.Column("pain_points", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("buying_signals", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("objections", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("recommended_next_action", sa.Text(), nullable=True),
        sa.Column("owner_notes", sa.Text(), nullable=True),
        sa.Column("resolved", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index("ix_engagements_client_id", "engagements", ["client_id"], unique=False)
    op.create_index("ix_engagements_client_id_created_at", "engagements", ["client_id", "created_at"], unique=False)
    op.create_index("ix_engagements_lead_status", "engagements", ["lead_status"], unique=False)
    op.create_index("ix_engagements_created_at", "engagements", ["created_at"], unique=False)
    op.create_index("ix_engagements_session_id", "engagements", ["session_id"], unique=False)

    op.create_table(
        "follow_up_tasks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("engagement_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("instruction", sa.Text(), nullable=False),
        sa.Column("channel", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["engagement_id"], ["engagements.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index("ix_follow_up_tasks_client_id", "follow_up_tasks", ["client_id"], unique=False)
    op.create_index("ix_follow_up_tasks_engagement_id", "follow_up_tasks", ["engagement_id"], unique=False)
    op.create_index("ix_follow_up_tasks_created_at", "follow_up_tasks", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_follow_up_tasks_created_at", table_name="follow_up_tasks")
    op.drop_index("ix_follow_up_tasks_engagement_id", table_name="follow_up_tasks")
    op.drop_index("ix_follow_up_tasks_client_id", table_name="follow_up_tasks")
    op.drop_table("follow_up_tasks")

    op.drop_index("ix_engagements_session_id", table_name="engagements")
    op.drop_index("ix_engagements_created_at", table_name="engagements")
    op.drop_index("ix_engagements_lead_status", table_name="engagements")
    op.drop_index("ix_engagements_client_id_created_at", table_name="engagements")
    op.drop_index("ix_engagements_client_id", table_name="engagements")
    op.drop_table("engagements")

    op.drop_column("agent_configs", "active")
    op.drop_column("agent_configs", "goals")
    op.drop_column("agent_configs", "tone")

    op.drop_index("ix_clients_created_at", table_name="clients")
    op.drop_index("ix_clients_subscription_status", table_name="clients")
    op.drop_index("ix_clients_clerk_org_id", table_name="clients")
    op.drop_column("clients", "subscription_ends_at")
    op.drop_column("clients", "subscription_started_at")
    op.drop_column("clients", "industry")
    op.drop_column("clients", "clerk_org_id")
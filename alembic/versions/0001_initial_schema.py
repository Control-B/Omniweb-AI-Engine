"""Initial migration — create all Omniweb tables.

Revision ID: 0001
Revises: 
Create Date: 2026-04-11 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Enums ─────────────────────────────────────────────────
    plan_enum = postgresql.ENUM("starter", "growth", "pro", "agency", name="plan_enum", create_type=False)
    plan_enum.create(op.get_bind(), checkfirst=True)

    call_direction_enum = postgresql.ENUM("inbound", "outbound", name="call_direction_enum", create_type=False)
    call_direction_enum.create(op.get_bind(), checkfirst=True)

    call_status_enum = postgresql.ENUM(
        "queued", "ringing", "in_progress", "completed", "failed", "no_answer", "busy",
        name="call_status_enum", create_type=False
    )
    call_status_enum.create(op.get_bind(), checkfirst=True)

    urgency_enum = postgresql.ENUM("low", "medium", "high", "emergency", name="urgency_enum", create_type=False)
    urgency_enum.create(op.get_bind(), checkfirst=True)

    lead_status_enum = postgresql.ENUM("new", "contacted", "booked", "closed", "lost", name="lead_status_enum", create_type=False)
    lead_status_enum.create(op.get_bind(), checkfirst=True)

    sms_direction_enum = postgresql.ENUM("inbound", "outbound", name="sms_direction_enum", create_type=False)
    sms_direction_enum.create(op.get_bind(), checkfirst=True)

    sequence_trigger_enum = postgresql.ENUM(
        "after_call", "missed_call", "new_lead", "manual",
        name="sequence_trigger_enum", create_type=False
    )
    sequence_trigger_enum.create(op.get_bind(), checkfirst=True)

    # ── clients ───────────────────────────────────────────────
    op.create_table(
        "clients",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("stripe_customer_id", sa.String(100), nullable=True),
        sa.Column("stripe_subscription_id", sa.String(100), nullable=True),
        sa.Column("plan", sa.Enum("starter", "growth", "pro", "agency", name="plan_enum"), nullable=False, server_default="starter"),
        sa.Column("plan_minutes_used", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("supabase_user_id", sa.String(100), nullable=True),
        sa.Column("crm_webhook_url", sa.String(500), nullable=True),
        sa.Column("notification_email", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
        sa.UniqueConstraint("supabase_user_id"),
    )
    op.create_index("ix_clients_email", "clients", ["email"])
    op.create_index("ix_clients_stripe_customer_id", "clients", ["stripe_customer_id"])

    # ── agent_configs ─────────────────────────────────────────
    op.create_table(
        "agent_configs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agent_name", sa.String(100), nullable=False, server_default="Alex"),
        sa.Column("agent_greeting", sa.Text(), nullable=False, server_default="Thank you for calling! How can I help you today?"),
        sa.Column("voice_id", sa.String(100), nullable=False, server_default="EXAVITQu4vr4xnSDxMaL"),
        sa.Column("voice_stability", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("voice_similarity_boost", sa.Float(), nullable=False, server_default="0.75"),
        sa.Column("system_prompt", sa.Text(), nullable=False, server_default=""),
        sa.Column("llm_model", sa.String(100), nullable=False, server_default="gpt-4o"),
        sa.Column("temperature", sa.Float(), nullable=False, server_default="0.7"),
        sa.Column("business_name", sa.String(255), nullable=False, server_default=""),
        sa.Column("business_type", sa.String(100), nullable=True),
        sa.Column("timezone", sa.String(50), nullable=False, server_default="America/New_York"),
        sa.Column("booking_url", sa.String(500), nullable=True),
        sa.Column("business_hours", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("services", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("after_hours_message", sa.Text(), nullable=False, server_default="We are currently closed but will call you back first thing in the morning."),
        sa.Column("after_hours_sms_enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("allow_interruptions", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("min_endpointing_delay", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("max_endpointing_delay", sa.Float(), nullable=False, server_default="5.0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("client_id"),
    )
    op.create_index("ix_agent_configs_client_id", "agent_configs", ["client_id"])

    # ── phone_numbers ─────────────────────────────────────────
    op.create_table(
        "phone_numbers",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("twilio_sid", sa.String(100), nullable=False),
        sa.Column("phone_number", sa.String(30), nullable=False),
        sa.Column("livekit_sip_trunk_id", sa.String(100), nullable=True),
        sa.Column("livekit_dispatch_rule_id", sa.String(100), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("friendly_name", sa.String(255), nullable=True),
        sa.Column("area_code", sa.String(10), nullable=True),
        sa.Column("country", sa.String(5), nullable=False, server_default="US"),
        sa.Column("provisioned_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("twilio_sid"),
        sa.UniqueConstraint("phone_number"),
    )
    op.create_index("ix_phone_numbers_client_id", "phone_numbers", ["client_id"])
    op.create_index("ix_phone_numbers_phone_number", "phone_numbers", ["phone_number"])

    # ── calls ─────────────────────────────────────────────────
    op.create_table(
        "calls",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("phone_number_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("caller_number", sa.String(30), nullable=False),
        sa.Column("direction", sa.Enum("inbound", "outbound", name="call_direction_enum"), nullable=False),
        sa.Column("status", sa.Enum("queued", "ringing", "in_progress", "completed", "failed", "no_answer", "busy", name="call_status_enum"), nullable=False, server_default="queued"),
        sa.Column("livekit_room_name", sa.String(255), nullable=True),
        sa.Column("livekit_room_id", sa.String(255), nullable=True),
        sa.Column("twilio_call_sid", sa.String(100), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("recording_url", sa.String(500), nullable=True),
        sa.Column("recording_sid", sa.String(100), nullable=True),
        sa.Column("post_call_processed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("crm_webhook_fired", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["phone_number_id"], ["phone_numbers.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_calls_client_id", "calls", ["client_id"])
    op.create_index("ix_calls_caller_number", "calls", ["caller_number"])
    op.create_index("ix_calls_status", "calls", ["status"])
    op.create_index("ix_calls_started_at", "calls", ["started_at"])
    op.create_index("ix_calls_livekit_room_name", "calls", ["livekit_room_name"])

    # ── transcripts ───────────────────────────────────────────
    op.create_table(
        "transcripts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("call_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("turns", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("sentiment", sa.String(20), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["call_id"], ["calls.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("call_id"),
    )
    op.create_index("ix_transcripts_call_id", "transcripts", ["call_id"])
    op.create_index("ix_transcripts_client_id", "transcripts", ["client_id"])

    # ── leads ─────────────────────────────────────────────────
    op.create_table(
        "leads",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("call_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("caller_name", sa.String(255), nullable=True),
        sa.Column("caller_phone", sa.String(30), nullable=False),
        sa.Column("caller_email", sa.String(255), nullable=True),
        sa.Column("intent", sa.String(100), nullable=True),
        sa.Column("urgency", sa.Enum("low", "medium", "high", "emergency", name="urgency_enum"), nullable=False, server_default="medium"),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("services_requested", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("status", sa.Enum("new", "contacted", "booked", "closed", "lost", name="lead_status_enum"), nullable=False, server_default="new"),
        sa.Column("status_notes", sa.Text(), nullable=True),
        sa.Column("lead_score", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("follow_up_sent", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("follow_up_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["call_id"], ["calls.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("call_id"),
    )
    op.create_index("ix_leads_client_id", "leads", ["client_id"])
    op.create_index("ix_leads_status", "leads", ["status"])
    op.create_index("ix_leads_caller_phone", "leads", ["caller_phone"])
    op.create_index("ix_leads_created_at", "leads", ["created_at"])

    # ── sms_messages ──────────────────────────────────────────
    op.create_table(
        "sms_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("call_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("direction", sa.Enum("inbound", "outbound", name="sms_direction_enum"), nullable=False),
        sa.Column("to_number", sa.String(30), nullable=False),
        sa.Column("from_number", sa.String(30), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("twilio_sid", sa.String(100), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="queued"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["call_id"], ["calls.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sms_messages_client_id", "sms_messages", ["client_id"])
    op.create_index("ix_sms_messages_to_number", "sms_messages", ["to_number"])
    op.create_index("ix_sms_messages_sent_at", "sms_messages", ["sent_at"])

    # ── outreach_sequences ────────────────────────────────────
    op.create_table(
        "outreach_sequences",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("trigger", sa.Enum("after_call", "missed_call", "new_lead", "manual", name="sequence_trigger_enum"), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("steps", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("client_id", "name", name="uq_outreach_sequence_name"),
    )
    op.create_index("ix_outreach_sequences_client_id", "outreach_sequences", ["client_id"])


def downgrade() -> None:
    op.drop_table("outreach_sequences")
    op.drop_table("sms_messages")
    op.drop_table("leads")
    op.drop_table("transcripts")
    op.drop_table("calls")
    op.drop_table("phone_numbers")
    op.drop_table("agent_configs")
    op.drop_table("clients")

    # Drop enums
    for enum_name in [
        "sequence_trigger_enum", "sms_direction_enum", "lead_status_enum",
        "urgency_enum", "call_status_enum", "call_direction_enum", "plan_enum",
    ]:
        op.execute(f"DROP TYPE IF EXISTS {enum_name}")

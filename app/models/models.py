"""SQLAlchemy ORM models for Omniweb Agent Engine.

Multi-tenant design: every table that holds client data has a client_id FK.
All UUIDs are native PostgreSQL UUIDs.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ── Clients ──────────────────────────────────────────────────────────────────

class Client(Base):
    """A business that uses Omniweb (mechanic shop, law firm, doctor, etc.)"""
    __tablename__ = "clients"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)

    # Auth
    hashed_password: Mapped[str | None] = mapped_column(String(500), nullable=True)
    api_key_hash: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)

    # Billing
    stripe_customer_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    plan: Mapped[str] = mapped_column(
        Enum("starter", "growth", "pro", "agency", name="plan_enum", create_constraint=False),
        default="starter",
        nullable=False,
    )
    plan_minutes_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    supabase_user_id: Mapped[str | None] = mapped_column(String(100), nullable=True, unique=True)
    crm_webhook_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    notification_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    # Relationships
    agent_config: Mapped["AgentConfig | None"] = relationship(back_populates="client", uselist=False)
    phone_numbers: Mapped[list["PhoneNumber"]] = relationship(back_populates="client")
    calls: Mapped[list["Call"]] = relationship(back_populates="client")
    leads: Mapped[list["Lead"]] = relationship(back_populates="client")
    sms_messages: Mapped[list["SmsMessage"]] = relationship(back_populates="client")
    outreach_sequences: Mapped[list["OutreachSequence"]] = relationship(back_populates="client")

    __table_args__ = (
        Index("ix_clients_email", "email"),
        Index("ix_clients_stripe_customer_id", "stripe_customer_id"),
    )


# ── Agent Configs ─────────────────────────────────────────────────────────────

class AgentConfig(Base):
    """Per-client AI agent configuration — voice, prompt, hours, services."""
    __tablename__ = "agent_configs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, unique=True)

    # ElevenLabs agent linkage
    elevenlabs_agent_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    elevenlabs_kb_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Identity
    agent_name: Mapped[str] = mapped_column(String(100), default="Alex", nullable=False)
    agent_greeting: Mapped[str] = mapped_column(
        Text,
        default="Thank you for calling! How can I help you today?",
        nullable=False,
    )

    # Voice (ElevenLabs voice ID)
    voice_id: Mapped[str] = mapped_column(String(100), default="EXAVITQu4vr4xnSDxMaL", nullable=False)
    voice_stability: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    voice_similarity_boost: Mapped[float] = mapped_column(Float, default=0.75, nullable=False)

    # LLM / brain
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    llm_model: Mapped[str] = mapped_column(String(100), default="gpt-4o", nullable=False)
    temperature: Mapped[float] = mapped_column(Float, default=0.7, nullable=False)

    # Business context
    business_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    business_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    timezone: Mapped[str] = mapped_column(String(50), default="America/New_York", nullable=False)
    booking_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Business hours: {"mon": {"open": "09:00", "close": "17:00", "closed": false}, ...}
    business_hours: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    # Services offered: ["oil change", "brake repair", ...]
    services: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)

    # After-hours behavior
    after_hours_message: Mapped[str] = mapped_column(
        Text,
        default="We're currently closed but will call you back first thing in the morning.",
        nullable=False,
    )
    after_hours_sms_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Conversation tuning
    allow_interruptions: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    max_call_duration: Mapped[int] = mapped_column(Integer, default=1800, nullable=False)

    # Widget configuration
    widget_config: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    # Relationship
    client: Mapped["Client"] = relationship(back_populates="agent_config")

    __table_args__ = (
        Index("ix_agent_configs_client_id", "client_id"),
        Index("ix_agent_configs_elevenlabs_agent_id", "elevenlabs_agent_id"),
    )


# ── Phone Numbers ─────────────────────────────────────────────────────────────

class PhoneNumber(Base):
    """A Twilio phone number imported into ElevenLabs for a client."""
    __tablename__ = "phone_numbers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)

    # Twilio
    twilio_sid: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    phone_number: Mapped[str] = mapped_column(String(30), nullable=False, unique=True)  # E.164

    # ElevenLabs
    elevenlabs_phone_number_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    friendly_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    area_code: Mapped[str | None] = mapped_column(String(10), nullable=True)
    country: Mapped[str] = mapped_column(String(5), default="US", nullable=False)

    provisioned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    # Relationships
    client: Mapped["Client"] = relationship(back_populates="phone_numbers")
    calls: Mapped[list["Call"]] = relationship(back_populates="phone_number")

    __table_args__ = (
        Index("ix_phone_numbers_client_id", "client_id"),
        Index("ix_phone_numbers_phone_number", "phone_number"),
    )


# ── Calls ─────────────────────────────────────────────────────────────────────

class Call(Base):
    """A conversation handled by the AI agent — voice, text, or WhatsApp."""
    __tablename__ = "calls"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    phone_number_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("phone_numbers.id", ondelete="SET NULL"), nullable=True)

    # Call metadata
    caller_number: Mapped[str] = mapped_column(String(30), nullable=False, default="")
    direction: Mapped[str] = mapped_column(String(20), nullable=False, default="inbound")
    channel: Mapped[str] = mapped_column(String(20), nullable=False, default="voice")  # voice | text | whatsapp
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="queued")

    # ElevenLabs
    elevenlabs_conversation_id: Mapped[str | None] = mapped_column(String(100), nullable=True, unique=True)

    # Twilio (for SMS follow-ups or outbound)
    twilio_call_sid: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Timing
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Recording
    recording_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Post-call
    post_call_processed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    crm_webhook_fired: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    # Relationships
    client: Mapped["Client"] = relationship(back_populates="calls")
    phone_number: Mapped["PhoneNumber | None"] = relationship(back_populates="calls")
    transcript: Mapped["Transcript | None"] = relationship(back_populates="call", uselist=False)
    lead: Mapped["Lead | None"] = relationship(back_populates="call", uselist=False)
    sms_messages: Mapped[list["SmsMessage"]] = relationship(back_populates="call")

    __table_args__ = (
        Index("ix_calls_client_id", "client_id"),
        Index("ix_calls_caller_number", "caller_number"),
        Index("ix_calls_status", "status"),
        Index("ix_calls_started_at", "started_at"),
        Index("ix_calls_channel", "channel"),
        Index("ix_calls_elevenlabs_conversation_id", "elevenlabs_conversation_id"),
    )


# ── Transcripts ───────────────────────────────────────────────────────────────

class Transcript(Base):
    """Full conversation transcript — stored as JSONB turns."""
    __tablename__ = "transcripts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    call_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("calls.id", ondelete="CASCADE"), nullable=False, unique=True)
    client_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)

    # turns: [{"speaker": "agent"|"caller", "text": "...", "timestamp": 0.0}]
    turns: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)

    # Derived fields (populated by post-call LLM processing)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    sentiment: Mapped[str | None] = mapped_column(String(20), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    # Relationships
    call: Mapped["Call"] = relationship(back_populates="transcript")

    __table_args__ = (
        Index("ix_transcripts_call_id", "call_id"),
        Index("ix_transcripts_client_id", "client_id"),
    )


# ── Leads ─────────────────────────────────────────────────────────────────────

class Lead(Base):
    """A qualified lead extracted from a conversation by the post-call LLM processor."""
    __tablename__ = "leads"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    call_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("calls.id", ondelete="SET NULL"), nullable=True, unique=True)
    client_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)

    # Contact info
    caller_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    caller_phone: Mapped[str] = mapped_column(String(30), nullable=False)
    caller_email: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Lead classification
    intent: Mapped[str | None] = mapped_column(String(100), nullable=True)
    urgency: Mapped[str] = mapped_column(String(20), default="medium", nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    services_requested: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)

    # Pipeline status
    status: Mapped[str] = mapped_column(String(20), default="new", nullable=False)
    status_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Scoring (0.0–1.0)
    lead_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    # Follow-up
    follow_up_sent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    follow_up_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    # Relationships
    call: Mapped["Call | None"] = relationship(back_populates="lead")
    client: Mapped["Client"] = relationship(back_populates="leads")

    __table_args__ = (
        Index("ix_leads_client_id", "client_id"),
        Index("ix_leads_status", "status"),
        Index("ix_leads_caller_phone", "caller_phone"),
        Index("ix_leads_created_at", "created_at"),
    )


# ── SMS Messages ──────────────────────────────────────────────────────────────

class SmsMessage(Base):
    """An SMS message sent or received as part of a client's campaign or follow-up."""
    __tablename__ = "sms_messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    call_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("calls.id", ondelete="SET NULL"), nullable=True)

    direction: Mapped[str] = mapped_column(String(20), nullable=False)
    to_number: Mapped[str] = mapped_column(String(30), nullable=False)
    from_number: Mapped[str] = mapped_column(String(30), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)

    # Twilio
    twilio_sid: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="queued", nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    # Relationships
    client: Mapped["Client"] = relationship(back_populates="sms_messages")
    call: Mapped["Call | None"] = relationship(back_populates="sms_messages")

    __table_args__ = (
        Index("ix_sms_messages_client_id", "client_id"),
        Index("ix_sms_messages_to_number", "to_number"),
        Index("ix_sms_messages_sent_at", "sent_at"),
    )


# ── Outreach Sequences ────────────────────────────────────────────────────────

class OutreachSequence(Base):
    """An automated follow-up sequence (series of SMS steps after a trigger)."""
    __tablename__ = "outreach_sequences"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    trigger: Mapped[str] = mapped_column(String(30), nullable=False, default="after_call")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # steps: [{"delay_minutes": 5, "type": "sms", "template": "Hi {name}, thanks for calling..."}]
    steps: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    # Relationship
    client: Mapped["Client"] = relationship(back_populates="outreach_sequences")

    __table_args__ = (
        Index("ix_outreach_sequences_client_id", "client_id"),
        UniqueConstraint("client_id", "name", name="uq_outreach_sequence_name"),
    )

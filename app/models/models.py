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

    # Role: "client" (default tenant) or "admin" (platform owner)
    role: Mapped[str] = mapped_column(String(20), default="client", nullable=False)

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
    clerk_user_id: Mapped[str | None] = mapped_column(String(100), nullable=True, unique=True)
    crm_webhook_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    webhook_secret: Mapped[str | None] = mapped_column(String(128), nullable=True)
    notification_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    permissions: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    password_reset_token_hash: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    password_reset_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    invite_token_hash: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    invite_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    invited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    invite_accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Embed code — unique per client, tied to email+phone, non-transferable
    embed_code: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True, index=True)
    embed_domain: Mapped[str | None] = mapped_column(String(255), nullable=True)
    embed_phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    embed_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    trial_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    # Relationships
    agent_config: Mapped["AgentConfig | None"] = relationship(back_populates="client", uselist=False)
    phone_numbers: Mapped[list["PhoneNumber"]] = relationship(back_populates="client")
    calls: Mapped[list["Call"]] = relationship(back_populates="client")
    leads: Mapped[list["Lead"]] = relationship(back_populates="client")
    sms_messages: Mapped[list["SmsMessage"]] = relationship(back_populates="client")
    outreach_sequences: Mapped[list["OutreachSequence"]] = relationship(back_populates="client")
    webhook_events: Mapped[list["WebhookEvent"]] = relationship(back_populates="client")
    site_template_instances: Mapped[list["SiteTemplateInstance"]] = relationship(back_populates="client")
    shopify_store: Mapped["ShopifyStore | None"] = relationship(back_populates="client", uselist=False)
    shopify_sessions: Mapped[list["ShopifyAssistantSession"]] = relationship(back_populates="client")
    shopify_discount_requests: Mapped[list["ShopifyDiscountApproval"]] = relationship(back_populates="client")

    __table_args__ = (
        Index("ix_clients_email", "email"),
        Index("ix_clients_stripe_customer_id", "stripe_customer_id"),
        Index("ix_clients_clerk_user_id", "clerk_user_id"),
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
        default="Hi, I'd love to help you today, so tell me the problem you're trying to solve, and I'll understand your needs, recommend the right solution, and answer your questions so you can move forward faster by text or voice. Talk to me.",
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

    # Language & multilingual presets
    supported_languages: Mapped[list] = mapped_column(
        JSONB,
        default=lambda: ["en"],
        nullable=False,
        doc="Enabled language codes, e.g. ['en','es','fr']",
    )
    language_presets: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
        doc="ElevenLabs language_presets config (keyed by language code)",
    )

    # Widget configuration
    widget_config: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    # ── Multi-tenant AI platform fields ─────────────────────────────────────
    # Industry & agent mode (drives prompt composition, guardrails, tool set)
    industry: Mapped[str] = mapped_column(String(100), default="general", nullable=False)
    agent_mode: Mapped[str] = mapped_column(String(50), default="lead_qualifier", nullable=False)

    # Custom guardrails & escalation triggers (appended to industry defaults)
    custom_guardrails: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    custom_escalation_triggers: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)

    # Additional business context (FAQs, policies, etc.)
    custom_context: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Whether to use the prompt engine to compose the system_prompt automatically
    use_prompt_engine: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Human handoff configuration
    handoff_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    handoff_phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    handoff_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    handoff_message: Mapped[str] = mapped_column(
        Text,
        default="Let me connect you with a member of our team who can help with this directly.",
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    # Relationship
    client: Mapped["Client"] = relationship(back_populates="agent_config")

    __table_args__ = (
        Index("ix_agent_configs_client_id", "client_id"),
        Index("ix_agent_configs_elevenlabs_agent_id", "elevenlabs_agent_id"),
        Index("ix_agent_configs_industry", "industry"),
    )


# ── Shopify Commerce Assistant ──────────────────────────────────────────────

class ShopifyStore(Base):
    """Per-client Shopify store configuration for the commerce assistant."""
    __tablename__ = "shopify_stores"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("clients.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    shop_domain: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    shop_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    shop_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    shop_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    granted_scopes: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    storefront_access_token: Mapped[str | None] = mapped_column(String(255), nullable=True)
    admin_access_token: Mapped[str | None] = mapped_column(String(255), nullable=True)
    install_state_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    install_state_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    installed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    uninstalled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_install_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    storefront_api_version: Mapped[str] = mapped_column(String(20), default="2026-07", nullable=False)
    app_status: Mapped[str] = mapped_column(String(30), default="draft", nullable=False)
    sales_channel_name: Mapped[str | None] = mapped_column(String(100), nullable=True)

    assistant_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    require_discount_approval: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    allow_discount_requests: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    allowed_discount_types: Mapped[list] = mapped_column(JSONB, default=lambda: ["code"], nullable=False)
    support_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    support_policy: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    nav_config: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    checkout_config: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    # Shopify Billing
    shopify_subscription_gid: Mapped[str | None] = mapped_column(String(255), nullable=True)
    shopify_plan: Mapped[str | None] = mapped_column(String(50), nullable=True)
    shopify_subscription_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    shopify_billing_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    client: Mapped["Client"] = relationship(back_populates="shopify_store")
    sessions: Mapped[list["ShopifyAssistantSession"]] = relationship(back_populates="store")
    discount_requests: Mapped[list["ShopifyDiscountApproval"]] = relationship(back_populates="store")

    __table_args__ = (
        Index("ix_shopify_stores_client_id", "client_id"),
        Index("ix_shopify_stores_shop_domain", "shop_domain"),
        Index("ix_shopify_stores_shop_id", "shop_id"),
        Index("ix_shopify_stores_assistant_enabled", "assistant_enabled"),
    )


class ShopifyAssistantSession(Base):
    """Tracks a single storefront shopper's AI conversation context."""
    __tablename__ = "shopify_assistant_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    store_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("shopify_stores.id", ondelete="CASCADE"), nullable=False)

    storefront_session_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    shopper_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    shopper_locale: Mapped[str | None] = mapped_column(String(20), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(10), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="active", nullable=False)
    last_intent: Mapped[str | None] = mapped_column(String(100), nullable=True)

    context: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    transcript: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    last_recommendations: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    client: Mapped["Client"] = relationship(back_populates="shopify_sessions")
    store: Mapped["ShopifyStore"] = relationship(back_populates="sessions")
    discount_requests: Mapped[list["ShopifyDiscountApproval"]] = relationship(back_populates="session")

    __table_args__ = (
        Index("ix_shopify_assistant_sessions_client_id", "client_id"),
        Index("ix_shopify_assistant_sessions_store_id", "store_id"),
        Index("ix_shopify_assistant_sessions_status", "status"),
        Index("ix_shopify_assistant_sessions_last_seen_at", "last_seen_at"),
    )


class ShopifyDiscountApproval(Base):
    """Merchant-gated discount requests created by the AI assistant."""
    __tablename__ = "shopify_discount_approvals"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    store_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("shopify_stores.id", ondelete="CASCADE"), nullable=False)
    session_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("shopify_assistant_sessions.id", ondelete="SET NULL"), nullable=True)

    status: Mapped[str] = mapped_column(String(30), default="pending", nullable=False)
    discount_type: Mapped[str] = mapped_column(String(30), default="code", nullable=False)
    value_type: Mapped[str] = mapped_column(String(30), default="percentage", nullable=False)
    value: Mapped[float | None] = mapped_column(Float, nullable=True)
    currency: Mapped[str | None] = mapped_column(String(10), nullable=True)
    code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    shopper_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    merchant_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    cart_snapshot: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    approved_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    client: Mapped["Client"] = relationship(back_populates="shopify_discount_requests")
    store: Mapped["ShopifyStore"] = relationship(back_populates="discount_requests")
    session: Mapped["ShopifyAssistantSession | None"] = relationship(back_populates="discount_requests")

    __table_args__ = (
        Index("ix_shopify_discount_approvals_client_id", "client_id"),
        Index("ix_shopify_discount_approvals_store_id", "store_id"),
        Index("ix_shopify_discount_approvals_session_id", "session_id"),
        Index("ix_shopify_discount_approvals_status", "status"),
        Index("ix_shopify_discount_approvals_created_at", "created_at"),
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

    # Call routing mode: "ai" = ElevenLabs agent, "forward" = Twilio forwards to a real phone
    mode: Mapped[str] = mapped_column(String(20), default="ai", nullable=False)
    forward_to: Mapped[str | None] = mapped_column(String(30), nullable=True)  # E.164 number to forward to
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


# ── Webhook Events ────────────────────────────────────────────────────────────

class WebhookEvent(Base):
    """Log of every outbound webhook delivery attempt."""
    __tablename__ = "webhook_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)

    event: Mapped[str] = mapped_column(String(50), nullable=False)          # e.g. lead.created, call.completed
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)   # pending | delivered | failed
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    # Relationships
    client: Mapped["Client"] = relationship(back_populates="webhook_events")

    __table_args__ = (
        Index("ix_webhook_events_client_id", "client_id"),
        Index("ix_webhook_events_event", "event"),
        Index("ix_webhook_events_created_at", "created_at"),
        Index("ix_webhook_events_status", "status"),
    )


# ── Agent Templates ───────────────────────────────────────────────────────────

class ToolCallLog(Base):
    """Audit log for every ElevenLabs tool call processed by the platform."""
    __tablename__ = "tool_call_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)

    tool_name: Mapped[str] = mapped_column(String(100), nullable=False)
    parameters: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    result: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    success: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Optional conversation linkage
    conversation_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    lead_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("leads.id", ondelete="SET NULL"), nullable=True)

    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    # Relationships
    client: Mapped["Client"] = relationship()

    __table_args__ = (
        Index("ix_tool_call_logs_client_id", "client_id"),
        Index("ix_tool_call_logs_tool_name", "tool_name"),
        Index("ix_tool_call_logs_created_at", "created_at"),
    )


class AgentTemplate(Base):
    """Reusable agent template created by admin.

    When a new client signs up, they get an agent pre-configured from the
    default template. Clients can also pick from available templates.
    """
    __tablename__ = "agent_templates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    industry: Mapped[str] = mapped_column(String(100), nullable=False, default="general")  # roofing, ecommerce, legal, etc.
    agent_mode: Mapped[str] = mapped_column(String(50), nullable=False, default="lead_qualifier")
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)  # auto-applied on signup
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Template config (same fields as AgentConfig)
    agent_name: Mapped[str] = mapped_column(String(100), default="AI Assistant", nullable=False)
    agent_greeting: Mapped[str] = mapped_column(Text, default="Thank you for calling! How can I help you today?", nullable=False)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    voice_id: Mapped[str] = mapped_column(String(100), default="EXAVITQu4vr4xnSDxMaL", nullable=False)
    voice_stability: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    voice_similarity_boost: Mapped[float] = mapped_column(Float, default=0.75, nullable=False)
    llm_model: Mapped[str] = mapped_column(String(100), default="gpt-4o", nullable=False)
    temperature: Mapped[float] = mapped_column(Float, default=0.7, nullable=False)
    max_call_duration: Mapped[int] = mapped_column(Integer, default=1800, nullable=False)
    after_hours_message: Mapped[str] = mapped_column(Text, default="We're currently closed but will call you back first thing in the morning.", nullable=False)
    after_hours_sms_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    allow_interruptions: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    services: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    business_hours: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    supported_languages: Mapped[list] = mapped_column(
        JSONB,
        default=lambda: ["en", "es", "fr", "de", "ar", "hi", "pt", "it", "ja", "ko", "zh", "nl", "pl", "ru", "tr", "uk"],
        nullable=False,
    )
    language_presets: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    widget_config: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class SiteTemplateInstance(Base):
    """A client-specific website instance created from a coded site template."""
    __tablename__ = "site_template_instances"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("clients.id", ondelete="CASCADE"),
        nullable=False,
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    site_slug: Mapped[str] = mapped_column(String(255), nullable=False)
    public_slug: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    template_slug: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    content: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    theme_overrides: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    agent_embed_config: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    client: Mapped["Client"] = relationship(back_populates="site_template_instances")

    __table_args__ = (
        Index("ix_site_template_instances_client_id", "client_id"),
        Index("ix_site_template_instances_template_slug", "template_slug"),
        Index("ix_site_template_instances_public_slug", "public_slug"),
        UniqueConstraint("client_id", "site_slug", name="uq_site_template_instance_slug_per_client"),
    )

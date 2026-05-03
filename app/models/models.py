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
    clerk_org_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
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
    trial_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    subscription_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    website_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    primary_goal: Mapped[str | None] = mapped_column(String(100), nullable=True)
    public_widget_key: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True, index=True)
    saas_widget_status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)
    allowed_domains: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    widget_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    widget_installed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    widget_last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    widget_primary_color: Mapped[str | None] = mapped_column(String(32), nullable=True)
    widget_position: Mapped[str] = mapped_column(String(32), default="bottom-right", nullable=False)
    widget_welcome_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    voice_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    widget_last_domain: Mapped[str | None] = mapped_column(String(255), nullable=True)
    widget_last_page_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    setup_progress: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    onboarding_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    industry: Mapped[str | None] = mapped_column(String(100), nullable=True)
    subscription_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    subscription_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

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
    engagements: Mapped[list["Engagement"]] = relationship(back_populates="client")
    follow_up_tasks: Mapped[list["FollowUpTask"]] = relationship(back_populates="client")
    tenant_channels: Mapped[list["TenantChannel"]] = relationship(back_populates="client")
    retell_agents: Mapped[list["TenantRetellAgent"]] = relationship(back_populates="client")
    tenant_call_logs: Mapped[list["TenantCallLog"]] = relationship(back_populates="client")
    usage_metering: Mapped[list["TenantUsageMetering"]] = relationship(back_populates="client")
    escalation_rules: Mapped[list["TenantEscalationRule"]] = relationship(back_populates="client")
    scheduling_config: Mapped["TenantSchedulingConfig | None"] = relationship(back_populates="client", uselist=False)
    scheduling_bookings: Mapped[list["SchedulingBooking"]] = relationship(back_populates="client")

    __table_args__ = (
        Index("ix_clients_email", "email"),
        Index("ix_clients_stripe_customer_id", "stripe_customer_id"),
        Index("ix_clients_clerk_user_id", "clerk_user_id"),
        Index("ix_clients_subscription_status", "subscription_status"),
        Index("ix_clients_created_at", "created_at"),
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
    retell_agent_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)

    # Identity
    agent_name: Mapped[str] = mapped_column(String(100), default="Alex", nullable=False)
    agent_greeting: Mapped[str] = mapped_column(
        Text,
        default="Thank you for visiting today, I am your AI assistant... how can I assist you?",
        nullable=False,
    )

    # Voice (ElevenLabs voice ID)
    voice_id: Mapped[str] = mapped_column(String(100), default="nf4MCGNSdM0hxM95ZBQR", nullable=False)
    voice_stability: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    voice_similarity_boost: Mapped[float] = mapped_column(Float, default=0.75, nullable=False)

    # LLM / brain
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    llm_model: Mapped[str] = mapped_column(String(100), default="gpt-4o", nullable=False)
    temperature: Mapped[float] = mapped_column(Float, default=0.7, nullable=False)

    # Business context
    business_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    business_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    website_domain: Mapped[str | None] = mapped_column(String(255), nullable=True)
    timezone: Mapped[str] = mapped_column(String(50), default="America/New_York", nullable=False)
    booking_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    tone: Mapped[str] = mapped_column(String(30), default="professional", nullable=False)
    goals: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

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
    agent_mode: Mapped[str] = mapped_column(String(50), default="general_lead_gen", nullable=False)
    enabled_channels: Mapped[list] = mapped_column(JSONB, default=lambda: ["website_chat"], nullable=False)
    lead_capture_fields: Mapped[list] = mapped_column(
        JSONB,
        default=lambda: ["name", "email", "phone", "company", "goal"],
        nullable=False,
    )
    qualification_rules: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    enabled_features: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    custom_instructions: Mapped[str | None] = mapped_column(Text, nullable=True)

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
    retell_call_id: Mapped[str | None] = mapped_column(String(120), nullable=True, unique=True)

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
        Index("ix_calls_retell_call_id", "retell_call_id"),
    )


# ── Multi-channel AI Telephony ────────────────────────────────────────────────

class TenantChannel(Base):
    """Tenant channel registry for chat, web voice, and Retell-powered telephony."""
    __tablename__ = "tenant_channels"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    channel_type: Mapped[str] = mapped_column(String(40), nullable=False)
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="disabled", nullable=False)
    config_json: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    client: Mapped["Client"] = relationship(back_populates="tenant_channels")

    __table_args__ = (
        UniqueConstraint("tenant_id", "channel_type", name="uq_tenant_channels_tenant_channel"),
        Index("ix_tenant_channels_tenant_id", "tenant_id"),
        Index("ix_tenant_channels_channel_type", "channel_type"),
        Index("ix_tenant_channels_status", "status"),
    )


class TenantSchedulingConfig(Base):
    """Tenant-owned mapping into the internal Cal.diy scheduling service."""
    __tablename__ = "tenant_scheduling_configs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)

    calcom_user_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    default_event_type_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    booking_mode: Mapped[str] = mapped_column(String(40), default="ai-assisted", nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="disabled", nullable=False)
    event_type_ids: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    settings_json: Mapped[dict] = mapped_column("settings", JSONB, default=dict, nullable=False)
    last_health_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    last_health_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    client: Mapped["Client"] = relationship(back_populates="scheduling_config")

    __table_args__ = (
        UniqueConstraint("tenant_id", name="uq_tenant_scheduling_configs_tenant_id"),
        Index("ix_tenant_scheduling_configs_tenant_id", "tenant_id"),
        Index("ix_tenant_scheduling_configs_status", "status"),
    )


class SchedulingBooking(Base):
    """Tenant-scoped booking audit rows mirrored from Cal.diy responses."""
    __tablename__ = "scheduling_bookings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    lead_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("leads.id", ondelete="SET NULL"), nullable=True)

    calcom_booking_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    calcom_booking_uid: Mapped[str | None] = mapped_column(String(160), nullable=True)
    event_type_id: Mapped[str] = mapped_column(String(120), nullable=False)
    attendee_name: Mapped[str] = mapped_column(String(255), nullable=False)
    attendee_email: Mapped[str] = mapped_column(String(255), nullable=False)
    attendee_phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    start_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    end_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    timezone: Mapped[str] = mapped_column(String(80), default="America/New_York", nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="confirmed", nullable=False)
    topic: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    client: Mapped["Client"] = relationship(back_populates="scheduling_bookings")

    __table_args__ = (
        Index("ix_scheduling_bookings_tenant_id", "tenant_id"),
        Index("ix_scheduling_bookings_created_at", "created_at"),
        Index("ix_scheduling_bookings_status", "status"),
        UniqueConstraint("tenant_id", "calcom_booking_uid", name="uq_scheduling_bookings_tenant_uid"),
    )


class TenantRetellAgent(Base):
    """Retell phone agent linked to a tenant's shared Omniweb brain."""
    __tablename__ = "tenant_retell_agents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    retell_agent_id: Mapped[str | None] = mapped_column(String(120), nullable=True, unique=True, index=True)
    retell_phone_number: Mapped[str | None] = mapped_column(String(30), nullable=True, index=True)
    human_escalation_phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    fallback_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    webhook_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="provisioning", nullable=False)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    client: Mapped["Client"] = relationship(back_populates="retell_agents")

    __table_args__ = (
        UniqueConstraint("tenant_id", name="uq_tenant_retell_agents_tenant_id"),
        Index("ix_tenant_retell_agents_tenant_id", "tenant_id"),
        Index("ix_tenant_retell_agents_status", "status"),
    )


class TenantCallLog(Base):
    """Provider-normalized call log for AI telephony."""
    __tablename__ = "tenant_call_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    provider: Mapped[str] = mapped_column(String(40), default="retell", nullable=False)
    provider_call_id: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    retell_agent_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    caller_phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    direction: Mapped[str] = mapped_column(String(20), default="inbound", nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    transcript: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    outcome: Mapped[str | None] = mapped_column(String(120), nullable=True)
    escalation_triggered: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    client: Mapped["Client"] = relationship(back_populates="tenant_call_logs")

    __table_args__ = (
        UniqueConstraint("provider", "provider_call_id", name="uq_tenant_call_logs_provider_call"),
        Index("ix_tenant_call_logs_tenant_id", "tenant_id"),
        Index("ix_tenant_call_logs_created_at", "created_at"),
    )


class TenantUsageMetering(Base):
    """Tenant-level usage rollups for Retell AI telephony billing."""
    __tablename__ = "tenant_usage_metering"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    channel_type: Mapped[str] = mapped_column(String(40), default="ai_telephony", nullable=False)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    calls_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    minutes_used: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    plan_limit_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    overage_minutes: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    provider_cost_estimate: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    subscriber_billed_usage: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    client: Mapped["Client"] = relationship(back_populates="usage_metering")

    __table_args__ = (
        UniqueConstraint("tenant_id", "channel_type", "period_start", name="uq_usage_metering_tenant_channel_period"),
        Index("ix_usage_metering_tenant_id", "tenant_id"),
        Index("ix_usage_metering_period_start", "period_start"),
    )


class TenantEscalationRule(Base):
    """Escalation settings shared by channels and enforced by the Omniweb brain."""
    __tablename__ = "tenant_escalation_rules"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    channel_type: Mapped[str] = mapped_column(String(40), default="ai_telephony", nullable=False)
    human_escalation_phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    fallback_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    business_hours: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    trigger_keywords: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    client: Mapped["Client"] = relationship(back_populates="escalation_rules")

    __table_args__ = (
        UniqueConstraint("tenant_id", "channel_type", name="uq_escalation_rules_tenant_channel"),
        Index("ix_escalation_rules_tenant_id", "tenant_id"),
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


class Engagement(Base):
    """Tenant-scoped analytics engagement record used by the SaaS dashboard."""
    __tablename__ = "engagements"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)

    session_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String(50), nullable=False, default="website_chat")
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    language: Mapped[str | None] = mapped_column(String(20), nullable=True)
    visitor_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    visitor_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    visitor_phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    lead_status: Mapped[str] = mapped_column(String(40), nullable=False, default="new")
    intent: Mapped[str | None] = mapped_column(String(100), nullable=True)
    contact_captured: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    qualified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    follow_up_needed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    summary_short: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary_full: Mapped[str | None] = mapped_column(Text, nullable=True)
    transcript: Mapped[str | None] = mapped_column(Text, nullable=True)
    lead_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    pain_points: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    buying_signals: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    objections: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    recommended_next_action: Mapped[str | None] = mapped_column(Text, nullable=True)
    owner_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    agent_mode: Mapped[str] = mapped_column(String(50), nullable=False, default="general_lead_gen")
    conversion_stage: Mapped[str] = mapped_column(String(50), nullable=False, default="awareness")
    metadata_json: Mapped[dict] = mapped_column("metadata", JSONB, default=dict, nullable=False)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    client: Mapped["Client"] = relationship(back_populates="engagements")
    follow_up_tasks: Mapped[list["FollowUpTask"]] = relationship(back_populates="engagement")

    __table_args__ = (
        Index("ix_engagements_client_id", "client_id"),
        Index("ix_engagements_client_id_created_at", "client_id", "created_at"),
        Index("ix_engagements_lead_status", "lead_status"),
        Index("ix_engagements_created_at", "created_at"),
    )


class FollowUpTask(Base):
    """Pending or completed follow-up actions tied to an engagement."""
    __tablename__ = "follow_up_tasks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    engagement_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("engagements.id", ondelete="CASCADE"), nullable=False)

    instruction: Mapped[str] = mapped_column(Text, nullable=False)
    channel: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    scheduled_for: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    client: Mapped["Client"] = relationship(back_populates="follow_up_tasks")
    engagement: Mapped["Engagement"] = relationship(back_populates="follow_up_tasks")

    __table_args__ = (
        Index("ix_follow_up_tasks_client_id", "client_id"),
        Index("ix_follow_up_tasks_engagement_id", "engagement_id"),
        Index("ix_follow_up_tasks_created_at", "created_at"),
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
    agent_greeting: Mapped[str] = mapped_column(Text, default="Thank you for visiting today, I am your AI assistant... how can I assist you?", nullable=False)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    voice_id: Mapped[str] = mapped_column(String(100), default="nf4MCGNSdM0hxM95ZBQR", nullable=False)
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

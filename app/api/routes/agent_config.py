"""Agent Config API — manage per-client AI agent settings.

When config is updated, the changes are synced to the ElevenLabs agent.
The prompt engine automatically composes the system prompt from the
tenant's industry, agent mode, business context, and custom instructions.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.core.auth import get_current_client
from app.core.logging import get_logger
from app.models.models import AgentConfig
from app.services import elevenlabs_service
from app.services.prompt_engine import compose_system_prompt, compose_greeting
from app.services.industry_config import (
    get_industry,
    list_industries,
    get_agent_modes,
    get_qualification_fields,
)

logger = get_logger(__name__)
router = APIRouter(prefix="/agent-config", tags=["agent-config"])


class AgentConfigUpdate(BaseModel):
    elevenlabs_agent_id: Optional[str] = None
    agent_name: Optional[str] = None
    agent_greeting: Optional[str] = None
    voice_id: Optional[str] = None
    voice_stability: Optional[float] = None
    voice_similarity_boost: Optional[float] = None
    system_prompt: Optional[str] = None
    llm_model: Optional[str] = None
    temperature: Optional[float] = None
    business_name: Optional[str] = None
    business_type: Optional[str] = None
    timezone: Optional[str] = None
    booking_url: Optional[str] = None
    business_hours: Optional[dict] = None
    services: Optional[list] = None
    after_hours_message: Optional[str] = None
    after_hours_sms_enabled: Optional[bool] = None
    allow_interruptions: Optional[bool] = None
    max_call_duration: Optional[int] = None
    supported_languages: Optional[list[str]] = None
    language_presets: Optional[dict] = None
    widget_config: Optional[dict] = None
    # Multi-tenant AI platform fields
    industry: Optional[str] = None
    agent_mode: Optional[str] = None
    custom_guardrails: Optional[list[str]] = None
    custom_escalation_triggers: Optional[list[str]] = None
    custom_context: Optional[str] = None
    use_prompt_engine: Optional[bool] = None
    handoff_enabled: Optional[bool] = None
    handoff_phone: Optional[str] = None
    handoff_email: Optional[str] = None
    handoff_message: Optional[str] = None


@router.get("/{client_id}")
async def get_config(
    client_id: str,
    current_client: dict = Depends(get_current_client),
    db: AsyncSession = Depends(get_session),
) -> dict:
    # Tenant isolation: non-admin can only see own config
    if current_client.get("role") != "admin" and client_id != current_client["client_id"]:
        raise HTTPException(403, "Access denied")
    result = await db.execute(
        select(AgentConfig).where(AgentConfig.client_id == client_id)
    )
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(404, f"No agent config for client {client_id}")
    return {f: getattr(config, f) for f in AgentConfig.__table__.columns.keys()}


@router.put("/{client_id}")
async def upsert_config(
    client_id: str,
    body: AgentConfigUpdate,
    current_client: dict = Depends(get_current_client),
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Create or update the agent config for a client.

    If the client has an ElevenLabs agent, sync the changes to it.
    If no ElevenLabs agent exists yet, create one.
    """
    # Tenant isolation
    if current_client.get("role") != "admin" and client_id != current_client["client_id"]:
        raise HTTPException(403, "Access denied")
    result = await db.execute(
        select(AgentConfig).where(AgentConfig.client_id == client_id)
    )
    config = result.scalar_one_or_none()
    if not config:
        config = AgentConfig(client_id=client_id)
        db.add(config)

    for field, value in body.model_dump(exclude_none=True).items():
        setattr(config, field, value)

    await db.flush()

    # ── Compose system prompt via prompt engine (if enabled) ──
    effective_prompt = config.system_prompt
    if config.use_prompt_engine:
        effective_prompt = compose_system_prompt(
            agent_name=config.agent_name or "Alex",
            business_name=config.business_name or "",
            industry_slug=config.industry or "general",
            agent_mode=config.agent_mode,
            business_type=config.business_type,
            services=config.services or [],
            business_hours=config.business_hours or {},
            timezone=config.timezone or "America/New_York",
            booking_url=config.booking_url,
            after_hours_message=config.after_hours_message or "",
            custom_prompt=config.system_prompt,  # tenant's raw prompt becomes "custom instructions"
            custom_guardrails=config.custom_guardrails or [],
            custom_escalation_triggers=config.custom_escalation_triggers or [],
            custom_context=config.custom_context,
        )

    # Compose greeting if not explicitly set
    effective_greeting = config.agent_greeting
    if not body.agent_greeting and config.use_prompt_engine:
        effective_greeting = compose_greeting(
            industry_slug=config.industry or "general",
            agent_mode=config.agent_mode,
            agent_name=config.agent_name or "Alex",
            business_name=config.business_name or "",
            custom_greeting=config.agent_greeting if body.agent_greeting else None,
        )

    # Sync to ElevenLabs (skip if only elevenlabs_agent_id was changed)
    fields_that_sync = {"agent_name", "agent_greeting", "voice_id", "voice_stability",
                        "voice_similarity_boost", "system_prompt", "business_name",
                        "max_call_duration", "supported_languages", "language_presets",
                        "industry", "agent_mode", "custom_guardrails",
                        "custom_escalation_triggers", "custom_context", "use_prompt_engine",
                        "services", "business_hours", "timezone", "booking_url",
                        "after_hours_message"}
    has_sync_fields = bool(fields_that_sync & set(body.model_dump(exclude_none=True).keys()))
    try:
        if config.elevenlabs_agent_id and has_sync_fields:
            # Update existing agent
            await elevenlabs_service.update_agent(
                config.elevenlabs_agent_id,
                name=f"{config.business_name or ''} - {config.agent_name or ''}".strip(" -"),
                first_message=effective_greeting,
                system_prompt=effective_prompt,
                voice_id=config.voice_id,
                voice_stability=config.voice_stability,
                voice_similarity_boost=config.voice_similarity_boost,
                max_duration_seconds=config.max_call_duration,
                supported_languages=config.supported_languages if body.supported_languages is not None else None,
                language_presets_override=config.language_presets if body.language_presets is not None else None,
                business_name=config.business_name or "",
            )
            logger.info(f"Synced config to ElevenLabs agent {config.elevenlabs_agent_id}")
        elif not config.elevenlabs_agent_id and has_sync_fields:
            # Create new ElevenLabs agent
            result_el = await elevenlabs_service.create_agent(
                name=f"{config.business_name or ''} - {config.agent_name or ''}".strip(" -"),
                first_message=effective_greeting,
                system_prompt=effective_prompt,
                voice_id=config.voice_id,
                voice_stability=config.voice_stability,
                voice_similarity_boost=config.voice_similarity_boost,
                max_duration_seconds=config.max_call_duration,
                supported_languages=config.supported_languages,
                business_name=config.business_name or "",
            )
            config.elevenlabs_agent_id = result_el["agent_id"]
            logger.info(f"Created ElevenLabs agent: {config.elevenlabs_agent_id}")
    except Exception as exc:
        logger.error(f"Failed to sync config to ElevenLabs: {exc}")
        # Don't fail the request — save config locally even if ElevenLabs is down

    await db.commit()
    await db.refresh(config)
    return {
        "ok": True,
        "client_id": client_id,
        "elevenlabs_agent_id": config.elevenlabs_agent_id,
        "industry": config.industry,
        "agent_mode": config.agent_mode,
        "use_prompt_engine": config.use_prompt_engine,
    }


@router.get("/{client_id}/widget")
async def get_widget_embed(
    client_id: str,
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Get the embeddable chat widget code for the client's agent.

    Public endpoint — no auth required (used by client websites).
    """
    result = await db.execute(
        select(AgentConfig).where(AgentConfig.client_id == client_id)
    )
    config = result.scalar_one_or_none()
    if not config or not config.elevenlabs_agent_id:
        raise HTTPException(404, "No ElevenLabs agent configured")

    embed_data = elevenlabs_service.get_widget_embed_code(config.elevenlabs_agent_id)

    return {
        "agent_id": config.elevenlabs_agent_id,
        "embed_code": embed_data["iframe"],
        "legacy_embed_code": embed_data["legacy"],
        "widget_url": embed_data["widget_url"],
        "talk_url": f"https://elevenlabs.io/app/talk-to/{config.elevenlabs_agent_id}",
    }


# ── Industry & mode metadata endpoints ──────────────────────────────────────


@router.get("/meta/industries")
async def get_industries() -> list[dict]:
    """List all available industries for agent configuration."""
    return list_industries()


@router.get("/meta/agent-modes")
async def get_modes() -> dict:
    """List all available agent modes."""
    return get_agent_modes()


@router.get("/meta/qualification-fields/{industry_slug}")
async def get_fields(industry_slug: str) -> list[dict]:
    """Get the qualification fields for an industry."""
    return get_qualification_fields(industry_slug)


@router.get("/{client_id}/prompt-preview")
async def preview_composed_prompt(
    client_id: str,
    current_client: dict = Depends(get_current_client),
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Preview the composed system prompt for a client's agent config.

    Useful for debugging and reviewing what the agent will actually see.
    """
    if current_client.get("role") != "admin" and client_id != current_client["client_id"]:
        raise HTTPException(403, "Access denied")

    result = await db.execute(
        select(AgentConfig).where(AgentConfig.client_id == client_id)
    )
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(404, f"No agent config for client {client_id}")

    composed = compose_system_prompt(
        agent_name=config.agent_name or "Alex",
        business_name=config.business_name or "",
        industry_slug=config.industry or "general",
        agent_mode=config.agent_mode,
        business_type=config.business_type,
        services=config.services or [],
        business_hours=config.business_hours or {},
        timezone=config.timezone or "America/New_York",
        booking_url=config.booking_url,
        after_hours_message=config.after_hours_message or "",
        custom_prompt=config.system_prompt,
        custom_guardrails=config.custom_guardrails or [],
        custom_escalation_triggers=config.custom_escalation_triggers or [],
        custom_context=config.custom_context,
    )

    greeting = compose_greeting(
        industry_slug=config.industry or "general",
        agent_mode=config.agent_mode,
        agent_name=config.agent_name or "Alex",
        business_name=config.business_name or "",
    )

    return {
        "composed_prompt": composed,
        "composed_greeting": greeting,
        "industry": config.industry,
        "agent_mode": config.agent_mode,
        "use_prompt_engine": config.use_prompt_engine,
        "prompt_length_chars": len(composed),
    }

"""Agent Config API — manage per-client AI agent settings.

When config is updated, high-level fields are synced to the linked Retell agent
(voice language, display name). Full prompts and tools are edited in Retell;
this service keeps business context aligned where the API allows.
"""
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Any, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.core.auth import get_current_client
from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.models import AgentConfig, Client
from app.services import retell_service
from app.services.omniweb_brain_service import compose_channel_prompt
from app.services.prompt_engine import compose_system_prompt, compose_greeting
from app.services.industry_config import (
    get_industry,
    list_industries,
    get_agent_modes,
    get_qualification_fields,
)

logger = get_logger(__name__)
router = APIRouter(prefix="/agent-config", tags=["agent-config"])
settings = get_settings()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _build_widget_embed_snippet(*, embed_code: str, client_id: str) -> tuple[str, str]:
    """HTML for third-party sites (e.g. marketing omniweb.ai): iframe loads the Next.js widget route.

    Do not point at omniweb.ai — that is a separate app (seahorse). Use PLATFORM_URL (dashboard /widget host).
    There is no ``/widget/loader.js``; the voice UI is ``/widget/{client_id}`` with API at ENGINE_BASE_URL.
    """
    platform_url = settings.PLATFORM_URL.rstrip("/")
    widget_url = f"{platform_url}/widget/{client_id}"
    snippet = f"""<!-- Omniweb AI Widget — Deepgram voice UI (iframe). embed_code={embed_code} (domain lock / analytics). -->
<iframe
  src="{widget_url}"
  title="Omniweb AI"
  allow="microphone; autoplay"
  style="position:fixed;bottom:0;right:0;width:min(100vw - 1rem, 420px);height:min(100dvh - 1rem, 640px);max-width:420px;max-height:640px;border:0;border-radius:12px;z-index:99999;box-shadow:0 12px 48px rgba(0,0,0,0.35)"
></iframe>"""
    return snippet, widget_url


class AgentConfigUpdate(BaseModel):
    retell_agent_id: Optional[str] = None
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
    goals: Optional[list[str]] = None
    active: Optional[bool] = None
    # Multi-tenant AI platform fields
    industry: Optional[str] = None
    agent_mode: Optional[str] = None
    enabled_channels: Optional[list[str]] = None
    lead_capture_fields: Optional[list[str]] = None
    enabled_features: Optional[dict] = None
    qualification_rules: Optional[dict] = None
    custom_instructions: Optional[str] = None
    custom_guardrails: Optional[list[str]] = None
    custom_escalation_triggers: Optional[list[str]] = None
    custom_context: Optional[str] = None
    use_prompt_engine: Optional[bool] = None
    handoff_enabled: Optional[bool] = None
    handoff_phone: Optional[str] = None
    handoff_email: Optional[str] = None
    handoff_message: Optional[str] = None
    website_domain: Optional[str] = None


class BuildProvidersRequest(BaseModel):
    retell_agent_id: Optional[str] = None
    language: Optional[str] = None


@router.get("/setup-status/{client_id}")
async def setup_status(
    client_id: str,
    current_client: dict = Depends(get_current_client),
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Check whether the client has completed required onboarding fields.

    Returns setup_complete=True only when business_name and website_domain are set.
    Any frontend can call this to decide whether to show onboarding.
    """
    if current_client.get("role") != "admin" and client_id != current_client["client_id"]:
        raise HTTPException(403, "Access denied")
    result = await db.execute(
        select(AgentConfig).where(AgentConfig.client_id == client_id)
    )
    config = result.scalar_one_or_none()
    if not config:
        return {
            "setup_complete": False,
            "missing": ["business_name", "website_domain", "industry"],
            "has_config": False,
        }
    missing = []
    if not config.business_name:
        missing.append("business_name")
    if not config.website_domain:
        missing.append("website_domain")
    if not config.industry:
        missing.append("industry")
    return {
        "setup_complete": len(missing) == 0,
        "missing": missing,
        "has_config": True,
        "business_name": config.business_name,
        "website_domain": config.website_domain,
        "industry": config.industry,
    }


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
    data = {f: getattr(config, f) for f in AgentConfig.__table__.columns.keys()}
    # Flag indicating all required fields are present
    data["setup_complete"] = bool(config.business_name and config.website_domain)
    return data


@router.put("/{client_id}")
async def upsert_config(
    client_id: str,
    body: AgentConfigUpdate,
    current_client: dict = Depends(get_current_client),
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Create or update the agent config for a client.

    If ``retell_agent_id`` is set, patches the Retell agent (language, name).
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
        if field == "website_domain" and value:
            # Normalize domain
            domain = value.strip().lower()
            for prefix in ("https://", "http://", "www."):
                if domain.startswith(prefix):
                    domain = domain[len(prefix):]
            domain = domain.rstrip("/")
            # Check uniqueness (excluding this config)
            dup = await db.execute(
                select(AgentConfig).where(
                    AgentConfig.website_domain == domain,
                    AgentConfig.client_id != config.client_id,
                )
            )
            if dup.scalar_one_or_none():
                raise HTTPException(409, "An agent already exists for this domain")
            value = domain
        setattr(config, field, value)

    await db.flush()

    # ── Compose system prompt via prompt engine (if enabled) ──
    owner_instructions = config.custom_instructions or config.system_prompt
    custom_context = config.custom_context
    if custom_context and owner_instructions and custom_context.strip() == owner_instructions.strip():
        custom_context = None
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
            custom_prompt=owner_instructions,
            custom_guardrails=config.custom_guardrails or [],
            custom_escalation_triggers=config.custom_escalation_triggers or [],
            custom_context=custom_context,
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

    fields_that_sync = {
        "agent_name",
        "business_name",
        "supported_languages",
        "retell_agent_id",
        "industry",
        "agent_mode",
        "system_prompt",
        "use_prompt_engine",
        "services",
        "business_hours",
        "timezone",
        "booking_url",
        "after_hours_message",
        "custom_instructions",
        "custom_guardrails",
        "custom_escalation_triggers",
        "custom_context",
    }
    has_sync_fields = bool(fields_that_sync & set(body.model_dump(exclude_none=True).keys()))
    try:
        if config.retell_agent_id and has_sync_fields:
            lang = retell_service.map_locale_to_retell_language(
                list(config.supported_languages or ["en"])
            )
            display = f"{config.business_name or ''} - {config.agent_name or ''}".strip(" -") or (
                config.agent_name or "Omniweb Agent"
            )
            await retell_service.patch_agent(
                config.retell_agent_id,
                {
                    "agent_name": display[:120],
                    "language": lang,
                    "max_call_duration_ms": min(
                        max(int(config.max_call_duration) * 1000, 60_000),
                        3_600_000,
                    ),
                    "begin_message": effective_greeting,
                    "general_prompt": compose_channel_prompt(config, "ai_telephony"),
                },
            )
            logger.info("Synced config to Retell agent", retell_agent_id=config.retell_agent_id)
    except Exception as exc:
        logger.error(f"Failed to sync config to Retell: {exc}")

    await db.commit()
    await db.refresh(config)
    return {
        "ok": True,
        "client_id": client_id,
        "retell_agent_id": config.retell_agent_id,
        "industry": config.industry,
        "agent_mode": config.agent_mode,
        "use_prompt_engine": config.use_prompt_engine,
    }


@router.get("/{client_id}/widget")
async def get_widget_embed(
    client_id: str,
    current_client: dict = Depends(get_current_client),
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Get the embeddable widget code for the authenticated client's site."""
    if current_client.get("role") != "admin" and client_id != current_client["client_id"]:
        raise HTTPException(403, "Access denied")

    client = await db.get(Client, client_id)
    if not client:
        raise HTTPException(404, "Client not found")

    result = await db.execute(
        select(AgentConfig).where(AgentConfig.client_id == client_id)
    )
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(404, "No agent configuration found")

    if not client.embed_code:
        client.embed_code = secrets.token_hex(16)
        if config.website_domain and not client.embed_domain:
            client.embed_domain = config.website_domain

        if client.stripe_subscription_id:
            client.embed_expires_at = None
        elif client.trial_ends_at:
            client.embed_expires_at = client.trial_ends_at
        else:
            client.embed_expires_at = _utcnow() + timedelta(days=14)

        await db.commit()
        await db.refresh(client)

    embed_snippet, widget_url = _build_widget_embed_snippet(
        embed_code=client.embed_code,
        client_id=str(client.id),
    )

    return {
        "agent_id": str(client.id),
        "embed_code": embed_snippet,
        "retell_agent_id": config.retell_agent_id,
        "widget_url": widget_url,
        "embed_domain": client.embed_domain,
        "embed_expires_at": client.embed_expires_at.isoformat() if client.embed_expires_at else None,
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

    owner_instructions = config.custom_instructions or config.system_prompt
    custom_context = config.custom_context
    if custom_context and owner_instructions and custom_context.strip() == owner_instructions.strip():
        custom_context = None
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
        custom_prompt=owner_instructions,
        custom_guardrails=config.custom_guardrails or [],
        custom_escalation_triggers=config.custom_escalation_triggers or [],
        custom_context=custom_context,
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


@router.post("/{client_id}/build-providers")
async def build_providers(
    client_id: str,
    body: BuildProvidersRequest,
    current_client: dict = Depends(get_current_client),
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Build provider-ready settings from tenant config.

    - Deepgram: returns a SettingsConfiguration payload your frontend/backend can use.
    - Retell: patches a linked agent if `retell_agent_id` exists.
    """
    if current_client.get("role") != "admin" and client_id != current_client["client_id"]:
        raise HTTPException(403, "Access denied")

    result = await db.execute(
        select(AgentConfig).where(AgentConfig.client_id == client_id)
    )
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(404, f"No agent config for client {client_id}")

    supported_languages = list(config.supported_languages or ["en"])
    requested_language = (body.language or "").strip().lower()
    if requested_language:
        effective_langs = [requested_language]
    else:
        effective_langs = supported_languages

    # Build composed prompt from the same source your runtime uses.
    owner_instructions = config.custom_instructions or config.system_prompt
    custom_context = config.custom_context
    if custom_context and owner_instructions and custom_context.strip() == owner_instructions.strip():
        custom_context = None
    composed_prompt = compose_system_prompt(
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
        custom_prompt=owner_instructions,
        custom_guardrails=config.custom_guardrails or [],
        custom_escalation_triggers=config.custom_escalation_triggers or [],
        custom_context=custom_context,
    )

    deepgram_settings: dict[str, Any] | None = None
    if settings.deepgram_configured:
        deepgram_settings = {
            "type": "SettingsConfiguration",
            "audio": {
                "input": {"encoding": "linear16", "sample_rate": 16000},
                "output": {"encoding": "linear16", "sample_rate": 24000, "container": "none"},
            },
            "agent": {
                "listen": {
                    "provider": {
                        "type": "deepgram",
                        "model": settings.DEEPGRAM_STT_MODEL,
                        "smart_format": False,
                    }
                },
                "think": {
                    "provider": {
                        "type": "open_ai",
                        "model": settings.DEEPGRAM_AGENT_MODEL,
                        "temperature": 0.7,
                    },
                    "prompt": composed_prompt,
                },
                "speak": {
                    "provider": {
                        "type": "deepgram",
                        "model": config.voice_id or settings.DEEPGRAM_TTS_VOICE,
                    }
                },
            },
            "metadata": {
                "client_id": client_id,
                "business_name": config.business_name or "",
                "language": (
                    "multi"
                    if len(effective_langs) > 1
                    else retell_service.map_locale_to_retell_language(effective_langs)
                ),
                "project_id": settings.DEEPGRAM_PROJECT_ID or None,
            },
        }

    retell_agent_id = body.retell_agent_id or config.retell_agent_id
    retell_patch_result: dict[str, Any] | None = None
    if settings.retell_configured and retell_agent_id:
        language = retell_service.map_locale_to_retell_language(effective_langs)
        display_name = (
            f"{config.business_name or ''} - {config.agent_name or ''}".strip(" -")
            or config.agent_name
            or "Omniweb Agent"
        )
        patch_payload = {
            "agent_name": display_name[:120],
            "language": language,
            "begin_message": config.agent_greeting,
            "general_prompt": compose_channel_prompt(config, "ai_telephony"),
            "max_call_duration_ms": min(
                max(int(config.max_call_duration or 1800) * 1000, 60_000),
                3_600_000,
            ),
        }
        retell_patch_result = await retell_service.patch_agent(
            retell_agent_id,
            patch_payload,
        )
        if not config.retell_agent_id:
            config.retell_agent_id = retell_agent_id

    # Store latest provider build metadata.
    widget = dict(config.widget_config or {})
    widget["provider_build"] = {
        "updated_at": _utcnow().isoformat(),
        "deepgram": {
            "configured": settings.deepgram_configured,
            "project_id": settings.DEEPGRAM_PROJECT_ID or None,
            "stt_model": settings.DEEPGRAM_STT_MODEL,
            "tts_voice": config.voice_id or settings.DEEPGRAM_TTS_VOICE,
        },
        "retell": {
            "configured": settings.retell_configured,
            "agent_id": retell_agent_id,
        },
    }
    config.widget_config = widget

    await db.commit()
    await db.refresh(config)

    return {
        "ok": True,
        "client_id": client_id,
        "deepgram": {
            "configured": settings.deepgram_configured,
            "project_id": settings.DEEPGRAM_PROJECT_ID or None,
            "settings": deepgram_settings,
        },
        "retell": {
            "configured": settings.retell_configured,
            "agent_id": retell_agent_id,
            "patch_result": retell_patch_result,
        },
    }

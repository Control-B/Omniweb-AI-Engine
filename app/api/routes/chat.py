"""Chat API — widget configuration for voice (Deepgram Voice Agent + optional Retell)."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.core.auth import get_current_client
from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.models import AgentConfig
from app.api.routes.deepgram import VoiceAgentBootstrapRequest, run_voice_agent_bootstrap
from app.services import retell_service

logger = get_logger(__name__)
settings = get_settings()
router = APIRouter(prefix="/chat", tags=["chat"])

# Canonical browser path for Deepgram bootstrap (some CDNs/WAFs block ``/api/deepgram/...`` POST).
_VOICE_BOOTSTRAP_PATH = "/api/chat/voice-agent/bootstrap"


@router.post("/voice-agent/bootstrap")
async def voice_agent_bootstrap_public(
    req: VoiceAgentBootstrapRequest,
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Mint Deepgram JWT + Voice Agent settings for the embed widget (alias of deepgram route)."""
    return await run_voice_agent_bootstrap(req, db)


@router.post("/welcome-audio")
async def get_welcome_audio():
    """Welcome clips are produced inside the Retell voice session."""
    raise HTTPException(
        501,
        detail="Welcome audio is handled by Retell during the live web/phone call.",
    )


@router.get("/languages")
async def get_chat_languages() -> dict:
    """Public language options for widgets (Retell-aligned)."""
    return {
        "default_language": "en",
        "languages": retell_service.language_options_public(),
    }


@router.get("/widget/{client_id}")
async def get_widget(
    client_id: str,
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Public widget metadata for embedding (Deepgram Voice Agent or Retell web call)."""
    result = await db.execute(
        select(AgentConfig).where(AgentConfig.client_id == client_id)
    )
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(404, "No agent configured for this client")

    engine_url = getattr(settings, "ENGINE_BASE_URL", settings.APP_BASE_URL).rstrip("/")
    out: dict = {
        "client_id": client_id,
        "agent_name": config.agent_name,
        "engine_url": engine_url,
    }
    if settings.deepgram_configured:
        out["voice_provider"] = "deepgram"
        out["deepgram_bootstrap_path"] = _VOICE_BOOTSTRAP_PATH
    if config.retell_agent_id:
        out["retell_agent_id"] = config.retell_agent_id
        out["web_call_path"] = "/api/retell/web-call"
    if not settings.deepgram_configured and not config.retell_agent_id:
        raise HTTPException(404, "No voice provider configured for this client")

    return out


@router.get("/config/{client_id}")
async def get_chat_config(
    client_id: str,
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Configuration for frontend SDK integration (Deepgram and/or Retell)."""
    result = await db.execute(
        select(AgentConfig).where(AgentConfig.client_id == client_id)
    )
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(404, "No agent configured for this client")

    engine_url = getattr(settings, "ENGINE_BASE_URL", settings.APP_BASE_URL).rstrip("/")
    out: dict = {
        "client_id": client_id,
        "retell_agent_id": config.retell_agent_id,
        "agent_name": config.agent_name,
        "greeting": config.agent_greeting,
        "business_name": config.business_name,
        "engine_url": engine_url,
    }
    if settings.deepgram_configured:
        out["voice_provider"] = "deepgram"
        out["deepgram_bootstrap_path"] = _VOICE_BOOTSTRAP_PATH
    if config.retell_agent_id:
        out["web_call_path"] = "/api/retell/web-call"
    return out


@router.get("/conversations")
async def list_chat_conversations(
    current_client: dict = Depends(get_current_client),
    page_size: int = Query(30, le=100),
    cursor: str | None = Query(None),
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Text conversation history will return here once wired to Retell chat."""
    _ = page_size
    _ = cursor
    _ = db
    _ = current_client
    return {"conversations": [], "has_more": False}

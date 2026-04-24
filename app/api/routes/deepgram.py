"""Deepgram Voice Agent — public bootstrap for the marketing / embed widget."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.models import AgentConfig
from app.services import deepgram_service

logger = get_logger(__name__)
settings = get_settings()
router = APIRouter(prefix="/deepgram", tags=["deepgram"])


class VoiceAgentBootstrapRequest(BaseModel):
    client_id: str | None = None
    language: str | None = None


@router.post("/voice-agent/bootstrap")
async def voice_agent_bootstrap(
    req: VoiceAgentBootstrapRequest,
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Return a short-lived Deepgram JWT + Voice Agent ``Settings`` for the browser.

    Mirrors ``POST /api/retell/web-call``: ``client_id`` selects the tenant; if omitted,
    ``LANDING_PAGE_CLIENT_ID`` is used when set.
    """
    if not settings.deepgram_configured:
        raise HTTPException(503, detail="Deepgram is not configured")

    raw_id = (req.client_id or settings.LANDING_PAGE_CLIENT_ID or "").strip()
    if not raw_id:
        raise HTTPException(
            400,
            detail="client_id is required (or set LANDING_PAGE_CLIENT_ID for anonymous widget)",
        )
    try:
        cid = UUID(raw_id)
    except ValueError:
        raise HTTPException(400, detail="Invalid client_id")

    result = await db.execute(select(AgentConfig).where(AgentConfig.client_id == cid))
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(404, detail="No agent configuration for this client")

    try:
        token_payload = await deepgram_service.grant_temporary_token(ttl_seconds=600)
    except Exception as exc:
        logger.error("Deepgram grant token failed", error=str(exc))
        raise HTTPException(502, detail="Failed to mint Deepgram session token") from exc

    access_token = token_payload.get("access_token")
    if not access_token:
        raise HTTPException(502, detail="Deepgram grant response missing access_token")

    voice_settings = deepgram_service.build_voice_agent_settings(
        config,
        language=req.language,
    )

    return {
        "ok": True,
        "client_id": str(config.client_id),
        "agent_name": config.agent_name or "Omniweb AI",
        "websocket_url": deepgram_service.DEEPGRAM_AGENT_WS_URL,
        "access_token": access_token,
        "expires_in": token_payload.get("expires_in"),
        "settings": voice_settings,
    }

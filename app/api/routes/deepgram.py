"""Deepgram Voice Agent — public bootstrap for the marketing / embed widget."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.models import AgentConfig, Call, Client, Transcript
from app.services import deepgram_service
from app.services.saas_workspace_service import (
    client_subscription_allows_widget,
    resolve_client_by_public_identifier,
)

logger = get_logger(__name__)
settings = get_settings()
router = APIRouter(prefix="/deepgram", tags=["deepgram"])


class VoiceAgentBootstrapRequest(BaseModel):
    client_id: str | None = None
    language: str | None = None
    voice_override: str | None = None  # e.g. "aura-2-orion-en" from test console


class SessionTranscriptLine(BaseModel):
    role: str
    content: str
    timestamp: str | int | float | None = None


class VoiceAgentSessionCompleteRequest(BaseModel):
    client_id: str
    language: str | None = None
    mode: str = "voice"
    started_at: datetime | None = None
    ended_at: datetime | None = None
    transcript: list[SessionTranscriptLine] = []


async def run_voice_agent_bootstrap(
    req: VoiceAgentBootstrapRequest,
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Shared implementation for ``POST .../voice-agent/bootstrap`` (see routers below)."""
    if not settings.deepgram_configured:
        raise HTTPException(503, detail="Deepgram is not configured")

    raw_id = (req.client_id or settings.LANDING_PAGE_CLIENT_ID or "").strip()

    config: AgentConfig | None = None
    if raw_id:
        client = await resolve_client_by_public_identifier(db, raw_id)
        if not client:
            raise HTTPException(404, detail="No client found for client_id or widget key")
        result = await db.execute(select(AgentConfig).where(AgentConfig.client_id == client.id))
        config = result.scalar_one_or_none()
        if not config:
            raise HTTPException(404, detail="No agent configuration for this client")
    elif settings.WIDGET_REQUIRE_CLIENT_ID:
        raise HTTPException(
            400,
            detail="client_id is required (or set LANDING_PAGE_CLIENT_ID for anonymous widget)",
        )
    else:
        # Deterministic default tenant: smallest client_id (matches former min() behavior).
        # Avoid scalar_subquery + equality — some stacks surface it as a DB/API 500.
        result = await db.execute(
            select(AgentConfig).order_by(AgentConfig.client_id.asc()).limit(1)
        )
        config = result.scalars().first()
        if not config:
            raise HTTPException(404, detail="No agent configuration in database")

    # ── Subscription / trial gate ────────────────────────────────────────────
    tenant = await db.get(Client, config.client_id)
    if tenant and not client_subscription_allows_widget(tenant):
        raise HTTPException(
            403,
            detail="Trial expired or subscription inactive. Please subscribe to continue using the widget.",
        )

    try:
        token_payload = await deepgram_service.grant_temporary_token(ttl_seconds=600)
    except Exception as exc:
        logger.error("Deepgram grant token failed", error=str(exc))
        raise HTTPException(
            400,
            detail=(
                "Deepgram token grant failed: invalid credentials. "
                "Replace DEEPGRAM_API_KEY with an active Deepgram API key that has Member access."
            ),
        ) from exc

    access_token = token_payload.get("access_token")
    if not access_token:
        raise HTTPException(500, detail="Deepgram grant response missing access_token")

    try:
        voice_settings = deepgram_service.build_voice_agent_settings(
            config,
            language=req.language,
            voice_override=req.voice_override,
        )
    except Exception as exc:
        logger.exception(
            "Voice agent settings build failed",
            client_id=str(config.client_id),
            error=str(exc),
        )
        raise HTTPException(
            500,
            detail="Failed to build voice agent settings (check agent JSON fields in DB)",
        ) from exc

    return {
        "ok": True,
        "client_id": str(config.client_id),
        "agent_name": config.agent_name or "Omniweb AI",
        "websocket_url": deepgram_service.DEEPGRAM_AGENT_WS_URL,
        "access_token": access_token,
        "expires_in": token_payload.get("expires_in"),
        "settings": voice_settings,
    }


@router.post("/voice-agent/bootstrap")
async def voice_agent_bootstrap(
    req: VoiceAgentBootstrapRequest,
    db: AsyncSession = Depends(get_session),
) -> dict:
    return await run_voice_agent_bootstrap(req, db)


@router.post("/voice-agent/session-complete")
async def voice_agent_session_complete(
    req: VoiceAgentSessionCompleteRequest,
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Persist a completed Deepgram widget session and generate a summary."""
    try:
        cid = UUID(req.client_id)
    except ValueError:
        raise HTTPException(400, detail="Invalid client_id")

    result = await db.execute(select(AgentConfig).where(AgentConfig.client_id == cid))
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(404, detail="No agent configuration for this client")

    turns = deepgram_service.transcript_lines_to_turns(
        [line.model_dump() for line in req.transcript]
    )
    caller_turns = [turn for turn in turns if turn.get("speaker") == "caller"]
    if not caller_turns:
        return {"ok": True, "saved": False, "reason": "no_user_messages"}

    started_at = req.started_at or datetime.now(timezone.utc)
    ended_at = req.ended_at or datetime.now(timezone.utc)
    duration_seconds = max(0, int((ended_at - started_at).total_seconds()))
    channel = "text" if req.mode == "text" else "voice"

    call = Call(
        id=uuid4(),
        client_id=config.client_id,
        caller_number="",
        direction="inbound",
        channel=channel,
        status="completed",
        started_at=started_at,
        ended_at=ended_at,
        duration_seconds=duration_seconds,
        post_call_processed=True,
    )
    db.add(call)
    await db.flush()

    summary = await deepgram_service.summarize_transcript(turns)
    transcript = Transcript(
        id=uuid4(),
        call_id=call.id,
        client_id=config.client_id,
        turns=turns,
        summary=summary,
        sentiment=None,
    )
    db.add(transcript)
    await db.commit()

    return {
        "ok": True,
        "saved": True,
        "call_id": str(call.id),
        "summary": summary,
        "turn_count": len(turns),
        "channel": channel,
    }

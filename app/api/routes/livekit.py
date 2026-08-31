"""LiveKit Real-Time WebRTC Audio & Telephony API Endpoints.

Handles:
- LiveKit room token generation for WebRTC browser clients
- Room dispatch & agent session creation
- LiveKit webhook events
"""
from __future__ import annotations

import time
from typing import Any
from uuid import uuid4

import jwt
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.core.logging import get_logger
from app.voice.livekit_agent import LiveKitContactCenterSession
from app.voice.pipelines import VoicePipelineManager

logger = get_logger(__name__)
settings = get_settings()
router = APIRouter(prefix="/livekit", tags=["livekit"])


class TokenRequest(BaseModel):
    room_name: str | None = None
    participant_identity: str | None = None
    participant_name: str | None = "Website Visitor"
    tenant_id: str | None = "default_tenant"
    channel: str | None = "browser_voice"


class TokenResponse(BaseModel):
    ok: bool = True
    token: str
    room_name: str
    participant_identity: str
    livekit_url: str
    mode: str = "oss_development"
    expires_in: int = 7200


def create_livekit_token(
    room_name: str,
    participant_identity: str,
    participant_name: str = "Visitor",
    api_key: str | None = None,
    api_secret: str | None = None,
    ttl_seconds: int = 7200,
) -> str:
    """Generate a signed LiveKit JWT access token."""
    key = api_key or settings.LIVEKIT_API_KEY or "devkey"
    secret = api_secret or settings.LIVEKIT_API_SECRET or "secret"
    now = int(time.time())

    claims = {
        "iss": key,
        "sub": participant_identity,
        "name": participant_name,
        "nbf": now - 10,
        "exp": now + ttl_seconds,
        "video": {
            "room": room_name,
            "roomJoin": True,
            "canPublish": True,
            "canSubscribe": True,
            "canPublishData": True,
        },
    }

    token = jwt.encode(claims, secret, algorithm="HS256")
    return token


@router.get("/token", response_model=TokenResponse)
async def get_livekit_token(
    room: str | None = Query(None, description="LiveKit room name"),
    identity: str | None = Query(None, description="Unique participant identity"),
    name: str = Query("Website Visitor", description="Participant display name"),
    tenant_id: str = Query("default_tenant", description="Tenant ID"),
    channel: str = Query("browser_voice", description="Interaction channel"),
) -> TokenResponse:
    """Issue a LiveKit WebRTC access token for browser audio streaming."""
    room_name = room or f"omniweb-{tenant_id}-{uuid4().hex[:8]}"
    participant_id = identity or f"user-{uuid4().hex[:8]}"

    token = create_livekit_token(
        room_name=room_name,
        participant_identity=participant_id,
        participant_name=name,
    )

    livekit_url = settings.LIVEKIT_URL or "ws://localhost:7880"
    mode = "oss_development" if (settings.LIVEKIT_API_KEY or "devkey") == "devkey" else "cloud_production"

    logger.info(
        f"[LiveKit] Issued token for participant '{participant_id}' in room '{room_name}' (mode: {mode})"
    )

    return TokenResponse(
        ok=True,
        token=token,
        room_name=room_name,
        participant_identity=participant_id,
        livekit_url=livekit_url,
        mode=mode,
        expires_in=7200,
    )


@router.post("/token", response_model=TokenResponse)
async def post_livekit_token(req: TokenRequest) -> TokenResponse:
    """Issue a LiveKit token via POST request."""
    return await get_livekit_token(
        room=req.room_name,
        identity=req.participant_identity,
        name=req.participant_name or "Website Visitor",
        tenant_id=req.tenant_id or "default_tenant",
        channel=req.channel or "browser_voice",
    )


@router.get("/status")
async def get_livekit_status() -> dict[str, Any]:
    """Check LiveKit service configuration and availability."""
    livekit_url = settings.LIVEKIT_URL or "ws://localhost:7880"
    is_dev = (settings.LIVEKIT_API_KEY or "devkey") == "devkey"

    return {
        "ok": True,
        "configured": settings.livekit_configured or is_dev,
        "livekit_url": livekit_url,
        "mode": "oss_development" if is_dev else "production",
        "stt_engine": settings.DEEPGRAM_STT_MODEL,
        "default_voice": settings.DEEPGRAM_TTS_VOICE,
        "enable_livekit": settings.ENABLE_LIVEKIT,
    }

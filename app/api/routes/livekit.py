"""LiveKit API routes — token generation & room management.

The frontend calls ``POST /api/livekit/token`` to get a short-lived JWT,
then connects directly to LiveKit Cloud via WebRTC.  The hosted agent
(configured in LiveKit Cloud dashboard) auto-dispatches to the room
and handles the full STT → LLM → TTS pipeline.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.logging import get_logger
from app.services import livekit_service

logger = get_logger(__name__)
settings = get_settings()

router = APIRouter(prefix="/livekit", tags=["livekit"])


class TokenRequest(BaseModel):
    """Request body for creating a LiveKit session token."""
    client_id: str | None = None
    channel: str = "web"  # "web" | "phone" | "embed"


class TokenResponse(BaseModel):
    """Response with everything the frontend needs to connect."""
    token: str
    room_name: str
    livekit_url: str


@router.post("/token", response_model=TokenResponse)
async def create_session_token(req: TokenRequest):
    """Generate a LiveKit access token for a visitor session.

    The frontend uses this to connect via the LiveKit SDK.
    The hosted agent (configured in LiveKit Cloud → Agents) automatically
    joins the room — no self-hosted worker process needed.
    """
    if not settings.livekit_configured:
        raise HTTPException(status_code=503, detail="LiveKit not configured")

    room_name = livekit_service.create_room_name(
        client_id=req.client_id,
        channel=req.channel,
    )

    # Metadata visible to the hosted agent (for lead tracking, etc.)
    metadata: dict[str, Any] = {
        "client_id": req.client_id or "",
        "channel": req.channel,
    }

    token = livekit_service.generate_participant_token(
        room_name=room_name,
        participant_name="visitor",
        metadata=json.dumps(metadata),
    )

    logger.info(
        "LiveKit session created",
        room=room_name,
        channel=req.channel,
    )

    return TokenResponse(
        token=token,
        room_name=room_name,
        livekit_url=settings.LIVEKIT_URL,
    )


@router.get("/rooms")
async def list_active_rooms():
    """List active LiveKit rooms (admin/debug endpoint)."""
    if not settings.livekit_configured:
        raise HTTPException(status_code=503, detail="LiveKit not configured")

    rooms = await livekit_service.list_rooms()
    return {"rooms": rooms, "count": len(rooms)}

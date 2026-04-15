"""LiveKit API routes — token generation, prompt composition & agent dispatch.

The frontend calls ``POST /api/livekit/token`` to get a short-lived JWT,
then connects directly to LiveKit Cloud via WebRTC.  The route composes
a per-tenant system prompt (via the prompt engine) and dispatches our
self-hosted agent worker with that prompt as dispatch metadata.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.logging import get_logger
from app.services import livekit_service
from app.services.prompt_engine import compose_system_prompt, compose_greeting

logger = get_logger(__name__)
settings = get_settings()

router = APIRouter(prefix="/livekit", tags=["livekit"])


# ── Omniweb landing-page default prompt ──────────────────────────────────────

OMNIWEB_SYSTEM_PROMPT = compose_system_prompt(
    agent_name="Ava",
    business_name="Omniweb",
    industry_slug="general",
    agent_mode="lead_qualifier",
    business_type="AI Voice & Text Agent Platform",
    services=[
        "AI voice agents for websites",
        "AI text chat agents",
        "Lead capture & qualification",
        "Appointment booking",
        "24/7 customer service automation",
        "Multi-language support",
        "CRM integrations",
        "Custom agent branding",
    ],
    timezone="America/New_York",
    booking_url="https://omniweb.ai",
    after_hours_message="Our AI agents work 24/7 — there are no after-hours!",
    custom_prompt=(
        "You represent Omniweb (omniweb.ai), an AI-powered voice and text agent "
        "platform that helps businesses automate lead capture, customer service, "
        "and appointment booking. Our agents deploy as a simple widget on any "
        "website and start converting visitors instantly — no coding required.\n\n"
        "Key selling points:\n"
        "- Deploys in under 5 minutes with a single line of code\n"
        "- AI voice agent that sounds human — not a chatbot\n"
        "- Captures leads 24/7 even when the business is closed\n"
        "- Qualifies leads with natural conversation, not forms\n"
        "- Books appointments directly on the business calendar\n"
        "- Supports 29+ languages automatically\n"
        "- Works on any website (WordPress, Shopify, Wix, custom)\n"
        "- Customizable voice, personality, and industry knowledge\n"
        "- Starter plan begins at $49/month\n\n"
        "If someone asks about pricing, explain our tiered plans start at $49/month "
        "for small businesses, and we offer a free trial so they can see it in action. "
        "Always try to collect their name and email to follow up."
    ),
)

OMNIWEB_GREETING = (
    "Hey there! I'm Ava from Omniweb. We help businesses like yours turn website "
    "visitors into customers using AI-powered voice and text agents — think of it "
    "as a 24/7 sales rep that never takes a break. What kind of business are you running?"
)


class TokenRequest(BaseModel):
    """Request body for creating a LiveKit session token."""
    client_id: str | None = None
    channel: str = "web"  # "web" | "phone" | "embed"
    language: str = "en"  # ISO 639-1 language code


class TokenResponse(BaseModel):
    """Response with everything the frontend needs to connect."""
    token: str
    room_name: str
    livekit_url: str


@router.post("/token", response_model=TokenResponse)
async def create_session_token(req: TokenRequest):
    """Generate a LiveKit access token and dispatch the agent with a prompt.

    For the landing page (no client_id), uses the Omniweb default prompt.
    For tenant embed widgets (client_id provided), will look up the
    tenant's AgentConfig and compose a per-tenant prompt.
    """
    if not settings.livekit_configured:
        raise HTTPException(status_code=503, detail="LiveKit not configured")

    room_name = livekit_service.create_room_name(
        client_id=req.client_id,
        channel=req.channel,
    )

    # Participant metadata (visible to the agent worker)
    participant_metadata: dict[str, Any] = {
        "client_id": req.client_id or "",
        "channel": req.channel,
    }

    token = livekit_service.generate_participant_token(
        room_name=room_name,
        participant_name="visitor",
        metadata=json.dumps(participant_metadata),
    )

    # ── Compose the system prompt ────────────────────────────────────────
    # TODO: When client_id is provided, look up AgentConfig from DB and
    #       compose a tenant-specific prompt. For now, use the Omniweb default.
    system_prompt = OMNIWEB_SYSTEM_PROMPT
    first_message = OMNIWEB_GREETING

    # Dispatch the self-hosted agent with the prompt as metadata
    await livekit_service.dispatch_agent(
        room_name,
        system_prompt=system_prompt,
        first_message=first_message,
        language=req.language,
    )

    logger.info(
        "LiveKit session created",
        room=room_name,
        channel=req.channel,
        language=req.language,
        prompt_len=len(system_prompt),
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

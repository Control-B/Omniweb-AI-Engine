"""LiveKit service — token generation, room management & agent dispatch.

The frontend receives a short-lived token, connects to LiveKit Cloud
via WebRTC.  The engine dispatches our self-hosted agent worker with
per-tenant prompt metadata so every business gets a customized AI voice.

Pipeline: Deepgram STT → OpenAI LLM → Cartesia TTS (via LiveKit Inference).
"""

from __future__ import annotations

import json
import time
import uuid
from datetime import timedelta
from typing import Any

from livekit.api import AccessToken, VideoGrants, LiveKitAPI, CreateAgentDispatchRequest

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


def generate_participant_token(
    *,
    room_name: str,
    participant_name: str = "visitor",
    participant_identity: str | None = None,
    metadata: str = "",
    ttl: int = 3600,
) -> str:
    """Generate a short-lived access token for a participant.

    Args:
        room_name: The LiveKit room to join (created on-the-fly).
        participant_name: Display name shown in the room.
        participant_identity: Unique identity (defaults to UUID).
        metadata: JSON string passed to the agent worker (client_id, language, etc.).
        ttl: Token lifetime in seconds (default 1 hour).

    Returns:
        A signed JWT string the frontend passes to ``LiveKitRoom``.
    """
    identity = participant_identity or f"visitor_{uuid.uuid4().hex[:8]}"

    token = (
        AccessToken(settings.LIVEKIT_API_KEY, settings.LIVEKIT_API_SECRET)
        .with_identity(identity)
        .with_name(participant_name)
        .with_metadata(metadata)
        .with_grants(
            VideoGrants(
                room_join=True,
                room=room_name,
                can_publish=True,
                can_subscribe=True,
                can_publish_data=True,
            )
        )
        .with_ttl(timedelta(seconds=ttl))
    )

    jwt = token.to_jwt()
    logger.info(
        "Generated LiveKit token",
        room=room_name,
        identity=identity,
        ttl=ttl,
    )
    return jwt


def create_room_name(client_id: str | None = None, channel: str = "web") -> str:
    """Generate a unique room name for a conversation session.

    Format: ``omniweb_{channel}_{client_id_prefix}_{timestamp_hex}``
    """
    prefix = (client_id or "anon")[:8]
    ts = hex(int(time.time()))[2:]
    return f"omniweb_{channel}_{prefix}_{ts}"


async def dispatch_agent(
    room_name: str,
    *,
    system_prompt: str = "",
    first_message: str = "",
    language: str = "en",
) -> None:
    """Dispatch the self-hosted Omniweb agent to a room with prompt metadata.

    The agent worker reads ``ctx.job.metadata`` to get the system prompt,
    first message, and language, enabling per-tenant customization.
    """
    agent_name = settings.LIVEKIT_AGENT_NAME
    if not agent_name:
        logger.warning("LIVEKIT_AGENT_NAME not set — skipping agent dispatch")
        return

    # Pack prompt + language into dispatch metadata so the worker can read it
    dispatch_metadata = json.dumps({
        "system_prompt": system_prompt,
        "first_message": first_message,
        "language": language,
    })

    async with LiveKitAPI(
        url=settings.LIVEKIT_URL,
        api_key=settings.LIVEKIT_API_KEY,
        api_secret=settings.LIVEKIT_API_SECRET,
    ) as api:
        dispatch = await api.agent_dispatch.create_dispatch(
            CreateAgentDispatchRequest(
                agent_name=agent_name,
                room=room_name,
                metadata=dispatch_metadata,
            )
        )
        logger.info(
            "Dispatched agent to room",
            agent=agent_name,
            room=room_name,
            dispatch_id=dispatch.id,
            prompt_len=len(system_prompt),
        )


async def list_rooms() -> list[dict[str, Any]]:
    """List active LiveKit rooms (for admin dashboard)."""
    if not settings.livekit_configured:
        return []

    async with LiveKitAPI(
        url=settings.LIVEKIT_URL,
        api_key=settings.LIVEKIT_API_KEY,
        api_secret=settings.LIVEKIT_API_SECRET,
    ) as api:
        rooms_resp = await api.room.list_rooms()
        return [
            {
                "name": r.name,
                "num_participants": r.num_participants,
                "creation_time": r.creation_time,
                "metadata": r.metadata,
            }
            for r in rooms_resp.rooms
        ]


async def delete_room(room_name: str) -> None:
    """Force-close a LiveKit room."""
    if not settings.livekit_configured:
        return

    async with LiveKitAPI(
        url=settings.LIVEKIT_URL,
        api_key=settings.LIVEKIT_API_KEY,
        api_secret=settings.LIVEKIT_API_SECRET,
    ) as api:
        await api.room.delete_room(room_name)
        logger.info("Deleted LiveKit room", room=room_name)

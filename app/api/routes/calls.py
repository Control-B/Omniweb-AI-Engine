"""Calls API — conversation history, status, and ElevenLabs conversation sync.

Dashboard/platform endpoints:
    GET    /calls                list calls for a client (paginated)
    GET    /calls/{id}          call detail with transcript
    GET    /calls/sync          sync recent conversations from ElevenLabs
    GET    /calls/{id}/audio    proxy audio download from ElevenLabs
"""
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.api.deps import get_session
from app.core.auth import get_current_client
from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.models import AgentConfig, Call, PhoneNumber, Transcript
from app.services import elevenlabs_service

logger = get_logger(__name__)
settings = get_settings()
router = APIRouter(tags=["calls"])


def _resolve_client_id(current_client: dict, client_id: str | None) -> str:
    """If admin and client_id given, use it. Otherwise use the caller's own."""
    if client_id and current_client.get("role") == "admin":
        return client_id
    return current_client["client_id"]


# ── Dashboard endpoints ───────────────────────────────────────────────────────

@router.get("/calls")
async def list_calls(
    current_client: dict = Depends(get_current_client),
    client_id: Optional[str] = Query(None),
    channel: Optional[str] = Query(None),  # voice | text | whatsapp
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    db: AsyncSession = Depends(get_session),
) -> dict:
    """List calls/conversations for a client, newest first."""
    cid = _resolve_client_id(current_client, client_id)
    query = select(Call).where(Call.client_id == cid)
    if channel:
        query = query.where(Call.channel == channel)
    query = query.order_by(desc(Call.started_at)).limit(limit).offset(offset)

    result = await db.execute(query)
    calls = result.scalars().all()

    # Get total count
    count_query = select(func.count(Call.id)).where(Call.client_id == cid)
    if channel:
        count_query = count_query.where(Call.channel == channel)
    total = (await db.execute(count_query)).scalar() or 0

    return {
        "calls": [
            {
                "id": str(c.id),
                "caller_number": c.caller_number,
                "direction": c.direction,
                "channel": c.channel,
                "status": c.status,
                "provider": c.provider,
                "duration_seconds": c.duration_seconds,
                "started_at": c.started_at.isoformat() if c.started_at else None,
                "ended_at": c.ended_at.isoformat() if c.ended_at else None,
                "post_call_processed": c.post_call_processed,
                "elevenlabs_conversation_id": c.elevenlabs_conversation_id,
                "retell_call_id": c.retell_call_id,
            }
            for c in calls
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/calls/{call_id}")
async def get_call(
    call_id: UUID,
    current_client: dict = Depends(get_current_client),
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Get call detail including transcript."""
    call = await db.get(Call, call_id)
    if not call:
        raise HTTPException(404, "Call not found")

    # Tenant isolation: non-admin can only see own calls
    if current_client.get("role") != "admin" and str(call.client_id) != current_client["client_id"]:
        raise HTTPException(404, "Call not found")

    # Load transcript
    transcript_result = await db.execute(
        select(Transcript).where(Transcript.call_id == call_id)
    )
    transcript = transcript_result.scalar_one_or_none()

    return {
        "id": str(call.id),
        "client_id": str(call.client_id),
        "caller_number": call.caller_number,
        "direction": call.direction,
        "channel": call.channel,
        "status": call.status,
        "provider": call.provider,
        "duration_seconds": call.duration_seconds,
        "recording_url": call.recording_url,
        "started_at": call.started_at.isoformat() if call.started_at else None,
        "ended_at": call.ended_at.isoformat() if call.ended_at else None,
        "post_call_processed": call.post_call_processed,
        "elevenlabs_conversation_id": call.elevenlabs_conversation_id,
        "retell_call_id": call.retell_call_id,
        "transcript": {
            "turns": transcript.turns if transcript else [],
            "summary": transcript.summary if transcript else None,
            "sentiment": transcript.sentiment if transcript else None,
        },
    }


@router.post("/calls/sync")
async def sync_conversations(
    current_client: dict = Depends(get_current_client),
    client_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Sync recent conversations from ElevenLabs into the local DB.

    Useful as a fallback if webhooks were missed, or for initial data import.
    """
    cid = _resolve_client_id(current_client, client_id)
    # Get client's agent
    result = await db.execute(
        select(AgentConfig).where(AgentConfig.client_id == cid)
    )
    config = result.scalar_one_or_none()
    if not config or not config.elevenlabs_agent_id:
        return {"synced": 0, "message": "No ElevenLabs agent configured"}

    try:
        data = await elevenlabs_service.list_conversations(
            agent_id=config.elevenlabs_agent_id,
            page_size=100,
        )
    except Exception as exc:
        logger.error(f"Failed to fetch conversations from ElevenLabs: {exc}")
        return {"synced": 0, "error": str(exc)}

    synced = 0
    for conv in data.get("conversations", []):
        conv_id = conv.get("conversation_id", "")

        # Skip if already exists
        existing = await db.execute(
            select(Call.id).where(Call.elevenlabs_conversation_id == conv_id)
        )
        if existing.scalar_one_or_none():
            continue

        # Create call record
        start_time = conv.get("start_time_unix_secs")
        call = Call(
            client_id=cid,
            caller_number="",
            direction=conv.get("direction", "inbound"),
            channel="voice" if conv.get("conversation_initiation_source") in ("phone_call", "twilio") else "text",
            status="completed",
            elevenlabs_conversation_id=conv_id,
            duration_seconds=conv.get("call_duration_secs"),
            started_at=datetime.fromtimestamp(start_time, tz=timezone.utc) if start_time else None,
        )
        db.add(call)
        synced += 1

    await db.commit()
    return {"synced": synced, "total_in_elevenlabs": len(data.get("conversations", []))}

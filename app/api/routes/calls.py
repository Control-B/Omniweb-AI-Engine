"""Calls API — conversation history, status, and Retell-backed sessions.

Dashboard/platform endpoints:
    GET    /calls                list calls for a client (paginated)
    GET    /calls/{id}          call detail with transcript
    GET    /calls/sync          no-op (Retell pushes via webhooks)
"""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.core.auth import get_current_client
from app.core.logging import get_logger
from app.models.models import Call, Transcript

logger = get_logger(__name__)
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
                "duration_seconds": c.duration_seconds,
                "started_at": c.started_at.isoformat() if c.started_at else None,
                "ended_at": c.ended_at.isoformat() if c.ended_at else None,
                "post_call_processed": c.post_call_processed,
                "retell_call_id": c.retell_call_id,
                "elevenlabs_conversation_id": c.elevenlabs_conversation_id,
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
        "duration_seconds": call.duration_seconds,
        "recording_url": call.recording_url,
        "started_at": call.started_at.isoformat() if call.started_at else None,
        "ended_at": call.ended_at.isoformat() if call.ended_at else None,
        "post_call_processed": call.post_call_processed,
        "retell_call_id": call.retell_call_id,
        "elevenlabs_conversation_id": call.elevenlabs_conversation_id,
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
    """Retell pushes call events to ``/api/webhooks/retell`` — no pull sync."""
    _ = _resolve_client_id(current_client, client_id)
    _ = db  # unused; keeps signature stable for clients
    return {
        "synced": 0,
        "message": "Conversation sync is handled by Retell webhooks.",
    }

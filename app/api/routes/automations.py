"""Automations API — CRUD for outreach sequences.

Endpoints:
    GET    /automations           — list sequences for the current client
    POST   /automations           — create a new sequence
    PUT    /automations/{id}      — update an existing sequence
    DELETE /automations/{id}      — delete a sequence
"""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.core.auth import get_current_client
from app.core.logging import get_logger
from app.models.models import OutreachSequence

logger = get_logger(__name__)
router = APIRouter(prefix="/automations", tags=["automations"])


class StepSchema(BaseModel):
    type: str  # sms | wait | call
    config: dict  # {body: ""} | {minutes: ""} | {note: ""}


class SequenceCreate(BaseModel):
    name: str
    trigger: str = "after_call"  # after_call | missed_call | new_lead | manual
    enabled: bool = True
    steps: list[StepSchema] = []


class SequenceUpdate(BaseModel):
    name: Optional[str] = None
    trigger: Optional[str] = None
    enabled: Optional[bool] = None
    steps: Optional[list[StepSchema]] = None


def _resolve_client_id(current_client: dict, client_id: str | None) -> str:
    if client_id and current_client.get("role") == "admin":
        return client_id
    return current_client["client_id"]


def _serialize(seq: OutreachSequence) -> dict:
    """Convert an OutreachSequence to API-friendly dict."""
    return {
        "id": str(seq.id),
        "name": seq.name,
        "trigger": seq.trigger,
        "enabled": seq.is_active,
        "steps": seq.steps or [],
        "created_at": seq.created_at.isoformat() if seq.created_at else None,
        "updated_at": seq.updated_at.isoformat() if seq.updated_at else None,
    }


@router.get("")
async def list_sequences(
    client_id: str | None = None,
    current_client: dict = Depends(get_current_client),
    db: AsyncSession = Depends(get_session),
) -> dict:
    """List all outreach sequences for the client."""
    cid = _resolve_client_id(current_client, client_id)
    result = await db.execute(
        select(OutreachSequence)
        .where(OutreachSequence.client_id == cid)
        .order_by(OutreachSequence.created_at)
    )
    sequences = result.scalars().all()
    return {"sequences": [_serialize(s) for s in sequences]}


@router.post("", status_code=201)
async def create_sequence(
    body: SequenceCreate,
    current_client: dict = Depends(get_current_client),
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Create a new outreach sequence."""
    cid = current_client["client_id"]

    # Convert steps from frontend format to storage format
    steps_data = [
        {
            "type": s.type,
            "delay_minutes": int(s.config.get("minutes", 0)) if s.type == "wait" else 0,
            "template": s.config.get("body", "") if s.type == "sms" else "",
            "note": s.config.get("note", "") if s.type == "call" else "",
            **s.config,
        }
        for s in body.steps
    ]

    seq = OutreachSequence(
        client_id=cid,
        name=body.name,
        trigger=body.trigger,
        is_active=body.enabled,
        steps=steps_data,
    )
    db.add(seq)
    await db.commit()
    await db.refresh(seq)

    logger.info(f"Sequence created: {seq.name} ({seq.id}) for client {cid}")
    return _serialize(seq)


@router.put("/{sequence_id}")
async def update_sequence(
    sequence_id: str,
    body: SequenceUpdate,
    current_client: dict = Depends(get_current_client),
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Update an existing outreach sequence."""
    cid = current_client["client_id"]

    result = await db.execute(
        select(OutreachSequence).where(
            OutreachSequence.id == sequence_id,
            OutreachSequence.client_id == cid,
        )
    )
    seq = result.scalar_one_or_none()
    if not seq:
        raise HTTPException(404, "Sequence not found")

    if body.name is not None:
        seq.name = body.name
    if body.trigger is not None:
        seq.trigger = body.trigger
    if body.enabled is not None:
        seq.is_active = body.enabled
    if body.steps is not None:
        seq.steps = [
            {
                "type": s.type,
                "delay_minutes": int(s.config.get("minutes", 0)) if s.type == "wait" else 0,
                "template": s.config.get("body", "") if s.type == "sms" else "",
                "note": s.config.get("note", "") if s.type == "call" else "",
                **s.config,
            }
            for s in body.steps
        ]

    await db.commit()
    await db.refresh(seq)

    logger.info(f"Sequence updated: {seq.name} ({seq.id})")
    return _serialize(seq)


@router.delete("/{sequence_id}")
async def delete_sequence(
    sequence_id: str,
    current_client: dict = Depends(get_current_client),
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Delete an outreach sequence."""
    cid = current_client["client_id"]

    result = await db.execute(
        select(OutreachSequence).where(
            OutreachSequence.id == sequence_id,
            OutreachSequence.client_id == cid,
        )
    )
    seq = result.scalar_one_or_none()
    if not seq:
        raise HTTPException(404, "Sequence not found")

    await db.delete(seq)
    await db.commit()

    logger.info(f"Sequence deleted: {seq.name} ({seq.id})")
    return {"ok": True, "message": f"Sequence '{seq.name}' deleted"}

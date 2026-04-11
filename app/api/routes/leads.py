"""Leads API — view and manage extracted leads."""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.core.logging import get_logger
from app.models.models import Lead

logger = get_logger(__name__)
router = APIRouter(prefix="/leads", tags=["leads"])


class LeadStatusUpdate(BaseModel):
    status: str  # new | contacted | booked | closed | lost


@router.get("")
async def list_leads(
    client_id: str = Query(...),
    status: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    db: AsyncSession = Depends(get_session),
) -> dict:
    q = select(Lead).where(Lead.client_id == client_id)
    if status:
        q = q.where(Lead.status == status)
    q = q.order_by(desc(Lead.created_at)).limit(limit).offset(offset)
    result = await db.execute(q)
    leads = result.scalars().all()
    return {
        "leads": [
            {
                "id": str(l.id),
                "call_id": str(l.call_id),
                "caller_name": l.caller_name,
                "caller_phone": l.caller_phone,
                "intent": l.intent,
                "urgency": l.urgency,
                "summary": l.summary,
                "status": l.status,
                "lead_score": l.lead_score,
                "follow_up_sent": l.follow_up_sent,
                "created_at": l.created_at.isoformat() if l.created_at else None,
            }
            for l in leads
        ],
        "total": len(leads),
    }


@router.get("/{lead_id}")
async def get_lead(lead_id: UUID, db: AsyncSession = Depends(get_session)) -> dict:
    lead = await db.get(Lead, lead_id)
    if not lead:
        raise HTTPException(404, "Lead not found")
    return {
        "id": str(lead.id),
        "call_id": str(lead.call_id),
        "client_id": str(lead.client_id),
        "caller_name": lead.caller_name,
        "caller_phone": lead.caller_phone,
        "caller_email": lead.caller_email,
        "intent": lead.intent,
        "urgency": lead.urgency,
        "summary": lead.summary,
        "services_requested": lead.services_requested,
        "status": lead.status,
        "lead_score": lead.lead_score,
        "follow_up_sent": lead.follow_up_sent,
        "follow_up_at": lead.follow_up_at.isoformat() if lead.follow_up_at else None,
    }


@router.patch("/{lead_id}/status")
async def update_lead_status(
    lead_id: UUID,
    body: LeadStatusUpdate,
    db: AsyncSession = Depends(get_session),
) -> dict:
    lead = await db.get(Lead, lead_id)
    if not lead:
        raise HTTPException(404, "Lead not found")
    lead.status = body.status
    await db.commit()
    return {"id": str(lead.id), "status": body.status}

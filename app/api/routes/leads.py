"""Leads API — view and manage extracted leads."""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import desc, func, select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.core.auth import get_current_client
from app.core.logging import get_logger
from app.models.models import Lead

logger = get_logger(__name__)
router = APIRouter(prefix="/leads", tags=["leads"])


def _resolve_client_id(current_client: dict, client_id: str | None) -> str:
    if client_id and current_client.get("role") == "admin":
        return client_id
    return current_client["client_id"]


class LeadStatusUpdate(BaseModel):
    status: str  # new | contacted | booked | closed | lost


@router.get("")
async def list_leads(
    current_client: dict = Depends(get_current_client),
    client_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None, description="Search by name, phone, or email"),
    sort_by: Optional[str] = Query("created_at", description="Sort field: created_at, lead_score, urgency"),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    db: AsyncSession = Depends(get_session),
) -> dict:
    cid = _resolve_client_id(current_client, client_id)
    q = select(Lead).where(Lead.client_id == cid)
    count_q = select(func.count(Lead.id)).where(Lead.client_id == cid)

    if status:
        q = q.where(Lead.status == status)
        count_q = count_q.where(Lead.status == status)

    if search:
        search_filter = or_(
            Lead.caller_name.ilike(f"%{search}%"),
            Lead.caller_phone.ilike(f"%{search}%"),
            Lead.caller_email.ilike(f"%{search}%"),
        )
        q = q.where(search_filter)
        count_q = count_q.where(search_filter)

    # Sort
    if sort_by == "lead_score":
        q = q.order_by(desc(Lead.lead_score))
    elif sort_by == "urgency":
        q = q.order_by(desc(Lead.urgency))
    else:
        q = q.order_by(desc(Lead.created_at))

    total = await db.scalar(count_q)
    q = q.limit(limit).offset(offset)
    result = await db.execute(q)
    leads = result.scalars().all()

    return {
        "leads": [
            {
                "id": str(l.id),
                "call_id": str(l.call_id) if l.call_id else None,
                "caller_name": l.caller_name,
                "caller_phone": l.caller_phone,
                "caller_email": l.caller_email,
                "intent": l.intent,
                "urgency": l.urgency,
                "summary": l.summary,
                "services_requested": l.services_requested,
                "status": l.status,
                "lead_score": l.lead_score,
                "follow_up_sent": l.follow_up_sent,
                "created_at": l.created_at.isoformat() if l.created_at else None,
            }
            for l in leads
        ],
        "total": total or 0,
    }


@router.get("/{lead_id}")
async def get_lead(
    lead_id: UUID,
    current_client: dict = Depends(get_current_client),
    db: AsyncSession = Depends(get_session),
) -> dict:
    lead = await db.get(Lead, lead_id)
    if not lead:
        raise HTTPException(404, "Lead not found")
    if current_client.get("role") != "admin" and str(lead.client_id) != current_client["client_id"]:
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
        "created_at": lead.created_at.isoformat() if lead.created_at else None,
        "status_notes": getattr(lead, "status_notes", None),
    }


@router.patch("/{lead_id}/status")
async def update_lead_status(
    lead_id: UUID,
    body: LeadStatusUpdate,
    current_client: dict = Depends(get_current_client),
    db: AsyncSession = Depends(get_session),
) -> dict:
    lead = await db.get(Lead, lead_id)
    if not lead:
        raise HTTPException(404, "Lead not found")
    if current_client.get("role") != "admin" and str(lead.client_id) != current_client["client_id"]:
        raise HTTPException(404, "Lead not found")
    lead.status = body.status
    await db.commit()
    return {"id": str(lead.id), "status": body.status}

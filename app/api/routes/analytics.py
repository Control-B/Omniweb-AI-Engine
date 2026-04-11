"""Analytics API — call stats, lead funnel, usage metrics."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.models.models import Call, CallStatus, Lead

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/summary")
async def get_summary(
    client_id: str = Query(...),
    db: AsyncSession = Depends(get_session),
) -> dict:
    # Total calls
    total_calls = await db.scalar(
        select(func.count(Call.id)).where(Call.client_id == client_id)
    )
    # Completed calls
    completed_calls = await db.scalar(
        select(func.count(Call.id)).where(
            Call.client_id == client_id,
            Call.status == CallStatus.completed,
        )
    )
    # Avg duration
    avg_duration = await db.scalar(
        select(func.avg(Call.duration_seconds)).where(
            Call.client_id == client_id,
            Call.duration_seconds.isnot(None),
        )
    )
    # Total leads
    total_leads = await db.scalar(
        select(func.count(Lead.id)).where(Lead.client_id == client_id)
    )
    # Leads by status
    lead_statuses = await db.execute(
        select(Lead.status, func.count(Lead.id))
        .where(Lead.client_id == client_id)
        .group_by(Lead.status)
    )
    leads_by_status = {str(row[0]): row[1] for row in lead_statuses}

    return {
        "total_calls": total_calls or 0,
        "completed_calls": completed_calls or 0,
        "avg_duration_seconds": round(float(avg_duration or 0), 1),
        "total_leads": total_leads or 0,
        "leads_by_status": leads_by_status,
        "conversion_rate": round((total_leads or 0) / max(completed_calls or 1, 1) * 100, 1),
    }

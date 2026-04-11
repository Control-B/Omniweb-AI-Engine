"""Analytics API — call stats, lead funnel, usage metrics."""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.core.auth import get_current_client
from app.models.models import Call, Lead

router = APIRouter(prefix="/analytics", tags=["analytics"])


def _resolve_client_id(current_client: dict, client_id: str | None) -> str:
    if client_id and current_client.get("role") == "admin":
        return client_id
    return current_client["client_id"]


@router.get("/summary")
async def get_summary(
    current_client: dict = Depends(get_current_client),
    client_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_session),
) -> dict:
    cid = _resolve_client_id(current_client, client_id)
    # Total calls
    total_calls = await db.scalar(
        select(func.count(Call.id)).where(Call.client_id == cid)
    )
    # Completed calls
    completed_calls = await db.scalar(
        select(func.count(Call.id)).where(
            Call.client_id == cid,
            Call.status == "completed",
        )
    )
    # Avg duration
    avg_duration = await db.scalar(
        select(func.avg(Call.duration_seconds)).where(
            Call.client_id == cid,
            Call.duration_seconds.isnot(None),
        )
    )
    # Total leads
    total_leads = await db.scalar(
        select(func.count(Lead.id)).where(Lead.client_id == cid)
    )
    # Leads by status
    lead_statuses = await db.execute(
        select(Lead.status, func.count(Lead.id))
        .where(Lead.client_id == cid)
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

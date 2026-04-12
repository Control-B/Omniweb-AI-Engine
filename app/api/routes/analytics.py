"""Analytics API — call stats, lead funnel, usage metrics, tool call history."""
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, and_, cast, Date
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.core.auth import get_current_client
from app.models.models import Call, Lead, ToolCallLog

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
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=today_start.weekday())

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
    # Calls today
    calls_today = await db.scalar(
        select(func.count(Call.id)).where(
            Call.client_id == cid,
            Call.created_at >= today_start,
        )
    )
    # Calls this week
    calls_this_week = await db.scalar(
        select(func.count(Call.id)).where(
            Call.client_id == cid,
            Call.created_at >= week_start,
        )
    )
    # Missed calls (status = missed or no_answer)
    missed_calls = await db.scalar(
        select(func.count(Call.id)).where(
            Call.client_id == cid,
            Call.status.in_(["missed", "no_answer"]),
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
    # Leads today
    leads_today = await db.scalar(
        select(func.count(Lead.id)).where(
            Lead.client_id == cid,
            Lead.created_at >= today_start,
        )
    )
    # Booked appointments
    booked_appointments = await db.scalar(
        select(func.count(Lead.id)).where(
            Lead.client_id == cid,
            Lead.status == "booked",
        )
    )
    # Leads by status (funnel)
    lead_statuses = await db.execute(
        select(Lead.status, func.count(Lead.id))
        .where(Lead.client_id == cid)
        .group_by(Lead.status)
    )
    leads_by_status = {str(row[0]): row[1] for row in lead_statuses}

    # Average lead score
    avg_lead_score = await db.scalar(
        select(func.avg(Lead.lead_score)).where(Lead.client_id == cid)
    )

    # Tool calls today
    tool_calls_today = await db.scalar(
        select(func.count(ToolCallLog.id)).where(
            ToolCallLog.client_id == cid,
            ToolCallLog.created_at >= today_start,
        )
    )

    return {
        "total_calls": total_calls or 0,
        "completed_calls": completed_calls or 0,
        "calls_today": calls_today or 0,
        "calls_this_week": calls_this_week or 0,
        "missed_calls": missed_calls or 0,
        "avg_duration_seconds": round(float(avg_duration or 0), 1),
        "total_leads": total_leads or 0,
        "leads_today": leads_today or 0,
        "booked_appointments": booked_appointments or 0,
        "leads_by_status": leads_by_status,
        "avg_lead_score": round(float(avg_lead_score or 0), 2),
        "conversion_rate": round((total_leads or 0) / max(completed_calls or 1, 1) * 100, 1),
        "tool_calls_today": tool_calls_today or 0,
    }


@router.get("/weekly")
async def get_weekly_stats(
    current_client: dict = Depends(get_current_client),
    client_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Return daily call and lead counts for the past 7 days."""
    cid = _resolve_client_id(current_client, client_id)
    now = datetime.now(timezone.utc)
    seven_days_ago = (now - timedelta(days=6)).replace(hour=0, minute=0, second=0, microsecond=0)

    # Daily calls
    call_rows = await db.execute(
        select(
            cast(Call.created_at, Date).label("day"),
            func.count(Call.id),
        )
        .where(Call.client_id == cid, Call.created_at >= seven_days_ago)
        .group_by("day")
        .order_by("day")
    )
    calls_by_day = {str(r[0]): r[1] for r in call_rows}

    # Daily leads
    lead_rows = await db.execute(
        select(
            cast(Lead.created_at, Date).label("day"),
            func.count(Lead.id),
        )
        .where(Lead.client_id == cid, Lead.created_at >= seven_days_ago)
        .group_by("day")
        .order_by("day")
    )
    leads_by_day = {str(r[0]): r[1] for r in lead_rows}

    # Build 7-day series
    days = []
    for i in range(7):
        d = seven_days_ago + timedelta(days=i)
        day_str = d.strftime("%Y-%m-%d")
        day_label = d.strftime("%a")
        days.append({
            "date": day_str,
            "label": day_label,
            "calls": calls_by_day.get(day_str, 0),
            "leads": leads_by_day.get(day_str, 0),
        })

    return {"days": days}


@router.get("/tool-calls")
async def get_tool_call_logs(
    current_client: dict = Depends(get_current_client),
    client_id: Optional[str] = Query(None),
    tool_name: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Return tool call audit logs with filtering."""
    cid = _resolve_client_id(current_client, client_id)
    q = select(ToolCallLog).where(ToolCallLog.client_id == cid)
    if tool_name:
        q = q.where(ToolCallLog.tool_name == tool_name)
    q = q.order_by(ToolCallLog.created_at.desc()).limit(limit).offset(offset)

    result = await db.execute(q)
    logs = result.scalars().all()

    # Count total
    count_q = select(func.count(ToolCallLog.id)).where(ToolCallLog.client_id == cid)
    if tool_name:
        count_q = count_q.where(ToolCallLog.tool_name == tool_name)
    total = await db.scalar(count_q)

    # Tool call summary counts
    summary_rows = await db.execute(
        select(ToolCallLog.tool_name, func.count(ToolCallLog.id))
        .where(ToolCallLog.client_id == cid)
        .group_by(ToolCallLog.tool_name)
    )
    tool_summary = {str(r[0]): r[1] for r in summary_rows}

    return {
        "logs": [
            {
                "id": str(log.id),
                "tool_name": log.tool_name,
                "parameters": log.parameters,
                "result": log.result,
                "success": log.success,
                "error_message": log.error_message,
                "lead_id": str(log.lead_id) if log.lead_id else None,
                "duration_ms": log.duration_ms,
                "created_at": log.created_at.isoformat() if log.created_at else None,
            }
            for log in logs
        ],
        "total": total or 0,
        "tool_summary": tool_summary,
    }

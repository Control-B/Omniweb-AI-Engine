"""Analytics API for the SaaS dashboard and legacy reports."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from json import JSONDecodeError
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import Date, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.core.auth import get_current_client
from app.models.models import Call, Engagement, FollowUpTask, Lead, ToolCallLog
from app.services.dashboard_sync_service import (
    DashboardApiError,
    apply_engagement_filters,
    getCurrentTenantFromRequest,
    parse_filter_params,
    parse_transcript_message_count,
    require_feature_access,
    serialize_engagement_detail,
    serialize_engagement_summary,
    success_response,
    summarize_transcript_server_side,
    sync_billing_status,
)

router = APIRouter(prefix="/analytics", tags=["analytics"])


class EngagementPatchIn(BaseModel):
    leadStatus: str | None = Field(None, min_length=2, max_length=40)
    followUpNeeded: bool | None = None
    ownerNotes: str | None = Field(None, max_length=5000)
    resolved: bool | None = None


def _resolve_client_id(current_client: dict, client_id: str | None) -> str:
    if client_id and current_client.get("role") == "admin":
        return client_id
    return current_client["client_id"]


async def _read_json(request: Request) -> dict:
    try:
        payload = await request.json()
    except JSONDecodeError as exc:
        raise DashboardApiError(400, "INVALID_JSON", "Request body must be valid JSON") from exc
    if not isinstance(payload, dict):
        raise DashboardApiError(400, "INVALID_JSON", "Request body must be a JSON object")
    return payload


def _parse_body(model: type[BaseModel], payload: dict) -> BaseModel:
    try:
        return model.model_validate(payload)
    except ValidationError as exc:
        raise DashboardApiError(400, "VALIDATION_ERROR", exc.errors()[0]["msg"]) from exc


@router.get("/summary")
async def get_summary(request: Request, db: AsyncSession = Depends(get_session)) -> dict:
    context = await getCurrentTenantFromRequest(request, db)
    billing_status = await sync_billing_status(db, context.tenant)
    require_feature_access(billing_status)
    filters = parse_filter_params(request)

    query = apply_engagement_filters(select(Engagement), context.tenant_id, filters)
    result = await db.execute(query)
    engagements = result.scalars().all()

    total_conversations = len(engagements)
    qualified_leads = sum(1 for engagement in engagements if engagement.qualified)
    follow_up_needed = sum(1 for engagement in engagements if engagement.follow_up_needed)
    contact_info_captured = sum(1 for engagement in engagements if engagement.contact_captured)
    message_counts = [parse_transcript_message_count(engagement.transcript) for engagement in engagements]
    avg_messages = round(sum(message_counts) / len(message_counts), 2) if message_counts else 0
    conversion_rate = round((qualified_leads / total_conversations) * 100, 2) if total_conversations else 0

    return success_response(
        {
            "totalConversations": total_conversations,
            "qualifiedLeads": qualified_leads,
            "followUpNeeded": follow_up_needed,
            "contactInfoCaptured": contact_info_captured,
            "avgMessagesPerSession": avg_messages,
            "conversionRate": conversion_rate,
        }
    )


@router.get("/engagements")
async def list_engagements(request: Request, db: AsyncSession = Depends(get_session)) -> dict:
    context = await getCurrentTenantFromRequest(request, db)
    billing_status = await sync_billing_status(db, context.tenant)
    require_feature_access(billing_status)
    filters = parse_filter_params(request)

    base_query = apply_engagement_filters(select(Engagement), context.tenant_id, filters)
    total = await db.scalar(select(func.count()).select_from(base_query.subquery()))
    page = filters["page"]
    page_size = filters["pageSize"]
    offset = (page - 1) * page_size
    result = await db.execute(
        base_query.order_by(Engagement.created_at.desc()).offset(offset).limit(page_size)
    )
    engagements = result.scalars().all()

    return success_response(
        {
            "items": [serialize_engagement_summary(engagement) for engagement in engagements],
            "pagination": {
                "page": page,
                "pageSize": page_size,
                "total": total or 0,
            },
        }
    )


@router.get("/engagements/{engagement_id}")
async def get_engagement_detail(engagement_id: str, request: Request, db: AsyncSession = Depends(get_session)) -> dict:
    context = await getCurrentTenantFromRequest(request, db)
    billing_status = await sync_billing_status(db, context.tenant)
    require_feature_access(billing_status)

    engagement = await db.get(Engagement, engagement_id)
    if not engagement or engagement.client_id != context.tenant_id:
        raise DashboardApiError(404, "ENGAGEMENT_NOT_FOUND", "Engagement not found")

    tasks_result = await db.execute(
        select(FollowUpTask)
        .where(FollowUpTask.engagement_id == engagement.id, FollowUpTask.client_id == context.tenant_id)
        .order_by(FollowUpTask.created_at.desc())
    )
    tasks = tasks_result.scalars().all()
    return success_response(serialize_engagement_detail(engagement, tasks))


@router.patch("/engagements/{engagement_id}")
async def patch_engagement(engagement_id: str, request: Request, db: AsyncSession = Depends(get_session)) -> dict:
    context = await getCurrentTenantFromRequest(request, db)
    billing_status = await sync_billing_status(db, context.tenant)
    require_feature_access(billing_status)
    body = _parse_body(EngagementPatchIn, await _read_json(request))

    engagement = await db.get(Engagement, engagement_id)
    if not engagement or engagement.client_id != context.tenant_id:
        raise DashboardApiError(404, "ENGAGEMENT_NOT_FOUND", "Engagement not found")

    if body.leadStatus is not None:
        engagement.lead_status = body.leadStatus.strip()
    if body.followUpNeeded is not None:
        engagement.follow_up_needed = body.followUpNeeded
    if body.ownerNotes is not None:
        engagement.owner_notes = body.ownerNotes.strip() if body.ownerNotes else None
    if body.resolved is not None:
        engagement.resolved = body.resolved

    await db.commit()
    await db.refresh(engagement)
    tasks_result = await db.execute(
        select(FollowUpTask)
        .where(FollowUpTask.engagement_id == engagement.id, FollowUpTask.client_id == context.tenant_id)
        .order_by(FollowUpTask.created_at.desc())
    )
    tasks = tasks_result.scalars().all()
    return success_response(serialize_engagement_detail(engagement, tasks))


@router.post("/engagements/{engagement_id}/summarize")
async def summarize_engagement(engagement_id: str, request: Request, db: AsyncSession = Depends(get_session)) -> dict:
    context = await getCurrentTenantFromRequest(request, db)
    billing_status = await sync_billing_status(db, context.tenant)
    require_feature_access(billing_status)

    engagement = await db.get(Engagement, engagement_id)
    if not engagement or engagement.client_id != context.tenant_id:
        raise DashboardApiError(404, "ENGAGEMENT_NOT_FOUND", "Engagement not found")
    if not engagement.transcript:
        raise DashboardApiError(400, "TRANSCRIPT_MISSING", "Transcript is required to summarize this engagement")

    summary = await summarize_transcript_server_side(engagement.transcript)
    engagement.summary_short = summary["summaryShort"]
    engagement.summary_full = summary["summaryFull"]
    engagement.intent = summary["intent"]
    engagement.lead_score = summary["leadScore"]
    engagement.pain_points = summary["painPoints"]
    engagement.buying_signals = summary["buyingSignals"]
    engagement.objections = summary["objections"]
    engagement.recommended_next_action = summary["recommendedNextAction"]
    engagement.follow_up_needed = summary["followUpNeeded"]

    await db.commit()
    await db.refresh(engagement)
    tasks_result = await db.execute(
        select(FollowUpTask)
        .where(FollowUpTask.engagement_id == engagement.id, FollowUpTask.client_id == context.tenant_id)
        .order_by(FollowUpTask.created_at.desc())
    )
    tasks = tasks_result.scalars().all()
    return success_response(serialize_engagement_detail(engagement, tasks))


@router.get("/weekly")
async def get_weekly_stats(
    current_client: dict = Depends(get_current_client),
    client_id: str | None = None,
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Return daily call and lead counts for the past 7 days."""
    cid = _resolve_client_id(current_client, client_id)
    now = datetime.now(timezone.utc)
    seven_days_ago = (now - timedelta(days=6)).replace(hour=0, minute=0, second=0, microsecond=0)

    call_rows = await db.execute(
        select(
            cast(Call.created_at, Date).label("day"),
            func.count(Call.id),
        )
        .where(Call.client_id == cid, Call.created_at >= seven_days_ago)
        .group_by("day")
        .order_by("day")
    )
    calls_by_day = {str(row[0]): row[1] for row in call_rows}

    lead_rows = await db.execute(
        select(
            cast(Lead.created_at, Date).label("day"),
            func.count(Lead.id),
        )
        .where(Lead.client_id == cid, Lead.created_at >= seven_days_ago)
        .group_by("day")
        .order_by("day")
    )
    leads_by_day = {str(row[0]): row[1] for row in lead_rows}

    days = []
    for offset in range(7):
        day = seven_days_ago + timedelta(days=offset)
        day_key = day.strftime("%Y-%m-%d")
        days.append(
            {
                "date": day_key,
                "label": day.strftime("%a"),
                "calls": calls_by_day.get(day_key, 0),
                "leads": leads_by_day.get(day_key, 0),
            }
        )

    return {"days": days}


@router.get("/tool-calls")
async def get_tool_call_logs(
    current_client: dict = Depends(get_current_client),
    client_id: str | None = None,
    tool_name: str | None = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Return tool call audit logs with filtering."""
    cid = _resolve_client_id(current_client, client_id)
    query = select(ToolCallLog).where(ToolCallLog.client_id == cid)
    if tool_name:
        query = query.where(ToolCallLog.tool_name == tool_name)
    query = query.order_by(ToolCallLog.created_at.desc()).limit(limit).offset(offset)

    result = await db.execute(query)
    logs = result.scalars().all()

    count_query = select(func.count(ToolCallLog.id)).where(ToolCallLog.client_id == cid)
    if tool_name:
        count_query = count_query.where(ToolCallLog.tool_name == tool_name)
    total = await db.scalar(count_query)

    summary_rows = await db.execute(
        select(ToolCallLog.tool_name, func.count(ToolCallLog.id))
        .where(ToolCallLog.client_id == cid)
        .group_by(ToolCallLog.tool_name)
    )
    tool_summary = {str(row[0]): row[1] for row in summary_rows}

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

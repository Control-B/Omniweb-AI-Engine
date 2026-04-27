"""Admin API — platform owner endpoints for managing tenants and templates.

All endpoints require admin role.

Endpoints:
    GET    /admin/clients                     — list all clients
    GET    /admin/clients/{id}                — client detail
    PATCH  /admin/clients/{id}                — edit client (plan, active, role)
    GET    /admin/clients/{id}/agent-config    — view a client's agent config
    PUT    /admin/clients/{id}/agent-config    — edit a client's agent config
    GET    /admin/templates                    — list templates
    POST   /admin/templates                    — create template
    PUT    /admin/templates/{id}               — update template
    DELETE /admin/templates/{id}               — deactivate template
    POST   /admin/impersonate/{client_id}      — get JWT as client (admin only)
    GET    /admin/stats                        — platform-wide stats
"""
from typing import Optional
from uuid import UUID
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import desc, func, select, and_, cast, Date
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.core.auth import create_access_token, get_effective_permissions, require_permissions
from app.core.logging import get_logger
from app.models.models import AgentConfig, AgentTemplate, Call, Client, Lead, PhoneNumber, ToolCallLog

logger = get_logger(__name__)
router = APIRouter(prefix="/admin", tags=["admin"])


# ══════════════════════════════════════════════════════════════════════════════
#  Client Management
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/clients")
async def list_clients(
    admin: dict = Depends(require_permissions("clients.read")),
    search: Optional[str] = Query(None),
    plan: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    db: AsyncSession = Depends(get_session),
) -> dict:
    """List all clients with optional filters."""
    q = select(Client).where(Client.role == "client")  # don't list other admins
    if search:
        q = q.where(
            Client.name.ilike(f"%{search}%") | Client.email.ilike(f"%{search}%")
        )
    if plan:
        q = q.where(Client.plan == plan)
    if is_active is not None:
        q = q.where(Client.is_active == is_active)
    q = q.order_by(desc(Client.created_at)).limit(limit).offset(offset)

    result = await db.execute(q)
    clients = result.scalars().all()

    # Count total
    count_q = select(func.count(Client.id)).where(Client.role == "client")
    total = await db.scalar(count_q) or 0

    return {
        "clients": [
            {
                "id": str(c.id),
                "name": c.name,
                "email": c.email,
                "plan": c.plan,
                "is_active": c.is_active,
                "created_at": c.created_at.isoformat() if c.created_at else None,
            }
            for c in clients
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/clients/{client_id}")
async def get_client(
    client_id: str,
    admin: dict = Depends(require_permissions("clients.read")),
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Get full client details including agent config summary."""
    client = await db.get(Client, client_id)
    if not client:
        raise HTTPException(404, "Client not found")

    # Get agent config
    result = await db.execute(
        select(AgentConfig).where(AgentConfig.client_id == client_id)
    )
    config = result.scalar_one_or_none()

    # Count calls, leads, numbers
    call_count = await db.scalar(
        select(func.count(Call.id)).where(Call.client_id == client_id)
    ) or 0
    lead_count = await db.scalar(
        select(func.count(Lead.id)).where(Lead.client_id == client_id)
    ) or 0
    number_count = await db.scalar(
        select(func.count(PhoneNumber.id)).where(PhoneNumber.client_id == client_id)
    ) or 0

    return {
        "id": str(client.id),
        "name": client.name,
        "email": client.email,
        "plan": client.plan,
        "role": client.role,
        "is_active": client.is_active,
        "created_at": client.created_at.isoformat() if client.created_at else None,
        "updated_at": client.updated_at.isoformat() if client.updated_at else None,
        "agent_config": {
            "agent_name": config.agent_name if config else None,
            "retell_agent_id": config.retell_agent_id if config else None,
            "business_name": config.business_name if config else None,
        } if config else None,
        "stats": {
            "total_calls": call_count,
            "total_leads": lead_count,
            "total_numbers": number_count,
        },
    }


class ClientPatchRequest(BaseModel):
    plan: Optional[str] = None
    is_active: Optional[bool] = None
    role: Optional[str] = None  # careful with this one
    name: Optional[str] = None


@router.patch("/clients/{client_id}")
async def update_client(
    client_id: str,
    body: ClientPatchRequest,
    admin: dict = Depends(require_permissions("clients.write")),
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Update a client's plan, status, or role."""
    client = await db.get(Client, client_id)
    if not client:
        raise HTTPException(404, "Client not found")

    for field, value in body.model_dump(exclude_none=True).items():
        setattr(client, field, value)

    await db.commit()
    await db.refresh(client)

    return {
        "id": str(client.id),
        "name": client.name,
        "plan": client.plan,
        "role": client.role,
        "is_active": client.is_active,
    }


# ══════════════════════════════════════════════════════════════════════════════
#  Impersonation
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/impersonate/{client_id}")
async def impersonate_client(
    client_id: str,
    admin: dict = Depends(require_permissions("clients.impersonate")),
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Generate a JWT token as if you were this client.

    Useful for debugging or configuring a client's agent on their behalf.
    """
    client = await db.get(Client, client_id)
    if not client:
        raise HTTPException(404, "Client not found")

    token = create_access_token(
        client_id=str(client.id),
        email=client.email,
        plan=client.plan,
        role=client.role,
          permissions=get_effective_permissions(client.role, client.permissions),
        extra={"impersonated_by": admin["client_id"]},
    )

    return {
        "access_token": token,
        "token_type": "bearer",
        "client_id": str(client.id),
        "email": client.email,
        "plan": client.plan,
        "role": client.role,
        "impersonated_by": admin["email"],
    }


# ══════════════════════════════════════════════════════════════════════════════
#  Template Management
# ══════════════════════════════════════════════════════════════════════════════

class TemplateCreate(BaseModel):
    name: str
    description: str = ""
    industry: str = "general"
    agent_mode: str = "lead_qualifier"
    is_default: bool = False
    agent_name: str = "AI Assistant"
    agent_greeting: str = "Thank you for visiting our website today... it will be a pleasure to help you?"
    system_prompt: str = ""
    voice_id: str = "EXAVITQu4vr4xnSDxMaL"
    voice_stability: float = 0.5
    voice_similarity_boost: float = 0.75
    llm_model: str = "gpt-4o"
    temperature: float = 0.7
    max_call_duration: int = 1800
    after_hours_message: str = "We're currently closed but will call you back first thing in the morning."
    after_hours_sms_enabled: bool = True
    allow_interruptions: bool = True
    services: list = []
    business_hours: dict = {}
    widget_config: dict = {}


class TemplateUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    industry: Optional[str] = None
    agent_mode: Optional[str] = None
    is_default: Optional[bool] = None
    is_active: Optional[bool] = None
    agent_name: Optional[str] = None
    agent_greeting: Optional[str] = None
    system_prompt: Optional[str] = None
    voice_id: Optional[str] = None
    voice_stability: Optional[float] = None
    voice_similarity_boost: Optional[float] = None
    llm_model: Optional[str] = None
    temperature: Optional[float] = None
    max_call_duration: Optional[int] = None
    after_hours_message: Optional[str] = None
    after_hours_sms_enabled: Optional[bool] = None
    allow_interruptions: Optional[bool] = None
    services: Optional[list] = None
    business_hours: Optional[dict] = None
    widget_config: Optional[dict] = None


def _template_to_dict(t: AgentTemplate) -> dict:
    return {
        "id": str(t.id),
        "name": t.name,
        "description": t.description,
        "industry": t.industry,
        "agent_mode": getattr(t, "agent_mode", "lead_qualifier"),
        "is_default": t.is_default,
        "is_active": t.is_active,
        "agent_name": t.agent_name,
        "agent_greeting": t.agent_greeting,
        "system_prompt": t.system_prompt,
        "voice_id": t.voice_id,
        "voice_stability": t.voice_stability,
        "voice_similarity_boost": t.voice_similarity_boost,
        "llm_model": t.llm_model,
        "temperature": t.temperature,
        "max_call_duration": t.max_call_duration,
        "after_hours_message": t.after_hours_message,
        "after_hours_sms_enabled": t.after_hours_sms_enabled,
        "allow_interruptions": t.allow_interruptions,
        "services": t.services,
        "business_hours": t.business_hours,
        "widget_config": t.widget_config,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "updated_at": t.updated_at.isoformat() if t.updated_at else None,
    }


@router.get("/templates")
async def list_templates(
    admin: dict = Depends(require_permissions("templates.read")),
    industry: Optional[str] = Query(None),
    active_only: bool = Query(True),
    db: AsyncSession = Depends(get_session),
) -> dict:
    """List all agent templates."""
    q = select(AgentTemplate)
    if active_only:
        q = q.where(AgentTemplate.is_active == True)
    if industry:
        q = q.where(AgentTemplate.industry == industry)
    q = q.order_by(AgentTemplate.name)
    result = await db.execute(q)
    templates = result.scalars().all()
    return {"templates": [_template_to_dict(t) for t in templates]}


@router.post("/templates", status_code=201)
async def create_template(
    body: TemplateCreate,
    admin: dict = Depends(require_permissions("templates.write")),
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Create a new agent template."""
    # If setting as default, unset any existing default
    if body.is_default:
        existing_defaults = await db.execute(
            select(AgentTemplate).where(AgentTemplate.is_default == True)
        )
        for t in existing_defaults.scalars():
            t.is_default = False

    template = AgentTemplate(**body.model_dump())
    db.add(template)
    await db.commit()
    await db.refresh(template)
    logger.info(f"Template created: {template.name} ({template.id})")
    return _template_to_dict(template)


@router.put("/templates/{template_id}")
async def update_template(
    template_id: str,
    body: TemplateUpdate,
    admin: dict = Depends(require_permissions("templates.write")),
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Update an existing template."""
    template = await db.get(AgentTemplate, template_id)
    if not template:
        raise HTTPException(404, "Template not found")

    updates = body.model_dump(exclude_none=True)

    # If setting as default, unset others
    if updates.get("is_default"):
        existing_defaults = await db.execute(
            select(AgentTemplate).where(
                AgentTemplate.is_default == True,
                AgentTemplate.id != template.id,
            )
        )
        for t in existing_defaults.scalars():
            t.is_default = False

    for field, value in updates.items():
        setattr(template, field, value)

    await db.commit()
    await db.refresh(template)
    return _template_to_dict(template)


@router.delete("/templates/{template_id}")
async def delete_template(
    template_id: str,
    admin: dict = Depends(require_permissions("templates.write")),
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Soft-delete a template (set is_active=False)."""
    template = await db.get(AgentTemplate, template_id)
    if not template:
        raise HTTPException(404, "Template not found")
    template.is_active = False
    template.is_default = False
    await db.commit()
    return {"ok": True, "template_id": str(template.id), "name": template.name}


# ══════════════════════════════════════════════════════════════════════════════
#  Agents — view all client agent configs
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/agents")
async def list_agents(
    admin: dict = Depends(require_permissions("agents.read")),
    db: AsyncSession = Depends(get_session),
) -> dict:
    """List all agents across all clients, joined with client info."""
    result = await db.execute(
        select(AgentConfig, Client)
        .join(Client, AgentConfig.client_id == Client.id)
        .order_by(desc(AgentConfig.updated_at))
    )
    rows = result.all()

    agents = []
    for config, client in rows:
        # Get call + lead counts for this client
        call_count = await db.scalar(
            select(func.count(Call.id)).where(Call.client_id == client.id)
        ) or 0
        lead_count = await db.scalar(
            select(func.count(Lead.id)).where(Lead.client_id == client.id)
        ) or 0

        agents.append({
            "id": str(config.id),
            "client_id": str(client.id),
            "client_name": client.name,
            "client_email": client.email,
            "business_name": config.business_name or client.name,
            "plan": client.plan,
            "is_active": client.is_active,
            "agent_name": config.agent_name,
            "retell_agent_id": config.retell_agent_id,
            "language": (config.supported_languages or ["en"])[0],
            "supported_languages": config.supported_languages or [],
            "greeting": config.agent_greeting,
            "system_prompt": (config.system_prompt or "")[:200],  # truncated preview
            "call_count": call_count,
            "lead_count": lead_count,
            "created_at": config.created_at.isoformat() if config.created_at else None,
            "updated_at": config.updated_at.isoformat() if config.updated_at else None,
        })

    return {"agents": agents, "total": len(agents)}


# ══════════════════════════════════════════════════════════════════════════════
#  Conversations / Sessions — all calls across all clients
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/conversations")
async def list_conversations(
    admin: dict = Depends(require_permissions("conversations.read")),
    channel: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    db: AsyncSession = Depends(get_session),
) -> dict:
    """List all conversations/calls across all clients with client info."""
    q = (
        select(Call, Client, AgentConfig)
        .join(Client, Call.client_id == Client.id)
        .outerjoin(AgentConfig, AgentConfig.client_id == Client.id)
    )
    count_q = select(func.count(Call.id))

    if channel:
        q = q.where(Call.channel == channel)
        count_q = count_q.where(Call.channel == channel)
    if status:
        q = q.where(Call.status == status)
        count_q = count_q.where(Call.status == status)

    total = await db.scalar(count_q) or 0
    q = q.order_by(desc(Call.started_at)).limit(limit).offset(offset)
    result = await db.execute(q)
    rows = result.all()

    conversations = []
    for call, client, config in rows:
        conversations.append({
            "id": str(call.id),
            "client_id": str(client.id),
            "client_name": client.name,
            "business_name": (config.business_name if config else None) or client.name,
            "caller_number": call.caller_number,
            "direction": call.direction,
            "channel": call.channel,
            "status": call.status,
            "duration_seconds": call.duration_seconds,
            "started_at": call.started_at.isoformat() if call.started_at else None,
            "ended_at": call.ended_at.isoformat() if call.ended_at else None,
            "post_call_processed": call.post_call_processed,
            "retell_call_id": call.retell_call_id,
            "elevenlabs_conversation_id": call.elevenlabs_conversation_id,
        })

    return {"conversations": conversations, "total": total}


# ══════════════════════════════════════════════════════════════════════════════
#  Platform Stats
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/stats")
async def platform_stats(
    admin: dict = Depends(require_permissions("overview.read")),
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Get platform-wide statistics for the admin dashboard."""
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=today_start.weekday())

    total_clients = await db.scalar(
        select(func.count(Client.id)).where(Client.role == "client")
    ) or 0
    active_clients = await db.scalar(
        select(func.count(Client.id)).where(
            Client.role == "client", Client.is_active == True
        )
    ) or 0
    total_calls = await db.scalar(select(func.count(Call.id))) or 0
    total_leads = await db.scalar(select(func.count(Lead.id))) or 0
    total_numbers = await db.scalar(select(func.count(PhoneNumber.id))) or 0

    # Today counts
    calls_today = await db.scalar(
        select(func.count(Call.id)).where(Call.created_at >= today_start)
    ) or 0
    leads_today = await db.scalar(
        select(func.count(Lead.id)).where(Lead.created_at >= today_start)
    ) or 0

    # This week
    calls_this_week = await db.scalar(
        select(func.count(Call.id)).where(Call.created_at >= week_start)
    ) or 0

    # Booked appointments
    booked_appointments = await db.scalar(
        select(func.count(Lead.id)).where(Lead.status == "booked")
    ) or 0

    # Leads by status
    status_result = await db.execute(
        select(Lead.status, func.count(Lead.id)).group_by(Lead.status)
    )
    leads_by_status = {str(row[0]): row[1] for row in status_result}

    # Clients per plan
    plan_result = await db.execute(
        select(Client.plan, func.count(Client.id))
        .where(Client.role == "client")
        .group_by(Client.plan)
    )
    clients_by_plan = {str(row[0]): row[1] for row in plan_result}

    # Recent leads (last 10)
    recent_leads_result = await db.execute(
        select(Lead).order_by(desc(Lead.created_at)).limit(10)
    )
    recent_leads = [
        {
            "id": str(l.id),
            "caller_name": l.caller_name,
            "caller_phone": l.caller_phone,
            "intent": l.intent,
            "urgency": l.urgency,
            "status": l.status,
            "lead_score": l.lead_score,
            "services_requested": l.services_requested,
            "created_at": l.created_at.isoformat() if l.created_at else None,
        }
        for l in recent_leads_result.scalars().all()
    ]

    # Recent calls (last 10)
    recent_calls_result = await db.execute(
        select(Call).order_by(desc(Call.started_at)).limit(10)
    )
    recent_calls = [
        {
            "id": str(c.id),
            "caller_number": c.caller_number,
            "direction": c.direction,
            "channel": c.channel,
            "status": c.status,
            "duration_seconds": c.duration_seconds,
            "started_at": c.started_at.isoformat() if c.started_at else None,
        }
        for c in recent_calls_result.scalars().all()
    ]

    # Tool call stats
    tool_calls_today = await db.scalar(
        select(func.count(ToolCallLog.id)).where(ToolCallLog.created_at >= today_start)
    ) or 0

    tool_summary_result = await db.execute(
        select(ToolCallLog.tool_name, func.count(ToolCallLog.id))
        .group_by(ToolCallLog.tool_name)
    )
    tool_summary = {str(row[0]): row[1] for row in tool_summary_result}

    recent_tool_calls_result = await db.execute(
        select(ToolCallLog).order_by(desc(ToolCallLog.created_at)).limit(10)
    )
    recent_tool_calls = [
        {
            "id": str(t.id),
            "tool_name": t.tool_name,
            "success": t.success,
            "duration_ms": t.duration_ms,
            "created_at": t.created_at.isoformat() if t.created_at else None,
        }
        for t in recent_tool_calls_result.scalars().all()
    ]

    # 7-day trend
    weekly = []
    for i in range(6, -1, -1):
        day = today_start - timedelta(days=i)
        day_end = day + timedelta(days=1)
        day_calls = await db.scalar(
            select(func.count(Call.id)).where(
                Call.created_at >= day,
                Call.created_at < day_end,
            )
        ) or 0
        day_leads = await db.scalar(
            select(func.count(Lead.id)).where(
                Lead.created_at >= day,
                Lead.created_at < day_end,
            )
        ) or 0
        weekly.append({
            "date": day.strftime("%Y-%m-%d"),
            "label": day.strftime("%a"),
            "calls": day_calls,
            "leads": day_leads,
        })

    return {
        "total_clients": total_clients,
        "active_clients": active_clients,
        "total_calls": total_calls,
        "total_leads": total_leads,
        "total_numbers": total_numbers,
        "calls_today": calls_today,
        "leads_today": leads_today,
        "calls_this_week": calls_this_week,
        "booked_appointments": booked_appointments,
        "leads_by_status": leads_by_status,
        "clients_by_plan": clients_by_plan,
        "tool_calls_today": tool_calls_today,
        "tool_summary": tool_summary,
        "recent_leads": recent_leads,
        "recent_calls": recent_calls,
        "recent_tool_calls": recent_tool_calls,
        "weekly": weekly,
    }

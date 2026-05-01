"""Shared service layer for the SaaS dashboard sync APIs."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from math import ceil
from typing import Any
from uuid import UUID

import httpx
from fastapi import HTTPException, Request
from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import _resolve_clerk_token
from app.core.config import get_settings
from app.models.models import AgentConfig, Client, Engagement, FollowUpTask
from app.services.agent_config_service import ensure_agent_config_defaults, serialize_agent_config as serialize_universal_agent_config
from app.services.agent_modes import DEFAULT_AGENT_MODE
from app.services.prompt_engine import compose_system_prompt
from app.services.saas_workspace_service import normalize_website_input

settings = get_settings()

DEFAULT_AGENT_NAME = "Omniweb AI"
DEFAULT_WELCOME_MESSAGE = (
    "Welcome! I’m here to answer questions, recommend the right solution, "
    "and help you get the most value from our services. How can I help you today?"
)
DEFAULT_AGENT_TONE = "professional"
DEFAULT_AGENT_GOALS = [
    "lead_qualification",
    "customer_support",
    "sales_assistance",
]
PUBLIC_TO_STORAGE_PLAN = {
    "starter": "starter",
    "standard": "growth",
    "business": "agency",
}
STORAGE_TO_PUBLIC_PLAN = {
    "starter": "starter",
    "growth": "standard",
    "pro": "standard",
    "standard": "standard",
    "agency": "business",
    "business": "business",
}
FEATURE_LOCK_MESSAGE = "Trial expired. Upgrade to continue."


class DashboardApiError(Exception):
    def __init__(self, status_code: int, code: str, message: str):
        self.status_code = status_code
        self.code = code
        self.message = message
        super().__init__(message)


@dataclass
class TenantContext:
    clerk_user_id: str | None
    clerk_org_id: str | None
    tenant_id: UUID
    tenant: Client
    email: str | None
    full_name: str | None
    first_name: str | None
    last_name: str | None
    onboarding_required: bool


def success_response(data: Any) -> dict[str, Any]:
    return {"success": True, "data": data}


def error_response(code: str, message: str) -> dict[str, Any]:
    return {
        "success": False,
        "error": {
            "code": code,
            "message": message,
        },
    }


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def serialize_datetime(value: datetime | None) -> str | None:
    if not value:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def normalize_public_plan(plan: str | None) -> str:
    if not plan:
        return "starter"
    return STORAGE_TO_PUBLIC_PLAN.get(plan, "starter")


def map_public_plan_to_storage(plan: str) -> str:
    if plan not in PUBLIC_TO_STORAGE_PLAN:
        raise DashboardApiError(400, "INVALID_PLAN", "Invalid plan selection")
    return PUBLIC_TO_STORAGE_PLAN[plan]


def slugify_industry(value: str | None) -> str:
    raw = (value or "general").strip().lower()
    slug = "_".join(part for part in raw.replace("-", " ").split() if part)
    return slug[:100] if slug else "general"


def is_onboarding_completed(tenant: Client) -> bool:
    return tenant.onboarding_completed_at is not None


async def get_agent_config(db: AsyncSession, tenant_id: UUID) -> AgentConfig | None:
    result = await db.execute(select(AgentConfig).where(AgentConfig.client_id == tenant_id))
    return result.scalar_one_or_none()


async def get_or_create_agent_config(db: AsyncSession, tenant: Client) -> AgentConfig:
    agent = await get_agent_config(db, tenant.id)
    if agent:
        return agent

    business_name = tenant.name or DEFAULT_AGENT_NAME
    industry_slug = slugify_industry(tenant.industry)
    _, website_url = normalize_website_input(tenant.website_url or "https://example.com")
    website_domain = website_url.replace("https://", "").rstrip("/")

    agent = AgentConfig(
        client_id=tenant.id,
        agent_name=DEFAULT_AGENT_NAME,
        agent_greeting=DEFAULT_WELCOME_MESSAGE,
        business_name=business_name[:255],
        business_type=(tenant.industry or "general")[:100],
        website_domain=website_domain[:255],
        industry=industry_slug,
        agent_mode=DEFAULT_AGENT_MODE,
        tone=DEFAULT_AGENT_TONE,
        goals=list(DEFAULT_AGENT_GOALS),
        active=True,
        custom_context=f"Website: {website_url}",
    )
    ensure_agent_config_defaults(agent, tenant)
    db.add(agent)
    await db.flush()
    return agent


def getTenantBillingStatus(tenant: Client) -> dict[str, Any]:
    now = utcnow()
    subscription_status = (tenant.subscription_status or "trialing").lower()
    trial_started_at = tenant.trial_started_at
    trial_ends_at = tenant.trial_ends_at
    subscription_started_at = tenant.subscription_started_at
    subscription_ends_at = tenant.subscription_ends_at

    if subscription_status != "active" and trial_ends_at is not None:
        trial_end = trial_ends_at if trial_ends_at.tzinfo else trial_ends_at.replace(tzinfo=timezone.utc)
        if now > trial_end:
            subscription_status = "expired"

    if subscription_status == "active" and subscription_ends_at is not None:
        subscription_end = subscription_ends_at if subscription_ends_at.tzinfo else subscription_ends_at.replace(tzinfo=timezone.utc)
        if now > subscription_end:
            subscription_status = "expired"

    if subscription_status == "active":
        end = subscription_ends_at
    else:
        end = trial_ends_at

    days_left = None
    if end is not None:
        normalized_end = end if end.tzinfo else end.replace(tzinfo=timezone.utc)
        diff = normalized_end - now
        if diff.total_seconds() <= 0:
            days_left = 0
        else:
            days_left = max(1, ceil(diff.total_seconds() / 86400))

    is_trial_active = subscription_status == "trialing" and (days_left is None or days_left > 0)
    is_expired = subscription_status in {"expired", "canceled"}
    can_access_features = subscription_status == "active" or is_trial_active

    return {
        "plan": normalize_public_plan(tenant.plan),
        "subscriptionStatus": subscription_status,
        "trialStartedAt": serialize_datetime(trial_started_at),
        "trialEndsAt": serialize_datetime(trial_ends_at),
        "subscriptionStartedAt": serialize_datetime(subscription_started_at),
        "subscriptionEndsAt": serialize_datetime(subscription_ends_at),
        "daysLeft": days_left,
        "isTrialActive": is_trial_active,
        "isExpired": is_expired,
        "canAccessFeatures": can_access_features,
    }


async def sync_billing_status(db: AsyncSession, tenant: Client) -> dict[str, Any]:
    billing = getTenantBillingStatus(tenant)
    if tenant.subscription_status != billing["subscriptionStatus"]:
        tenant.subscription_status = billing["subscriptionStatus"]
        await db.commit()
        await db.refresh(tenant)
        billing = getTenantBillingStatus(tenant)
    return billing


def require_feature_access(billing_status: dict[str, Any]) -> None:
    if not billing_status["canAccessFeatures"]:
        raise DashboardApiError(402, "PAYMENT_REQUIRED", FEATURE_LOCK_MESSAGE)


async def getCurrentTenantFromRequest(req: Request, db: AsyncSession) -> TenantContext:
    authorization = req.headers.get("Authorization", "")
    prefix = "Bearer "
    if not authorization.startswith(prefix):
        raise DashboardApiError(401, "AUTH_REQUIRED", "Authentication required")

    token = authorization[len(prefix):].strip()
    if not token:
        raise DashboardApiError(401, "AUTH_REQUIRED", "Authentication required")

    try:
        current = await _resolve_clerk_token(token)
    except HTTPException as exc:
        raise DashboardApiError(exc.status_code, "AUTH_REQUIRED", exc.detail) from exc

    tenant = await db.get(Client, UUID(current["client_id"]))
    if not tenant:
        raise DashboardApiError(404, "TENANT_NOT_FOUND", "Workspace not found")

    await sync_billing_status(db, tenant)
    return TenantContext(
        clerk_user_id=current.get("clerk_user_id"),
        clerk_org_id=current.get("clerk_org_id"),
        tenant_id=tenant.id,
        tenant=tenant,
        email=current.get("email"),
        full_name=current.get("full_name"),
        first_name=current.get("first_name"),
        last_name=current.get("last_name"),
        onboarding_required=not is_onboarding_completed(tenant),
    )


async def maybe_get_tenant_from_request(req: Request, db: AsyncSession) -> TenantContext | None:
    try:
        return await getCurrentTenantFromRequest(req, db)
    except DashboardApiError:
        return None


def build_redirect_target(tenant: Client | None, billing_status: dict[str, Any] | None) -> str:
    if tenant is None:
        return "/sign-in"
    if not is_onboarding_completed(tenant):
        return "/onboarding"
    if billing_status and billing_status["canAccessFeatures"]:
        return "/dashboard"
    return "/pricing"


def build_widget_base_url() -> str:
    return (settings.PUBLIC_WIDGET_BASE_URL or settings.APP_BASE_URL or settings.ENGINE_BASE_URL).rstrip("/")


def build_widget_embed_code(tenant_id: UUID) -> str:
    return f'<script src="{build_widget_base_url()}/widget.js" data-tenant-id="{tenant_id}" async></script>'


def serialize_tenant_profile(context: TenantContext, billing_status: dict[str, Any], agent: AgentConfig | None) -> dict[str, Any]:
    tenant = context.tenant
    website_domain = agent.website_domain if agent and getattr(agent, "website_domain", None) else None
    if not website_domain and tenant.website_url:
        try:
            website_domain, _ = normalize_website_input(tenant.website_url)
        except ValueError:
            website_domain = tenant.website_url
    industry = tenant.industry or (agent.business_type if agent else None) or (agent.industry if agent else None)
    return {
        "authenticated": True,
        "tenantId": str(tenant.id),
        "clerkUserId": context.clerk_user_id,
        "clerkOrgId": context.clerk_org_id,
        "businessName": tenant.name,
        "industry": industry,
        "websiteDomain": website_domain,
        "onboardingCompleted": is_onboarding_completed(tenant),
        "plan": billing_status["plan"],
        "subscriptionStatus": billing_status["subscriptionStatus"],
        "trialStartedAt": billing_status["trialStartedAt"],
        "trialEndsAt": billing_status["trialEndsAt"],
        "subscriptionStartedAt": billing_status["subscriptionStartedAt"],
        "subscriptionEndsAt": billing_status["subscriptionEndsAt"],
        "daysLeft": billing_status["daysLeft"],
        "canAccessFeatures": billing_status["canAccessFeatures"],
        "email": context.email,
        "fullName": context.full_name,
        "firstName": context.first_name,
        "lastName": context.last_name,
    }


def serialize_agent_config(agent: AgentConfig) -> dict[str, Any]:
    ensure_agent_config_defaults(agent)
    payload = serialize_universal_agent_config(agent)
    payload["createdAt"] = serialize_datetime(agent.created_at)
    payload["updatedAt"] = serialize_datetime(agent.updated_at)
    return payload


def parse_transcript_message_count(transcript: str | None) -> int:
    if not transcript:
        return 0
    lines = [line.strip() for line in transcript.splitlines() if line.strip()]
    return len(lines)


def serialize_engagement_summary(engagement: Engagement) -> dict[str, Any]:
    return {
        "id": str(engagement.id),
        "sessionId": engagement.session_id,
        "channel": engagement.channel,
        "sourceUrl": engagement.source_url,
        "language": engagement.language,
        "visitorName": engagement.visitor_name,
        "visitorEmail": engagement.visitor_email,
        "visitorPhone": engagement.visitor_phone,
        "leadStatus": engagement.lead_status,
        "intent": engagement.intent,
        "contactCaptured": engagement.contact_captured,
        "qualified": engagement.qualified,
        "followUpNeeded": engagement.follow_up_needed,
        "summaryShort": engagement.summary_short,
        "leadScore": engagement.lead_score,
        "agentMode": engagement.agent_mode,
        "conversionStage": engagement.conversion_stage,
        "metadata": dict(engagement.metadata or {}),
        "createdAt": serialize_datetime(engagement.created_at),
        "updatedAt": serialize_datetime(engagement.updated_at),
    }


def serialize_follow_up_task(task: FollowUpTask) -> dict[str, Any]:
    return {
        "id": str(task.id),
        "tenantId": str(task.client_id),
        "engagementId": str(task.engagement_id),
        "instruction": task.instruction,
        "channel": task.channel,
        "status": task.status,
        "scheduledFor": serialize_datetime(task.scheduled_for),
        "createdAt": serialize_datetime(task.created_at),
        "updatedAt": serialize_datetime(task.updated_at),
    }


def serialize_engagement_detail(engagement: Engagement, follow_up_tasks: list[FollowUpTask]) -> dict[str, Any]:
    payload = serialize_engagement_summary(engagement)
    payload.update(
        {
            "tenantId": str(engagement.client_id),
            "summaryFull": engagement.summary_full,
            "transcript": engagement.transcript,
            "painPoints": list(engagement.pain_points or []),
            "buyingSignals": list(engagement.buying_signals or []),
            "objections": list(engagement.objections or []),
            "recommendedNextAction": engagement.recommended_next_action,
            "ownerNotes": engagement.owner_notes,
            "resolved": engagement.resolved,
            "followUpTasks": [serialize_follow_up_task(task) for task in follow_up_tasks],
        }
    )
    return payload


def apply_engagement_filters(query: Select[Any], tenant_id: UUID, params: dict[str, Any]) -> Select[Any]:
    query = query.where(Engagement.client_id == tenant_id)

    if params.get("dateFrom"):
        query = query.where(Engagement.created_at >= params["dateFrom"])
    if params.get("dateTo"):
        query = query.where(Engagement.created_at <= params["dateTo"])
    if params.get("channel"):
        query = query.where(Engagement.channel == params["channel"])
    if params.get("leadStatus"):
        query = query.where(Engagement.lead_status == params["leadStatus"])
    if params.get("intent"):
        query = query.where(Engagement.intent == params["intent"])
    if params.get("followUpNeeded") is not None:
        query = query.where(Engagement.follow_up_needed == params["followUpNeeded"])
    if params.get("contactCaptured") is not None:
        query = query.where(Engagement.contact_captured == params["contactCaptured"])
    if params.get("search"):
        search = f"%{params['search']}%"
        query = query.where(
            or_(
                Engagement.session_id.ilike(search),
                Engagement.visitor_name.ilike(search),
                Engagement.visitor_email.ilike(search),
                Engagement.visitor_phone.ilike(search),
                Engagement.summary_short.ilike(search),
                Engagement.summary_full.ilike(search),
            )
        )
    return query


def parse_bool_filter(value: str | None) -> bool | None:
    if value is None or value == "":
        return None
    if value.lower() == "true":
        return True
    if value.lower() == "false":
        return False
    raise DashboardApiError(400, "INVALID_FILTER", f"Invalid boolean filter value: {value}")


def parse_filter_params(req: Request) -> dict[str, Any]:
    query = req.query_params
    try:
        page = int(query.get("page", "1"))
        page_size = int(query.get("pageSize", "20"))
    except ValueError as exc:
        raise DashboardApiError(400, "INVALID_PAGINATION", "Pagination values must be integers") from exc
    if page < 1 or page_size < 1 or page_size > 100:
        raise DashboardApiError(400, "INVALID_PAGINATION", "Invalid pagination values")

    date_from = query.get("dateFrom")
    date_to = query.get("dateTo")
    try:
        parsed_date_from = datetime.fromisoformat(date_from.replace("Z", "+00:00")) if date_from else None
        parsed_date_to = datetime.fromisoformat(date_to.replace("Z", "+00:00")) if date_to else None
    except ValueError as exc:
        raise DashboardApiError(400, "INVALID_FILTER", "dateFrom/dateTo must be valid ISO dates") from exc
    if parsed_date_to is not None and parsed_date_to.tzinfo is None:
        parsed_date_to = parsed_date_to.replace(tzinfo=timezone.utc)
    if parsed_date_to is not None:
        parsed_date_to = parsed_date_to.replace(hour=23, minute=59, second=59, microsecond=999999)
    if parsed_date_from is not None and parsed_date_from.tzinfo is None:
        parsed_date_from = parsed_date_from.replace(tzinfo=timezone.utc)

    return {
        "page": page,
        "pageSize": page_size,
        "dateFrom": parsed_date_from,
        "dateTo": parsed_date_to,
        "channel": query.get("channel") or None,
        "leadStatus": query.get("leadStatus") or None,
        "intent": query.get("intent") or None,
        "followUpNeeded": parse_bool_filter(query.get("followUpNeeded")),
        "contactCaptured": parse_bool_filter(query.get("contactCaptured")),
        "search": query.get("search") or None,
    }


def build_mock_summary_payload(transcript: str) -> dict[str, Any]:
    lower = transcript.lower()
    summary_short = transcript.strip().replace("\n", " ")
    if len(summary_short) > 220:
        summary_short = f"{summary_short[:217].rstrip()}..."

    intent = None
    if any(token in lower for token in ["price", "pricing", "cost", "plan"]):
        intent = "pricing_question"
    elif any(token in lower for token in ["book", "appointment", "schedule", "quote"]):
        intent = "booking_request_quote"
    elif any(token in lower for token in ["support", "help", "issue", "problem"]):
        intent = "support_request"
    elif any(token in lower for token in ["service", "implementation", "setup"]):
        intent = "service_inquiry"
    else:
        intent = "other"

    pain_points = []
    if "after hours" in lower:
        pain_points.append("Needs coverage after hours")
    if "manual" in lower:
        pain_points.append("Current workflow is too manual")
    if "slow" in lower or "delay" in lower:
        pain_points.append("Response time is a concern")

    buying_signals = []
    if "demo" in lower or "call me" in lower:
        buying_signals.append("Requested a next step")
    if "@" in transcript:
        buying_signals.append("Shared an email address")
    if any(char.isdigit() for char in transcript):
        buying_signals.append("Shared numeric contact details")

    objections = []
    if "budget" in lower or "expensive" in lower:
        objections.append("Pricing sensitivity")
    if "later" in lower or "not ready" in lower:
        objections.append("Timing hesitation")

    lead_score = min(100, 40 + (len(buying_signals) * 20) + (len(pain_points) * 8))
    follow_up_needed = len(buying_signals) > 0 or intent in {"pricing_question", "booking_request_quote"}
    summary_full = (
        f"Intent: {intent.replace('_', ' ')}. "
        f"Pain points: {', '.join(pain_points) if pain_points else 'none noted'}. "
        f"Buying signals: {', '.join(buying_signals) if buying_signals else 'none noted'}. "
        f"Objections: {', '.join(objections) if objections else 'none noted'}."
    )
    recommended = (
        "Follow up with plan guidance and a clear next step."
        if follow_up_needed
        else "Monitor this conversation and capture contact details on the next high-intent interaction."
    )
    return {
        "summaryShort": summary_short,
        "summaryFull": summary_full,
        "intent": intent,
        "leadScore": lead_score,
        "painPoints": pain_points,
        "buyingSignals": buying_signals,
        "objections": objections,
        "recommendedNextAction": recommended,
        "followUpNeeded": follow_up_needed,
    }


async def summarize_transcript_server_side(transcript: str) -> dict[str, Any]:
    if not transcript.strip():
        raise DashboardApiError(400, "TRANSCRIPT_MISSING", "Transcript is required to summarize this engagement")

    if not settings.DEEPGRAM_API_KEY:
        return build_mock_summary_payload(transcript)

    endpoint = "https://api.deepgram.com/v1/read?language=en&summarize=true&topics=true&intents=true"
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                endpoint,
                headers={
                    "Authorization": f"Token {settings.DEEPGRAM_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={"text": transcript},
            )
            response.raise_for_status()
            payload = response.json()
    except Exception:
        return build_mock_summary_payload(transcript)

    summary_short = (
        payload.get("results", {}).get("summary", {}).get("text")
        or payload.get("results", {}).get("summary", {}).get("short")
        or build_mock_summary_payload(transcript)["summaryShort"]
    )
    top_intents = payload.get("results", {}).get("intents", {}).get("intents", []) or []
    intent = top_intents[0].get("intent") if top_intents else build_mock_summary_payload(transcript)["intent"]
    topics = payload.get("results", {}).get("topics", {}).get("topics", []) or []
    buying_signals = [topic.get("topic") for topic in topics[:3] if topic.get("topic")]
    mock = build_mock_summary_payload(transcript)
    return {
        "summaryShort": summary_short,
        "summaryFull": f"{summary_short} Topics: {', '.join(buying_signals) if buying_signals else 'none detected' }.",
        "intent": intent,
        "leadScore": mock["leadScore"],
        "painPoints": mock["painPoints"],
        "buyingSignals": buying_signals or mock["buyingSignals"],
        "objections": mock["objections"],
        "recommendedNextAction": mock["recommendedNextAction"],
        "followUpNeeded": mock["followUpNeeded"],
    }
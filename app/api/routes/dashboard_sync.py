"""Dashboard sync endpoints for the new SaaS frontend."""
from __future__ import annotations

from datetime import datetime, timedelta
from json import JSONDecodeError

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.models.models import Engagement, FollowUpTask
from app.services.dashboard_sync_service import (
    DEFAULT_AGENT_GOALS,
    DEFAULT_AGENT_NAME,
    DEFAULT_AGENT_TONE,
    DEFAULT_WELCOME_MESSAGE,
    DashboardApiError,
    build_redirect_target,
    build_widget_embed_code,
    getCurrentTenantFromRequest,
    get_or_create_agent_config,
    map_public_plan_to_storage,
    maybe_get_tenant_from_request,
    normalize_website_input,
    require_feature_access,
    serialize_agent_config,
    serialize_datetime,
    serialize_follow_up_task,
    serialize_tenant_profile,
    success_response,
    sync_billing_status,
    utcnow,
)

router = APIRouter(tags=["dashboard-sync"])


class OnboardingCompleteIn(BaseModel):
    businessName: str = Field(..., min_length=2, max_length=255)
    industry: str = Field(..., min_length=2, max_length=100)
    websiteDomain: str = Field(..., min_length=3, max_length=2048)


class ProfilePatchIn(BaseModel):
    businessName: str = Field(..., min_length=2, max_length=255)
    industry: str = Field(..., min_length=2, max_length=100)
    websiteDomain: str = Field(..., min_length=3, max_length=2048)


class MockUpgradeIn(BaseModel):
    plan: str


class AgentConfigPatchIn(BaseModel):
    agentName: str | None = Field(None, min_length=2, max_length=100)
    welcomeMessage: str | None = Field(None, min_length=5, max_length=4000)
    tone: str | None = Field(None, min_length=3, max_length=30)
    goals: list[str] | None = Field(None, max_length=25)
    active: bool | None = None


class FollowUpCreateIn(BaseModel):
    engagementId: str
    instruction: str = Field(..., min_length=5, max_length=5000)
    channel: str = Field(..., min_length=2, max_length=40)
    scheduledFor: str | None = None


def _parse_body(model: type[BaseModel], payload: dict) -> BaseModel:
    try:
        return model.model_validate(payload)
    except ValidationError as exc:
        raise DashboardApiError(400, "VALIDATION_ERROR", exc.errors()[0]["msg"]) from exc


async def _read_json(request: Request) -> dict:
    try:
        payload = await request.json()
    except JSONDecodeError as exc:
        raise DashboardApiError(400, "INVALID_JSON", "Request body must be valid JSON") from exc
    if not isinstance(payload, dict):
        raise DashboardApiError(400, "INVALID_JSON", "Request body must be a JSON object")
    return payload


@router.get("/me/status")
async def get_me_status(request: Request, db: AsyncSession = Depends(get_session)) -> dict:
    context = await maybe_get_tenant_from_request(request, db)
    if context is None:
        return success_response(
            {
                "authenticated": False,
                "onboardingCompleted": False,
                "tenantId": None,
                "businessName": None,
                "industry": None,
                "websiteDomain": None,
                "plan": None,
                "subscriptionStatus": None,
                "trialStartedAt": None,
                "trialEndsAt": None,
                "daysLeft": None,
                "canAccessFeatures": False,
                "redirectTarget": "/sign-in",
            }
        )

    agent = await get_or_create_agent_config(db, context.tenant)
    billing_status = await sync_billing_status(db, context.tenant)
    payload = serialize_tenant_profile(context, billing_status, agent)
    payload["redirectTarget"] = build_redirect_target(context.tenant, billing_status)
    return success_response(payload)


@router.post("/onboarding/complete")
async def complete_onboarding(request: Request, db: AsyncSession = Depends(get_session)) -> dict:
    context = await getCurrentTenantFromRequest(request, db)
    body = _parse_body(OnboardingCompleteIn, await _read_json(request))

    website_domain, website_url = normalize_website_input(body.websiteDomain)
    tenant = context.tenant
    tenant.name = body.businessName.strip()
    tenant.industry = body.industry.strip()
    tenant.website_url = website_url
    if context.clerk_org_id:
        tenant.clerk_org_id = context.clerk_org_id

    now = utcnow()
    tenant.onboarding_completed_at = now
    if tenant.trial_started_at is None:
        tenant.trial_started_at = now
        tenant.trial_ends_at = now + timedelta(days=7)
        tenant.subscription_status = "trialing"
        tenant.plan = map_public_plan_to_storage("starter")

    agent = await get_or_create_agent_config(db, tenant)
    agent.agent_name = DEFAULT_AGENT_NAME
    agent.agent_greeting = DEFAULT_WELCOME_MESSAGE
    agent.business_name = tenant.name[:255]
    agent.business_type = tenant.industry[:100]
    agent.website_domain = website_domain[:255]
    agent.industry = body.industry.strip().lower().replace(" ", "_")[:100]
    agent.tone = DEFAULT_AGENT_TONE
    agent.goals = list(DEFAULT_AGENT_GOALS)
    agent.active = True

    await db.commit()
    await db.refresh(tenant)
    await db.refresh(agent)

    billing_status = await sync_billing_status(db, tenant)
    return success_response(
        {
            "tenant": serialize_tenant_profile(context, billing_status, agent),
            "billingStatus": billing_status,
            "agentConfig": serialize_agent_config(agent),
        }
    )


@router.get("/profile")
async def get_profile(request: Request, db: AsyncSession = Depends(get_session)) -> dict:
    context = await getCurrentTenantFromRequest(request, db)
    agent = await get_or_create_agent_config(db, context.tenant)
    billing_status = await sync_billing_status(db, context.tenant)
    profile = serialize_tenant_profile(context, billing_status, agent)
    return success_response(
        {
            "email": context.email,
            "fullName": context.full_name,
            "firstName": context.first_name,
            "lastName": context.last_name,
            "businessName": profile["businessName"],
            "industry": profile["industry"],
            "websiteDomain": profile["websiteDomain"],
            "plan": profile["plan"],
            "subscriptionStatus": profile["subscriptionStatus"],
            "daysLeft": profile["daysLeft"],
        }
    )


@router.patch("/profile")
async def patch_profile(request: Request, db: AsyncSession = Depends(get_session)) -> dict:
    context = await getCurrentTenantFromRequest(request, db)
    body = _parse_body(ProfilePatchIn, await _read_json(request))

    website_domain, website_url = normalize_website_input(body.websiteDomain)
    tenant = context.tenant
    tenant.name = body.businessName.strip()
    tenant.industry = body.industry.strip()
    tenant.website_url = website_url

    agent = await get_or_create_agent_config(db, tenant)
    agent.business_name = tenant.name[:255]
    agent.business_type = tenant.industry[:100]
    agent.website_domain = website_domain[:255]
    agent.industry = body.industry.strip().lower().replace(" ", "_")[:100]

    await db.commit()
    await db.refresh(tenant)
    await db.refresh(agent)

    billing_status = await sync_billing_status(db, tenant)
    return success_response(serialize_tenant_profile(context, billing_status, agent))


@router.get("/billing/status")
async def get_billing_status(request: Request, db: AsyncSession = Depends(get_session)) -> dict:
    context = await getCurrentTenantFromRequest(request, db)
    billing_status = await sync_billing_status(db, context.tenant)
    billing_status["stripeReady"] = False
    return success_response(billing_status)


@router.post("/billing/mock-upgrade")
async def post_mock_upgrade(request: Request, db: AsyncSession = Depends(get_session)) -> dict:
    context = await getCurrentTenantFromRequest(request, db)
    body = _parse_body(MockUpgradeIn, await _read_json(request))

    tenant = context.tenant
    tenant.plan = map_public_plan_to_storage(body.plan)
    tenant.subscription_status = "active"
    tenant.subscription_started_at = utcnow()
    tenant.subscription_ends_at = tenant.subscription_started_at + timedelta(days=30)
    await db.commit()
    await db.refresh(tenant)

    billing_status = await sync_billing_status(db, tenant)
    billing_status["stripeReady"] = False
    return success_response(billing_status)


@router.get("/agent/config")
async def get_agent_config_route(request: Request, db: AsyncSession = Depends(get_session)) -> dict:
    context = await getCurrentTenantFromRequest(request, db)
    billing_status = await sync_billing_status(db, context.tenant)
    require_feature_access(billing_status)
    agent = await get_or_create_agent_config(db, context.tenant)
    await db.commit()
    await db.refresh(agent)
    return success_response(serialize_agent_config(agent))


@router.patch("/agent/config")
async def patch_agent_config_route(request: Request, db: AsyncSession = Depends(get_session)) -> dict:
    context = await getCurrentTenantFromRequest(request, db)
    billing_status = await sync_billing_status(db, context.tenant)
    require_feature_access(billing_status)
    body = _parse_body(AgentConfigPatchIn, await _read_json(request))

    agent = await get_or_create_agent_config(db, context.tenant)
    if body.agentName is not None:
        agent.agent_name = body.agentName.strip()
    if body.welcomeMessage is not None:
        agent.agent_greeting = body.welcomeMessage.strip()
    if body.tone is not None:
        agent.tone = body.tone.strip()
    if body.goals is not None:
        agent.goals = [goal.strip() for goal in body.goals if goal.strip()][:25]
    if body.active is not None:
        agent.active = body.active

    await db.commit()
    await db.refresh(agent)
    return success_response(serialize_agent_config(agent))


@router.get("/widget/embed-code")
async def get_widget_embed_code_route(request: Request, db: AsyncSession = Depends(get_session)) -> dict:
    context = await getCurrentTenantFromRequest(request, db)
    billing_status = await sync_billing_status(db, context.tenant)
    require_feature_access(billing_status)
    agent = await get_or_create_agent_config(db, context.tenant)
    website_domain = agent.website_domain
    return success_response(
        {
            "tenantId": str(context.tenant_id),
            "websiteDomain": website_domain,
            "embedCode": build_widget_embed_code(context.tenant_id),
        }
    )


@router.get("/follow-ups")
async def get_follow_ups(request: Request, db: AsyncSession = Depends(get_session)) -> dict:
    context = await getCurrentTenantFromRequest(request, db)
    billing_status = await sync_billing_status(db, context.tenant)
    require_feature_access(billing_status)
    result = await db.execute(
        select(FollowUpTask).where(FollowUpTask.client_id == context.tenant_id).order_by(FollowUpTask.created_at.desc())
    )
    tasks = result.scalars().all()
    return success_response({"items": [serialize_follow_up_task(task) for task in tasks]})


@router.post("/follow-ups")
async def create_follow_up(request: Request, db: AsyncSession = Depends(get_session)) -> dict:
    context = await getCurrentTenantFromRequest(request, db)
    billing_status = await sync_billing_status(db, context.tenant)
    require_feature_access(billing_status)
    body = _parse_body(FollowUpCreateIn, await _read_json(request))

    engagement = await db.get(Engagement, body.engagementId)
    if not engagement or engagement.client_id != context.tenant_id:
        raise DashboardApiError(404, "ENGAGEMENT_NOT_FOUND", "Engagement not found")

    scheduled_for = None
    if body.scheduledFor:
        try:
            scheduled_for = datetime.fromisoformat(body.scheduledFor.replace("Z", "+00:00"))
        except ValueError as exc:
            raise DashboardApiError(400, "INVALID_DATETIME", "scheduledFor must be a valid ISO datetime") from exc

    task = FollowUpTask(
        client_id=context.tenant_id,
        engagement_id=engagement.id,
        instruction=body.instruction.strip(),
        channel=body.channel.strip(),
        status="pending",
        scheduled_for=scheduled_for,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return success_response(serialize_follow_up_task(task))

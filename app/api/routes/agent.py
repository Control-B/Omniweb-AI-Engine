from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.services.agent_config_service import (
    apply_agent_config_updates,
    apply_agent_template,
    build_prompt_for_payload,
    ensure_agent_config_defaults,
    list_templates_payload,
    run_agent_test,
    serialize_agent_config,
)
from app.services.dashboard_sync_service import (
    DashboardApiError,
    getCurrentTenantFromRequest,
    get_or_create_agent_config,
    require_feature_access,
    sync_billing_status,
)

router = APIRouter(prefix="/agent", tags=["agent"])


class AgentConfigPatchIn(BaseModel):
    agentName: str | None = Field(None, min_length=2, max_length=100)
    welcomeMessage: str | None = Field(None, min_length=5, max_length=4000)
    tone: str | None = Field(None, min_length=3, max_length=30)
    businessName: str | None = Field(None, min_length=2, max_length=255)
    businessType: str | None = Field(None, min_length=2, max_length=100)
    industry: str | None = Field(None, min_length=2, max_length=100)
    websiteDomain: str | None = Field(None, min_length=3, max_length=255)
    bookingUrl: str | None = Field(None, max_length=500)
    agentMode: str | None = Field(None, min_length=2, max_length=50)
    goals: list[str] | None = Field(None, max_length=25)
    enabledChannels: list[str] | None = Field(None, max_length=10)
    leadCaptureFields: list[str] | None = Field(None, max_length=20)
    enabledFeatures: dict[str, bool] | None = None
    qualificationRules: dict[str, Any] | None = None
    customInstructions: str | None = Field(None, max_length=6000)
    active: bool | None = None


class ApplyTemplateIn(BaseModel):
    templateId: str = Field(..., min_length=2, max_length=120)


class BuildPromptIn(AgentConfigPatchIn):
    channel: str | None = Field(None, min_length=2, max_length=40)


class AgentTestIn(AgentConfigPatchIn):
    channel: str | None = Field(None, min_length=2, max_length=40)
    message: str = Field(..., min_length=1, max_length=4000)


async def _get_tenant_agent(request: Request, db: AsyncSession) -> tuple[Any, Any]:
    context = await getCurrentTenantFromRequest(request, db)
    billing_status = await sync_billing_status(db, context.tenant)
    require_feature_access(billing_status)
    agent = await get_or_create_agent_config(db, context.tenant)
    ensure_agent_config_defaults(agent, context.tenant)
    return context, agent


@router.get("/config")
async def get_agent_config_route(request: Request, db: AsyncSession = Depends(get_session)) -> dict:
    _, agent = await _get_tenant_agent(request, db)
    await db.commit()
    await db.refresh(agent)
    return serialize_agent_config(agent)


@router.patch("/config")
async def patch_agent_config_route(
    request: Request,
    body: AgentConfigPatchIn,
    db: AsyncSession = Depends(get_session),
) -> dict:
    context, agent = await _get_tenant_agent(request, db)
    apply_agent_config_updates(agent, body.model_dump(exclude_none=True))
    ensure_agent_config_defaults(agent, context.tenant)
    await db.commit()
    await db.refresh(agent)
    return serialize_agent_config(agent)


@router.get("/templates")
async def get_agent_templates_route(
    request: Request,
    agentMode: str | None = Query(None),
    db: AsyncSession = Depends(get_session),
) -> dict:
    await _get_tenant_agent(request, db)
    return {"templates": list_templates_payload(agentMode)}


@router.post("/apply-template")
async def apply_agent_template_route(
    request: Request,
    body: ApplyTemplateIn,
    db: AsyncSession = Depends(get_session),
) -> dict:
    context, agent = await _get_tenant_agent(request, db)
    try:
        template = apply_agent_template(agent, body.templateId)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    ensure_agent_config_defaults(agent, context.tenant)
    await db.commit()
    await db.refresh(agent)
    return {
        "template": template,
        "config": serialize_agent_config(agent),
    }


@router.post("/build-prompt")
async def build_agent_prompt_route(
    request: Request,
    body: BuildPromptIn,
    db: AsyncSession = Depends(get_session),
) -> dict:
    context, agent = await _get_tenant_agent(request, db)
    base = serialize_agent_config(agent, include_prompt=False)
    payload = {**base, **body.model_dump(exclude_none=True)}
    payload.setdefault("businessName", context.tenant.name)
    payload.setdefault("businessType", context.tenant.industry)
    return build_prompt_for_payload(payload)


@router.post("/test")
async def test_agent_route(
    request: Request,
    body: AgentTestIn,
    db: AsyncSession = Depends(get_session),
) -> dict:
    context, agent = await _get_tenant_agent(request, db)
    base = serialize_agent_config(agent, include_prompt=False)
    payload = {**base, **body.model_dump(exclude_none=True)}
    payload.setdefault("businessName", context.tenant.name)
    payload.setdefault("businessType", context.tenant.industry)
    return run_agent_test(payload, body.message)

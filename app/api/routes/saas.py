"""SaaS onboarding, workspace, widget configuration, and public widget API."""
from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.core.auth import get_current_client, is_internal_staff_role
from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.models import AgentConfig, Client
from app.services.prompt_engine import compose_system_prompt
from app.services.saas_workspace_service import (
    ALLOWED_PRIMARY_GOALS,
    apply_saas_onboarding,
    calculate_trial_remaining,
    client_subscription_allows_widget,
    default_setup_progress,
    get_agent_config_for_client,
    is_platform_domain,
    normalize_public_domain,
    normalize_website_input,
    resolve_client_by_widget_key,
)

logger = get_logger(__name__)
settings = get_settings()

router = APIRouter(tags=["saas"])
public_router = APIRouter(prefix="/public/widget", tags=["public-widget"])


class OnboardingIn(BaseModel):
    business_name: str = Field(..., min_length=1, max_length=255)
    industry: str = Field(..., min_length=1, max_length=100)
    website: str = Field(..., min_length=1, max_length=2048)
    primary_goal: str


class WidgetConfigPatch(BaseModel):
    agent_name: str | None = Field(None, max_length=100)
    welcome_message: str | None = None
    business_instructions: str | None = None
    tone: str | None = Field(None, max_length=30)
    lead_questions: list[str] | None = None
    call_to_action: str | None = Field(None, max_length=200)
    theme_color: str | None = Field(None, max_length=32)
    position: Literal["bottom-right", "bottom-left"] | None = None
    knowledge_source_url: str | None = Field(None, max_length=2048)
    widget_status: Literal["draft", "active", "disabled"] | None = None


class PublicChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(..., max_length=12000)


class PublicChatIn(BaseModel):
    widget_key: str = Field(..., min_length=8, max_length=128)
    messages: list[PublicChatMessage] = Field(..., max_length=50)


def _engine_base() -> str:
    return (settings.ENGINE_BASE_URL or settings.APP_BASE_URL).rstrip("/")


def _widget_snippet(base_url: str, public_widget_key: str) -> str:
    return (
        f'<script src="{base_url}/widget.js" '
        f'data-tenant-id="{public_widget_key}" async></script>'
    )


async def _get_tenant_client(db: AsyncSession, current: dict) -> Client:
    if is_internal_staff_role(current.get("role")):
        raise HTTPException(403, "Use a tenant account for this endpoint")
    client = await db.get(Client, UUID(current["client_id"]))
    if not client:
        raise HTTPException(404, "Workspace not found")
    return client


def _saas_ui(agent: AgentConfig) -> dict[str, Any]:
    wc = agent.widget_config or {}
    ui = wc.get("saas_ui") if isinstance(wc, dict) else {}
    return ui if isinstance(ui, dict) else {}


@router.post("/onboarding")
async def post_onboarding(
    body: OnboardingIn,
    current: dict = Depends(get_current_client),
    db: AsyncSession = Depends(get_session),
) -> dict:
    if body.primary_goal not in ALLOWED_PRIMARY_GOALS:
        raise HTTPException(400, "Invalid primary_goal")
    try:
        normalize_website_input(body.website)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e

    client = await _get_tenant_client(db, current)
    try:
        client, agent = await apply_saas_onboarding(
            db,
            client,
            business_name=body.business_name.strip(),
            industry=body.industry.strip(),
            website_input=body.website.strip(),
            primary_goal=body.primary_goal,
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e

    return await build_workspace_payload(db, client, agent)


async def build_workspace_payload(
    db: AsyncSession,
    client: Client,
    agent: AgentConfig | None = None,
) -> dict:
    if agent is None:
        agent = await get_agent_config_for_client(db, client.id)
    trial = calculate_trial_remaining(client.trial_ends_at)
    ui = _saas_ui(agent) if agent else {}
    progress = dict(default_setup_progress())
    progress.update(client.setup_progress or {})
    return {
        "workspace": {
            "client_id": str(client.id),
            "business_name": agent.business_name if agent else client.name,
            "industry": agent.industry if agent else None,
            "website_url": client.website_url,
            "website_domain": agent.website_domain if agent else None,
            "primary_goal": client.primary_goal,
            "onboarding_completed_at": client.onboarding_completed_at.isoformat()
            if client.onboarding_completed_at
            else None,
        },
        "widget": {
            "public_widget_key": client.public_widget_key,
            "status": client.saas_widget_status,
            "agent_name": agent.agent_name if agent else None,
            "welcome_message": agent.agent_greeting if agent else None,
            "theme_color": ui.get("theme_color") or "#6366f1",
            "position": ui.get("position") or "bottom-right",
        },
        "widget_config": {
            "business_instructions": (agent.custom_context if agent else None) or "",
            "tone": ui.get("tone") or "professional",
            "lead_questions": ui.get("lead_questions") or [],
            "call_to_action": ui.get("call_to_action") or "Chat with us",
            "knowledge_source_url": ui.get("knowledge_source_url") or "",
        },
        "trial": {
            "subscription_status": client.subscription_status,
            "trial_started_at": client.trial_started_at.isoformat() if client.trial_started_at else None,
            "trial_ends_at": client.trial_ends_at.isoformat() if client.trial_ends_at else None,
            "remaining": trial,
        },
        "setup_progress": progress,
        "needs_onboarding": client.onboarding_completed_at is None,
    }


@router.get("/me/workspace")
async def get_me_workspace(
    current: dict = Depends(get_current_client),
    db: AsyncSession = Depends(get_session),
) -> dict:
    if is_internal_staff_role(current.get("role")):
        raise HTTPException(403, "Tenant workspace only")
    client = await _get_tenant_client(db, current)
    agent = await get_agent_config_for_client(db, client.id)
    return await build_workspace_payload(db, client, agent)


@router.patch("/widget/config")
async def patch_widget_config(
    body: WidgetConfigPatch,
    current: dict = Depends(get_current_client),
    db: AsyncSession = Depends(get_session),
) -> dict:
    client = await _get_tenant_client(db, current)
    agent = await get_agent_config_for_client(db, client.id)
    if not agent:
        raise HTTPException(400, "Complete onboarding first")

    if body.widget_status is not None:
        client.saas_widget_status = body.widget_status

    if body.agent_name is not None:
        agent.agent_name = body.agent_name.strip() or agent.agent_name
    if body.welcome_message is not None:
        agent.agent_greeting = body.welcome_message

    if body.business_instructions is not None:
        agent.custom_context = body.business_instructions
        agent.system_prompt = compose_system_prompt(
            agent_name=agent.agent_name,
            business_name=agent.business_name,
            industry_slug=agent.industry,
            agent_mode=agent.agent_mode,
            business_type=agent.business_type,
            custom_context=agent.custom_context,
        )

    wc = dict(agent.widget_config or {})
    ui = dict(wc.get("saas_ui") or {})
    if body.tone is not None:
        ui["tone"] = body.tone
    if body.lead_questions is not None:
        ui["lead_questions"] = body.lead_questions[:20]
    if body.call_to_action is not None:
        ui["call_to_action"] = body.call_to_action
    if body.theme_color is not None:
        ui["theme_color"] = body.theme_color
    if body.position is not None:
        ui["position"] = body.position
    if body.knowledge_source_url is not None:
        ui["knowledge_source_url"] = body.knowledge_source_url.strip()
    wc["saas_ui"] = ui
    agent.widget_config = wc

    progress = dict(default_setup_progress())
    progress.update(client.setup_progress or {})
    progress["ai_agent_configured"] = True
    client.setup_progress = progress

    await db.commit()
    await db.refresh(agent)
    await db.refresh(client)
    return await build_workspace_payload(db, client, agent)


@router.get("/widget/embed-code")
async def get_widget_embed_code(
    current: dict = Depends(get_current_client),
    db: AsyncSession = Depends(get_session),
) -> dict:
    client = await _get_tenant_client(db, current)
    if not client.public_widget_key:
        raise HTTPException(400, "Complete onboarding to receive an embed key")
    base = _engine_base()
    snippet = _widget_snippet(base, client.public_widget_key)
    return {
        "public_widget_key": client.public_widget_key,
        "embed_snippet": snippet,
        "script_url": f"{base}/widget.js",
        "gtm_instructions": [
            "Create a new Google Tag Manager Custom HTML tag.",
            "Paste the Omniweb script snippet into the tag.",
            "Set the trigger to All Pages, then submit and publish.",
        ],
    }


@router.post("/widget/test")
async def post_widget_test(
    current: dict = Depends(get_current_client),
    db: AsyncSession = Depends(get_session),
) -> dict:
    client = await _get_tenant_client(db, current)
    if not client.public_widget_key:
        raise HTTPException(400, "Complete onboarding first")
    progress = dict(default_setup_progress())
    progress.update(client.setup_progress or {})
    progress["widget_tested"] = True
    client.setup_progress = progress
    await db.commit()
    await db.refresh(client)
    platform = settings.PLATFORM_URL.rstrip("/")
    agent = await get_agent_config_for_client(db, client.id)
    return {
        "ok": True,
        "preview_url": f"{platform}/widget/{client.id}",
        "message": "Open the preview URL or use the in-dashboard test page.",
        "workspace": await build_workspace_payload(db, client, agent),
    }


class SetupProgressPatch(BaseModel):
    embed_installed: bool | None = None
    subscription_activated: bool | None = None


@router.patch("/me/workspace/setup-progress")
async def patch_setup_progress(
    body: SetupProgressPatch,
    current: dict = Depends(get_current_client),
    db: AsyncSession = Depends(get_session),
) -> dict:
    client = await _get_tenant_client(db, current)
    progress = dict(default_setup_progress())
    progress.update(client.setup_progress or {})
    if body.embed_installed is not None:
        progress["embed_installed"] = body.embed_installed
    if body.subscription_activated is not None:
        progress["subscription_activated"] = body.subscription_activated
    client.setup_progress = progress
    await db.commit()
    await db.refresh(client)
    agent = await get_agent_config_for_client(db, client.id)
    return await build_workspace_payload(db, client, agent)


@public_router.get("/bootstrap")
async def public_widget_bootstrap(
    widget_key: str,
    request: Request,
    db: AsyncSession = Depends(get_session),
) -> dict:
    client = await resolve_client_by_widget_key(db, widget_key.strip())
    if not client:
        raise HTTPException(404, "Widget not found")

    request_domain = normalize_public_domain(
        request.headers.get("origin") or request.headers.get("referer")
    )
    platform_request = is_platform_domain(request_domain)
    allowed = client_subscription_allows_widget(client)
    active = platform_request or (client.saas_widget_status == "active" and allowed)

    agent = await get_agent_config_for_client(db, client.id)
    ui = _saas_ui(agent) if agent else {}

    if not active:
        reason = "trial_ended"
        if client.saas_widget_status != "active":
            reason = "widget_disabled"
        return {
            "active": False,
            "inactive_reason": reason,
            "message": "Your Omniweb trial has ended. Upgrade to reactivate your AI agent.",
        }

    return {
        "active": True,
        "inactive_reason": None,
        "agent_name": agent.agent_name if agent else "Assistant",
        "welcome_message": agent.agent_greeting if agent else "",
        "theme_color": ui.get("theme_color") or "#6366f1",
        "position": ui.get("position") or "bottom-right",
        "call_to_action": ui.get("call_to_action") or "Chat with us",
        "chat_path": "/api/public/widget/chat",
    }


@public_router.post("/chat")
async def public_widget_chat(
    body: PublicChatIn,
    request: Request,
    db: AsyncSession = Depends(get_session),
) -> dict:
    # TODO: Redis-backed rate limit per widget_key + IP for production scale.
    if not settings.openai_configured:
        raise HTTPException(503, "AI chat is temporarily unavailable")

    client = await resolve_client_by_widget_key(db, body.widget_key.strip())
    if not client:
        raise HTTPException(403, "Invalid widget key")

    request_domain = normalize_public_domain(
        request.headers.get("origin") or request.headers.get("referer")
    )
    if (
        not is_platform_domain(request_domain)
        and (client.saas_widget_status != "active" or not client_subscription_allows_widget(client))
    ):
        raise HTTPException(403, "Widget is not active")

    agent = await get_agent_config_for_client(db, client.id)
    if not agent:
        raise HTTPException(404, "Agent not configured")

    system_prompt = agent.system_prompt or ""
    from openai import AsyncOpenAI

    oai = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    msgs: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
    for m in body.messages[-24:]:
        msgs.append({"role": m.role, "content": m.content[:12000]})

    try:
        response = await oai.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=msgs,
            max_tokens=500,
            temperature=0.7,
        )
        text = (response.choices[0].message.content or "").strip()
    except Exception as e:
        logger.error(f"public_widget_chat OpenAI error: {e}")
        raise HTTPException(503, "Could not generate a reply") from e

    return {"role": "assistant", "content": text or "Thanks — how else can I help?"}

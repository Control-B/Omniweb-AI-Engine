from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.core.auth import get_current_client, is_internal_staff_role
from app.models.models import Client
from app.services.omniweb_brain_service import BrainRequest, OmniwebBrainService
from app.services.saas_workspace_service import get_agent_config_for_client
from app.services.widget_service import (
    SHOPIFY_WIDGET_SCRIPT_PATH,
    VALID_WIDGET_POSITIONS,
    WIDGET_SCRIPT_PATH,
    WidgetAccessError,
    append_widget_event,
    append_widget_transcript,
    build_public_widget_config,
    ensure_public_widget_id,
    get_or_create_widget_engagement,
    get_widget_settings_payload,
    mark_widget_seen,
    mock_chat_reply,
    normalize_allowed_domains,
    sanitize_event_metadata,
    validate_widget_request,
)

router = APIRouter(prefix="/widget", tags=["widget"])
asset_router = APIRouter(tags=["widget-asset"])


def success_response(data: Any) -> dict[str, Any]:
    return {"success": True, "data": data}


def blocked_response(message: str = "Widget is not available for this account.", code: str = "WIDGET_BLOCKED", status_code: int = 403) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "success": False,
            "error": {
                "code": code,
                "message": message,
            },
        },
    )


async def _get_tenant_client(db: AsyncSession, current: dict) -> Client:
    if is_internal_staff_role(current.get("role")):
        raise HTTPException(403, "Use a tenant account for this endpoint")
    client = await db.get(Client, current["client_id"])
    if not client:
        raise HTTPException(404, "Workspace not found")
    return client


class WidgetHandshakeIn(BaseModel):
    publicWidgetId: str = Field(..., min_length=8, max_length=128)
    domain: str = Field(..., min_length=1, max_length=255)
    pageUrl: str = Field(..., min_length=1, max_length=2048)
    referrer: str | None = Field(None, max_length=2048)


class WidgetInstallPingIn(BaseModel):
    publicWidgetId: str = Field(..., min_length=8, max_length=128)
    domain: str = Field(..., min_length=1, max_length=255)
    pageUrl: str = Field(..., min_length=1, max_length=2048)


class WidgetEventIn(BaseModel):
    publicWidgetId: str = Field(..., min_length=8, max_length=128)
    sessionId: str = Field(..., min_length=8, max_length=120)
    eventType: Literal[
        "widget_loaded",
        "widget_opened",
        "message_sent",
        "lead_captured",
        "voice_started",
        "voice_ended",
    ]
    domain: str = Field(..., min_length=1, max_length=255)
    pageUrl: str = Field(..., min_length=1, max_length=2048)
    metadata: dict[str, Any] = Field(default_factory=dict)


class WidgetChatIn(BaseModel):
    publicWidgetId: str = Field(..., min_length=8, max_length=128)
    sessionId: str = Field(..., min_length=8, max_length=120)
    message: str = Field(..., min_length=1, max_length=4000)
    domain: str = Field(..., min_length=1, max_length=255)
    pageUrl: str = Field(..., min_length=1, max_length=2048)
    language: str | None = Field(None, max_length=12)
    detectedLanguage: str | None = Field(None, max_length=12)
    languageMode: str | None = Field(None, max_length=12)


class WidgetSettingsPatch(BaseModel):
    widgetEnabled: bool | None = None
    allowedDomains: list[str] | None = None
    widgetPrimaryColor: str | None = Field(None, max_length=32)
    widgetPosition: Literal["bottom-right", "bottom-left"] | None = None
    widgetWelcomeMessage: str | None = Field(None, max_length=2000)
    voiceEnabled: bool | None = None


@asset_router.get("/widget.js")
async def get_widget_script() -> Response:
    if not Path(WIDGET_SCRIPT_PATH).exists():
        raise HTTPException(404, "widget.js not found")
    return FileResponse(
        WIDGET_SCRIPT_PATH,
        media_type="application/javascript",
        headers={"Cache-Control": "public, max-age=300"},
    )


@asset_router.get("/static/omniweb-shopify-widget.js")
async def get_shopify_widget_script() -> Response:
    if not Path(SHOPIFY_WIDGET_SCRIPT_PATH).exists():
        raise HTTPException(404, "omniweb-shopify-widget.js not found")
    return FileResponse(
        SHOPIFY_WIDGET_SCRIPT_PATH,
        media_type="application/javascript",
        headers={"Cache-Control": "public, max-age=300"},
    )


@router.get("/embed-code")
async def get_widget_embed_code(
    current: dict = Depends(get_current_client),
    db: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    client = await _get_tenant_client(db, current)
    agent = await get_agent_config_for_client(db, client.id)
    ensure_public_widget_id(client)

    # Auto-seed omniweb.ai as an allowed domain so the widget always works
    # on the primary site without any manual configuration step.
    existing = normalize_allowed_domains(getattr(client, "allowed_domains", []) or [])
    if "omniweb.ai" not in existing:
        existing.append("omniweb.ai")
        client.allowed_domains = existing

    # Default widget to enabled if it hasn't been explicitly disabled
    if getattr(client, "widget_enabled", None) is None:
        client.widget_enabled = True
    if (client.saas_widget_status or "active") == "disabled" and getattr(client, "widget_enabled", True):
        client.saas_widget_status = "active"

    await db.commit()
    await db.refresh(client)
    return success_response(get_widget_settings_payload(client, agent))


@router.patch("/settings")
async def patch_widget_settings(
    body: WidgetSettingsPatch,
    current: dict = Depends(get_current_client),
    db: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    client = await _get_tenant_client(db, current)
    agent = await get_agent_config_for_client(db, client.id)
    ensure_public_widget_id(client)

    if body.widgetEnabled is not None:
        client.widget_enabled = body.widgetEnabled
        if body.widgetEnabled and client.saas_widget_status == "disabled":
            client.saas_widget_status = "active"
        if body.widgetEnabled is False:
            client.saas_widget_status = "disabled"
    if body.allowedDomains is not None:
        domains = normalize_allowed_domains(body.allowedDomains)
        if "omniweb.ai" not in domains:
            domains.append("omniweb.ai")
        client.allowed_domains = domains
    if body.widgetPrimaryColor is not None:
        client.widget_primary_color = body.widgetPrimaryColor.strip() or None
    if body.widgetPosition is not None:
        if body.widgetPosition not in VALID_WIDGET_POSITIONS:
            raise HTTPException(400, "Invalid widget position")
        client.widget_position = body.widgetPosition
    if body.widgetWelcomeMessage is not None:
        client.widget_welcome_message = body.widgetWelcomeMessage.strip() or None
    if body.voiceEnabled is not None:
        client.voice_enabled = body.voiceEnabled

    if agent:
        widget_config = dict(agent.widget_config or {})
        saas_ui = dict(widget_config.get("saas_ui") or {})
        if body.widgetPrimaryColor is not None:
            saas_ui["theme_color"] = client.widget_primary_color or body.widgetPrimaryColor
        if body.widgetPosition is not None:
            saas_ui["position"] = client.widget_position
        widget_config["saas_ui"] = saas_ui
        agent.widget_config = widget_config
        if body.widgetWelcomeMessage is not None and client.widget_welcome_message:
            agent.agent_greeting = client.widget_welcome_message

    await db.commit()
    if agent:
        await db.refresh(agent)
    await db.refresh(client)
    return success_response(get_widget_settings_payload(client, agent))


@router.post("/handshake")
async def post_widget_handshake(
    body: WidgetHandshakeIn,
    db: AsyncSession = Depends(get_session),
) -> JSONResponse:
    try:
        client, agent, normalized_domain, _, _ = await validate_widget_request(
            db,
            public_widget_id=body.publicWidgetId,
            domain=body.domain,
        )
    except WidgetAccessError as exc:
        return blocked_response(exc.message, exc.code, exc.status_code)

    mark_widget_seen(client, domain=normalized_domain, page_url=body.pageUrl)
    await db.commit()
    return JSONResponse(content=success_response(build_public_widget_config(client, agent)))


@router.post("/install-ping")
async def post_widget_install_ping(
    body: WidgetInstallPingIn,
    db: AsyncSession = Depends(get_session),
) -> JSONResponse:
    try:
        client, _, normalized_domain, _, _ = await validate_widget_request(
            db,
            public_widget_id=body.publicWidgetId,
            domain=body.domain,
        )
    except WidgetAccessError as exc:
        return blocked_response(exc.message, exc.code, exc.status_code)

    mark_widget_seen(client, domain=normalized_domain, page_url=body.pageUrl)
    await db.commit()
    return JSONResponse(content=success_response({"installed": True}))


@router.post("/events")
async def post_widget_event(
    body: WidgetEventIn,
    db: AsyncSession = Depends(get_session),
) -> JSONResponse:
    try:
        client, agent, normalized_domain, _, _ = await validate_widget_request(
            db,
            public_widget_id=body.publicWidgetId,
            domain=body.domain,
        )
    except WidgetAccessError as exc:
        return blocked_response(exc.message, exc.code, exc.status_code)

    mark_widget_seen(client, domain=normalized_domain, page_url=body.pageUrl)
    engagement = await get_or_create_widget_engagement(
        db,
        client=client,
        agent=agent,
        session_id=body.sessionId,
        domain=normalized_domain,
        page_url=body.pageUrl,
        channel="ai_voice_call" if body.eventType in {"voice_started", "voice_ended"} else "website_chat",
    )
    append_widget_event(
        engagement,
        event_type=body.eventType,
        domain=normalized_domain,
        page_url=body.pageUrl,
        metadata=sanitize_event_metadata(body.metadata),
    )
    await db.commit()
    return JSONResponse(content=success_response({"accepted": True}))


@router.post("/chat")
async def post_widget_chat(
    body: WidgetChatIn,
    db: AsyncSession = Depends(get_session),
) -> JSONResponse:
    try:
        client, agent, normalized_domain, _, _ = await validate_widget_request(
            db,
            public_widget_id=body.publicWidgetId,
            domain=body.domain,
        )
    except WidgetAccessError as exc:
        return blocked_response(exc.message, exc.code, exc.status_code)

    mark_widget_seen(client, domain=normalized_domain, page_url=body.pageUrl)
    engagement = await get_or_create_widget_engagement(
        db,
        client=client,
        agent=agent,
        session_id=body.sessionId,
        domain=normalized_domain,
        page_url=body.pageUrl,
    )
    append_widget_transcript(engagement, "Visitor", body.message)
    append_widget_event(
        engagement,
        event_type="message_sent",
        domain=normalized_domain,
        page_url=body.pageUrl,
        metadata={"source": "widget_chat"},
    )

    selected_language = (body.language or "").strip().lower()
    detected_language = (body.detectedLanguage or "").strip().lower()
    language_mode = (body.languageMode or "").strip().lower()
    if language_mode == "auto" or selected_language in {"auto", "multi"}:
        effective_language = detected_language or "auto"
    else:
        effective_language = selected_language or detected_language or None

    try:
        brain_response = await OmniwebBrainService(db).run(
            BrainRequest(
                tenant_id=client.id,
                channel_type="chat",
                user_message=body.message,
                metadata={
                    "provider": "omniweb_widget",
                    "session_id": body.sessionId,
                    "domain": normalized_domain,
                    "page_url": body.pageUrl,
                    "language": effective_language,
                    "detected_language": detected_language or None,
                    "language_mode": language_mode or None,
                },
            )
        )
        reply = brain_response.response_text
    except Exception:
        reply = mock_chat_reply(body.message)

    append_widget_transcript(engagement, "Assistant", reply)
    await db.commit()

    return JSONResponse(
        content=success_response(
            {
                "sessionId": body.sessionId,
                "message": {
                    "role": "assistant",
                    "content": reply,
                },
            }
        )
    )

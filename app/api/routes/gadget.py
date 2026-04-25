"""Gadget bridge endpoints.

These routes are for server-to-server calls from Gadget/new and use
``GADGET_ENGINE_SHARED_SECRET`` rather than the Retell tool secret.
"""

from __future__ import annotations

import hmac
import time
import uuid
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.api.routes.deepgram import VoiceAgentBootstrapRequest, run_voice_agent_bootstrap
from app.api.routes.webhooks_tools import (
    CaptureLeadRequest,
    _build_summary,
    _enforce_guardrails,
    _log_tool_call,
    _resolve_tenant,
    _score_lead,
)
from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.models import Lead, ShopifyAssistantSession, ShopifyStore
from app.services.shopify_assistant_service import ShopifyAssistantService, utcnow
from app.services.shopify_oauth_service import ShopifyOAuthError, ShopifyOAuthService

logger = get_logger(__name__)
settings = get_settings()
router = APIRouter(prefix="/gadget", tags=["gadget"])


class GadgetVoiceSessionRequest(BaseModel):
    shop_domain: str | None = Field(None, description="Shopify .myshopify.com domain")
    gadget_store_id: str | None = Field(None, description="Optional Gadget/Shopify store id")
    storefront_session_id: str | None = Field(None, description="Optional storefront/browser session id")
    client_id: str | None = Field(None, description="Fallback Omniweb client UUID")
    language: str | None = Field("en", description="Requested language code")
    agent_id: str | None = Field(None, description="Optional external/Gadget agent id")
    shopper_email: str | None = None
    shopper_locale: str | None = None
    currency: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class GadgetCaptureLeadRequest(CaptureLeadRequest):
    shop_domain: str | None = None
    gadget_store_id: str | None = None
    session_id: str | None = None
    client_id: str | None = None


def _verify_gadget_secret(secret: str | None) -> None:
    expected = (settings.GADGET_ENGINE_SHARED_SECRET or "").strip()
    if not expected:
        raise HTTPException(503, "GADGET_ENGINE_SHARED_SECRET is not configured")
    if not secret or not hmac.compare_digest(secret, expected):
        raise HTTPException(403, "Invalid Gadget shared secret")


def _gadget_base_url() -> str:
    return settings.ENGINE_BASE_URL.rstrip("/") or settings.APP_BASE_URL.rstrip("/")


def _normalize_shop_domain(shop_domain: str | None) -> str | None:
    if not shop_domain:
        return None
    try:
        return ShopifyOAuthService.normalize_shop_domain(shop_domain)
    except ShopifyOAuthError as exc:
        raise HTTPException(400, str(exc)) from exc


async def _resolve_store(
    db: AsyncSession,
    *,
    shop_domain: str | None = None,
    gadget_store_id: str | None = None,
    client_id: str | None = None,
    require_enabled: bool = True,
) -> ShopifyStore | None:
    normalized_shop = _normalize_shop_domain(shop_domain)

    clauses = []
    if normalized_shop:
        clauses.append(ShopifyStore.shop_domain == normalized_shop)
    if gadget_store_id:
        clauses.append(ShopifyStore.shop_id == gadget_store_id)
    if client_id:
        try:
            clauses.append(ShopifyStore.client_id == uuid.UUID(client_id))
        except ValueError as exc:
            raise HTTPException(400, "Invalid client_id") from exc

    if not clauses:
        return None

    result = await db.execute(select(ShopifyStore).where(*clauses).limit(1))
    store = result.scalar_one_or_none()
    if not store:
        raise HTTPException(404, "Shopify store is not configured in Omniweb")
    if require_enabled and (not store.assistant_enabled or store.app_status != "installed"):
        raise HTTPException(403, "Storefront assistant is not enabled for this shop")
    return store


async def _resolve_client_id_for_gadget_voice(
    db: AsyncSession,
    body: GadgetVoiceSessionRequest,
) -> tuple[str, ShopifyStore | None]:
    if body.shop_domain or body.gadget_store_id:
        store = await _resolve_store(
            db,
            shop_domain=body.shop_domain,
            gadget_store_id=body.gadget_store_id,
            client_id=body.client_id,
            require_enabled=True,
        )
        if store:
            return str(store.client_id), store
    if body.client_id:
        # Explicit fallback for non-Shopify Gadget flows.
        return body.client_id, None
    raise HTTPException(400, "Provide shop_domain, gadget_store_id, or client_id")


async def _create_shopify_voice_session(
    db: AsyncSession,
    *,
    store: ShopifyStore | None,
    body: GadgetVoiceSessionRequest,
) -> ShopifyAssistantSession | None:
    if not store:
        return None

    context = ShopifyAssistantService.merge_context(
        {},
        {
            "shop_domain": store.shop_domain,
            "gadget_store_id": body.gadget_store_id,
            "voice_agent_id": body.agent_id,
            "voice_metadata": body.metadata,
        },
    )
    session = ShopifyAssistantSession(
        client_id=store.client_id,
        store_id=store.id,
        storefront_session_id=body.storefront_session_id,
        shopper_email=body.shopper_email,
        shopper_locale=body.shopper_locale,
        currency=body.currency,
        context=context,
        transcript=[],
        last_recommendations=[],
        last_seen_at=utcnow(),
    )
    db.add(session)
    await db.flush()
    await db.refresh(session)
    return session


@router.post("/voice/session")
async def create_voice_session(
    body: GadgetVoiceSessionRequest,
    x_gadget_secret: str | None = Header(None),
    x_engine_secret: str | None = Header(None),
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Create a Deepgram Voice Agent session payload for Gadget.

    Gadget should call this server-to-server with ``X-Gadget-Secret`` set to the
    shared value stored in ``GADGET_ENGINE_SHARED_SECRET``.
    """
    _verify_gadget_secret(x_gadget_secret or x_engine_secret)

    client_id, store = await _resolve_client_id_for_gadget_voice(db, body)

    payload = await run_voice_agent_bootstrap(
        VoiceAgentBootstrapRequest(client_id=client_id, language=body.language),
        db,
    )
    session = await _create_shopify_voice_session(db, store=store, body=body)

    base_url = _gadget_base_url()
    return {
        **payload,
        "voice_session_id": str(session.id if session else uuid.uuid4()),
        "voice_provider": "deepgram",
        "shop_domain": store.shop_domain if store else body.shop_domain,
        "gadget_store_id": body.gadget_store_id,
        "session_endpoint": f"{base_url}/api/gadget/voice/session",
        "auth": {
            "header": "X-Gadget-Secret",
        },
        "connections": {
            "gadget_to_omniweb": {
                "type": "https",
                "base_url": base_url,
                "auth_header": "X-Gadget-Secret",
            },
            "browser_to_deepgram": {
                "type": "websocket",
                "url": payload["websocket_url"],
                "subprotocols": ["bearer", "<access_token>"],
            },
        },
        "tool_endpoints": {
            "capture_lead": f"{base_url}/api/gadget/tools/capture-lead",
        },
        "metadata": body.metadata,
    }


@router.post("/voice-session")
async def create_voice_session_alias(
    body: GadgetVoiceSessionRequest,
    x_gadget_secret: str | None = Header(None),
    x_engine_secret: str | None = Header(None),
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Compatibility alias for clients looking for ``/voice-session``."""
    return await create_voice_session(
        body=body,
        x_gadget_secret=x_gadget_secret,
        x_engine_secret=x_engine_secret,
        db=db,
    )


@router.post("/tools/capture-lead")
async def gadget_capture_lead(
    body: GadgetCaptureLeadRequest,
    x_gadget_secret: str | None = Header(None),
    x_engine_secret: str | None = Header(None),
    x_agent_id: str | None = Header(None),
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Capture a lead from Gadget using ``GADGET_ENGINE_SHARED_SECRET``."""
    _verify_gadget_secret(x_gadget_secret or x_engine_secret)
    t0 = time.time()

    store = None
    if body.session_id:
        try:
            session = await db.get(ShopifyAssistantSession, uuid.UUID(body.session_id))
        except ValueError as exc:
            raise HTTPException(400, "Invalid session_id") from exc
        if not session:
            raise HTTPException(404, "Voice session not found")
        store = await db.get(ShopifyStore, session.store_id)
    else:
        store = await _resolve_store(
            db,
            shop_domain=body.shop_domain,
            gadget_store_id=body.gadget_store_id,
            client_id=body.client_id,
            require_enabled=False,
        )

    if store:
        client_id = store.client_id
        industry_slug = "ecommerce"
        custom_guardrails = []
    else:
        client_id, industry_slug, custom_guardrails = await _resolve_tenant(x_agent_id)

    lead_id = uuid.uuid4()

    lead = Lead(
        id=lead_id,
        client_id=client_id,
        caller_name=body.name,
        caller_phone=body.phone or "not-provided",
        caller_email=body.email,
        intent=body.industry or body.challenge,
        urgency=body.urgency or "medium",
        summary=_build_summary(body),
        services_requested=[s.strip() for s in body.services_interested.split(",")]
        if body.services_interested
        else [],
        status="new",
        lead_score=_score_lead(body),
        follow_up_sent=False,
    )
    db.add(lead)
    await db.flush()

    response_text = (
        f"Lead saved successfully. {body.name}'s information has been recorded. "
        "Our team will follow up shortly."
    )
    response_text = _enforce_guardrails(
        response_text,
        tool_name="capture_lead",
        industry_slug=industry_slug,
        custom_guardrails=custom_guardrails,
    )
    result = {"result": response_text}
    await _log_tool_call(
        "gadget_capture_lead",
        body.model_dump(),
        result,
        client_id=client_id,
        lead_id=lead_id,
        duration_ms=int((time.time() - t0) * 1000),
    )
    logger.info("Lead captured via Gadget", lead_id=str(lead_id), client_id=str(client_id))
    return result

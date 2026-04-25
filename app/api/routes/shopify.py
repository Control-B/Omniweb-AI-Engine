from __future__ import annotations

import hmac
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.api.routes.deepgram import VoiceAgentBootstrapRequest, run_voice_agent_bootstrap
from app.core.config import get_settings
from app.core.auth import get_current_client, is_internal_staff_role
from app.models.models import AgentConfig, Client, Lead, ShopifyAssistantSession, ShopifyDiscountApproval, ShopifyStore
from app.services.shopify_api_service import ShopifyAPIError, ShopifyAPIService
from app.services.shopify_billing_service import ShopifyBillingError, ShopifyBillingService
from app.services.shopify_crypto_service import ShopifyCryptoService
from app.services.shopify_oauth_service import ShopifyOAuthError, ShopifyOAuthService
from app.services.shopify_product_service import ShopifyProductService
from app.services.shopify_webhook_service import ShopifyWebhookService
from app.services.prompt_engine import compose_greeting
from app.services.shopify_assistant_service import ShopifyAssistantService, utcnow
from app.services.shopify_storefront_bridge_service import (
    ShopifyStorefrontBridgeError,
    ShopifyStorefrontBridgeService,
)
from app.services.url_knowledge_service import UrlKnowledgeService

router = APIRouter(prefix="/shopify", tags=["shopify"])
settings = get_settings()


class ProductSignal(BaseModel):
    id: str = ""
    title: str = ""
    handle: str | None = None
    url: str | None = None
    product_type: str | None = None
    vendor: str | None = None
    tags: list[str] = Field(default_factory=list)
    collections: list[str] = Field(default_factory=list)
    features: list[str] = Field(default_factory=list)
    price: float | None = None
    compare_at_price: float | None = None
    quantity: int | None = None
    available: bool | None = None


class StorefrontContext(BaseModel):
    shop_domain: str
    storefront_session_id: str | None = None
    shopper_email: str | None = None
    shopper_locale: str | None = None
    currency: str | None = None
    current_page_url: str | None = None
    current_page_title: str | None = None
    search_query: str | None = None
    checkout_url: str | None = None
    cart_total: float | None = None
    current_product: ProductSignal | None = None
    viewed_products: list[ProductSignal] = Field(default_factory=list)
    cart_lines: list[ProductSignal] = Field(default_factory=list)
    catalog_candidates: list[ProductSignal] = Field(default_factory=list)
    support_context: dict[str, Any] = Field(default_factory=dict)
    attributes: dict[str, Any] = Field(default_factory=dict)


class ShopifyConfigUpsert(BaseModel):
    shop_domain: str
    storefront_access_token: str | None = None
    admin_access_token: str | None = None
    storefront_api_version: str | None = None
    app_status: str | None = None
    sales_channel_name: str | None = None
    assistant_enabled: bool | None = None
    require_discount_approval: bool | None = None
    allow_discount_requests: bool | None = None
    allowed_discount_types: list[str] | None = None
    support_email: str | None = None
    support_policy: dict[str, Any] | None = None
    nav_config: dict[str, Any] | None = None
    checkout_config: dict[str, Any] | None = None


class StartSessionRequest(BaseModel):
    client_id: str
    context: StorefrontContext


class UpdateContextRequest(BaseModel):
    context: StorefrontContext


class AssistantReplyRequest(BaseModel):
    message: str
    context: StorefrontContext | None = None


class DiscountDecisionRequest(BaseModel):
    code: str | None = None
    value: float | None = None
    value_type: str | None = None
    merchant_note: str | None = None
    expires_at: datetime | None = None


class ShopifyInstallRequest(BaseModel):
    shop: str


class PublicSessionRequest(BaseModel):
    context: StorefrontContext


class PublicVoiceSessionRequest(BaseModel):
    context: StorefrontContext
    language: str | None = "en"


class StorefrontEvent(BaseModel):
    type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    timestamp: str | None = None


class StorefrontEventsRequest(BaseModel):
    events: list[StorefrontEvent] = Field(default_factory=list)


class EngineShopSyncRequest(BaseModel):
    shop_domain: str
    engine_client_id: str | None = None
    shop_name: str | None = None
    shop_email: str | None = None
    admin_access_token: str | None = None
    storefront_access_token: str | None = None
    granted_scopes: list[str] = Field(default_factory=list)
    storefront_api_version: str | None = None
    plan: str = "starter"
    subscription_status: str = "trialing"
    assistant_enabled: bool = True
    agent_config: dict[str, Any] = Field(default_factory=dict)


class EngineSubscriptionSyncRequest(BaseModel):
    shop_domain: str
    plan: str = "starter"
    subscription_status: str = "active"
    shopify_subscription_gid: str | None = None


class EngineStoreDisableRequest(BaseModel):
    shop_domain: str
    reason: str = "disabled"


class EngineAgentConfigSyncRequest(BaseModel):
    shop_domain: str
    agent_config: dict[str, Any] = Field(default_factory=dict)


class EngineKnowledgeJobRequest(BaseModel):
    shop_domain: str
    source_id: str | None = None
    url: str


def _verify_shopify_engine_secret(secret: str | None) -> None:
    expected = (settings.SHOPIFY_ENGINE_SHARED_SECRET or settings.GADGET_ENGINE_SHARED_SECRET or "").strip()
    if not expected:
        raise HTTPException(503, "SHOPIFY_ENGINE_SHARED_SECRET is not configured")
    if not secret or not hmac.compare_digest(secret, expected):
        raise HTTPException(403, "Invalid Shopify engine shared secret")


def _shopify_synthetic_client_email(shop_domain: str) -> str:
    safe = shop_domain.replace("@", "").replace("/", "-")
    return f"shopify+{safe}@omniweb.local"


async def _get_or_create_shopify_engine_client(
    db: AsyncSession,
    *,
    shop_domain: str,
    engine_client_id: str | None = None,
    shop_name: str | None = None,
    shop_email: str | None = None,
    plan: str = "starter",
) -> Client:
    client = None
    if engine_client_id:
        try:
            client = await db.get(Client, uuid.UUID(engine_client_id))
        except ValueError as exc:
            raise HTTPException(400, "Invalid engine_client_id") from exc

    if not client:
        store_result = await db.execute(
            select(ShopifyStore).where(ShopifyStore.shop_domain == shop_domain).limit(1)
        )
        existing_store = store_result.scalar_one_or_none()
        if existing_store:
            client = await db.get(Client, existing_store.client_id)

    if not client:
        email = _shopify_synthetic_client_email(shop_domain)
        client_result = await db.execute(select(Client).where(Client.email == email).limit(1))
        client = client_result.scalar_one_or_none()

    if not client:
        client = Client(
            name=shop_name or shop_domain,
            email=_shopify_synthetic_client_email(shop_domain),
            notification_email=shop_email,
            role="client",
            is_active=True,
        )
        db.add(client)
        await db.flush()

    if shop_name:
        client.name = shop_name
    if shop_email:
        client.notification_email = shop_email
    if plan in {"starter", "growth", "pro", "agency"}:
        client.plan = plan
    return client


async def _get_or_create_shopify_engine_store(
    db: AsyncSession,
    *,
    client: Client,
    shop_domain: str,
) -> ShopifyStore:
    result = await db.execute(select(ShopifyStore).where(ShopifyStore.shop_domain == shop_domain).limit(1))
    store = result.scalar_one_or_none()
    if not store:
        store = ShopifyStore(client_id=client.id, shop_domain=shop_domain)
        db.add(store)
        await db.flush()
    store.client_id = client.id
    store.shop_domain = shop_domain
    return store


async def _sync_engine_agent_config(
    db: AsyncSession,
    *,
    client_id: uuid.UUID,
    shop_domain: str,
    agent_config: dict[str, Any] | None,
) -> AgentConfig:
    result = await db.execute(select(AgentConfig).where(AgentConfig.client_id == client_id).limit(1))
    config = result.scalar_one_or_none()
    if not config:
        config = AgentConfig(
            client_id=client_id,
            agent_name="Omniweb AI",
            business_name=shop_domain,
            business_type="ecommerce",
            industry="ecommerce",
            agent_mode="ecommerce_assistant",
        )
        db.add(config)
        await db.flush()

    payload = agent_config or {}
    if payload.get("agentName") is not None:
        config.agent_name = str(payload["agentName"] or "Omniweb AI")
    if payload.get("businessName") is not None:
        config.business_name = str(payload["businessName"] or shop_domain)
    if payload.get("greeting") is not None:
        config.agent_greeting = str(payload["greeting"] or config.agent_greeting)
    if payload.get("systemPrompt") is not None:
        config.system_prompt = str(payload["systemPrompt"] or "")
    if isinstance(payload.get("supportedLanguages"), list):
        config.supported_languages = [str(lang) for lang in payload["supportedLanguages"] if str(lang).strip()] or ["en"]
    if isinstance(payload.get("widgetSettings"), dict):
        config.widget_config = payload["widgetSettings"]
    if not config.business_name:
        config.business_name = shop_domain
    config.business_type = config.business_type or "ecommerce"
    config.industry = "ecommerce"
    config.agent_mode = "ecommerce_assistant"
    return config


@router.post("/engine/sync-shop")
async def sync_shop_from_shopify_app(
    body: EngineShopSyncRequest,
    x_omniweb_shopify_secret: str | None = Header(None),
    x_engine_secret: str | None = Header(None),
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Mirror Shopify app install/config state into the AI Engine."""
    _verify_shopify_engine_secret(x_omniweb_shopify_secret or x_engine_secret)
    try:
        shop_domain = ShopifyOAuthService.normalize_shop_domain(body.shop_domain)
    except ShopifyOAuthError as exc:
        raise HTTPException(400, str(exc)) from exc

    client = await _get_or_create_shopify_engine_client(
        db,
        shop_domain=shop_domain,
        engine_client_id=body.engine_client_id,
        shop_name=body.shop_name,
        shop_email=body.shop_email,
        plan=body.plan,
    )
    store = await _get_or_create_shopify_engine_store(db, client=client, shop_domain=shop_domain)
    store.shop_name = body.shop_name or store.shop_name
    store.shop_email = body.shop_email or store.shop_email
    store.app_status = "installed"
    store.installed_at = store.installed_at or utcnow()
    store.uninstalled_at = None
    store.assistant_enabled = body.assistant_enabled
    if body.admin_access_token:
        store.admin_access_token = ShopifyCryptoService.encrypt(body.admin_access_token)
    if body.storefront_access_token:
        store.storefront_access_token = ShopifyCryptoService.encrypt(body.storefront_access_token)
    if body.granted_scopes:
        store.granted_scopes = body.granted_scopes
    if body.storefront_api_version:
        store.storefront_api_version = body.storefront_api_version
    store.shopify_plan = body.plan
    store.shopify_subscription_status = body.subscription_status
    store.shopify_billing_updated_at = utcnow()

    agent_config = await _sync_engine_agent_config(
        db,
        client_id=client.id,
        shop_domain=shop_domain,
        agent_config=body.agent_config,
    )
    nav_config = body.agent_config.get("navConfig") if body.agent_config else None
    if isinstance(nav_config, dict):
        store.nav_config = nav_config

    await db.flush()
    await db.refresh(store)
    return {
        "ok": True,
        "client_id": str(client.id),
        "store_id": str(store.id),
        "agent_config_id": str(agent_config.id),
        "shop_domain": store.shop_domain,
        "assistant_enabled": store.assistant_enabled,
    }


@router.post("/engine/sync-agent-config")
async def sync_agent_config_from_shopify_app(
    body: EngineAgentConfigSyncRequest,
    x_omniweb_shopify_secret: str | None = Header(None),
    x_engine_secret: str | None = Header(None),
    db: AsyncSession = Depends(get_session),
) -> dict:
    _verify_shopify_engine_secret(x_omniweb_shopify_secret or x_engine_secret)
    store = await _get_store_by_shop_domain(db, ShopifyOAuthService.normalize_shop_domain(body.shop_domain))
    if not store:
        raise HTTPException(404, "Shopify store is not configured in Omniweb")
    config = await _sync_engine_agent_config(
        db,
        client_id=store.client_id,
        shop_domain=store.shop_domain,
        agent_config=body.agent_config,
    )
    nav_config = body.agent_config.get("navConfig") if body.agent_config else None
    if isinstance(nav_config, dict):
        store.nav_config = nav_config
    await db.flush()
    return {"ok": True, "agent_config_id": str(config.id), "client_id": str(store.client_id)}


@router.post("/engine/sync-subscription")
async def sync_subscription_from_shopify_app(
    body: EngineSubscriptionSyncRequest,
    x_omniweb_shopify_secret: str | None = Header(None),
    x_engine_secret: str | None = Header(None),
    db: AsyncSession = Depends(get_session),
) -> dict:
    _verify_shopify_engine_secret(x_omniweb_shopify_secret or x_engine_secret)
    store = await _get_store_by_shop_domain(db, ShopifyOAuthService.normalize_shop_domain(body.shop_domain))
    if not store:
        raise HTTPException(404, "Shopify store is not configured in Omniweb")
    store.shopify_plan = body.plan
    store.shopify_subscription_status = body.subscription_status
    store.shopify_subscription_gid = body.shopify_subscription_gid or store.shopify_subscription_gid
    store.shopify_billing_updated_at = utcnow()
    await db.flush()
    return {"ok": True, "client_id": str(store.client_id), "shop_domain": store.shop_domain}


@router.post("/engine/disable-store")
async def disable_store_from_shopify_app(
    body: EngineStoreDisableRequest,
    x_omniweb_shopify_secret: str | None = Header(None),
    x_engine_secret: str | None = Header(None),
    db: AsyncSession = Depends(get_session),
) -> dict:
    _verify_shopify_engine_secret(x_omniweb_shopify_secret or x_engine_secret)
    store = await _get_store_by_shop_domain(db, ShopifyOAuthService.normalize_shop_domain(body.shop_domain))
    if not store:
        raise HTTPException(404, "Shopify store is not configured in Omniweb")

    store.assistant_enabled = False
    reason = (body.reason or "").lower()
    if reason in {"uninstalled", "app_uninstalled"}:
        store.app_status = "uninstalled"
        store.uninstalled_at = utcnow()
    elif reason in {"cancelled", "canceled", "subscription_cancelled"}:
        store.shopify_subscription_status = "cancelled"
    await db.flush()
    return {"ok": True, "client_id": str(store.client_id), "shop_domain": store.shop_domain}


@router.post("/engine/knowledge-jobs")
async def enqueue_shopify_knowledge_job(
    body: EngineKnowledgeJobRequest,
    x_omniweb_shopify_secret: str | None = Header(None),
    x_engine_secret: str | None = Header(None),
    db: AsyncSession = Depends(get_session),
) -> dict:
    _verify_shopify_engine_secret(x_omniweb_shopify_secret or x_engine_secret)
    store = await _get_store_by_shop_domain(db, ShopifyOAuthService.normalize_shop_domain(body.shop_domain))
    if not store:
        raise HTTPException(404, "Shopify store is not configured in Omniweb")
    result = await db.execute(select(AgentConfig).where(AgentConfig.client_id == store.client_id).limit(1))
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(404, "Agent config not found for Shopify store")

    try:
        ingest = await UrlKnowledgeService.ingest_website(body.url)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(502, "Failed to ingest Shopify knowledge URL") from exc

    summary = ingest.get("summary") or ""
    if not summary:
        raise HTTPException(422, "No readable knowledge extracted from URL")

    existing = (config.custom_context or "").strip()
    source_url = ingest.get("source_url") or body.url
    section = f"Shopify knowledge source: {source_url}\n{summary}"
    config.custom_context = f"{existing}\n\n{section}".strip() if existing else section
    config.website_domain = source_url
    await db.flush()
    return {
        "ok": True,
        "job_id": body.source_id,
        "url": source_url,
        "pages_crawled": ingest.get("pages_crawled", 0),
        "summary_chars": len(summary),
    }


@router.get("/engine/analytics")
async def get_shopify_engine_analytics(
    shop_domain: str = Query(...),
    x_omniweb_shopify_secret: str | None = Header(None),
    x_engine_secret: str | None = Header(None),
    db: AsyncSession = Depends(get_session),
) -> dict:
    _verify_shopify_engine_secret(x_omniweb_shopify_secret or x_engine_secret)
    store = await _get_store_by_shop_domain(db, ShopifyOAuthService.normalize_shop_domain(shop_domain))
    if not store:
        raise HTTPException(404, "Shopify store is not configured in Omniweb")

    sessions_count = await db.scalar(
        select(func.count()).select_from(ShopifyAssistantSession).where(ShopifyAssistantSession.store_id == store.id)
    )
    active_sessions_count = await db.scalar(
        select(func.count()).select_from(ShopifyAssistantSession).where(
            ShopifyAssistantSession.store_id == store.id,
            ShopifyAssistantSession.status == "active",
        )
    )
    leads_count = await db.scalar(
        select(func.count()).select_from(Lead).where(Lead.client_id == store.client_id)
    )
    discount_requests_count = await db.scalar(
        select(func.count()).select_from(ShopifyDiscountApproval).where(ShopifyDiscountApproval.store_id == store.id)
    )
    approved_discounts_count = await db.scalar(
        select(func.count()).select_from(ShopifyDiscountApproval).where(
            ShopifyDiscountApproval.store_id == store.id,
            ShopifyDiscountApproval.status == "approved",
        )
    )
    recent_result = await db.execute(
        select(ShopifyAssistantSession)
        .where(ShopifyAssistantSession.store_id == store.id)
        .order_by(ShopifyAssistantSession.last_seen_at.desc())
        .limit(10)
    )
    recent_sessions = [
        {
            "id": str(session.id),
            "status": session.status,
            "shopper_email": session.shopper_email,
            "shopper_locale": session.shopper_locale,
            "currency": session.currency,
            "last_intent": session.last_intent,
            "current_page_url": (session.context or {}).get("current_page_url"),
            "messages": len(session.transcript or []),
            "last_seen_at": session.last_seen_at.isoformat() if session.last_seen_at else None,
            "created_at": session.created_at.isoformat() if session.created_at else None,
        }
        for session in recent_result.scalars().all()
    ]

    return {
        "ok": True,
        "shop_domain": store.shop_domain,
        "client_id": str(store.client_id),
        "conversations": sessions_count or 0,
        "active_sessions": active_sessions_count or 0,
        "qualified_leads": leads_count or 0,
        "discount_requests": discount_requests_count or 0,
        "approved_discounts": approved_discounts_count or 0,
        "recent_sessions": recent_sessions,
    }


@router.get("/public/bootstrap")
async def get_public_storefront_bootstrap(
    shop: str,
    db: AsyncSession = Depends(get_session),
) -> dict:
    try:
        shop_domain = ShopifyOAuthService.normalize_shop_domain(shop)
    except ShopifyOAuthError as exc:
        raise HTTPException(400, str(exc)) from exc

    store = await _get_store_by_shop_domain(db, shop_domain)
    if not store or not store.assistant_enabled or store.app_status != "installed":
        raise HTTPException(404, "Storefront assistant is not available for this shop")

    context = StorefrontContext(shop_domain=shop_domain)
    greeting = await _build_welcome_message(db, str(store.client_id), context, store)
    public_token = ShopifyStorefrontBridgeService.issue_public_token(store)
    return ShopifyStorefrontBridgeService.bootstrap_payload(
        store=store,
        greeting=greeting,
        public_token=public_token,
    )


@router.post("/public/sessions")
async def start_public_storefront_session(
    body: PublicSessionRequest,
    authorization: str | None = Header(None),
    db: AsyncSession = Depends(get_session),
) -> dict:
    store, _payload = await _authenticate_public_storefront_request(db, authorization, body.context.shop_domain)
    context = body.context.model_dump(exclude_none=True)
    context = ShopifyAssistantService.merge_context(
        context,
        {
            "nav_config": store.nav_config or {},
            "support_context": {
                **(store.support_policy or {}),
                **(context.get("support_context") or {}),
            },
            "checkout_config": store.checkout_config or {},
        },
    )
    session = ShopifyAssistantSession(
        client_id=store.client_id,
        store_id=store.id,
        storefront_session_id=body.context.storefront_session_id,
        shopper_email=body.context.shopper_email,
        shopper_locale=body.context.shopper_locale,
        currency=body.context.currency,
        context=ShopifyAssistantService.merge_context({}, context),
        transcript=[],
        last_recommendations=[],
        last_seen_at=utcnow(),
    )
    db.add(session)
    await db.flush()
    await db.refresh(session)

    welcome_message = await _build_welcome_message(db, str(store.client_id), body.context, store)
    return {
        "session_id": str(session.id),
        "welcome_message": welcome_message,
        "assistant_enabled": store.assistant_enabled,
        "context_summary": ShopifyStorefrontBridgeService.summarize_context(session),
    }


@router.post("/public/voice/session")
async def start_public_storefront_voice_session(
    body: PublicVoiceSessionRequest,
    authorization: str | None = Header(None),
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Create a direct Omniweb voice session for Shopify storefront widgets."""
    store, _payload = await _authenticate_public_storefront_request(
        db, authorization, body.context.shop_domain
    )
    context = body.context.model_dump(exclude_none=True)
    context = ShopifyAssistantService.merge_context(
        context,
        {
            "nav_config": store.nav_config or {},
            "support_context": {
                **(store.support_policy or {}),
                **(context.get("support_context") or {}),
            },
            "checkout_config": store.checkout_config or {},
        },
    )
    session = ShopifyAssistantSession(
        client_id=store.client_id,
        store_id=store.id,
        storefront_session_id=body.context.storefront_session_id,
        shopper_email=body.context.shopper_email,
        shopper_locale=body.context.shopper_locale,
        currency=body.context.currency,
        context=ShopifyAssistantService.merge_context({}, context),
        transcript=[],
        last_recommendations=[],
        last_seen_at=utcnow(),
    )
    db.add(session)
    await db.flush()
    await db.refresh(session)

    voice_payload = await run_voice_agent_bootstrap(
        VoiceAgentBootstrapRequest(
            client_id=str(store.client_id),
            language=body.language,
        ),
        db,
    )
    return {
        **voice_payload,
        "voice_provider": "deepgram",
        "voice_session_id": str(session.id),
        "shop_domain": store.shop_domain,
        "store_id": str(store.id),
        "storefront_session_id": body.context.storefront_session_id,
    }


@router.post("/public/sessions/{session_id}/context")
async def update_public_storefront_context(
    session_id: str,
    body: UpdateContextRequest,
    authorization: str | None = Header(None),
    db: AsyncSession = Depends(get_session),
) -> dict:
    store, _payload = await _authenticate_public_storefront_request(db, authorization, body.context.shop_domain)
    session = await _get_public_session(db, session_id)
    _ensure_public_session_access(session, store)

    session.context = ShopifyAssistantService.merge_context(
        session.context,
        body.context.model_dump(exclude_none=True),
    )
    session.context = ShopifyAssistantService.merge_context(
        session.context,
        {
            "nav_config": store.nav_config or {},
            "support_context": store.support_policy or {},
            "checkout_config": store.checkout_config or {},
        },
    )
    session.shopper_email = body.context.shopper_email or session.shopper_email
    session.shopper_locale = body.context.shopper_locale or session.shopper_locale
    session.currency = body.context.currency or session.currency
    session.last_seen_at = utcnow()
    await db.flush()
    return {"ok": True, "context_summary": ShopifyStorefrontBridgeService.summarize_context(session)}


@router.post("/public/sessions/{session_id}/reply")
async def create_public_storefront_reply(
    session_id: str,
    body: AssistantReplyRequest,
    authorization: str | None = Header(None),
    db: AsyncSession = Depends(get_session),
) -> dict:
    shop_domain = body.context.shop_domain if body.context else None
    if not shop_domain:
        raise HTTPException(400, "Shop domain is required in context for public replies")
    store, _payload = await _authenticate_public_storefront_request(db, authorization, shop_domain)
    session = await _get_public_session(db, session_id)
    _ensure_public_session_access(session, store)

    session.context = ShopifyAssistantService.merge_context(
        session.context,
        body.context.model_dump(exclude_none=True),
    )
    session.context = ShopifyAssistantService.merge_context(
        session.context,
        {
            "nav_config": store.nav_config or {},
            "support_context": store.support_policy or {},
            "checkout_config": store.checkout_config or {},
        },
    )
    session.shopper_email = body.context.shopper_email or session.shopper_email
    session.shopper_locale = body.context.shopper_locale or session.shopper_locale
    session.currency = body.context.currency or session.currency

    result = await ShopifyAssistantService.generate_reply(
        db,
        store=store,
        session=session,
        shopper_message=body.message,
    )
    return {
        "session_id": str(session.id),
        "context_summary": ShopifyStorefrontBridgeService.summarize_context(session),
        **result,
    }


@router.post("/public/sessions/{session_id}/events")
async def ingest_public_storefront_events(
    session_id: str,
    body: StorefrontEventsRequest,
    shop: str,
    authorization: str | None = Header(None),
    db: AsyncSession = Depends(get_session),
) -> dict:
    store, _payload = await _authenticate_public_storefront_request(db, authorization, shop)
    session = await _get_public_session(db, session_id)
    _ensure_public_session_access(session, store)

    context = dict(session.context or {})
    for event in body.events:
        context = ShopifyAssistantService.apply_behavior_event(context, event.model_dump(exclude_none=True))
    session.context = context
    session.last_seen_at = utcnow()
    await db.flush()
    return {
        "ok": True,
        "processed_events": len(body.events),
        "context_summary": ShopifyStorefrontBridgeService.summarize_context(session),
    }


@router.post("/install/{client_id}")
async def begin_shopify_install(
    client_id: str,
    body: ShopifyInstallRequest,
    current_client: dict = Depends(get_current_client),
    db: AsyncSession = Depends(get_session),
) -> dict:
    _ensure_client_access(client_id, current_client)

    try:
        shop_domain = ShopifyOAuthService.normalize_shop_domain(body.shop)
    except ShopifyOAuthError as exc:
        raise HTTPException(400, str(exc)) from exc

    existing_store_for_shop = await _get_store_by_shop_domain(db, shop_domain)
    if existing_store_for_shop and str(existing_store_for_shop.client_id) != client_id:
        raise HTTPException(409, "This Shopify store is already connected to another client")

    store = await _get_store_for_client(db, client_id, allow_missing=True)
    if store is None:
        store = ShopifyStore(client_id=uuid.UUID(client_id), shop_domain=shop_domain)
        db.add(store)
    else:
        store.shop_domain = shop_domain

    state = ShopifyOAuthService.issue_install_state(store)
    install_url = ShopifyOAuthService.build_install_url(shop=shop_domain, state=state)
    await db.flush()
    await db.refresh(store)

    return {
        "install_url": install_url,
        "shop_domain": shop_domain,
        "app_status": store.app_status,
        "expires_at": store.install_state_expires_at.isoformat() if store.install_state_expires_at else None,
    }


@router.get("/install-status/{client_id}")
async def get_shopify_install_status(
    client_id: str,
    current_client: dict = Depends(get_current_client),
    db: AsyncSession = Depends(get_session),
) -> dict:
    _ensure_client_access(client_id, current_client)
    store = await _get_store_for_client(db, client_id)
    return {
        **_serialize_store(store),
        "install_in_progress": bool(store.install_state_hash and store.install_state_expires_at and store.install_state_expires_at >= utcnow()),
    }


@router.get("/oauth/callback")
async def complete_shopify_install(
    request: Request,
    shop: str,
    code: str,
    state: str,
    db: AsyncSession = Depends(get_session),
):
    try:
        ShopifyOAuthService.verify_callback_hmac(list(request.query_params.multi_items()))
        shop_domain = ShopifyOAuthService.normalize_shop_domain(shop)
    except ShopifyOAuthError as exc:
        raise HTTPException(400, str(exc)) from exc

    store = await _get_store_by_shop_domain(db, shop_domain)
    if not store:
        raise HTTPException(404, "No pending Shopify install was found for this shop")

    try:
        ShopifyOAuthService.verify_state(store, state)
        token_payload = await ShopifyOAuthService.exchange_code_for_token(shop=shop_domain, code=code)

        store.admin_access_token = ShopifyCryptoService.encrypt(token_payload["access_token"])
        store.granted_scopes = [scope.strip() for scope in (token_payload.get("scope") or "").split(",") if scope.strip()]
        store.uninstalled_at = None
        store.last_install_error = None

        identity = await ShopifyAPIService.get_shop_identity(store)
        storefront = await ShopifyAPIService.create_storefront_access_token(
            store,
            title=f"Omniweb storefront token for {shop_domain}",
        )

        store.shop_id = identity.get("id")
        store.shop_name = identity.get("name")
        store.shop_email = identity.get("email")
        store.storefront_access_token = ShopifyCryptoService.encrypt(storefront.get("access_token") or store.storefront_access_token)
        store.storefront_api_version = store.storefront_api_version or "2026-07"
        store.app_status = "installed"
        store.installed_at = utcnow()

        ShopifyOAuthService.clear_install_state(store)
        await db.flush()
        await db.refresh(store)

        # Register mandatory webhooks (best-effort, don't block install)
        try:
            await ShopifyWebhookService.register_mandatory_webhooks(store)
        except Exception as wh_exc:
            import logging
            logging.getLogger(__name__).warning(f"Webhook registration failed (non-blocking): {wh_exc}")
    except (ShopifyOAuthError, ShopifyAPIError) as exc:
        store.app_status = "install_failed"
        store.last_install_error = str(exc)
        ShopifyOAuthService.clear_install_state(store)
        await db.flush()
        redirect_url = ShopifyOAuthService.build_admin_redirect(
            shop=shop_domain,
            status="error",
            client_id=str(store.client_id),
        )
        return RedirectResponse(redirect_url, status_code=302)

    redirect_url = ShopifyOAuthService.build_admin_redirect(
        shop=shop_domain,
        status="connected",
        client_id=str(store.client_id),
    )
    return RedirectResponse(redirect_url, status_code=302)


@router.get("/stores/{client_id}")
async def get_shopify_config(
    client_id: str,
    current_client: dict = Depends(get_current_client),
    db: AsyncSession = Depends(get_session),
) -> dict:
    _ensure_client_access(client_id, current_client)
    store = await _get_store_for_client(db, client_id)
    return _serialize_store(store)


@router.put("/stores/{client_id}")
async def upsert_shopify_config(
    client_id: str,
    body: ShopifyConfigUpsert,
    current_client: dict = Depends(get_current_client),
    db: AsyncSession = Depends(get_session),
) -> dict:
    _ensure_client_access(client_id, current_client)
    store = await _get_store_for_client(db, client_id, allow_missing=True)
    if store is None:
        store = ShopifyStore(client_id=uuid.UUID(client_id), shop_domain=body.shop_domain)
        db.add(store)

    for field, value in body.model_dump(exclude_none=True).items():
        setattr(store, field, value)

    await db.flush()
    await db.refresh(store)
    return _serialize_store(store)


@router.post("/sessions")
async def start_storefront_session(
    body: StartSessionRequest,
    db: AsyncSession = Depends(get_session),
) -> dict:
    store = await _get_public_store(db, client_id=body.client_id, shop_domain=body.context.shop_domain)
    context = body.context.model_dump(exclude_none=True)
    session = ShopifyAssistantSession(
        client_id=uuid.UUID(body.client_id),
        store_id=store.id,
        storefront_session_id=body.context.storefront_session_id,
        shopper_email=body.context.shopper_email,
        shopper_locale=body.context.shopper_locale,
        currency=body.context.currency,
        context=ShopifyAssistantService.merge_context({}, context),
        transcript=[],
        last_recommendations=[],
        last_seen_at=utcnow(),
    )
    db.add(session)
    await db.flush()
    await db.refresh(session)

    welcome_message = await _build_welcome_message(db, body.client_id, body.context, store)
    return {
        "session_id": str(session.id),
        "welcome_message": welcome_message,
        "assistant_enabled": store.assistant_enabled,
    }


@router.post("/sessions/{session_id}/context")
async def update_storefront_context(
    session_id: str,
    body: UpdateContextRequest,
    db: AsyncSession = Depends(get_session),
) -> dict:
    session = await _get_public_session(db, session_id)
    store = await db.get(ShopifyStore, session.store_id)
    if not store:
        raise HTTPException(404, "Store not found")
    if store.shop_domain != body.context.shop_domain:
        raise HTTPException(403, "Shop domain mismatch")

    session.context = ShopifyAssistantService.merge_context(session.context, body.context.model_dump(exclude_none=True))
    session.shopper_email = body.context.shopper_email or session.shopper_email
    session.shopper_locale = body.context.shopper_locale or session.shopper_locale
    session.currency = body.context.currency or session.currency
    session.last_seen_at = utcnow()
    await db.flush()
    return {"ok": True, "session_id": str(session.id), "last_seen_at": session.last_seen_at.isoformat()}


@router.post("/sessions/{session_id}/reply")
async def create_storefront_reply(
    session_id: str,
    body: AssistantReplyRequest,
    db: AsyncSession = Depends(get_session),
) -> dict:
    session = await _get_public_session(db, session_id)
    store = await db.get(ShopifyStore, session.store_id)
    if not store:
        raise HTTPException(404, "Store not found")
    if body.context is not None and store.shop_domain != body.context.shop_domain:
        raise HTTPException(403, "Shop domain mismatch")

    if body.context is not None:
        session.context = ShopifyAssistantService.merge_context(
            session.context,
            body.context.model_dump(exclude_none=True),
        )
        session.shopper_email = body.context.shopper_email or session.shopper_email
        session.shopper_locale = body.context.shopper_locale or session.shopper_locale
        session.currency = body.context.currency or session.currency

    result = await ShopifyAssistantService.generate_reply(
        db,
        store=store,
        session=session,
        shopper_message=body.message,
    )
    return {"session_id": str(session.id), **result}


@router.get("/discount-requests")
async def list_discount_requests(
    client_id: str = Query(...),
    status: str = Query("pending"),
    current_client: dict = Depends(get_current_client),
    db: AsyncSession = Depends(get_session),
) -> dict:
    _ensure_client_access(client_id, current_client)
    query = select(ShopifyDiscountApproval).where(ShopifyDiscountApproval.client_id == uuid.UUID(client_id))
    if status:
        query = query.where(ShopifyDiscountApproval.status == status)
    result = await db.execute(query.order_by(ShopifyDiscountApproval.created_at.desc()))
    requests = result.scalars().all()
    return {"requests": [_serialize_discount_request(item) for item in requests]}


@router.post("/discount-requests/{request_id}/approve")
async def approve_discount_request(
    request_id: str,
    body: DiscountDecisionRequest,
    current_client: dict = Depends(get_current_client),
    db: AsyncSession = Depends(get_session),
) -> dict:
    approval = await _get_discount_request(db, request_id)
    _ensure_client_access(str(approval.client_id), current_client)

    approval.status = "approved"
    approval.code = body.code or approval.code or f"OMNI-{str(approval.id).split('-')[0].upper()}"
    approval.value = body.value if body.value is not None else approval.value
    approval.value_type = body.value_type or approval.value_type
    approval.merchant_note = body.merchant_note
    approval.approved_by = current_client.get("email")
    approval.approved_at = utcnow()
    approval.expires_at = body.expires_at or approval.expires_at

    store = await db.get(ShopifyStore, approval.store_id)
    if store and store.admin_access_token:
        try:
            created_discount = await ShopifyAPIService.create_basic_discount_code(store, approval)
        except ShopifyAPIError as exc:
            raise HTTPException(502, f"Failed to create Shopify discount code: {exc}") from exc

        approval.code = created_discount.get("code") or approval.code
        approval.cart_snapshot = {
            **(approval.cart_snapshot or {}),
            "shopify_discount_id": created_discount.get("id"),
            "shopify_discount_title": created_discount.get("title"),
            "shopify_discount_starts_at": created_discount.get("starts_at"),
            "shopify_discount_ends_at": created_discount.get("ends_at"),
        }

    await db.flush()
    await db.refresh(approval)
    return _serialize_discount_request(approval)


@router.post("/discount-requests/{request_id}/reject")
async def reject_discount_request(
    request_id: str,
    body: DiscountDecisionRequest,
    current_client: dict = Depends(get_current_client),
    db: AsyncSession = Depends(get_session),
) -> dict:
    approval = await _get_discount_request(db, request_id)
    _ensure_client_access(str(approval.client_id), current_client)

    approval.status = "rejected"
    approval.merchant_note = body.merchant_note
    approval.rejected_at = utcnow()
    await db.flush()
    await db.refresh(approval)
    return _serialize_discount_request(approval)


def _ensure_client_access(client_id: str, current_client: dict) -> None:
    if is_internal_staff_role(current_client.get("role")):
        return
    if client_id != current_client.get("client_id"):
        raise HTTPException(403, "Access denied")


async def _get_store_for_client(db: AsyncSession, client_id: str, allow_missing: bool = False) -> ShopifyStore | None:
    result = await db.execute(select(ShopifyStore).where(ShopifyStore.client_id == uuid.UUID(client_id)))
    store = result.scalar_one_or_none()
    if not store and not allow_missing:
        raise HTTPException(404, "Shopify store is not configured for this client")
    return store


async def _get_store_by_shop_domain(db: AsyncSession, shop_domain: str) -> ShopifyStore | None:
    result = await db.execute(select(ShopifyStore).where(ShopifyStore.shop_domain == shop_domain))
    return result.scalar_one_or_none()


async def _get_public_store(db: AsyncSession, *, client_id: str, shop_domain: str) -> ShopifyStore:
    result = await db.execute(
        select(ShopifyStore).where(
            ShopifyStore.client_id == uuid.UUID(client_id),
            ShopifyStore.shop_domain == shop_domain,
            ShopifyStore.assistant_enabled == True,
        )
    )
    store = result.scalar_one_or_none()
    if not store:
        raise HTTPException(404, "Storefront assistant is not enabled for this shop")
    return store


async def _get_public_session(db: AsyncSession, session_id: str) -> ShopifyAssistantSession:
    session = await db.get(ShopifyAssistantSession, uuid.UUID(session_id))
    if not session:
        raise HTTPException(404, "Session not found")
    return session


async def _authenticate_public_storefront_request(
    db: AsyncSession,
    authorization: str | None,
    shop_domain: str,
) -> tuple[ShopifyStore, dict[str, Any]]:
    try:
        normalized_shop = ShopifyOAuthService.normalize_shop_domain(shop_domain)
        token = ShopifyStorefrontBridgeService.extract_bearer_token(authorization)
        payload = ShopifyStorefrontBridgeService.decode_public_token(token)
    except (ShopifyOAuthError, ShopifyStorefrontBridgeError) as exc:
        if isinstance(exc, ShopifyStorefrontBridgeError):
            raise ShopifyStorefrontBridgeService.http_exception(exc) from exc
        raise HTTPException(400, str(exc)) from exc

    store = await _get_store_by_shop_domain(db, normalized_shop)
    if not store or not store.assistant_enabled or store.app_status != "installed":
        raise HTTPException(404, "Storefront assistant is not available for this shop")

    try:
        ShopifyStorefrontBridgeService.require_store_match(payload, store)
    except ShopifyStorefrontBridgeError as exc:
        raise ShopifyStorefrontBridgeService.http_exception(exc) from exc

    return store, payload


def _ensure_public_session_access(session: ShopifyAssistantSession, store: ShopifyStore) -> None:
    if session.store_id != store.id or session.client_id != store.client_id:
        raise HTTPException(403, "Session does not belong to this storefront")


async def _get_discount_request(db: AsyncSession, request_id: str) -> ShopifyDiscountApproval:
    approval = await db.get(ShopifyDiscountApproval, uuid.UUID(request_id))
    if not approval:
        raise HTTPException(404, "Discount request not found")
    return approval


async def _build_welcome_message(
    db: AsyncSession,
    client_id: str,
    context: StorefrontContext,
    store: ShopifyStore,
) -> str:
    result = await db.execute(select(AgentConfig).where(AgentConfig.client_id == uuid.UUID(client_id)))
    config = result.scalar_one_or_none()
    business_name = config.business_name if config and config.business_name else store.shop_domain.split(".")[0].replace("-", " ").title()
    agent_name = config.agent_name if config else "Ava"
    base = compose_greeting(
        industry_slug="ecommerce",
        agent_mode="ecommerce_assistant",
        agent_name=agent_name,
        business_name=business_name,
    )
    behavior_summary = ShopifyAssistantService.build_behavior_summary(context.model_dump(exclude_none=True))
    greeting = f"Hi! Welcome to {business_name}. {base} How can I help you today?"
    if behavior_summary:
        return f"{greeting} {behavior_summary}"
    return greeting


def _serialize_store(store: ShopifyStore) -> dict[str, Any]:
    return {
        "id": str(store.id),
        "client_id": str(store.client_id),
        "shop_domain": store.shop_domain,
        "shop_id": store.shop_id,
        "shop_name": store.shop_name,
        "shop_email": store.shop_email,
        "storefront_api_version": store.storefront_api_version,
        "app_status": store.app_status,
        "sales_channel_name": store.sales_channel_name,
        "assistant_enabled": store.assistant_enabled,
        "require_discount_approval": store.require_discount_approval,
        "allow_discount_requests": store.allow_discount_requests,
        "allowed_discount_types": store.allowed_discount_types,
        "granted_scopes": store.granted_scopes,
        "support_email": store.support_email,
        "support_policy": store.support_policy,
        "nav_config": store.nav_config,
        "checkout_config": store.checkout_config,
        "has_storefront_access_token": bool(store.storefront_access_token),
        "has_admin_access_token": bool(store.admin_access_token),
        "installed_at": store.installed_at.isoformat() if store.installed_at else None,
        "uninstalled_at": store.uninstalled_at.isoformat() if store.uninstalled_at else None,
        "last_install_error": store.last_install_error,
        "created_at": store.created_at.isoformat() if store.created_at else None,
        "updated_at": store.updated_at.isoformat() if store.updated_at else None,
    }


def _serialize_discount_request(approval: ShopifyDiscountApproval) -> dict[str, Any]:
    return {
        "id": str(approval.id),
        "client_id": str(approval.client_id),
        "store_id": str(approval.store_id),
        "session_id": str(approval.session_id) if approval.session_id else None,
        "status": approval.status,
        "discount_type": approval.discount_type,
        "value_type": approval.value_type,
        "value": approval.value,
        "currency": approval.currency,
        "code": approval.code,
        "reason": approval.reason,
        "merchant_note": approval.merchant_note,
        "approved_by": approval.approved_by,
        "approved_at": approval.approved_at.isoformat() if approval.approved_at else None,
        "rejected_at": approval.rejected_at.isoformat() if approval.rejected_at else None,
        "expires_at": approval.expires_at.isoformat() if approval.expires_at else None,
        "created_at": approval.created_at.isoformat() if approval.created_at else None,
    }


# ── Billing ──────────────────────────────────────────────────────────────────


class SubscribeRequest(BaseModel):
    plan: str = Field(..., description="Plan key: 'starter' or 'pro'")


@router.post("/billing/subscribe")
async def billing_subscribe(
    body: SubscribeRequest,
    client=Depends(get_current_client),
    db: AsyncSession = Depends(get_session),
):
    """Create a Shopify app subscription and return the confirmation URL."""
    store = await _get_store(client.id, db)
    if not store or not store.admin_access_token:
        raise HTTPException(404, "Shopify store not connected")

    try:
        result = await ShopifyBillingService.create_subscription(store, body.plan)
    except ShopifyBillingError as exc:
        raise HTTPException(400, str(exc))

    # Persist pending subscription info
    store.shopify_subscription_gid = result.get("subscription_gid")
    store.shopify_plan = body.plan
    store.shopify_subscription_status = "pending"
    store.shopify_billing_updated_at = utcnow()
    await db.commit()

    return {"confirmation_url": result["confirmation_url"], "subscription_gid": result.get("subscription_gid")}


@router.get("/billing/status")
async def billing_status(
    client=Depends(get_current_client),
    db: AsyncSession = Depends(get_session),
):
    """Return current Shopify subscription status."""
    store = await _get_store(client.id, db)
    if not store or not store.admin_access_token:
        raise HTTPException(404, "Shopify store not connected")

    try:
        sub = await ShopifyBillingService.get_active_subscription(store)
    except ShopifyBillingError:
        sub = None

    # Sync DB with live status
    if sub:
        store.shopify_subscription_gid = sub.get("id")
        store.shopify_plan = sub.get("plan")
        store.shopify_subscription_status = sub.get("status")
        store.shopify_billing_updated_at = utcnow()
        await db.commit()

    return {
        "plan": store.shopify_plan,
        "status": store.shopify_subscription_status,
        "subscription_gid": store.shopify_subscription_gid,
    }


@router.post("/billing/cancel")
async def billing_cancel(
    client=Depends(get_current_client),
    db: AsyncSession = Depends(get_session),
):
    """Cancel the active Shopify app subscription."""
    store = await _get_store(client.id, db)
    if not store or not store.shopify_subscription_gid:
        raise HTTPException(404, "No active subscription")

    try:
        await ShopifyBillingService.cancel_subscription(store, store.shopify_subscription_gid)
    except ShopifyBillingError as exc:
        raise HTTPException(400, str(exc))

    store.shopify_subscription_status = "cancelled"
    store.shopify_billing_updated_at = utcnow()
    await db.commit()

    return {"status": "cancelled"}


async def _get_store(client_id: uuid.UUID, db: AsyncSession) -> ShopifyStore | None:
    result = await db.execute(select(ShopifyStore).where(ShopifyStore.client_id == client_id))
    return result.scalar_one_or_none()

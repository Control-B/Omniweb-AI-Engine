from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt as pyjwt
from fastapi import HTTPException

from app.core.config import get_settings
from app.models.models import ShopifyAssistantSession, ShopifyStore
from app.services.shopify_assistant_service import ShopifyAssistantService, utcnow

settings = get_settings()
_SIGNING_KEY = hashlib.sha256(settings.SECRET_KEY.encode()).digest()


class ShopifyStorefrontBridgeError(Exception):
    """Raised when storefront bridge token validation fails."""


class ShopifyStorefrontBridgeService:
    """Issues and validates short-lived public storefront tokens."""

    AUDIENCE = "shopify-storefront"
    PURPOSE = "shopify_storefront_bridge"
    TOKEN_TTL_MINUTES = 30

    @staticmethod
    def issue_public_token(store: ShopifyStore) -> dict[str, Any]:
        issued_at = utcnow()
        expires_at = issued_at + timedelta(minutes=ShopifyStorefrontBridgeService.TOKEN_TTL_MINUTES)
        payload = {
            "sub": str(store.id),
            "client_id": str(store.client_id),
            "shop": store.shop_domain,
            "purpose": ShopifyStorefrontBridgeService.PURPOSE,
            "aud": ShopifyStorefrontBridgeService.AUDIENCE,
            "iat": issued_at,
            "exp": expires_at,
        }
        token = pyjwt.encode(payload, _SIGNING_KEY, algorithm="HS256")
        return {"token": token, "expires_at": expires_at.isoformat()}

    @staticmethod
    def decode_public_token(token: str) -> dict[str, Any]:
        if not token:
            raise ShopifyStorefrontBridgeError("Missing storefront token")
        try:
            payload = pyjwt.decode(
                token,
                _SIGNING_KEY,
                algorithms=["HS256"],
                audience=ShopifyStorefrontBridgeService.AUDIENCE,
            )
        except pyjwt.ExpiredSignatureError as exc:
            raise ShopifyStorefrontBridgeError("Storefront token expired") from exc
        except pyjwt.InvalidTokenError as exc:
            raise ShopifyStorefrontBridgeError("Invalid storefront token") from exc

        if payload.get("purpose") != ShopifyStorefrontBridgeService.PURPOSE:
            raise ShopifyStorefrontBridgeError("Invalid storefront token purpose")
        return payload

    @staticmethod
    def require_store_match(payload: dict[str, Any], store: ShopifyStore) -> None:
        if payload.get("sub") != str(store.id) or payload.get("client_id") != str(store.client_id):
            raise ShopifyStorefrontBridgeError("Storefront token does not match this store")
        if payload.get("shop") != store.shop_domain:
            raise ShopifyStorefrontBridgeError("Storefront token shop mismatch")

    @staticmethod
    def extract_bearer_token(authorization: str | None) -> str:
        if not authorization:
            raise ShopifyStorefrontBridgeError("Missing Authorization header")
        prefix = "Bearer "
        if not authorization.startswith(prefix):
            raise ShopifyStorefrontBridgeError("Authorization header must be a bearer token")
        return authorization[len(prefix):].strip()

    @staticmethod
    def bootstrap_payload(
        *,
        store: ShopifyStore,
        greeting: str,
        public_token: dict[str, Any],
        telephony_config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "assistant_enabled": store.assistant_enabled,
            "shop_domain": store.shop_domain,
            "client_id": str(store.client_id),
            "greeting": greeting,
            "support_email": store.support_email,
            "nav_config": store.nav_config,
            "checkout_config": store.checkout_config,
            "telephony_config": telephony_config or {},
            "public_token": public_token["token"],
            "public_token_expires_at": public_token["expires_at"],
            "endpoints": {
                "start_session": "/api/shopify/public/sessions",
                "voice_session": "/api/shopify/public/voice/session",
                "phone_call": "/api/retell/phone-call",
                "update_context": "/api/shopify/public/sessions/{session_id}/context",
                "send_message": "/api/shopify/public/sessions/{session_id}/reply",
                "track_event": "/api/shopify/public/sessions/{session_id}/events",
            },
        }

    @staticmethod
    def summarize_context(session: ShopifyAssistantSession) -> dict[str, Any]:
        return {
            "session_id": str(session.id),
            "current_page_url": (session.context or {}).get("current_page_url"),
            "current_product": (session.context or {}).get("current_product"),
            "search_query": (session.context or {}).get("search_query"),
            "cart_total": (session.context or {}).get("cart_total"),
            "viewed_products_count": len((session.context or {}).get("viewed_products") or []),
            "recent_events_count": len((session.context or {}).get("recent_events") or []),
            "last_intent": session.last_intent,
            "last_seen_at": session.last_seen_at.isoformat() if session.last_seen_at else None,
        }

    @staticmethod
    def http_exception(exc: ShopifyStorefrontBridgeError) -> HTTPException:
        return HTTPException(status_code=401, detail=str(exc))

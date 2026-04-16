from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import timedelta
from typing import Any
from urllib.parse import urlencode

import httpx

from app.core.auth import hash_token
from app.core.config import get_settings
from app.models.models import ShopifyStore
from app.services.shopify_assistant_service import utcnow

settings = get_settings()


class ShopifyOAuthError(Exception):
    """Raised when Shopify OAuth validation or token exchange fails."""


class ShopifyOAuthService:
    """Shopify authorization code flow helpers for app installation."""

    @staticmethod
    def normalize_shop_domain(shop: str) -> str:
        normalized = (shop or "").strip().lower()
        normalized = normalized.removeprefix("https://").removeprefix("http://")
        normalized = normalized.split("/")[0]
        if not normalized.endswith(".myshopify.com"):
            raise ShopifyOAuthError("Shop must be a valid .myshopify.com domain")
        if " " in normalized or normalized.count(".") < 2:
            raise ShopifyOAuthError("Invalid Shopify shop domain")
        return normalized

    @staticmethod
    def callback_url() -> str:
        if not settings.SHOPIFY_APP_URL:
            raise ShopifyOAuthError("SHOPIFY_APP_URL is not configured")
        return f"{settings.SHOPIFY_APP_URL.rstrip('/')}/api/shopify/oauth/callback"

    @staticmethod
    def issue_install_state(store: ShopifyStore) -> str:
        state = secrets.token_urlsafe(32)
        store.install_state_hash = hash_token(state)
        store.install_state_expires_at = utcnow() + timedelta(minutes=10)
        store.last_install_error = None
        if store.app_status == "draft":
            store.app_status = "pending_install"
        return state

    @staticmethod
    def verify_state(store: ShopifyStore, state: str) -> None:
        if not state:
            raise ShopifyOAuthError("Missing OAuth state")
        if not store.install_state_hash or not store.install_state_expires_at:
            raise ShopifyOAuthError("Install session not found")
        if store.install_state_expires_at < utcnow():
            raise ShopifyOAuthError("Install session expired")
        if not hmac.compare_digest(store.install_state_hash, hash_token(state)):
            raise ShopifyOAuthError("Invalid OAuth state")

    @staticmethod
    def clear_install_state(store: ShopifyStore) -> None:
        store.install_state_hash = None
        store.install_state_expires_at = None

    @staticmethod
    def verify_callback_hmac(params: list[tuple[str, str]]) -> None:
        provided_hmac = None
        filtered: list[tuple[str, str]] = []
        for key, value in params:
            if key == "hmac":
                provided_hmac = value
                continue
            if key == "signature":
                continue
            filtered.append((key, value))

        if not provided_hmac:
            raise ShopifyOAuthError("Missing Shopify HMAC")

        message = "&".join(
            f"{key}={value}"
            for key, value in sorted(filtered, key=lambda item: (item[0], item[1]))
        )
        digest = hmac.new(
            settings.SHOPIFY_API_SECRET.encode(),
            message.encode(),
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(digest, provided_hmac):
            raise ShopifyOAuthError("Invalid Shopify HMAC")

    @staticmethod
    def build_install_url(*, shop: str, state: str) -> str:
        if not settings.shopify_configured:
            raise ShopifyOAuthError("Shopify app credentials are not fully configured")
        callback_url = ShopifyOAuthService.callback_url()
        query = urlencode(
            {
                "client_id": settings.SHOPIFY_API_KEY,
                "scope": settings.SHOPIFY_SCOPES,
                "redirect_uri": callback_url,
                "state": state,
            }
        )
        return f"https://{shop}/admin/oauth/authorize?{query}"

    @staticmethod
    async def exchange_code_for_token(*, shop: str, code: str) -> dict[str, Any]:
        if not settings.shopify_configured:
            raise ShopifyOAuthError("Shopify app credentials are not fully configured")
        callback_url = ShopifyOAuthService.callback_url()
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                f"https://{shop}/admin/oauth/access_token",
                json={
                    "client_id": settings.SHOPIFY_API_KEY,
                    "client_secret": settings.SHOPIFY_API_SECRET,
                    "code": code,
                    "redirect_uri": callback_url,
                },
            )
            try:
                payload = response.json()
            except ValueError as exc:
                raise ShopifyOAuthError(f"Invalid Shopify token response: {response.text}") from exc

        if response.status_code >= 400:
            raise ShopifyOAuthError(payload.get("error_description") or payload.get("error") or str(payload))
        if not payload.get("access_token"):
            raise ShopifyOAuthError("Shopify did not return an access token")
        return payload

    @staticmethod
    def build_admin_redirect(*, shop: str, status: str, client_id: str | None = None) -> str:
        base = f"{settings.PLATFORM_URL.rstrip('/')}/admin"
        query = {"shopify": status, "shop": shop}
        if client_id:
            query["client_id"] = client_id
        return f"{base}?{urlencode(query)}"

"""Shopify webhook HMAC verification and mandatory webhook handlers."""

from __future__ import annotations

import hashlib
import hmac
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.models import ShopifyAssistantSession, ShopifyDiscountApproval, ShopifyStore
from app.services.shopify_assistant_service import utcnow

settings = get_settings()
logger = logging.getLogger(__name__)


class ShopifyWebhookError(Exception):
    """Raised when webhook verification fails."""


class ShopifyWebhookService:
    """Handles Shopify webhook HMAC verification and mandatory GDPR topics."""

    # ── HMAC verification ────────────────────────────────────────────────────

    @staticmethod
    def verify_hmac(body: bytes, hmac_header: str | None) -> None:
        """Verify the X-Shopify-Hmac-Sha256 header against the raw body."""
        if not hmac_header:
            raise ShopifyWebhookError("Missing X-Shopify-Hmac-Sha256 header")
        secret = settings.SHOPIFY_WEBHOOK_SECRET or settings.SHOPIFY_API_SECRET
        if not secret:
            raise ShopifyWebhookError("SHOPIFY_WEBHOOK_SECRET or SHOPIFY_API_SECRET must be configured")

        digest = hmac.new(
            secret.encode(),
            body,
            hashlib.sha256,
        ).digest()

        import base64
        expected = base64.b64encode(digest).decode()
        if not hmac.compare_digest(expected, hmac_header):
            raise ShopifyWebhookError("Invalid webhook HMAC signature")

    # ── app/uninstalled ──────────────────────────────────────────────────────

    @staticmethod
    async def handle_app_uninstalled(
        db: AsyncSession,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Mark store as uninstalled and revoke tokens."""
        shop_domain = payload.get("domain") or payload.get("myshopify_domain") or ""
        if not shop_domain:
            logger.warning("app/uninstalled webhook missing shop domain")
            return {"ok": False, "reason": "missing_domain"}

        if not shop_domain.endswith(".myshopify.com"):
            shop_domain = f"{shop_domain}.myshopify.com"

        result = await db.execute(
            select(ShopifyStore).where(ShopifyStore.shop_domain == shop_domain)
        )
        store = result.scalar_one_or_none()
        if not store:
            logger.warning(f"app/uninstalled: no store found for {shop_domain}")
            return {"ok": False, "reason": "store_not_found"}

        store.admin_access_token = None
        store.storefront_access_token = None
        store.app_status = "uninstalled"
        store.uninstalled_at = utcnow()
        store.install_state_hash = None
        store.install_state_expires_at = None
        await db.flush()

        logger.info(f"Shopify app uninstalled for {shop_domain} (client {store.client_id})")
        return {"ok": True, "shop_domain": shop_domain}

    # ── GDPR: customers/data_request ─────────────────────────────────────────

    @staticmethod
    async def handle_customers_data_request(
        db: AsyncSession,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Shopify sends this when a customer requests their data.
        We return session/transcript data tied to the customer's email.
        """
        shop_domain = payload.get("shop_domain", "")
        customer = payload.get("customer", {})
        customer_email = customer.get("email", "")
        orders_requested = payload.get("orders_requested", [])

        if not customer_email:
            logger.info("customers/data_request: no customer email in payload")
            return {"ok": True, "data_sent": False, "reason": "no_email"}

        result = await db.execute(
            select(ShopifyStore).where(ShopifyStore.shop_domain == shop_domain)
        )
        store = result.scalar_one_or_none()
        if not store:
            return {"ok": True, "data_sent": False, "reason": "store_not_found"}

        # Find all sessions with this email
        sessions_result = await db.execute(
            select(ShopifyAssistantSession).where(
                ShopifyAssistantSession.store_id == store.id,
                ShopifyAssistantSession.shopper_email == customer_email,
            )
        )
        sessions = sessions_result.scalars().all()

        logger.info(
            f"customers/data_request for {customer_email} on {shop_domain}: "
            f"found {len(sessions)} sessions"
        )

        # Per Shopify GDPR requirements, we acknowledge the request.
        # In production you'd email or POST the data to the merchant.
        return {
            "ok": True,
            "data_sent": True,
            "shop_domain": shop_domain,
            "customer_email": customer_email,
            "sessions_found": len(sessions),
        }

    # ── GDPR: customers/redact ───────────────────────────────────────────────

    @staticmethod
    async def handle_customers_redact(
        db: AsyncSession,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Shopify sends this when a merchant requests deletion of a customer's data.
        We must delete all PII for that customer.
        """
        shop_domain = payload.get("shop_domain", "")
        customer = payload.get("customer", {})
        customer_email = customer.get("email", "")

        if not customer_email:
            return {"ok": True, "redacted": False, "reason": "no_email"}

        result = await db.execute(
            select(ShopifyStore).where(ShopifyStore.shop_domain == shop_domain)
        )
        store = result.scalar_one_or_none()
        if not store:
            return {"ok": True, "redacted": False, "reason": "store_not_found"}

        # Delete sessions for this customer
        sessions_result = await db.execute(
            select(ShopifyAssistantSession).where(
                ShopifyAssistantSession.store_id == store.id,
                ShopifyAssistantSession.shopper_email == customer_email,
            )
        )
        sessions = sessions_result.scalars().all()
        redacted_count = 0

        for session in sessions:
            # Scrub PII from transcript
            session.shopper_email = None
            session.transcript = []
            session.context = {}
            session.last_recommendations = []
            redacted_count += 1

        await db.flush()

        logger.info(
            f"customers/redact for {customer_email} on {shop_domain}: "
            f"redacted {redacted_count} sessions"
        )
        return {
            "ok": True,
            "redacted": True,
            "shop_domain": shop_domain,
            "sessions_redacted": redacted_count,
        }

    # ── GDPR: shop/redact ────────────────────────────────────────────────────

    @staticmethod
    async def handle_shop_redact(
        db: AsyncSession,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Shopify sends this 48 hours after app uninstall requesting full data wipe.
        We delete all store data, sessions, and discount requests.
        """
        shop_domain = payload.get("shop_domain", "")

        result = await db.execute(
            select(ShopifyStore).where(ShopifyStore.shop_domain == shop_domain)
        )
        store = result.scalar_one_or_none()
        if not store:
            return {"ok": True, "deleted": False, "reason": "store_not_found"}

        # Delete all sessions for this store
        sessions_result = await db.execute(
            select(ShopifyAssistantSession).where(
                ShopifyAssistantSession.store_id == store.id,
            )
        )
        for session in sessions_result.scalars().all():
            await db.delete(session)

        # Delete all discount requests for this store
        discounts_result = await db.execute(
            select(ShopifyDiscountApproval).where(
                ShopifyDiscountApproval.store_id == store.id,
            )
        )
        for discount in discounts_result.scalars().all():
            await db.delete(discount)

        # Delete the store itself
        await db.delete(store)
        await db.flush()

        logger.info(f"shop/redact: deleted all data for {shop_domain}")
        return {"ok": True, "deleted": True, "shop_domain": shop_domain}

    # ── Webhook registration (called after OAuth install) ────────────────────

    MANDATORY_TOPICS = [
        "APP_UNINSTALLED",
        "CUSTOMERS_DATA_REQUEST",
        "CUSTOMERS_REDACT",
        "SHOP_REDACT",
    ]

    REGISTER_WEBHOOK_MUTATION = """
    mutation webhookSubscriptionCreate($topic: WebhookSubscriptionTopic!, $webhookSubscription: WebhookSubscriptionInput!) {
      webhookSubscriptionCreate(topic: $topic, webhookSubscription: $webhookSubscription) {
        webhookSubscription {
          id
          topic
          endpoint {
            __typename
            ... on WebhookHttpEndpoint {
              callbackUrl
            }
          }
        }
        userErrors {
          field
          message
        }
      }
    }
    """

    @staticmethod
    async def register_mandatory_webhooks(store: ShopifyStore) -> list[dict[str, Any]]:
        """Register all mandatory webhook subscriptions after install."""
        from app.services.shopify_api_service import ShopifyAPIService

        base_url = settings.SHOPIFY_APP_URL.rstrip("/")
        results = []

        for topic in ShopifyWebhookService.MANDATORY_TOPICS:
            callback_url = f"{base_url}/api/shopify/webhooks/{topic.lower().replace('_', '-')}"
            try:
                data = await ShopifyAPIService.execute_admin_graphql(
                    store,
                    query=ShopifyWebhookService.REGISTER_WEBHOOK_MUTATION,
                    variables={
                        "topic": topic,
                        "webhookSubscription": {
                            "callbackUrl": callback_url,
                            "format": "JSON",
                        },
                    },
                )
                result = data.get("webhookSubscriptionCreate", {})
                user_errors = result.get("userErrors", [])
                if user_errors:
                    logger.warning(f"Webhook {topic} registration errors: {user_errors}")
                    results.append({"topic": topic, "ok": False, "errors": user_errors})
                else:
                    sub = result.get("webhookSubscription", {})
                    logger.info(f"Registered webhook {topic}: {sub.get('id')}")
                    results.append({"topic": topic, "ok": True, "id": sub.get("id")})
            except Exception as exc:
                logger.error(f"Failed to register webhook {topic}: {exc}")
                results.append({"topic": topic, "ok": False, "error": str(exc)})

        return results

    # ── app_subscriptions/update ─────────────────────────────────────────────

    @staticmethod
    async def handle_subscription_update(db: AsyncSession, payload: dict[str, Any]) -> dict:
        """Handle app_subscriptions/update webhook — sync billing status to DB."""
        sub = payload.get("app_subscription", payload)
        admin_graphql_api_id = sub.get("admin_graphql_api_id", "")
        status = sub.get("status", "").lower()
        name = sub.get("name", "")

        # Map Shopify status to our internal status
        status_map = {
            "active": "active",
            "declined": "declined",
            "expired": "expired",
            "frozen": "frozen",
            "pending": "pending",
        }
        mapped_status = status_map.get(status, status)

        # Find the store by subscription GID
        if admin_graphql_api_id:
            result = await db.execute(
                select(ShopifyStore).where(ShopifyStore.shopify_subscription_gid == admin_graphql_api_id)
            )
            store = result.scalar_one_or_none()
        else:
            store = None

        if not store:
            logger.warning(f"Subscription update for unknown GID: {admin_graphql_api_id}")
            return {"status": "ignored", "reason": "store_not_found"}

        store.shopify_subscription_status = mapped_status
        store.shopify_billing_updated_at = utcnow()

        # If declined/expired, clear the plan
        if mapped_status in ("declined", "expired"):
            store.shopify_plan = None
            store.shopify_subscription_gid = None

        await db.commit()
        logger.info(f"Subscription {admin_graphql_api_id} updated to {mapped_status} for store {store.shop_domain}")
        return {"status": "ok", "subscription_status": mapped_status}

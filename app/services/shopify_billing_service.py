"""Shopify Billing API — recurring app subscriptions via Shopify's GraphQL Admin API.

This replaces Stripe for Shopify merchants, using Shopify's native billing
so charges appear on the merchant's Shopify invoice.
"""

from __future__ import annotations

import logging
from typing import Any

from app.core.config import get_settings
from app.models.models import ShopifyStore
from app.services.shopify_api_service import ShopifyAPIError, ShopifyAPIService

settings = get_settings()
logger = logging.getLogger(__name__)


# ── Plan configuration ──────────────────────────────────────────────────────

SHOPIFY_PLANS: dict[str, dict[str, Any]] = {
    "starter": {"name": "Omniweb Starter", "amount": "29.00", "currency": "USD"},
    "pro": {"name": "Omniweb Pro", "amount": "99.00", "currency": "USD"},
}


class ShopifyBillingError(Exception):
    """Raised when a billing operation fails."""


class ShopifyBillingService:
    """Manages Shopify app subscriptions (recurring billing)."""

    # ── Create subscription ──────────────────────────────────────────────────

    CREATE_SUBSCRIPTION_MUTATION = """
    mutation AppSubscriptionCreate(
      $name: String!
      $lineItems: [AppSubscriptionLineItemInput!]!
      $returnUrl: URL!
      $test: Boolean
    ) {
      appSubscriptionCreate(
        name: $name
        lineItems: $lineItems
        returnUrl: $returnUrl
        test: $test
      ) {
        userErrors { field message }
        confirmationUrl
        appSubscription { id status }
      }
    }
    """

    @staticmethod
    async def create_subscription(
        store: ShopifyStore,
        *,
        plan: str,
        return_url: str,
    ) -> dict[str, Any]:
        """Create a Shopify app subscription and return the confirmation URL."""
        plan_config = SHOPIFY_PLANS.get(plan)
        if not plan_config:
            raise ShopifyBillingError(f"Unknown plan: {plan}")

        is_test = not settings.is_production

        data = await ShopifyAPIService.execute_admin_graphql(
            store,
            query=ShopifyBillingService.CREATE_SUBSCRIPTION_MUTATION,
            variables={
                "name": plan_config["name"],
                "lineItems": [
                    {
                        "plan": {
                            "appRecurringPricingDetails": {
                                "price": {
                                    "amount": plan_config["amount"],
                                    "currencyCode": plan_config["currency"],
                                },
                                "interval": "EVERY_30_DAYS",
                            },
                        },
                    },
                ],
                "returnUrl": return_url,
                "test": is_test,
            },
        )

        result = data.get("appSubscriptionCreate", {})
        user_errors = result.get("userErrors", [])
        if user_errors:
            msg = "; ".join(e.get("message", "Unknown error") for e in user_errors)
            raise ShopifyBillingError(msg)

        subscription = result.get("appSubscription") or {}
        return {
            "confirmation_url": result.get("confirmationUrl"),
            "subscription_gid": subscription.get("id", ""),
            "status": subscription.get("status", ""),
        }

    # ── Get active subscription ──────────────────────────────────────────────

    GET_ACTIVE_SUBSCRIPTION_QUERY = """
    query {
      currentAppInstallation {
        activeSubscriptions {
          id
          name
          status
          currentPeriodEnd
          lineItems {
            plan {
              pricingDetails {
                ... on AppRecurringPricing {
                  price { amount currencyCode }
                  interval
                }
              }
            }
          }
        }
      }
    }
    """

    @staticmethod
    async def get_active_subscription(store: ShopifyStore) -> dict[str, Any] | None:
        """Fetch the currently active subscription for the app."""
        data = await ShopifyAPIService.execute_admin_graphql(
            store,
            query=ShopifyBillingService.GET_ACTIVE_SUBSCRIPTION_QUERY,
        )

        subs = (
            data.get("currentAppInstallation", {})
            .get("activeSubscriptions", [])
        )
        if not subs:
            return None

        sub = subs[0]
        line_items = sub.get("lineItems", [])
        pricing = {}
        if line_items:
            pricing = (
                line_items[0].get("plan", {}).get("pricingDetails", {})
            )
        price_info = pricing.get("price", {})

        return {
            "id": sub.get("id"),
            "name": sub.get("name"),
            "status": sub.get("status"),
            "current_period_end": sub.get("currentPeriodEnd"),
            "amount": float(price_info.get("amount", 0)),
            "currency_code": price_info.get("currencyCode", "USD"),
        }

    # ── Cancel subscription ──────────────────────────────────────────────────

    CANCEL_SUBSCRIPTION_MUTATION = """
    mutation AppSubscriptionCancel($id: ID!) {
      appSubscriptionCancel(id: $id) {
        userErrors { field message }
        appSubscription { id status }
      }
    }
    """

    @staticmethod
    async def cancel_subscription(
        store: ShopifyStore,
        subscription_gid: str,
    ) -> dict[str, Any]:
        """Cancel an active Shopify app subscription."""
        data = await ShopifyAPIService.execute_admin_graphql(
            store,
            query=ShopifyBillingService.CANCEL_SUBSCRIPTION_MUTATION,
            variables={"id": subscription_gid},
        )

        result = data.get("appSubscriptionCancel", {})
        user_errors = result.get("userErrors", [])
        if user_errors:
            msg = "; ".join(e.get("message", "Unknown error") for e in user_errors)
            raise ShopifyBillingError(msg)

        subscription = result.get("appSubscription") or {}
        return {
            "id": subscription.get("id"),
            "status": subscription.get("status"),
        }

    # ── Helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def plan_from_subscription_name(name: str) -> str:
        """Derive plan slug from Shopify subscription name."""
        lower = (name or "").lower()
        if "pro" in lower:
            return "pro"
        if "starter" in lower:
            return "starter"
        return "free"

    @staticmethod
    def map_shopify_status(status: str) -> str:
        """Map Shopify subscription status to our internal status."""
        mapping = {
            "ACTIVE": "active",
            "PENDING": "trialing",
            "FROZEN": "past_due",
            "CANCELLED": "canceled",
            "EXPIRED": "canceled",
            "DECLINED": "none",
        }
        return mapping.get(status.upper(), "none")

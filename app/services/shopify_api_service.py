from __future__ import annotations

from datetime import timedelta
from typing import Any

import httpx

from app.core.config import get_settings
from app.models.models import ShopifyDiscountApproval, ShopifyStore
from app.services.shopify_assistant_service import utcnow

settings = get_settings()


class ShopifyAPIError(Exception):
    """Raised when a Shopify API request fails."""


class ShopifyAPIService:
    """Thin Shopify Admin API wrapper for approved commerce actions."""

    GET_SHOP_IDENTITY_QUERY = """
    query GetShopIdentity {
      shop {
        id
        name
        email
        primaryDomain {
          host
          url
        }
      }
    }
    """

    CREATE_STOREFRONT_ACCESS_TOKEN_MUTATION = """
    mutation CreateStorefrontAccessToken($input: StorefrontAccessTokenInput!) {
      storefrontAccessTokenCreate(input: $input) {
        storefrontAccessToken {
          accessToken
          title
          accessScopes {
            handle
          }
        }
        userErrors {
          field
          message
        }
      }
    }
    """

    CREATE_BASIC_DISCOUNT_MUTATION = """
    mutation CreateBasicDiscountCode($basicCodeDiscount: DiscountCodeBasicInput!) {
      discountCodeBasicCreate(basicCodeDiscount: $basicCodeDiscount) {
        codeDiscountNode {
          id
          codeDiscount {
            ... on DiscountCodeBasic {
              title
              startsAt
              endsAt
              codes(first: 1) {
                nodes {
                  code
                }
              }
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
    async def execute_admin_graphql(
        store: ShopifyStore,
        *,
        query: str,
        variables: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not store.admin_access_token:
            raise ShopifyAPIError("Missing Shopify admin access token")

        api_version = store.storefront_api_version or settings.SHOPIFY_API_VERSION
        url = f"https://{store.shop_domain}/admin/api/{api_version}/graphql.json"
        headers = {
            "Content-Type": "application/json",
            "X-Shopify-Access-Token": store.admin_access_token,
        }

        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                url,
                headers=headers,
                json={"query": query, "variables": variables or {}},
            )
            try:
                payload = response.json()
            except ValueError as exc:
                raise ShopifyAPIError(f"Invalid Shopify response: {response.text}") from exc

        if response.status_code >= 400:
            raise ShopifyAPIError(payload.get("errors") or payload)
        if payload.get("errors"):
            raise ShopifyAPIError(payload["errors"])
        return payload.get("data", {})

    @staticmethod
    async def create_basic_discount_code(
        store: ShopifyStore,
        approval: ShopifyDiscountApproval,
    ) -> dict[str, Any]:
        code = approval.code or f"OMNI-{str(approval.id).split('-')[0].upper()}"
        starts_at = utcnow()
        ends_at = approval.expires_at or (starts_at + timedelta(hours=2))
        percentage_value = float(approval.value or 0.0) / 100.0
        title = f"Omniweb approved discount {code}"

        variables = {
            "basicCodeDiscount": {
                "title": title,
                "code": code,
                "startsAt": starts_at.isoformat(),
                "endsAt": ends_at.isoformat(),
                "customerGets": {
                    "value": {"percentage": percentage_value},
                    "items": {"all": True},
                },
                "appliesOncePerCustomer": True,
                "usageLimit": 1,
            }
        }

        data = await ShopifyAPIService.execute_admin_graphql(
            store,
            query=ShopifyAPIService.CREATE_BASIC_DISCOUNT_MUTATION,
            variables=variables,
        )
        result = data.get("discountCodeBasicCreate") or {}
        user_errors = result.get("userErrors") or []
        if user_errors:
            message = "; ".join(
                error.get("message", "Unknown Shopify discount error") for error in user_errors
            )
            raise ShopifyAPIError(message)

        node = result.get("codeDiscountNode") or {}
        code_discount = node.get("codeDiscount") or {}
        codes = ((code_discount.get("codes") or {}).get("nodes") or [])
        return {
            "id": node.get("id"),
            "code": (codes[0] or {}).get("code") if codes else code,
            "title": code_discount.get("title") or title,
            "starts_at": code_discount.get("startsAt") or starts_at.isoformat(),
            "ends_at": code_discount.get("endsAt") or ends_at.isoformat(),
        }

    @staticmethod
    async def get_shop_identity(store: ShopifyStore) -> dict[str, Any]:
        data = await ShopifyAPIService.execute_admin_graphql(
            store,
            query=ShopifyAPIService.GET_SHOP_IDENTITY_QUERY,
        )
        return data.get("shop") or {}

    @staticmethod
    async def create_storefront_access_token(store: ShopifyStore, *, title: str) -> dict[str, Any]:
        data = await ShopifyAPIService.execute_admin_graphql(
            store,
            query=ShopifyAPIService.CREATE_STOREFRONT_ACCESS_TOKEN_MUTATION,
            variables={"input": {"title": title}},
        )
        result = data.get("storefrontAccessTokenCreate") or {}
        user_errors = result.get("userErrors") or []
        if user_errors:
            message = "; ".join(
                error.get("message", "Unknown storefront token error") for error in user_errors
            )
            raise ShopifyAPIError(message)
        token = result.get("storefrontAccessToken") or {}
        return {
            "access_token": token.get("accessToken"),
            "title": token.get("title"),
            "access_scopes": [
                scope.get("handle")
                for scope in token.get("accessScopes") or []
                if scope.get("handle")
            ],
        }

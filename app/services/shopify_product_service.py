"""Query the Shopify Storefront GraphQL API for products and collections."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.core.config import get_settings
from app.models.models import ShopifyStore

settings = get_settings()
logger = logging.getLogger(__name__)


class ShopifyProductServiceError(Exception):
    pass


class ShopifyProductService:
    """Fetches live product/collection data from the Shopify Storefront API."""

    SEARCH_PRODUCTS_QUERY = """
    query SearchProducts($query: String!, $first: Int!) {
      search(query: $query, first: $first, types: PRODUCT) {
        edges {
          node {
            ... on Product {
              id
              title
              handle
              productType
              vendor
              tags
              availableForSale
              onlineStoreUrl
              priceRange {
                minVariantPrice {
                  amount
                  currencyCode
                }
              }
              compareAtPriceRange {
                minVariantPrice {
                  amount
                  currencyCode
                }
              }
              images(first: 1) {
                edges {
                  node {
                    url
                    altText
                  }
                }
              }
              collections(first: 3) {
                edges {
                  node {
                    title
                  }
                }
              }
            }
          }
        }
      }
    }
    """

    FEATURED_PRODUCTS_QUERY = """
    query FeaturedProducts($first: Int!) {
      products(first: $first, sortKey: BEST_SELLING) {
        edges {
          node {
            id
            title
            handle
            productType
            vendor
            tags
            availableForSale
            onlineStoreUrl
            priceRange {
              minVariantPrice {
                amount
                currencyCode
              }
            }
            compareAtPriceRange {
              minVariantPrice {
                amount
                currencyCode
              }
            }
            images(first: 1) {
              edges {
                node {
                  url
                  altText
                }
              }
            }
            collections(first: 3) {
              edges {
                node {
                  title
                }
              }
            }
          }
        }
      }
    }
    """

    @staticmethod
    async def _execute_storefront_graphql(
        store: ShopifyStore,
        *,
        query: str,
        variables: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        from app.services.shopify_crypto_service import ShopifyCryptoService

        token = ShopifyCryptoService.decrypt(store.storefront_access_token)
        if not token:
            raise ShopifyProductServiceError("Missing Storefront access token")

        api_version = store.storefront_api_version or settings.SHOPIFY_API_VERSION
        url = f"https://{store.shop_domain}/api/{api_version}/graphql.json"
        headers = {
            "Content-Type": "application/json",
            "X-Shopify-Storefront-Access-Token": token,
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                url,
                headers=headers,
                json={"query": query, "variables": variables or {}},
            )
            try:
                payload = resp.json()
            except ValueError as exc:
                raise ShopifyProductServiceError(f"Invalid Storefront response: {resp.text}") from exc

        if resp.status_code >= 400:
            raise ShopifyProductServiceError(payload.get("errors") or payload)
        if payload.get("errors"):
            raise ShopifyProductServiceError(payload["errors"])
        return payload.get("data", {})

    @staticmethod
    def _normalize_storefront_product(node: dict[str, Any]) -> dict[str, Any]:
        price_range = node.get("priceRange", {}).get("minVariantPrice", {})
        compare_range = node.get("compareAtPriceRange", {}).get("minVariantPrice", {})
        images = node.get("images", {}).get("edges", [])
        collections = node.get("collections", {}).get("edges", [])
        return {
            "id": node.get("id", ""),
            "title": node.get("title", ""),
            "handle": node.get("handle", ""),
            "url": node.get("onlineStoreUrl") or f"/products/{node.get('handle', '')}",
            "product_type": node.get("productType", ""),
            "vendor": node.get("vendor", ""),
            "tags": node.get("tags", []),
            "collections": [e["node"]["title"] for e in collections if e.get("node")],
            "price": float(price_range.get("amount", 0)),
            "currency": price_range.get("currencyCode", "USD"),
            "compare_at_price": float(compare_range.get("amount", 0)) if compare_range.get("amount") else None,
            "available": node.get("availableForSale", True),
            "image_url": images[0]["node"]["url"] if images else None,
        }

    @staticmethod
    async def search_products(
        store: ShopifyStore,
        query: str,
        *,
        limit: int = 8,
    ) -> list[dict[str, Any]]:
        """Search products via the Storefront API."""
        data = await ShopifyProductService._execute_storefront_graphql(
            store,
            query=ShopifyProductService.SEARCH_PRODUCTS_QUERY,
            variables={"query": query, "first": min(limit, 20)},
        )
        edges = data.get("search", {}).get("edges", [])
        return [
            ShopifyProductService._normalize_storefront_product(edge["node"])
            for edge in edges
            if edge.get("node")
        ]

    @staticmethod
    async def get_featured_products(
        store: ShopifyStore,
        *,
        limit: int = 6,
    ) -> list[dict[str, Any]]:
        """Get best-selling products as featured recommendations."""
        data = await ShopifyProductService._execute_storefront_graphql(
            store,
            query=ShopifyProductService.FEATURED_PRODUCTS_QUERY,
            variables={"first": min(limit, 20)},
        )
        edges = data.get("products", {}).get("edges", [])
        return [
            ShopifyProductService._normalize_storefront_product(edge["node"])
            for edge in edges
            if edge.get("node")
        ]

"""Shopify webhook endpoints — GDPR mandatory + app lifecycle."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.services.shopify_webhook_service import ShopifyWebhookError, ShopifyWebhookService

router = APIRouter(prefix="/shopify/webhooks", tags=["shopify-webhooks"])
logger = logging.getLogger(__name__)


async def _verified_webhook_body(
    request: Request,
    x_shopify_hmac_sha256: str | None = Header(None),
) -> dict:
    """Read raw body, verify HMAC, return parsed JSON."""
    body = await request.body()
    try:
        ShopifyWebhookService.verify_hmac(body, x_shopify_hmac_sha256)
    except ShopifyWebhookError as exc:
        raise HTTPException(401, str(exc)) from exc

    import orjson
    try:
        return orjson.loads(body)
    except Exception as exc:
        raise HTTPException(400, "Invalid JSON payload") from exc


@router.post("/app-uninstalled")
async def webhook_app_uninstalled(
    request: Request,
    x_shopify_hmac_sha256: str | None = Header(None),
    db: AsyncSession = Depends(get_session),
):
    payload = await _verified_webhook_body(request, x_shopify_hmac_sha256)
    result = await ShopifyWebhookService.handle_app_uninstalled(db, payload)
    return result


@router.post("/customers-data-request")
async def webhook_customers_data_request(
    request: Request,
    x_shopify_hmac_sha256: str | None = Header(None),
    db: AsyncSession = Depends(get_session),
):
    payload = await _verified_webhook_body(request, x_shopify_hmac_sha256)
    result = await ShopifyWebhookService.handle_customers_data_request(db, payload)
    return result


@router.post("/customers-redact")
async def webhook_customers_redact(
    request: Request,
    x_shopify_hmac_sha256: str | None = Header(None),
    db: AsyncSession = Depends(get_session),
):
    payload = await _verified_webhook_body(request, x_shopify_hmac_sha256)
    result = await ShopifyWebhookService.handle_customers_redact(db, payload)
    return result


@router.post("/shop-redact")
async def webhook_shop_redact(
    request: Request,
    x_shopify_hmac_sha256: str | None = Header(None),
    db: AsyncSession = Depends(get_session),
):
    payload = await _verified_webhook_body(request, x_shopify_hmac_sha256)
    result = await ShopifyWebhookService.handle_shop_redact(db, payload)
    return result

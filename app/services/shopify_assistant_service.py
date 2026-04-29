from __future__ import annotations

import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.models import (
    ShopifyAssistantSession,
    ShopifyDiscountApproval,
    ShopifyStore,
)

logger = get_logger(__name__)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ShopifyAssistantService:
    """Rule-based commerce assistant orchestration for Shopify storefronts."""

    PRODUCT_INTENTS = {"product_discovery", "product_recommendation", "cross_sell", "upsell"}
    SUPPORT_INTENTS = {
        "shipping_policy",
        "returns_policy",
        "order_status",
        "size_help",
        "payment_guardrail",
        "general_support",
    }

    @staticmethod
    def merge_context(existing: dict[str, Any] | None, update: dict[str, Any] | None) -> dict[str, Any]:
        merged: dict[str, Any] = dict(existing or {})
        if not update:
            return merged

        list_keys = {"viewed_products", "cart_lines", "catalog_candidates"}
        for key, value in update.items():
            if value is None:
                continue
            if key in list_keys:
                merged[key] = [ShopifyAssistantService.normalize_product(item) for item in value][-25:]
            elif isinstance(value, dict) and isinstance(merged.get(key), dict):
                merged[key] = {**merged.get(key, {}), **value}
            elif key == "current_product" and isinstance(value, dict):
                merged[key] = ShopifyAssistantService.normalize_product(value)
            else:
                merged[key] = value

        return merged

    @staticmethod
    def apply_behavior_event(context: dict[str, Any] | None, event: dict[str, Any]) -> dict[str, Any]:
        merged = dict(context or {})
        event_type = str(event.get("type") or "unknown").strip().lower()
        payload = dict(event.get("payload") or {})

        if event_type == "page_view":
            merged["current_page_url"] = payload.get("url") or merged.get("current_page_url")
            merged["current_page_title"] = payload.get("title") or merged.get("current_page_title")
        elif event_type == "product_view":
            product = ShopifyAssistantService.normalize_product(payload.get("product") or {})
            merged["current_product"] = product
            merged["viewed_products"] = ShopifyAssistantService._prepend_unique_product(
                merged.get("viewed_products") or [],
                product,
            )
        elif event_type == "search":
            merged["search_query"] = payload.get("query") or merged.get("search_query")
        elif event_type in {"cart_view", "cart_update"}:
            cart_lines = [
                ShopifyAssistantService.normalize_product(item)
                for item in payload.get("cart_lines") or []
            ]
            merged["cart_lines"] = cart_lines
            if payload.get("cart_total") is not None:
                merged["cart_total"] = payload.get("cart_total")
            if payload.get("checkout_url"):
                merged["checkout_url"] = payload.get("checkout_url")
        elif event_type == "collection_view":
            if payload.get("candidates"):
                merged["catalog_candidates"] = [
                    ShopifyAssistantService.normalize_product(item)
                    for item in payload.get("candidates")
                ][-25:]

        attributes = payload.get("attributes") or {}
        if attributes:
            merged["attributes"] = {**(merged.get("attributes") or {}), **attributes}

        recent_events = list(merged.get("recent_events") or [])
        recent_events.append(
            {
                "type": event_type,
                "payload": payload,
                "timestamp": event.get("timestamp") or utcnow().isoformat(),
            }
        )
        merged["recent_events"] = recent_events[-50:]
        return merged

    @staticmethod
    def normalize_product(product: dict[str, Any] | None) -> dict[str, Any]:
        item = dict(product or {})
        item.setdefault("id", "")
        item.setdefault("title", "")
        item.setdefault("handle", "")
        item.setdefault("url", "")
        item.setdefault("product_type", "")
        item.setdefault("vendor", "")
        item["tags"] = [str(tag).strip().lower() for tag in item.get("tags", []) if str(tag).strip()]
        item["collections"] = [
            str(collection).strip().lower() for collection in item.get("collections", []) if str(collection).strip()
        ]
        item["features"] = [str(feature).strip() for feature in item.get("features", []) if str(feature).strip()]
        return item

    @staticmethod
    def _prepend_unique_product(existing: list[dict[str, Any]], product: dict[str, Any]) -> list[dict[str, Any]]:
        normalized_existing = [ShopifyAssistantService.normalize_product(item) for item in existing]
        product_id = product.get("id")
        deduped = [item for item in normalized_existing if item.get("id") != product_id]
        deduped.insert(0, product)
        return deduped[:25]

    @staticmethod
    def build_behavior_summary(context: dict[str, Any]) -> str | None:
        current_product = context.get("current_product") or {}
        viewed_products = context.get("viewed_products") or []
        cart_lines = context.get("cart_lines") or []
        search_query = (context.get("search_query") or "").strip()

        if current_product.get("title"):
            return f"I can see you're looking at {current_product['title']}."
        if cart_lines:
            top_cart = cart_lines[0]
            return f"I can see you already added {top_cart.get('title', 'an item')} to your cart."
        if viewed_products:
            recent = viewed_products[0]
            return f"I noticed you've been exploring {recent.get('title', 'a few items')} so far."
        if search_query:
            return f"I can help you narrow down options for '{search_query}'."
        return None

    @staticmethod
    def infer_intent(message: str, context: dict[str, Any]) -> str:
        text = (message or "").strip().lower()
        if any(token in text for token in ["discount", "coupon", "% off", "deal", "promo", "sale price"]):
            return "discount_request"
        if any(token in text for token in ["checkout", "ready to buy", "buy now", "place order"]):
            return "checkout"
        if any(token in text for token in ["track", "order status", "where is my order", "delivery status"]):
            return "order_status"
        if any(token in text for token in ["return", "exchange", "refund"]):
            return "returns_policy"
        if any(token in text for token in ["shipping", "delivery", "arrive"]):
            return "shipping_policy"
        if any(token in text for token in ["size", "fit", "small", "large", "measurement"]):
            return "size_help"
        if any(token in text for token in ["pay", "card", "payment", "apple pay", "paypal"]):
            return "payment_guardrail"
        if any(token in text for token in ["bundle", "pair with", "goes with", "match", "accessory"]):
            return "cross_sell"
        if any(token in text for token in ["recommend", "best", "which one", "compare", "looking for", "need help finding"]):
            return "product_recommendation"
        if context.get("cart_lines"):
            return "upsell"
        return "product_discovery"

    @staticmethod
    def recommend_products(message: str, context: dict[str, Any], limit: int = 3) -> list[dict[str, Any]]:
        candidates = [
            ShopifyAssistantService.normalize_product(item)
            for item in (context.get("catalog_candidates") or context.get("viewed_products") or [])
        ]
        if not candidates:
            return []

        current_product = ShopifyAssistantService.normalize_product(context.get("current_product"))
        cart_lines = [ShopifyAssistantService.normalize_product(item) for item in context.get("cart_lines", [])]
        text_tokens = ShopifyAssistantService._tokenize(message)
        current_tags = set(current_product.get("tags", []))
        cart_tags = {tag for line in cart_lines for tag in line.get("tags", [])}
        cart_ids = {line.get("id") for line in cart_lines}

        scored: list[tuple[float, dict[str, Any]]] = []
        for product in candidates:
            score = 0.0
            title_tokens = ShopifyAssistantService._tokenize(product.get("title", ""))
            product_type_tokens = ShopifyAssistantService._tokenize(product.get("product_type", ""))
            tag_tokens = set(product.get("tags", []))

            score += len(text_tokens & title_tokens) * 3.0
            score += len(text_tokens & product_type_tokens) * 2.5
            score += len(text_tokens & tag_tokens) * 2.0
            score += len(current_tags & tag_tokens) * 1.5
            score += len(cart_tags & tag_tokens) * 1.25

            if current_product.get("product_type") and product.get("product_type") == current_product.get("product_type"):
                score += 1.0
            if product.get("id") in cart_ids:
                score -= 1.0
            if product.get("available") is False:
                score -= 2.0

            reason = ShopifyAssistantService._build_product_reason(product, current_product, cart_lines, text_tokens)
            product["reason"] = reason
            scored.append((score, product))

        ranked = sorted(scored, key=lambda item: (item[0], item[1].get("title", "")), reverse=True)
        return [product for score, product in ranked if score > 0][:limit]

    @staticmethod
    async def create_discount_request(
        db: AsyncSession,
        *,
        store: ShopifyStore,
        session: ShopifyAssistantSession,
        shopper_message: str,
    ) -> ShopifyDiscountApproval:
        suggested_value = ShopifyAssistantService.suggest_discount_value(session.context or {})
        cart_total = ShopifyAssistantService.estimate_cart_total(session.context or {})
        reason = (
            f"Customer requested a discount after showing purchase intent. "
            f"Suggested {suggested_value:.0f}% off based on a cart value of {cart_total:.2f}."
        )

        approval = ShopifyDiscountApproval(
            id=uuid.uuid4(),
            client_id=session.client_id,
            store_id=store.id,
            session_id=session.id,
            status="pending",
            discount_type="code",
            value_type="percentage",
            value=suggested_value,
            currency=session.currency or (session.context or {}).get("currency"),
            reason=reason,
            shopper_message=shopper_message,
            cart_snapshot={
                "cart_total": cart_total,
                "cart_lines": (session.context or {}).get("cart_lines", []),
            },
            expires_at=utcnow() + timedelta(hours=2),
        )
        db.add(approval)
        await db.flush()
        await db.refresh(approval)
        return approval

    @staticmethod
    async def generate_reply(
        db: AsyncSession,
        *,
        store: ShopifyStore,
        session: ShopifyAssistantSession,
        shopper_message: str,
    ) -> dict[str, Any]:
        context = session.context or {}
        intent = ShopifyAssistantService.infer_intent(shopper_message, context)
        behavior_summary = ShopifyAssistantService.build_behavior_summary(context)
        recommendations = ShopifyAssistantService.recommend_products(shopper_message, context)
        support_response = ShopifyAssistantService.build_support_response(intent, context, store)

        action = "ask_clarifying_question"
        navigate_to = None
        checkout_url = context.get("checkout_url")
        discount_request = None
        lines: list[str] = []

        if behavior_summary:
            lines.append(behavior_summary)

        if intent in ShopifyAssistantService.SUPPORT_INTENTS:
            lines.append(support_response)
        elif intent == "discount_request":
            if store.allow_discount_requests and store.require_discount_approval:
                discount_request = await ShopifyAssistantService.create_discount_request(
                    db,
                    store=store,
                    session=session,
                    shopper_message=shopper_message,
                )
                action = "await_discount_approval"
                lines.append(
                    "I can request a store-approved discount for you, but I won't apply anything automatically. "
                    "I've sent the request to the store owner for approval."
                )
            else:
                lines.append(
                    "I can help you find the best-value option, but this store isn't accepting AI discount requests right now."
                )
        elif intent == "checkout" and checkout_url:
            action = "navigate_to_checkout"
            navigate_to = checkout_url
            lines.append(
                "You're ready for checkout. I'll send you there now, and you'll complete payment securely on the store's checkout page."
            )
        elif recommendations:
            action = "navigate_to_product"
            navigate_to = recommendations[0].get("url") or recommendations[0].get("handle")
            top_names = ", ".join(product.get("title", "item") for product in recommendations[:3])
            lines.append(f"Based on what you've shared, I'd start with {top_names}.")
            reason = recommendations[0].get("reason")
            if reason:
                lines.append(reason)
        else:
            lines.append(
                "Tell me what you're shopping for, who it's for, or the problem you're trying to solve, and I'll narrow it down fast."
            )

        if intent in ShopifyAssistantService.PRODUCT_INTENTS and recommendations:
            lines.append("I can also guide you straight to the product page and explain the key benefits before you decide.")
        if intent == "checkout" and checkout_url:
            lines.append("I won't handle payment details directly — you'll enter those securely yourself.")

        message = " ".join(part.strip() for part in lines if part and part.strip())
        assistant_turn = {
            "role": "assistant",
            "message": message,
            "intent": intent,
            "recommended_products": recommendations,
            "navigate_to": navigate_to,
            "discount_request_id": str(discount_request.id) if discount_request else None,
            "timestamp": utcnow().isoformat(),
        }
        shopper_turn = {
            "role": "shopper",
            "message": shopper_message,
            "timestamp": utcnow().isoformat(),
        }

        transcript = list(session.transcript or [])
        transcript.extend([shopper_turn, assistant_turn])
        session.transcript = transcript[-50:]
        session.last_intent = intent
        session.last_recommendations = recommendations
        session.last_seen_at = utcnow()
        await db.flush()

        return {
            "message": message,
            "intent": intent,
            "action": action,
            "navigate_to": navigate_to,
            "recommended_products": recommendations,
            "checkout_url": checkout_url if action == "navigate_to_checkout" else None,
            "discount_request": ShopifyAssistantService.serialize_discount_request(discount_request),
            "support_resolution": support_response if intent in ShopifyAssistantService.SUPPORT_INTENTS else None,
            "requires_human": False,
        }

    @staticmethod
    def build_support_response(intent: str, context: dict[str, Any], store: ShopifyStore) -> str:
        policies = {**(store.support_policy or {}), **(context.get("support_context") or {})}
        if intent == "shipping_policy":
            return policies.get(
                "shipping",
                "I can help you choose the fastest option and point you to the shipping details on the product page.",
            )
        if intent == "returns_policy":
            return policies.get(
                "returns",
                "I can explain the return and exchange policy, and if you want, I can guide you to the right policy page next.",
            )
        if intent == "order_status":
            return policies.get(
                "order_status",
                "I can help you locate the order tracking page or guide you to support if you already have an order number.",
            )
        if intent == "size_help":
            return policies.get(
                "size",
                "I can compare fit, features, and intended use so you can choose the right size with more confidence.",
            )
        if intent == "payment_guardrail":
            return "I can guide you to checkout and help with the steps, but you'll enter payment details securely yourself on Shopify checkout."
        return "I can answer most product, shipping, returns, and checkout questions in real time and guide you to the right page."

    @staticmethod
    def suggest_discount_value(context: dict[str, Any]) -> float:
        cart_total = ShopifyAssistantService.estimate_cart_total(context)
        if cart_total >= 250:
            return 15.0
        if cart_total >= 100:
            return 10.0
        return 5.0

    @staticmethod
    def estimate_cart_total(context: dict[str, Any]) -> float:
        if context.get("cart_total") is not None:
            try:
                return float(context["cart_total"])
            except (TypeError, ValueError):
                pass

        total = 0.0
        for line in context.get("cart_lines", []):
            try:
                quantity = int(line.get("quantity", 1) or 1)
                price = float(line.get("price") or 0.0)
                total += quantity * price
            except (TypeError, ValueError):
                continue
        return total

    @staticmethod
    def serialize_discount_request(approval: ShopifyDiscountApproval | None) -> dict[str, Any] | None:
        if not approval:
            return None
        return {
            "id": str(approval.id),
            "status": approval.status,
            "discount_type": approval.discount_type,
            "value_type": approval.value_type,
            "value": approval.value,
            "code": approval.code,
            "reason": approval.reason,
            "expires_at": approval.expires_at.isoformat() if approval.expires_at else None,
        }

    @staticmethod
    def _tokenize(text: str) -> set[str]:
        return {token for token in re.findall(r"[a-z0-9]+", (text or "").lower()) if len(token) > 1}

    @staticmethod
    def _build_product_reason(
        product: dict[str, Any],
        current_product: dict[str, Any],
        cart_lines: list[dict[str, Any]],
        text_tokens: set[str],
    ) -> str:
        if current_product.get("product_type") and product.get("product_type") == current_product.get("product_type"):
            return f"It matches the same category as what you're viewing, so it's a strong side-by-side comparison."
        current_tags = set(current_product.get("tags", []))
        product_tags = set(product.get("tags", []))
        shared_tags = list(current_tags & product_tags)
        if shared_tags:
            return f"It lines up with the features you're already looking at, especially around {shared_tags[0]}."
        cart_types = {line.get("product_type") for line in cart_lines if line.get("product_type")}
        if cart_types and product.get("product_type") not in cart_types:
            return "It complements what's already in the cart, which makes it a strong cross-sell option."
        if text_tokens:
            return "It matches the intent in your question and is a strong fit for the benefits you're asking about."
        return "It's one of the strongest matches based on the products and behavior in this session."

from types import SimpleNamespace

from app.services.shopify_assistant_service import ShopifyAssistantService
from app.services.shopify_storefront_bridge_service import ShopifyStorefrontBridgeService


def test_public_token_round_trip():
    store = SimpleNamespace(id="store-1", client_id="client-1", shop_domain="demo-shop.myshopify.com")
    issued = ShopifyStorefrontBridgeService.issue_public_token(store)
    payload = ShopifyStorefrontBridgeService.decode_public_token(issued["token"])
    assert payload["shop"] == "demo-shop.myshopify.com"
    assert payload["client_id"] == "client-1"


def test_apply_behavior_event_sets_current_product():
    context = ShopifyAssistantService.apply_behavior_event(
        {},
        {
            "type": "product_view",
            "payload": {
                "product": {
                    "id": "prod-1",
                    "title": "Performance Socks",
                    "tags": ["running", "socks"],
                }
            },
        },
    )
    assert context["current_product"]["title"] == "Performance Socks"
    assert context["viewed_products"][0]["id"] == "prod-1"

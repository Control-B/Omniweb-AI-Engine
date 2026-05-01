from app.services.shopify_assistant_service import ShopifyAssistantService


def test_infer_discount_intent():
    intent = ShopifyAssistantService.infer_intent(
        "Can I get a discount if I buy both today?",
        {},
    )
    assert intent == "discount_request"


def test_recommend_products_prefers_matching_tags():
    context = {
        "current_product": {
            "id": "shoe-1",
            "title": "Cloud Runner",
            "product_type": "Running Shoes",
            "tags": ["running", "lightweight", "men"],
        },
        "catalog_candidates": [
            {
                "id": "shoe-2",
                "title": "Trail Runner Pro",
                "product_type": "Running Shoes",
                "tags": ["running", "trail", "lightweight"],
                "url": "/products/trail-runner-pro",
                "available": True,
            },
            {
                "id": "bag-1",
                "title": "Travel Duffel",
                "product_type": "Bags",
                "tags": ["travel"],
                "url": "/products/travel-duffel",
                "available": True,
            },
        ],
    }

    recommendations = ShopifyAssistantService.recommend_products(
        "I need lightweight running shoes",
        context,
    )

    assert recommendations
    assert recommendations[0]["id"] == "shoe-2"


def test_behavior_summary_uses_current_product():
    summary = ShopifyAssistantService.build_behavior_summary(
        {"current_product": {"title": "Performance Hoodie"}}
    )
    assert "Performance Hoodie" in summary

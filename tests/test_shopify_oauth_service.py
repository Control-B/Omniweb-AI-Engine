from app.services.shopify_oauth_service import ShopifyOAuthError, ShopifyOAuthService


def test_normalize_shop_domain_accepts_myshopify():
    shop = ShopifyOAuthService.normalize_shop_domain("https://example-store.myshopify.com/admin")
    assert shop == "example-store.myshopify.com"


def test_normalize_shop_domain_rejects_invalid_domain():
    try:
        ShopifyOAuthService.normalize_shop_domain("example.com")
    except ShopifyOAuthError as exc:
        assert "myshopify.com" in str(exc)
    else:
        raise AssertionError("Expected ShopifyOAuthError")

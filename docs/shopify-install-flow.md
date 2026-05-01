# Shopify install flow

This backend now supports the first production install layer for the Shopify commerce assistant.

## Required env vars

Add these to the API service environment:

- `SHOPIFY_API_KEY`
- `SHOPIFY_API_SECRET`
- `SHOPIFY_APP_URL`
- `SHOPIFY_WEBHOOK_SECRET`
- `SHOPIFY_API_VERSION` (defaults to `2026-07`)
- `SHOPIFY_SCOPES`

## Backend flow

1. Merchant signs into Omniweb dashboard.
2. Dashboard calls `POST /api/shopify/install/{client_id}` with `{ "shop": "merchant-store.myshopify.com" }`.
3. Backend stores a short-lived hashed install state on `shopify_stores` and returns the Shopify authorization URL.
4. Merchant approves the app on Shopify.
5. Shopify redirects to `GET /api/shopify/oauth/callback`.
6. Backend validates the callback HMAC and state, exchanges the authorization code for an Admin API token, fetches shop identity, and creates a Storefront access token.
7. Backend persists install metadata and redirects the merchant back to Omniweb admin with a success or error query string.

## Current endpoints

- `POST /api/shopify/install/{client_id}`
- `GET /api/shopify/install-status/{client_id}`
- `GET /api/shopify/oauth/callback`
- `GET /api/shopify/stores/{client_id}`
- `PUT /api/shopify/stores/{client_id}`

## Storefront bridge endpoints

These endpoints are designed for the next theme app embed or app proxy layer:

- `GET /api/shopify/public/bootstrap?shop=<shop>.myshopify.com`
- `POST /api/shopify/public/sessions`
- `POST /api/shopify/public/sessions/{session_id}/context`
- `POST /api/shopify/public/sessions/{session_id}/reply`
- `POST /api/shopify/public/sessions/{session_id}/events?shop=<shop>.myshopify.com`

### Intended bootstrap flow

1. The storefront script requests `/api/shopify/public/bootstrap` with the shop domain.
2. Backend returns a short-lived public bearer token plus the assistant greeting and endpoint map.
3. The storefront script starts a session with `POST /api/shopify/public/sessions`.
4. The storefront sends browsing events such as page views, product views, searches, and cart updates to `/events`.
5. The storefront sends customer messages to `/reply` and uses `navigate_to` / `checkout_url` in the response to guide the shopper.

## Next layer

After this install layer, the next recommended implementation is:

1. Theme app embed or app proxy bootstrap for storefront chat.
2. Polaris admin UI for merchant discount approvals and install status.
3. Webhook handling for `app/uninstalled` and order/customer sync.
4. Product/catalog sync and merchandising rules per merchant.

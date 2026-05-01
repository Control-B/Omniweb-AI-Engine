# Omniweb AI Shopify SaaS Architecture

## 1. Recommended Stack

Use the Shopify CLI Remix template for the embedded Shopify app.

Remix is the best default because it is Shopify's primary app template, has first-class App Bridge and Polaris support, gives clean server loaders/actions for OAuth, billing, and webhooks, and avoids inventing Shopify session plumbing. Next.js is still fine for the Omniweb marketing/dashboard app, but the Shopify embedded app should follow Shopify's official Remix path for App Store readiness.

Keep the existing FastAPI service as the AI orchestration backend on DigitalOcean. It already owns Deepgram voice sessions, RAG ingestion, product-aware replies, navigation actions, lead capture, and multi-tenant agent config. The Shopify app becomes the merchant control plane.

## 2. High-Level Architecture

### Shopify App Layer

Located at `frontend/shopify-app`.

Responsibilities:
- OAuth install and offline shop session storage.
- Embedded merchant dashboard with Polaris.
- Shopify Billing API for Starter, Growth, and Pro plans.
- Theme app extension deployment and activation instructions.
- Merchant configuration for agent behavior, widget styling, URL knowledge, and plan limits.
- Usage and analytics display.
- Secure server-to-server calls to the DO AI Engine.

### AI Orchestration Backend

Located in the existing FastAPI service under `app`.

Responsibilities:
- Voice/text agent orchestration.
- Deepgram, Retell, and future LiveKit integrations.
- RAG ingestion and retrieval.
- Product search and Shopify-aware tools.
- Site navigation actions.
- Lead qualification and capture.
- Conversation storage and usage metering.
- Tenant isolation by `shop_domain`, `client_id`, and public storefront tokens.

### Storefront Widget Layer

Use a Shopify theme app extension, not raw ScriptTag installation.

The app embed injects a stable widget script that bootstraps against:

`GET /api/shopify/public/bootstrap?shop=<shop>.myshopify.com`

The widget then uses short-lived public tokens for text, voice, events, and navigation.

## 3. DigitalOcean Deployment

Use DigitalOcean App Platform for MVP and production v1:
- `shopify-app`: Remix embedded app, Node service.
- `api`: existing FastAPI AI Engine.
- `dashboard`: existing Next.js Omniweb dashboard.
- Managed Postgres.
- Optional managed Redis for queues, locks, rate limits, and crawl jobs.

Use a Droplet only if you need custom networking, long-lived workers, or Docker Compose control. For Shopify App Store reliability, App Platform with separate services is the better first production move.

Recommended domains:
- `app.omniweb.ai` -> Remix Shopify embedded app.
- `api.omniweb.ai` -> FastAPI AI Engine.
- `omniweb.ai` -> public marketing site.
- Keep the DO default URL as fallback.

## 4. Billing Plans

All Shopify merchants are billed through Shopify Billing API.

| Plan | Trial | Price | Limits |
| --- | --- | --- | --- |
| Starter | 7 days | $29/mo | 1,000 conversations/mo, 250 products indexed, text + basic voice |
| Growth | 7 days | $99/mo | 5,000 conversations/mo, 2,500 products indexed, multilingual, RAG, navigation |
| Pro | 7 days | $249/mo | 25,000 conversations/mo, 25,000 products indexed, advanced analytics, priority queues |

Entitlements should be enforced in both the Shopify app and the AI Engine. The Shopify app is the billing source of truth; the AI Engine caches access state for runtime decisions.

## 5. Server-To-Server Contract

The Shopify app calls the AI Engine with:

- `X-Omniweb-Shopify-Secret`: shared server secret.
- `X-Omniweb-Shop-Domain`: normalized shop domain.
- JSON body containing `shop_domain`, `client_id`, `plan`, `subscription_status`, and feature settings.

Primary endpoints to keep or add in FastAPI:

- `POST /api/shopify/install/{client_id}`
- `GET /api/shopify/oauth/callback`
- `GET /api/shopify/public/bootstrap`
- `POST /api/shopify/public/sessions`
- `POST /api/shopify/public/voice/session`
- `POST /api/shopify/public/sessions/{session_id}/reply`
- `POST /api/shopify/public/events`
- `POST /api/shopify/engine/sync-shop`
- `POST /api/shopify/engine/sync-agent-config`
- `POST /api/shopify/engine/sync-subscription`
- `POST /api/shopify/engine/knowledge-jobs`

The existing Gadget endpoints can be retired after the Shopify app owns install, billing, and merchant settings.

## 6. MVP Roadmap

### Week One

1. Create Shopify CLI Remix app under `frontend/shopify-app`.
2. Configure OAuth, session storage, and webhook registration.
3. Add plans and Shopify Billing confirmation flow.
4. Add Polaris setup dashboard.
5. Sync installed shop, subscription, and agent config to FastAPI.
6. Use the existing theme app extension for storefront widget injection.
7. Verify storefront bootstrap and voice session against one development store.

### Week Two

1. Add product sync worker.
2. Add knowledge URL ingestion jobs.
3. Add usage metering and plan enforcement.
4. Add analytics and conversation review.
5. Harden webhooks and app uninstall cleanup.

### App Store Readiness

1. GDPR webhooks.
2. Billing test mode handling.
3. Clear onboarding and theme app embed instructions.
4. Privacy policy and data deletion docs.
5. Observability dashboards and alerting.

## 7. Reliability Rules

- Keep Shopify admin app failures isolated from voice runtime.
- Every runtime request must include tenant identity.
- Never trust storefront input for entitlement decisions.
- Use idempotency keys for install, billing, sync, and ingestion jobs.
- Store encrypted Shopify access tokens.
- Retry outbound Engine calls with exponential backoff.
- Log by `shop_domain`, `client_id`, `request_id`, and `session_id`.
- Use background jobs for crawling, product sync, and embeddings.

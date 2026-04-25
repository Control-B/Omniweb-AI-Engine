# Backend

The production AI orchestration backend currently lives in the existing FastAPI `app/` package.

For Shopify, this backend owns:

- Voice and text runtime
- Deepgram voice sessions
- RAG ingestion and retrieval
- Product-aware tools
- Navigation actions
- Lead capture
- Usage metering
- Tenant isolation

The new Shopify CLI app in `frontend/shopify-app` should call this backend through secure server-to-server endpoints and should not run AI runtime logic itself.

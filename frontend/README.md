# Frontend apps

## Public marketing site (`v0-omniweb-landing-page`)

The **omniweb.ai** experience lives in [`Control-B/v0-omniweb-landing-page`](https://github.com/Control-B/v0-omniweb-landing-page). It is **not** merged into this repo; connect it as a **second deployment** that talks to the **Omniweb-AI-Engine** FastAPI over HTTPS.

### Clone (optional sibling checkout)

```bash
git clone https://github.com/Control-B/v0-omniweb-landing-page.git frontend/v0-omniweb-landing-page
```

This repository ignores `frontend/v0-omniweb-landing-page/` so your local clone stays its own git repo. Push changes from that directory to `Control-B/v0-omniweb-landing-page`.

### How it connects to the engine

1. **Clerk** — Use the **same** Clerk application as the engine/dashboard (`NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` / `CLERK_SECRET_KEY`). The landing app exchanges the Clerk JWT at `{ENGINE}/api/auth/clerk-session` (see `lib/auth/engine.ts`).
2. **Engine URL** — Set `NEXT_PUBLIC_OMNIWEB_ENGINE_URL` and `OMNIWEB_ENGINE_URL` to your deployed engine (or `http://localhost:8000` locally).
3. **CORS** — In the engine, `CORS_ORIGINS` must include `https://omniweb.ai` (already included by default).
4. **API proxy** — Browser calls go to same-origin `/api/engine/*`, which the Next app proxies to `{ENGINE}/api/*` with the engine JWT cookie (`app/api/engine/[...path]/route.ts`).

See `frontend/v0-omniweb-landing-page/.env.production.example` and `.env.local.example` after you clone.

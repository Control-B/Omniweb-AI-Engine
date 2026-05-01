# DigitalOcean App Platform — Omniweb concert

Your repo ships **one App Platform spec** (`.do/app.yaml`) that runs **two components** behind one ingress:

| Path prefix | Component | Purpose |
|-------------|-----------|---------|
| `/api`, `/health`, `/static` | **api** (FastAPI, port 8000) | Omniweb Engine REST API (`/api/auth/clerk-session`, agents, widget, …) |
| everything else (`/`, `/dashboard`, `/sso-callback`, …) | **dashboard** (Next.js, port 3000) | Engine dashboard UI |

The default public URL looks like **`https://<your-app-slug>.ondigitalocean.app`**. Custom domain **`api.omniweb.ai`** is declared in `.do/app.yaml`; the **same ingress** applies to **all** hostnames attached to the app — so **`https://api.omniweb.ai/dashboard`** hits the Next service, and **`https://api.omniweb.ai/api/...`** hits FastAPI.

The **marketing site** at **`https://omniweb.ai`** is usually a **separate** App Platform app or deployment. Configure it separately to talk to the engine (below).

---

## 1. Engine API (same DO app → `api` component)

In **DigitalOcean → Your App → api component → Settings → Environment**:

- **`CLERK_SECRET_KEY`** — **Required** so `POST /api/auth/clerk-session` can verify Clerk JWTs from the browser or omniweb.ai server handoff. If this exists only in the UI and not in a redeployed spec, keep it synchronized after each push from Git.
- **`CORS_ORIGINS`** must include `https://omniweb.ai` and `https://www.omniweb.ai` (extend for any new marketing origins).

---

## 2. Engine dashboard (same DO app → `dashboard` component)

The **dashboard `Dockerfile`** bakes **`NEXT_PUBLIC_*` and Clerk at build time**:

- **`NEXT_PUBLIC_API_URL`** / **`NEXT_PUBLIC_ENGINE_URL`** — Public FastAPI base (no `/api` suffix). Prefer **`https://api.omniweb.ai`** once DNS resolves; otherwise the **`*.ondigitalocean.app`** URL (see `.do/app.yaml` comments).
- **`NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`** (**BUILD_TIME**) — **Same Clerk application** as omniweb.ai. Missing value → SSO and `/sso-callback` break on the slug host.
- **`CLERK_PUBLISHABLE_KEY`** — Same publishable key; `dashboard/next.config.js` maps it into the client bundle.

Change **BUILD_TIME** vars → trigger a fresh **deploy** so the image rebuilds.

---

## 3. Marketing (`omniweb.ai`, typically a second deployment)

Align env with the engine deployment:

```bash
# Same Clerk application as api + dashboard
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_...
CLERK_SECRET_KEY=sk_...

NEXT_PUBLIC_OMNIWEB_ENGINE_URL=https://api.omniweb.ai
OMNIWEB_ENGINE_URL=https://api.omniweb.ai

# Handoff target = engine Next dashboard (often same slug as engine app)
NEXT_PUBLIC_OMNIWEB_DASHBOARD_ORIGIN=https://<slug>.ondigitalocean.app
```

**Shortcut** (same hostname for API + Next): set both **`NEXT_PUBLIC_OMNIWEB_ENGINE_URL`** and **`NEXT_PUBLIC_OMNIWEB_DASHBOARD_ORIGIN`** to **`https://api.omniweb.ai`** — ingress splits `/api` vs `/` routes.

Clerk Dashboard → **Authorized redirect URLs** must include **`https://<dashboard-host>/sso-callback`** (and OAuth returns on omniweb.ai if applicable).

---

## 4. Cursor MCP + DigitalOcean

If **`apps-list`** returns **401**, add a DigitalOcean API token wherever Cursor configures the MCP server, then reconnect. Without that, the assistant cannot pull live routes or logs from DO.

---

## 5. Quick checks

1. **`GET https://<engine-public-host>/health`** → ok  
2. **`https://<slug>.ondigitalocean.app/dashboard`** (or `api.omniweb.ai/dashboard`) loads after Clerk sign-in  
3. Signed in on omniweb.ai → **`/api/engine-handoff`** completes (see Network tab for **`POST …/api/auth/clerk-session`**)  


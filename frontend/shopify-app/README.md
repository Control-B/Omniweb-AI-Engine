# Omniweb AI Shopify App

Production Shopify CLI Remix app for the Omniweb AI Sales / Revenue Agent.

## Role

This app is the Shopify merchant control plane:

- OAuth install
- Embedded Polaris admin
- Shopify Billing
- Theme app extension management
- Agent settings
- Knowledge source setup
- Usage and analytics
- Secure sync to the DigitalOcean AI Engine

The AI runtime stays in the DO FastAPI service.

## Local Setup

```bash
cp .env.example .env
pnpm install
pnpm prisma:generate
pnpm dev
```

## Production

Deploy this as a separate DigitalOcean App Platform service:

- Build: `pnpm install --frozen-lockfile && pnpm prisma:generate && pnpm build`
- Run: `pnpm prisma:migrate && pnpm start`
- Health check: `/app`

Use `app.omniweb.ai` for this service and keep `api.omniweb.ai` for the AI Engine.

## Week-One MVP Build Order

1. Run `shopify app dev` and complete install on a dev store.
2. Confirm sessions persist in Postgres.
3. Confirm billing request/confirmation in test mode.
4. Save agent config and verify Engine sync.
5. Enable the theme app embed.
6. Confirm storefront bootstrap, text reply, and voice session.

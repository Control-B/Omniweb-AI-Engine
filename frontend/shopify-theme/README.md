# Presence AI Shopify Theme

Presence AI is an original Shopify Online Store 2.0 theme concept for premium merchants who want video-led product education and an AI-ready shopping assistant.

## Positioning

- Premium editorial storefront for fashion, beauty, electronics, lifestyle, furniture, and product demo brands.
- Built around conversion sections: video hero, AI presenter, shoppable video, product comparison, guided buying, and assistant callouts.
- Provider-agnostic AI launcher with `window.PresenceAI.open()`, `window.PresenceAI.close()`, and `window.PresenceAI.sendContext()` hooks.

## Local Development

Use Shopify CLI from this folder:

```bash
shopify theme dev --store your-dev-store.myshopify.com
```

## AI Integration Notes

The floating assistant is intentionally backend-neutral. Configure:

- Agent ID
- Backend endpoint
- Text and voice labels
- Brand voice instructions
- Launcher position

Product and collection pages emit page context through the `presence-context` snippet. The JavaScript dispatches `presence-ai:context`, `presence-ai:open`, and `presence-ai:close` events so the Omniweb app, LiveKit, Retell, ElevenLabs, or another backend can attach later.

## Theme Store Readiness

This is a first implementation scaffold, not a final Theme Store submission package yet. Before submission, run Shopify theme validation, accessibility testing, performance audits, cross-browser QA, and full merchant setting review.

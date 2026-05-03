import { json } from "@remix-run/node";
import { useLoaderData } from "@remix-run/react";
import { useState } from "react";
import {
  BlockStack,
  Button,
  InlineStack,
  Page,
  Text,
} from "@shopify/polaris";
import { authenticate } from "../shopify.server";
import { prisma } from "../db.server";
import { syncShopToEngine } from "../services/engine.server";
import { ensureStorefrontAccessToken } from "../services/storefront-token.server";

// Send semantic gender keywords — the engine maps these to the ElevenLabs
// female/male voice (Sarah / Adam by default) with a Deepgram Aura voice of
// the matching gender as the deterministic fallback.
const FEMALE_VOICE = "female";
const MALE_VOICE   = "male";

export async function loader({ request }: { request: Request }) {
  const { admin, session } = await authenticate.admin(request);

  const shop = await prisma.shop.upsert({
    where: { shopDomain: session.shop },
    update: {},
    create: { shopDomain: session.shop, status: "installed" },
    include: { agentConfig: true, subscription: true },
  });

  let engineClientId = shop.engineClientId;

  // Try to sync so we always have a fresh client ID
  try {
    const storefrontToken = await ensureStorefrontAccessToken({
      admin,
      shopId: shop.id,
      shopDomain: session.shop,
      encryptedToken: shop.encryptedStorefrontToken,
    });
    const sync = await syncShopToEngine({
      shop_domain: session.shop,
      engine_client_id: shop.engineClientId,
      admin_access_token: session.accessToken,
      storefront_access_token: storefrontToken,
      granted_scopes: (session.scope || "").split(",").map((s) => s.trim()).filter(Boolean),
      storefront_api_version: process.env.SHOPIFY_API_VERSION || "2026-07",
      plan: shop.subscription?.plan || "starter",
      subscription_status: shop.subscription?.status || "trialing",
      assistant_enabled: true,
      agent_config: shop.agentConfig || {},
    });
    if (sync.client_id && sync.client_id !== shop.engineClientId) {
      engineClientId = sync.client_id;
      await prisma.shop.update({ where: { id: shop.id }, data: { engineClientId } });
    }
  } catch {
    // Non-fatal — use whatever clientId we already have
  }

  const engineUrl = process.env.ENGINE_URL || "https://omniweb-engine-rs6fr.ondigitalocean.app";
  const agentName = shop.agentConfig?.agentName || "Omniweb AI";
  const greeting  = shop.agentConfig?.greeting  || "Thank you for visiting today, I am your AI assistant... how can I assist you?";
  const shopDomain = session.shop; // e.g. "mystore.myshopify.com"

  return json({ engineClientId, engineUrl, agentName, greeting, shopDomain });
}

export default function TestConsole() {
  const { engineClientId, engineUrl, agentName, greeting, shopDomain } =
    useLoaderData<typeof loader>();

  const [voice, setVoice] = useState<"female" | "male">("female");

  const voiceId   = voice === "female" ? FEMALE_VOICE : MALE_VOICE;
  const widgetBase = engineClientId ? `${engineUrl}/widget/${engineClientId}` : null;
  const voiceUrl   = widgetBase ? `${widgetBase}?voice=${voiceId}&mode=voice` : null;
  const textUrl    = widgetBase ? `${widgetBase}?voice=${voiceId}&mode=text`  : null;
  const storefrontUrl = `https://${shopDomain}`;

  const ready = Boolean(widgetBase);

  return (
    <Page
      fullWidth
      title="Agent Test Console"
      subtitle={`"${agentName}" — test voice and text before shoppers see it`}
      backAction={{ url: "/app/agent", content: "Agent settings" }}
    >
      <div className="omni-page-shell omni-test-page">

        {/* ── top bar: voice toggle + storefront link ── */}
        <div className="omni-test-topbar">
          <div className="omni-test-topbar__left">
            <Text as="p" variant="bodySm" tone="subdued">Voice:</Text>
            <div className="omni-test-voice-toggle">
              <button
                type="button"
                className={`omni-test-voice-btn${voice === "female" ? " active" : ""}`}
                onClick={() => setVoice("female")}
              >
                <span className="omni-test-voice-btn__dot omni-test-voice-btn__dot--female" />
                Female
              </button>
              <button
                type="button"
                className={`omni-test-voice-btn${voice === "male" ? " active" : ""}`}
                onClick={() => setVoice("male")}
              >
                <span className="omni-test-voice-btn__dot omni-test-voice-btn__dot--male" />
                Male
              </button>
            </div>
          </div>

          <div className="omni-test-topbar__right">
            <a
              href={storefrontUrl}
              target="_blank"
              rel="noreferrer"
              className="omni-ask-ai-btn"
              title="Open your live storefront — the Ask AI widget will appear there"
            >
              <span className="omni-ask-ai-btn__orb" />
              Ask AI
            </a>
            <Text as="p" variant="bodySm" tone="subdued" alignment="center">
              Opens your storefront
            </Text>
          </div>
        </div>

        {/* ── greeting strip ── */}
        <div className="omni-test-greeting">
          <Text as="p" variant="bodySm" tone="subdued">
            Opening message:&nbsp;
          </Text>
          <Text as="p" variant="bodySm">
            <em>&ldquo;{greeting}&rdquo;</em>
          </Text>
        </div>

        {/* ── two widget windows ── */}
        {ready ? (
          <div className="omni-test-windows">
            {/* Voice window */}
            <div className="omni-test-window">
              <div className="omni-test-window__header">
                <span className="omni-test-window__dot omni-test-window__dot--red" />
                <span className="omni-test-window__dot omni-test-window__dot--teal" />
                <span className="omni-test-window__dot omni-test-window__dot--green" />
                <span className="omni-test-window__title">Voice agent</span>
                <a
                  href={voiceUrl!}
                  target="_blank"
                  rel="noreferrer"
                  className="omni-test-window__external"
                  title="Open in new tab"
                >
                  &#x2197;
                </a>
              </div>
              <iframe
                key={`voice-${voiceId}`}
                src={voiceUrl!}
                className="omni-test-window__frame"
                allow="microphone; camera"
                title="Voice agent preview"
              />
            </div>

            {/* Text window */}
            <div className="omni-test-window">
              <div className="omni-test-window__header">
                <span className="omni-test-window__dot omni-test-window__dot--red" />
                <span className="omni-test-window__dot omni-test-window__dot--teal" />
                <span className="omni-test-window__dot omni-test-window__dot--green" />
                <span className="omni-test-window__title">Text chat</span>
                <a
                  href={textUrl!}
                  target="_blank"
                  rel="noreferrer"
                  className="omni-test-window__external"
                  title="Open in new tab"
                >
                  &#x2197;
                </a>
              </div>
              <iframe
                key={`text-${voiceId}`}
                src={textUrl!}
                className="omni-test-window__frame"
                title="Text chat preview"
              />
            </div>
          </div>
        ) : (
          <div className="omni-test-not-ready">
            <div className="omni-test-not-ready__icon">&#9888;</div>
            <BlockStack gap="200">
              <Text as="p" fontWeight="semibold">Agent not synced yet</Text>
              <Text as="p" tone="subdued">
                Go to <strong>Agent Settings</strong>, fill in your details, and click&nbsp;
                <strong>Save and sync agent</strong>. Then come back here to test.
              </Text>
              <InlineStack>
                <Button url="/app/agent" variant="primary">
                  Go to Agent Settings
                </Button>
              </InlineStack>
            </BlockStack>
          </div>
        )}

        {/* ── checklist ── */}
        <div className="omni-test-checklist">
          {[
            ["Welcome message", "Does the agent open with your custom greeting?"],
            ["Product questions", "Ask about a product — does it answer from your knowledge base?"],
            ["Language switching", "Try a different language if you have multiple enabled."],
            ["Cart actions", "Ask to add something to cart — does it confirm?"],
            ["Voice quality", "Is the voice clear and natural at the chosen gender?"],
          ].map(([title, desc], i) => (
            <div key={i} className="omni-test-checklist__item">
              <span className="omni-test-checklist__num">{i + 1}</span>
              <div>
                <Text as="p" fontWeight="semibold" variant="bodySm">{title}</Text>
                <Text as="p" tone="subdued" variant="bodySm">{desc}</Text>
              </div>
            </div>
          ))}
        </div>

      </div>
    </Page>
  );
}

import { json } from "@remix-run/node";
import { useLoaderData } from "@remix-run/react";
import { useState } from "react";
import {
  Badge,
  BlockStack,
  Button,
  Card,
  InlineStack,
  Layout,
  Page,
  Text,
} from "@shopify/polaris";
import { authenticate } from "../shopify.server";
import { prisma } from "../db.server";

// Deepgram Aura-2 voices — one female, one male per major language
const FEMALE_VOICE = "aura-2-asteria-en";  // English, warm female
const MALE_VOICE   = "aura-2-orion-en";    // English, confident male

export async function loader({ request }: { request: Request }) {
  const { session } = await authenticate.admin(request);
  const shop = await prisma.shop.findUnique({
    where: { shopDomain: session.shop },
    include: { agentConfig: true },
  });

  const engineClientId = shop?.engineClientId ?? null;
  const engineUrl = process.env.ENGINE_URL || "https://omniweb-engine-rs6fr.ondigitalocean.app";
  const agentName  = shop?.agentConfig?.agentName  || "Omniweb AI";
  const greeting   = shop?.agentConfig?.greeting   || "Thank you for visiting our website today... it will be my pleasure to help you";

  return json({ engineClientId, engineUrl, agentName, greeting });
}

export default function TestConsole() {
  const { engineClientId, engineUrl, agentName, greeting } = useLoaderData<typeof loader>();
  const [voice, setVoice] = useState<"female" | "male">("female");
  const [mode,  setMode]  = useState<"voice" | "text">("voice");

  const voiceId = voice === "female" ? FEMALE_VOICE : MALE_VOICE;
  const widgetBase = engineClientId
    ? `${engineUrl}/widget/${engineClientId}`
    : null;

  const widgetUrl = widgetBase
    ? `${widgetBase}?voice=${voiceId}&mode=${mode}`
    : null;

  return (
    <Page
      fullWidth
      title="Agent Test Console"
      subtitle={`Test how shoppers experience "${agentName}" before going live`}
      backAction={{ url: "/app/agent", content: "Agent settings" }}
    >
      <div className="omni-page-shell">
      <Layout>
        {/* Hero */}
        <Layout.Section>
          <div className="omni-hero-card">
            <div className="omni-hero-card__inner">
              <BlockStack gap="300">
                <Text as="h2" variant="headingLg">
                  Talk to your AI agent
                </Text>
                <Text as="p" tone="subdued">
                  Select a voice, choose voice or text mode, then launch the session. This is exactly what shoppers will experience.
                </Text>
                <Text as="p" tone="subdued" variant="bodySm">
                  Opening message: <em>"{greeting}"</em>
                </Text>
              </BlockStack>
              {widgetUrl ? (
                <Button url={widgetUrl} target="_blank" variant="primary" size="large">
                  {mode === "voice" ? "Start voice session" : "Start text session"}
                </Button>
              ) : (
                <BlockStack gap="100">
                  <Badge tone="attention">Not configured</Badge>
                  <Text as="p" tone="subdued" variant="bodySm">
                    Save & sync your agent first
                  </Text>
                </BlockStack>
              )}
            </div>
          </div>
        </Layout.Section>

        {/* Voice picker */}
        <Layout.Section>
          <Card>
            <BlockStack gap="400">
              <div className="omni-card-accent" />
              <Text as="h2" variant="headingMd">Voice</Text>
              <Text as="p" tone="subdued">
                Choose whether your AI agent speaks in a female or male voice. You can change this any time.
              </Text>
              <div className="omni-voice-grid">
                {/* Female */}
                <button
                  type="button"
                  className={`omni-voice-card${voice === "female" ? " omni-voice-card--active" : ""}`}
                  onClick={() => setVoice("female")}
                >
                  <div className="omni-voice-card__avatar omni-voice-card__avatar--female">
                    <svg viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg" width="40" height="40">
                      <circle cx="24" cy="24" r="24" fill="#fce7f3"/>
                      <circle cx="24" cy="18" r="8" fill="#f9a8d4"/>
                      <ellipse cx="24" cy="36" rx="11" ry="7" fill="#f9a8d4"/>
                    </svg>
                  </div>
                  <BlockStack gap="100">
                    <Text as="p" fontWeight="semibold">Female voice</Text>
                    <Text as="p" tone="subdued" variant="bodySm">Warm, clear, professional</Text>
                  </BlockStack>
                  {voice === "female" && <span className="omni-voice-card__check">✓</span>}
                </button>

                {/* Male */}
                <button
                  type="button"
                  className={`omni-voice-card${voice === "male" ? " omni-voice-card--active" : ""}`}
                  onClick={() => setVoice("male")}
                >
                  <div className="omni-voice-card__avatar omni-voice-card__avatar--male">
                    <svg viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg" width="40" height="40">
                      <circle cx="24" cy="24" r="24" fill="#dbeafe"/>
                      <circle cx="24" cy="18" r="8" fill="#93c5fd"/>
                      <ellipse cx="24" cy="36" rx="11" ry="7" fill="#93c5fd"/>
                    </svg>
                  </div>
                  <BlockStack gap="100">
                    <Text as="p" fontWeight="semibold">Male voice</Text>
                    <Text as="p" tone="subdued" variant="bodySm">Confident, friendly, natural</Text>
                  </BlockStack>
                  {voice === "male" && <span className="omni-voice-card__check">✓</span>}
                </button>
              </div>
            </BlockStack>
          </Card>
        </Layout.Section>

        {/* Mode + Launch */}
        <Layout.Section>
          <Card>
            <BlockStack gap="400">
              <div className="omni-card-accent" />
              <Text as="h2" variant="headingMd">Session mode</Text>
              <InlineStack gap="300">
                <Button
                  variant={mode === "voice" ? "primary" : "secondary"}
                  onClick={() => setMode("voice")}
                >
                  Voice
                </Button>
                <Button
                  variant={mode === "text" ? "primary" : "secondary"}
                  onClick={() => setMode("text")}
                >
                  Text chat
                </Button>
              </InlineStack>
              <Text as="p" tone="subdued">
                {mode === "voice"
                  ? "Speak naturally — the agent will respond in real time with voice."
                  : "Type messages to test how the agent responds to written questions."}
              </Text>

              {widgetUrl ? (
                <Button url={widgetUrl} target="_blank" variant="primary" size="large">
                  {mode === "voice" ? "Open voice session" : "Open text session"}
                </Button>
              ) : (
                <Banner>
                  <Text as="p">Go to <strong>Agent Settings</strong>, save and sync, then come back to test.</Text>
                </Banner>
              )}
            </BlockStack>
          </Card>
        </Layout.Section>

        {/* Tips sidebar */}
        <Layout.Section variant="oneThird">
          <BlockStack gap="400">
            <Card>
              <BlockStack gap="300">
                <Text as="h2" variant="headingMd">What to check</Text>
                <div className="omni-muted-panel">
                  <BlockStack gap="200">
                    <Text as="p" fontWeight="semibold">1. Welcome message</Text>
                    <Text as="p" tone="subdued">Does the agent greet shoppers with your custom opening?</Text>
                    <Text as="p" fontWeight="semibold">2. Product questions</Text>
                    <Text as="p" tone="subdued">Ask about a product — does it answer from your knowledge base?</Text>
                    <Text as="p" fontWeight="semibold">3. Language</Text>
                    <Text as="p" tone="subdued">Try switching language if you have multiple enabled.</Text>
                    <Text as="p" fontWeight="semibold">4. Cart actions</Text>
                    <Text as="p" tone="subdued">Ask to add something to cart — does it confirm correctly?</Text>
                  </BlockStack>
                </div>
              </BlockStack>
            </Card>

            <Card>
              <BlockStack gap="300">
                <Text as="h2" variant="headingMd">Voice IDs used</Text>
                <BlockStack gap="100">
                  <Text as="p" tone="subdued" variant="bodySm">
                    Female: <code>aura-2-asteria-en</code>
                  </Text>
                  <Text as="p" tone="subdued" variant="bodySm">
                    Male: <code>aura-2-orion-en</code>
                  </Text>
                  <Text as="p" tone="subdued" variant="bodySm">
                    Powered by Deepgram Aura-2
                  </Text>
                </BlockStack>
              </BlockStack>
            </Card>
          </BlockStack>
        </Layout.Section>
      </Layout>
      </div>
    </Page>
  );
}

// Inline Banner helper (avoid extra import)
function Banner({ children }: { children: React.ReactNode }) {
  return (
    <div style={{
      background: "#fff3cd",
      border: "1px solid #ffc107",
      borderRadius: 8,
      padding: "12px 16px",
    }}>
      {children}
    </div>
  );
}

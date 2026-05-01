import { json } from "@remix-run/node";
import { useLoaderData } from "@remix-run/react";
import type { ReactNode } from "react";
import {
  BlockStack,
  Button,
  Card,
  Icon,
  InlineGrid,
  InlineStack,
  Layout,
  Page,
  Text,
} from "@shopify/polaris";
import {
  ChatIcon,
  GlobeIcon,
  SettingsIcon,
  StoreIcon,
} from "@shopify/polaris-icons";
import { authenticate } from "../shopify.server";
import { prisma } from "../db.server";
import { syncShopToEngine } from "../services/engine.server";
import { ensureStorefrontAccessToken } from "../services/storefront-token.server";

export async function loader({ request }: { request: Request }) {
  const { admin, session } = await authenticate.admin(request);
  const shop = await prisma.shop.upsert({
    where: { shopDomain: session.shop },
    update: { status: "installed" },
    create: { shopDomain: session.shop, status: "installed" },
    include: { subscription: true, agentConfig: true },
  });
  let engineClientId = shop.engineClientId;
  let engineSyncError: string | null = null;
  try {
    const storefrontToken = await ensureStorefrontAccessToken({
      admin,
      shopId: shop.id,
      shopDomain: session.shop,
      encryptedToken: shop.encryptedStorefrontToken,
    });
    const engineSync = await syncShopToEngine({
      shop_domain: session.shop,
      engine_client_id: shop.engineClientId,
      admin_access_token: session.accessToken,
      storefront_access_token: storefrontToken,
      granted_scopes: (session.scope || "").split(",").map((s) => s.trim()).filter(Boolean),
      storefront_api_version: process.env.SHOPIFY_API_VERSION || "2026-07",
      plan: shop.subscription?.plan || "starter",
      subscription_status: shop.subscription?.status || "trialing",
      assistant_enabled: Boolean(shop.agentConfig?.voiceEnabled ?? true),
      agent_config: shop.agentConfig || {},
    });
    if (engineSync.client_id && engineSync.client_id !== shop.engineClientId) {
      engineClientId = engineSync.client_id;
      await prisma.shop.update({
        where: { id: shop.id },
        data: { engineClientId },
      });
    }
  } catch (error) {
    engineSyncError = error instanceof Error ? error.message : "Engine sync failed";
  }

  const engineUrl = process.env.ENGINE_URL || "https://omniweb-engine-rs6fr.ondigitalocean.app";

  return json({
    shopDomain: session.shop,
    plan: shop?.subscription?.plan || "starter",
    status: shop?.subscription?.status || "trialing",
    agentConfigured: Boolean(shop?.agentConfig),
    agentName: shop?.agentConfig?.agentName || "Omniweb AI",
    languageCount: shop?.agentConfig?.supportedLanguages?.length ?? 1,
    engineConnected: Boolean(engineClientId),
    engineClientId,
    engineUrl,
    engineSyncError,
  });
}

function planLabel(plan: string) {
  return plan.charAt(0).toUpperCase() + plan.slice(1);
}

function StatusPill({
  children,
  tone,
}: {
  children: ReactNode;
  tone: "success" | "setup" | "sync";
}) {
  return (
    <span className={`omni-status-pill omni-status-pill--${tone}`}>
      {children}
    </span>
  );
}

function StepPill({ done, children }: { done?: boolean; children: ReactNode }) {
  return (
    <span className={`omni-step-pill ${done ? "omni-step-pill--done" : ""}`}>
      {children}
    </span>
  );
}

export default function Dashboard() {
  const data = useLoaderData<typeof loader>();
  const testUrl = data.engineClientId
    ? `${data.engineUrl}/widget/${data.engineClientId}`
    : null;

  return (
    <Page
      fullWidth
      title="Omniweb AI"
      subtitle="Your AI Sales & Revenue Agent for Shopify"
    >
      <div className="omni-page-shell">
      <Layout>
        <Layout.Section>
          <div className="omni-hero-card">
            <div className="omni-hero-card__inner">
              <BlockStack gap="300">
                <StatusPill tone={data.engineConnected ? "success" : "setup"}>
                  {data.engineConnected ? "Storefront ready" : "Setup in progress"}
                </StatusPill>
                <Text as="h2" variant="headingXl">
                  Turn visitors into helped shoppers.
                </Text>
                <Text as="p" tone="subdued">
                  Configure your agent, add store knowledge, and keep the storefront widget synced from one embedded workspace.
                </Text>
              </BlockStack>
              <InlineStack gap="300" align="end">
                <Button url="/app/agent" variant="primary">
                  Configure agent
                </Button>
                <Button url="/app/knowledge">
                  Add knowledge
                </Button>
              </InlineStack>
            </div>
          </div>
        </Layout.Section>

        {/* Quick-status strip */}
        <Layout.Section>
          <InlineGrid columns={{ xs: 1, md: 3 }} gap="400">
            {/* Subscription */}
            <Card>
              <BlockStack gap="300">
                <div className="omni-card-accent" />
                <InlineStack align="space-between">
                  <Text as="h2" variant="headingMd">Subscription</Text>
                  <Icon source={StoreIcon} tone="subdued" />
                </InlineStack>
                <StatusPill tone={data.status === "active" ? "success" : "setup"}>
                  {data.status === "trialing" ? "Free trial" : data.status}
                </StatusPill>
                <Text as="p" tone="subdued">
                  Plan: <strong>{planLabel(data.plan)}</strong>
                </Text>
                <Button url="/app/pricing" variant="secondary" size="slim">
                  Manage plan
                </Button>
              </BlockStack>
            </Card>

            {/* Agent */}
            <Card>
              <BlockStack gap="300">
                <div className="omni-card-accent" />
                <InlineStack align="space-between">
                  <Text as="h2" variant="headingMd">AI Agent</Text>
                  <Icon source={ChatIcon} tone="subdued" />
                </InlineStack>
                <StatusPill tone={data.agentConfigured ? "success" : "setup"}>
                  {data.agentConfigured ? "Configured" : "Needs setup"}
                </StatusPill>
                <Text as="p" tone="subdued">
                  {data.agentConfigured
                    ? `"${data.agentName}" — ${data.languageCount} language${data.languageCount !== 1 ? "s" : ""} active`
                    : "Set voice, text, languages, and sales behaviour."}
                </Text>
                <Button url="/app/agent" variant="primary" size="slim">
                  {data.agentConfigured ? "Edit agent" : "Configure agent"}
                </Button>
              </BlockStack>
            </Card>

            {/* Storefront widget */}
            <Card>
              <BlockStack gap="300">
                <div className="omni-card-accent" />
                <InlineStack align="space-between">
                  <Text as="h2" variant="headingMd">Storefront Widget</Text>
                  <Icon source={GlobeIcon} tone="subdued" />
                </InlineStack>
                <StatusPill tone={data.engineConnected ? "success" : "sync"}>
                  {data.engineConnected ? "Engine synced" : "Needs sync"}
                </StatusPill>
                <Text as="p" tone="subdued">
                  {data.engineSyncError
                    ? data.engineSyncError
                    : data.engineConnected
                    ? "Widget is live on your storefront."
                    : "Enable the widget in your theme app embeds."}
                </Text>
                <Button
                  url="shopify:admin/themes/current/editor?context=apps"
                  variant="secondary"
                  size="slim"
                >
                  Open theme editor
                </Button>
              </BlockStack>
            </Card>
          </InlineGrid>
        </Layout.Section>

        {/* Quick actions */}
        <Layout.Section>
          <Card>
            <BlockStack gap="400">
              <Text as="h2" variant="headingMd">Quick actions</Text>
              <InlineGrid columns={{ xs: 1, sm: 2, md: 4 }} gap="300">
                <Button url="/app/agent" icon={SettingsIcon}>
                  Agent settings
                </Button>
                <Button url="/app/knowledge" icon={GlobeIcon}>
                  Knowledge base
                </Button>
                <Button url="/app/analytics" icon={ChatIcon}>
                  View analytics
                </Button>
                {testUrl ? (
                  <Button url={testUrl} target="_blank" variant="secondary">
                    Test live widget
                  </Button>
                ) : (
                  <Button url="/app/test" variant="secondary">
                    Test live widget
                  </Button>
                )}
              </InlineGrid>
            </BlockStack>
          </Card>
        </Layout.Section>

        {/* Getting started checklist */}
        <Layout.Section>
          <Card>
            <BlockStack gap="400">
              <Text as="h2" variant="headingMd">Getting started</Text>
              <InlineGrid columns={{ xs: 1, md: 3 }} gap="300">
                <BlockStack gap="200">
                  <InlineStack gap="200" align="start">
                    <StepPill done={data.agentConfigured}>
                      {data.agentConfigured ? "✓" : "1"}
                    </StepPill>
                    <Text as="p" fontWeight="semibold">Configure your agent</Text>
                  </InlineStack>
                  <Text as="p" tone="subdued">
                    Set your agent name, greeting, goals, and the languages you want to support.
                  </Text>
                </BlockStack>
                <BlockStack gap="200">
                  <InlineStack gap="200" align="start">
                    <StepPill>2</StepPill>
                    <Text as="p" fontWeight="semibold">Add knowledge sources</Text>
                  </InlineStack>
                  <Text as="p" tone="subdued">
                    Paste URLs of your FAQ pages, policies, or product info so the agent can answer accurately.
                  </Text>
                </BlockStack>
                <BlockStack gap="200">
                  <InlineStack gap="200" align="start">
                    <StepPill done={data.engineConnected}>
                      {data.engineConnected ? "✓" : "3"}
                    </StepPill>
                    <Text as="p" fontWeight="semibold">Enable storefront widget</Text>
                  </InlineStack>
                  <Text as="p" tone="subdued">
                    Go to Online Store → Themes → Customise and toggle on the Omniweb app embed.
                  </Text>
                </BlockStack>
              </InlineGrid>
            </BlockStack>
          </Card>
        </Layout.Section>
      </Layout>
      </div>
    </Page>
  );
}

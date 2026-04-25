import { json } from "@remix-run/node";
import { useLoaderData } from "@remix-run/react";
import {
  Badge,
  BlockStack,
  Button,
  Card,
  InlineGrid,
  Layout,
  Page,
  Text,
} from "@shopify/polaris";
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
      granted_scopes: (session.scope || "").split(",").map((scope) => scope.trim()).filter(Boolean),
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
    // The dashboard should still render if the Engine is temporarily unavailable.
  }

  return json({
    shopDomain: session.shop,
    plan: shop?.subscription?.plan || "starter",
    status: shop?.subscription?.status || "trialing",
    agentConfigured: Boolean(shop?.agentConfig),
    engineConnected: Boolean(engineClientId),
    engineSyncError,
  });
}

export default function Dashboard() {
  const data = useLoaderData<typeof loader>();

  return (
    <Page title="Omniweb AI" subtitle="AI Sales / Revenue Agent for your Shopify store">
      <Layout>
        <Layout.Section>
          <InlineGrid columns={{ xs: 1, md: 3 }} gap="400">
            <Card>
              <BlockStack gap="300">
                <Text as="h2" variant="headingMd">Subscription</Text>
                <Badge tone={data.status === "active" ? "success" : "attention"}>{data.status}</Badge>
                <Text as="p" tone="subdued">Current plan: {data.plan}</Text>
                <Button url="/app/billing">Manage plan</Button>
              </BlockStack>
            </Card>
            <Card>
              <BlockStack gap="300">
                <Text as="h2" variant="headingMd">Agent</Text>
                <Badge tone={data.agentConfigured ? "success" : "attention"}>
                  {data.agentConfigured ? "Configured" : "Needs setup"}
                </Badge>
                <Text as="p" tone="subdued">Set voice, text, languages, and sales behavior.</Text>
                <Button url="/app/agent">Configure agent</Button>
              </BlockStack>
            </Card>
            <Card>
              <BlockStack gap="300">
                <Text as="h2" variant="headingMd">Storefront Widget</Text>
                <Badge tone={data.engineConnected ? "success" : "attention"}>
                  {data.engineConnected ? "Engine synced" : "Needs sync"}
                </Badge>
                <Text as="p" tone="subdued">
                  {data.engineSyncError || "Enable the Omniweb widget from Shopify theme app embeds."}
                </Text>
                <Button url="shopify:admin/themes/current/editor?context=apps">Open theme editor</Button>
              </BlockStack>
            </Card>
          </InlineGrid>
        </Layout.Section>
      </Layout>
    </Page>
  );
}

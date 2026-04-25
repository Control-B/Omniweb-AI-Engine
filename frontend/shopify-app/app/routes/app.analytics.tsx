import { json } from "@remix-run/node";
import { useLoaderData } from "@remix-run/react";
import { BlockStack, Card, InlineGrid, Layout, Page, Text } from "@shopify/polaris";
import { authenticate } from "../shopify.server";
import { prisma } from "../db.server";
import { getEngineAnalytics, type EngineAnalytics } from "../services/engine.server";

export async function loader({ request }: { request: Request }) {
  const { session } = await authenticate.admin(request);
  await prisma.shop.upsert({
    where: { shopDomain: session.shop },
    update: {},
    create: { shopDomain: session.shop, status: "installed" },
  });

  try {
    const analytics = await getEngineAnalytics(session.shop);
    return json({ analytics, error: null as string | null });
  } catch (error) {
    const fallback: EngineAnalytics = {
      ok: false,
      conversations: 0,
      active_sessions: 0,
      qualified_leads: 0,
      discount_requests: 0,
      approved_discounts: 0,
      recent_sessions: [],
    };
    return json({
      analytics: fallback,
      error: error instanceof Error ? error.message : "Unable to load Engine analytics",
    });
  }
}

export default function Analytics() {
  const { analytics, error } = useLoaderData<typeof loader>();

  return (
    <Page title="Analytics" subtitle="Conversation usage, lead quality, and revenue-agent activity">
      <Layout>
        <Layout.Section>
          <InlineGrid columns={{ xs: 1, md: 3 }} gap="400">
            <Card>
              <BlockStack gap="200">
                <Text as="h2" variant="headingMd">Conversations</Text>
                <Text as="p" variant="heading2xl">{analytics.conversations}</Text>
                <Text as="p" tone="subdued">{analytics.active_sessions} active sessions</Text>
              </BlockStack>
            </Card>
            <Card>
              <BlockStack gap="200">
                <Text as="h2" variant="headingMd">Qualified leads</Text>
                <Text as="p" variant="heading2xl">{analytics.qualified_leads}</Text>
              </BlockStack>
            </Card>
            <Card>
              <BlockStack gap="200">
                <Text as="h2" variant="headingMd">Discount requests</Text>
                <Text as="p" variant="heading2xl">{analytics.discount_requests}</Text>
                <Text as="p" tone="subdued">{analytics.approved_discounts} approved</Text>
              </BlockStack>
            </Card>
          </InlineGrid>
        </Layout.Section>
        <Layout.Section>
          <Card>
            <BlockStack gap="300">
              <Text as="h2" variant="headingMd">Recent sessions</Text>
              {error && <Text as="p" tone="critical">{error}</Text>}
              {analytics.recent_sessions.length === 0 ? (
                <Text as="p" tone="subdued">No storefront assistant sessions yet.</Text>
              ) : (
                analytics.recent_sessions.map((session) => (
                  <BlockStack gap="100" key={session.id}>
                    <Text as="p" fontWeight="semibold">
                      {session.last_intent || "Storefront conversation"} · {session.messages} messages
                    </Text>
                    <Text as="p" tone="subdued">
                      {session.current_page_url || "No page captured"} · {session.last_seen_at || "No timestamp"}
                    </Text>
                  </BlockStack>
                ))
              )}
            </BlockStack>
          </Card>
        </Layout.Section>
      </Layout>
    </Page>
  );
}

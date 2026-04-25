import { json } from "@remix-run/node";
import { useLoaderData } from "@remix-run/react";
import { BlockStack, Card, InlineGrid, Layout, Page, Text } from "@shopify/polaris";
import { authenticate } from "../shopify.server";
import { prisma } from "../db.server";

export async function loader({ request }: { request: Request }) {
  const { session } = await authenticate.admin(request);
  const shop = await prisma.shop.findUnique({
    where: { shopDomain: session.shop },
    include: { conversations: true, usageMeters: true },
  });

  return json({
    conversations: shop?.conversations.length || 0,
    leads: shop?.conversations.filter((conversation: { leadScore: number | null }) => (conversation.leadScore || 0) >= 70).length || 0,
    usage: shop?.usageMeters || [],
  });
}

export default function Analytics() {
  const data = useLoaderData<typeof loader>();

  return (
    <Page title="Analytics" subtitle="Conversation usage, lead quality, and revenue-agent activity">
      <Layout>
        <Layout.Section>
          <InlineGrid columns={{ xs: 1, md: 3 }} gap="400">
            <Card>
              <BlockStack gap="200">
                <Text as="h2" variant="headingMd">Conversations</Text>
                <Text as="p" variant="heading2xl">{data.conversations}</Text>
              </BlockStack>
            </Card>
            <Card>
              <BlockStack gap="200">
                <Text as="h2" variant="headingMd">Qualified leads</Text>
                <Text as="p" variant="heading2xl">{data.leads}</Text>
              </BlockStack>
            </Card>
            <Card>
              <BlockStack gap="200">
                <Text as="h2" variant="headingMd">Usage meters</Text>
                <Text as="p" variant="heading2xl">{data.usage.length}</Text>
              </BlockStack>
            </Card>
          </InlineGrid>
        </Layout.Section>
      </Layout>
    </Page>
  );
}

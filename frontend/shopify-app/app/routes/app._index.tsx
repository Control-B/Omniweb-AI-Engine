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

export async function loader({ request }: { request: Request }) {
  const { session } = await authenticate.admin(request);
  const shop = await prisma.shop.findUnique({
    where: { shopDomain: session.shop },
    include: { subscription: true, agentConfig: true },
  });

  return json({
    shopDomain: session.shop,
    plan: shop?.subscription?.plan || "starter",
    status: shop?.subscription?.status || "trialing",
    agentConfigured: Boolean(shop?.agentConfig),
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
                <Badge>Theme app embed</Badge>
                <Text as="p" tone="subdued">Enable the Omniweb widget from Shopify theme app embeds.</Text>
                <Button url="shopify:admin/themes/current/editor?context=apps">Open theme editor</Button>
              </BlockStack>
            </Card>
          </InlineGrid>
        </Layout.Section>
      </Layout>
    </Page>
  );
}

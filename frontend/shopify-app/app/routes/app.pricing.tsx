import { json } from "@remix-run/node";
import { useLoaderData } from "@remix-run/react";
import {
  Badge,
  Banner,
  BlockStack,
  Button,
  Card,
  Divider,
  InlineGrid,
  Layout,
  List,
  Page,
  Text,
} from "@shopify/polaris";
import {
  authenticate,
  STARTER_PLAN,
  GROWTH_PLAN,
  PRO_PLAN,
} from "../shopify.server";
import { prisma } from "../db.server";

const PLANS = {
  starter: {
    name: STARTER_PLAN,
    price: 149,
    tagline: "For small Shopify stores",
    conversations: "500 conversations/mo",
    features: [
      "1 AI storefront agent",
      "Text chat + Voice mode",
      "10 languages supported",
      "Knowledge base (5 docs)",
      "Basic analytics",
      "Email support",
    ],
  },
  growth: {
    name: GROWTH_PLAN,
    price: 299,
    tagline: "For growing stores & teams",
    conversations: "2,000 conversations/mo",
    features: [
      "3 AI storefront agents",
      "Text chat + Voice mode",
      "All 26 languages",
      "Unlimited knowledge base",
      "Advanced analytics + summaries",
      "Shopify native integration",
      "Priority support",
    ],
  },
  pro: {
    name: PRO_PLAN,
    price: 499,
    tagline: "For agencies & high-volume stores",
    conversations: "Unlimited conversations",
    features: [
      "Unlimited AI agents",
      "Text chat + Voice mode",
      "All 26 languages",
      "Unlimited knowledge base",
      "Full analytics suite",
      "White-label widget",
      "Multi-store support",
      "Dedicated support",
    ],
  },
} as const;

export async function loader({ request }: { request: Request }) {
  const { session } = await authenticate.admin(request);
  const shop = await prisma.shop.findUnique({
    where: { shopDomain: session.shop },
    include: { subscription: true },
  });

  const currentPlan: keyof typeof PLANS =
    (shop?.subscription?.plan as keyof typeof PLANS) || "starter";
  const status = shop?.subscription?.status || "trialing";

  return json({ currentPlan, status });
}

/**
 * Billing is intentionally disabled while the app stabilizes. Shopify Billing API
 * can be re-enabled once Partner Dashboard pricing mode is confirmed.
 */
export async function action({ request }: { request: Request }) {
  await authenticate.admin(request);
  return json({
    error:
      "Billing is temporarily disabled while the Shopify app deployment is stabilized. Your app features remain available.",
  });
}

export default function Pricing() {
  const { currentPlan, status } = useLoaderData<typeof loader>();

  return (
    <Page
      fullWidth
      title="Pricing"
      subtitle="Pricing is visible while Shopify Billing is temporarily paused during launch stabilization."
    >
      <div className="omni-page-shell">
        <Layout>
          <Layout.Section>
            <Banner title="Billing temporarily paused" tone="warning">
              <p>
                Shopify subscription checkout is disabled for now so the embedded app can deploy and operate normally. Plans are shown for reference, and billing can be re-enabled after the app is stable.
              </p>
            </Banner>
          </Layout.Section>

          {status === "trialing" && (
            <Layout.Section>
              <Banner title="Free trial" tone="info">
                <p>
                  Your trial is active. Plans are shown below for reference while
                  Shopify subscription checkout is paused.
                </p>
              </Banner>
            </Layout.Section>
          )}

          <Layout.Section>
            <InlineGrid columns={{ xs: 1, md: 3 }} gap="400">
              {(
                Object.entries(PLANS) as [
                  string,
                  (typeof PLANS)[keyof typeof PLANS],
                ][]
              ).map(([slug, plan]) => {
                const isCurrent = currentPlan === slug;
                return (
                  <Card key={slug}>
                    <BlockStack gap="400">
                      <BlockStack gap="200">
                        <Text as="h2" variant="headingLg" fontWeight="bold">
                          {plan.name}
                        </Text>
                        <Text as="p" tone="subdued">
                          {plan.tagline}
                        </Text>
                        <Text as="p" variant="heading2xl" fontWeight="bold">
                          ${plan.price}
                          <Text as="span" variant="bodyMd" tone="subdued">
                            /mo
                          </Text>
                        </Text>
                        <Text as="p" tone="subdued">
                          7-day free trial
                        </Text>
                        {isCurrent && (
                          <Badge
                            tone={status === "active" ? "success" : "attention"}
                          >
                            {status}
                          </Badge>
                        )}
                      </BlockStack>

                      <Divider />

                      <BlockStack gap="100">
                        <Text as="p" fontWeight="semibold">
                          {plan.conversations}
                        </Text>
                      </BlockStack>

                      <List type="bullet">
                        {plan.features.map((feature) => (
                          <List.Item key={feature}>{feature}</List.Item>
                        ))}
                      </List>

                      <Button
                        variant={isCurrent ? "secondary" : "primary"}
                        fullWidth
                        disabled
                      >
                        {isCurrent ? "Current plan" : "Billing paused"}
                      </Button>
                    </BlockStack>
                  </Card>
                );
              })}
            </InlineGrid>
          </Layout.Section>

          <Layout.Section>
            <Banner title="Financial & Transaction Policy" tone="warning">
              <p>
                The Omniweb AI agent can <strong>add products to carts</strong> and{" "}
                <strong>send cart reminders</strong>, but it{" "}
                <strong>
                  cannot process checkouts, issue refunds, or handle any financial
                  transactions
                </strong>
                . All financial requests are immediately escalated to a human
                representative.
              </p>
            </Banner>
          </Layout.Section>
        </Layout>
      </div>
    </Page>
  );
}

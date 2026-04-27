import { json } from "@remix-run/node";
import { Form, useLoaderData, useActionData } from "@remix-run/react";
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

function planSlugFromShopifyName(name: string): keyof typeof PLANS {
  if (name === GROWTH_PLAN) return "growth";
  if (name === PRO_PLAN) return "pro";
  return "starter";
}

function subscriptionStatusForDb(
  status: string,
): "active" | "trialing" | string {
  const u = status.toUpperCase();
  if (u === "ACTIVE" || u === "ACCEPTED") return "active";
  if (u === "PENDING") return "trialing";
  return status.toLowerCase();
}

const BILLING_PLANS = [STARTER_PLAN, GROWTH_PLAN, PRO_PLAN] as const;

export async function loader({ request }: { request: Request }) {
  const { session, billing } = await authenticate.admin(request);
  const shop = await prisma.shop.findUnique({
    where: { shopDomain: session.shop },
    include: { subscription: true },
  });

  let currentPlan: keyof typeof PLANS =
    (shop?.subscription?.plan as keyof typeof PLANS) || "starter";
  let status = shop?.subscription?.status || "trialing";

  const isTest = process.env.NODE_ENV !== "production";

  try {
    const check = await billing.check({
      plans: [...BILLING_PLANS],
      isTest,
    });

    if (check.hasActivePayment && check.appSubscriptions.length > 0 && shop) {
      const sub = check.appSubscriptions[0];
      const slug = planSlugFromShopifyName(sub.name);
      const dbStatus = subscriptionStatusForDb(sub.status);

      await prisma.subscription.upsert({
        where: { shopId: shop.id },
        update: {
          plan: slug,
          status: dbStatus,
          shopifySubscriptionGid: sub.id,
        },
        create: {
          shopId: shop.id,
          plan: slug,
          status: dbStatus,
          shopifySubscriptionGid: sub.id,
        },
      });

      currentPlan = slug;
      status = dbStatus;
    }
  } catch (err) {
    console.error("[pricing] billing.check failed (using DB cache):", err);
  }

  return json({ currentPlan, status });
}

/**
 * Opens Shopify's app subscription approval flow (merchant pays via Shopify invoice).
 * Do not use billing.require here — that skips the payment UI when a trial exists.
 */
export async function action({ request }: { request: Request }) {
  try {
    const { billing } = await authenticate.admin(request);
    const form = await request.formData();
    const planKey = String(form.get("plan") || "starter") as keyof typeof PLANS;
    const selected = PLANS[planKey] || PLANS.starter;
    const isTest = process.env.NODE_ENV !== "production";

    await billing.request({
      plan: selected.name,
      isTest,
    });
  } catch (err) {
    if (err instanceof Response) throw err;
    const msg =
      err instanceof Error ? err.message : "Could not open Shopify billing.";
    return json({ error: msg });
  }
  return json({ error: "Unexpected: billing did not redirect." });
}

export default function Pricing() {
  const { currentPlan, status } = useLoaderData<typeof loader>();
  const actionData = useActionData<typeof action>();

  return (
    <Page
      fullWidth
      title="Pricing"
      subtitle="Plans bill through Shopify: you approve the subscription once in Shopify, and charges appear on your regular Shopify invoice."
    >
      <div className="omni-page-shell">
        <Layout>
          <Layout.Section>
            <Banner title="Shopify subscription billing" tone="info">
              <p>
                When you choose a plan, Shopify opens a secure page to approve the app
                charge. Payment is handled entirely by Shopify — not a separate card
                form on our site.
              </p>
            </Banner>
          </Layout.Section>

          {actionData && "error" in actionData && actionData.error && (
            <Layout.Section>
              <Banner title="Could not start billing" tone="critical">
                <p>{actionData.error}</p>
              </Banner>
            </Layout.Section>
          )}

          {status === "trialing" && (
            <Layout.Section>
              <Banner title="Free trial" tone="info">
                <p>
                  Your trial is active. Pick a plan below to link a Shopify subscription
                  for when the trial ends.
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

                      <Form method="post">
                        <input type="hidden" name="plan" value={slug} />
                        <Button
                          submit
                          variant={isCurrent ? "secondary" : "primary"}
                          fullWidth
                          disabled={isCurrent && status === "active"}
                        >
                          {isCurrent && status === "active"
                            ? "Current plan"
                            : isCurrent
                              ? "Confirm with Shopify"
                              : `Subscribe with Shopify — ${plan.name}`}
                        </Button>
                      </Form>
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

import { json, redirect } from "@remix-run/node";
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
import { authenticate } from "../shopify.server";
import { prisma } from "../db.server";
import { syncShopToEngine } from "../services/engine.server";
import { ensureStorefrontAccessToken } from "../services/storefront-token.server";

const STARTER_PLAN = "Starter";
const GROWTH_PLAN = "Growth";
const PRO_PLAN = "Pro";

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
  return json({
    currentPlan: shop?.subscription?.plan || "starter",
    status: shop?.subscription?.status || "trialing",
  });
}

export async function action({ request }: { request: Request }) {
  try {
    const { admin, session, billing } = await authenticate.admin(request);
    const form = await request.formData();
    const plan = String(form.get("plan") || "starter") as keyof typeof PLANS;
    const selected = PLANS[plan] || PLANS.starter;

    // billing.require redirects to Shopify's billing approval page if no active sub.
    // It throws a Response (redirect) on success path — let that propagate.
    // Only catch real errors.
    try {
      await billing.require({
        plans: [selected.name],
        isTest: process.env.NODE_ENV !== "production",
        onFailure: async () =>
          billing.request({
            plan: selected.name,
            isTest: process.env.NODE_ENV !== "production",
          }),
      });
    } catch (billingErr) {
      // billing.require throws a Response redirect on the approval flow — let it through.
      if (billingErr instanceof Response) throw billingErr;
      // Real billing config error: record it in our DB but don't block.
      console.error("Billing require error (non-fatal):", billingErr);
    }

    const shop = await prisma.shop.upsert({
      where: { shopDomain: session.shop },
      update: {},
      create: { shopDomain: session.shop, status: "installed" },
    });

    await prisma.subscription.upsert({
      where: { shopId: shop.id },
      update: { plan, status: "trialing" },
      create: { shopId: shop.id, plan, status: "trialing" },
    });

    const storefrontToken = await ensureStorefrontAccessToken({
      admin,
      shopId: shop.id,
      shopDomain: session.shop,
      encryptedToken: shop.encryptedStorefrontToken,
    });

    try {
      const engineSync = await syncShopToEngine({
        shop_domain: session.shop,
        engine_client_id: shop.engineClientId,
        admin_access_token: session.accessToken,
        storefront_access_token: storefrontToken,
        granted_scopes: (session.scope || "").split(",").map((s) => s.trim()).filter(Boolean),
        storefront_api_version: process.env.SHOPIFY_API_VERSION || "2026-07",
        plan,
        subscription_status: "trialing",
        assistant_enabled: true,
        agent_config: {},
      });
      if (engineSync.client_id && engineSync.client_id !== shop.engineClientId) {
        await prisma.shop.update({
          where: { id: shop.id },
          data: { engineClientId: engineSync.client_id },
        });
      }
    } catch (syncErr) {
      console.error("Engine sync error (non-fatal):", syncErr);
    }

    return json({ upgraded: true, plan, error: null });
  } catch (err) {
    if (err instanceof Response) throw err;
    const msg = err instanceof Error ? err.message : "Something went wrong. Please try again.";
    return json({ upgraded: false, plan: null, error: msg });
  }
}

export default function Pricing() {
  const { currentPlan, status } = useLoaderData<typeof loader>();
  const actionData = useActionData<typeof action>();

  return (
    <Page
      fullWidth
      title="Pricing"
      subtitle="All plans include a 7-day free trial. Shopify billing handles subscription charges on your merchant invoice."
    >
      <div className="omni-page-shell">
      <Layout>
        {actionData?.upgraded && (
          <Layout.Section>
            <Banner title="Plan selected" tone="success">
              <p>Your plan has been updated. Shopify may ask you to approve the charge — check your email if prompted.</p>
            </Banner>
          </Layout.Section>
        )}
        {actionData?.error && (
          <Layout.Section>
            <Banner title="Could not change plan" tone="critical">
              <p>{actionData.error}</p>
            </Banner>
          </Layout.Section>
        )}
        {!actionData && status === "trialing" && (
          <Layout.Section>
            <Banner title="You're on a free trial" tone="info">
              <p>Your trial is active. Choose a plan below to continue after the trial ends.</p>
            </Banner>
          </Layout.Section>
        )}

        <Layout.Section>
          <InlineGrid columns={{ xs: 1, md: 3 }} gap="400">
            {(Object.entries(PLANS) as [string, typeof PLANS[keyof typeof PLANS]][]).map(([slug, plan]) => {
              const isCurrent = currentPlan === slug;
              return (
                <Card key={slug}>
                  <BlockStack gap="400">
                    <BlockStack gap="200">
                      <Text as="h2" variant="headingLg" fontWeight="bold">{plan.name}</Text>
                      <Text as="p" tone="subdued">{plan.tagline}</Text>
                      <Text as="p" variant="heading2xl" fontWeight="bold">${plan.price}<Text as="span" variant="bodyMd" tone="subdued">/mo</Text></Text>
                      <Text as="p" tone="subdued">7-day free trial</Text>
                      {isCurrent && (
                        <Badge tone={status === "active" ? "success" : "attention"}>{status}</Badge>
                      )}
                    </BlockStack>

                    <Divider />

                    <BlockStack gap="100">
                      <Text as="p" fontWeight="semibold">{plan.conversations}</Text>
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
                          ? "Reactivate plan"
                          : `Choose ${plan.name}`}
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
              <strong>cannot process checkouts, issue refunds, or handle any financial transactions</strong>.
              All financial requests are immediately escalated to a human representative.
            </p>
          </Banner>
        </Layout.Section>
      </Layout>
      </div>
    </Page>
  );
}

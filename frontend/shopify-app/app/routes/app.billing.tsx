import { json, redirect } from "@remix-run/node";
import { Form, useLoaderData } from "@remix-run/react";
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
  const { admin, session, billing } = await authenticate.admin(request);
  const form = await request.formData();
  const plan = String(form.get("plan") || "starter") as keyof typeof PLANS;
  const selected = PLANS[plan] || PLANS.starter;

  await billing.require({
    plans: [selected.name],
    isTest: process.env.NODE_ENV !== "production",
    onFailure: async () =>
      billing.request({
        plan: selected.name,
        isTest: process.env.NODE_ENV !== "production",
      }),
  });

  const shop = await prisma.shop.upsert({
    where: { shopDomain: session.shop },
    update: {},
    create: { shopDomain: session.shop, status: "installed" },
  });

  await prisma.subscription.upsert({
    where: { shopId: shop.id },
    update: { plan, status: "active" },
    create: { shopId: shop.id, plan, status: "active" },
  });

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
    plan,
    subscription_status: "active",
    assistant_enabled: true,
    agent_config: {},
  });
  if (engineSync.client_id && engineSync.client_id !== shop.engineClientId) {
    await prisma.shop.update({
      where: { id: shop.id },
      data: { engineClientId: engineSync.client_id },
    });
  }

  return redirect("/app/billing?upgraded=1");
}

export default function Pricing() {
  const { currentPlan, status } = useLoaderData<typeof loader>();

  return (
    <Page
      title="Pricing"
      subtitle="Shopify Billing handles subscriptions on the merchant invoice. All plans include a 7-day free trial."
    >
      <Layout>
        {status === "trialing" && (
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
    </Page>
  );
}

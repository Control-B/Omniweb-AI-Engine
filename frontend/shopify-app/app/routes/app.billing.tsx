import { json, redirect } from "@remix-run/node";
import { Form, useLoaderData } from "@remix-run/react";
import { Badge, BlockStack, Button, Card, InlineGrid, Layout, Page, Text } from "@shopify/polaris";
import { authenticate } from "../shopify.server";
import { prisma } from "../db.server";

const STARTER_PLAN = "Starter";
const GROWTH_PLAN = "Growth";
const PRO_PLAN = "Pro";

const PLANS = {
  starter: {
    name: STARTER_PLAN,
    price: 29,
    conversations: "1,000 conversations/mo",
    features: ["Voice + text assistant", "Basic product guidance", "250 products indexed"],
  },
  growth: {
    name: GROWTH_PLAN,
    price: 99,
    conversations: "5,000 conversations/mo",
    features: ["Multilingual assistant", "URL knowledge/RAG", "Navigation agent", "2,500 products indexed"],
  },
  pro: {
    name: PRO_PLAN,
    price: 249,
    conversations: "25,000 conversations/mo",
    features: ["Advanced analytics", "Priority processing", "25,000 products indexed", "Premium support"],
  },
} as const;

export async function loader({ request }: { request: Request }) {
  const { session } = await authenticate.admin(request);
  const shop = await prisma.shop.findUnique({
    where: { shopDomain: session.shop },
    include: { subscription: true },
  });
  return json({ currentPlan: shop?.subscription?.plan || "starter", status: shop?.subscription?.status || "trialing" });
}

export async function action({ request }: { request: Request }) {
  const { session, billing } = await authenticate.admin(request);
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

  return redirect("/app/billing?billing=confirmed");
}

export default function Billing() {
  const { currentPlan, status } = useLoaderData<typeof loader>();

  return (
    <Page title="Plan and Billing" subtitle="Shopify Billing handles subscriptions on the merchant invoice">
      <Layout>
        <Layout.Section>
          <InlineGrid columns={{ xs: 1, md: 3 }} gap="400">
            {Object.entries(PLANS).map(([slug, plan]) => (
              <Card key={slug}>
                <BlockStack gap="400">
                  <BlockStack gap="100">
                    <Text as="h2" variant="headingMd">{plan.name}</Text>
                    <Text as="p" variant="heading2xl">${plan.price}/mo</Text>
                    <Text as="p" tone="subdued">7-day free trial</Text>
                    {currentPlan === slug && <Badge tone={status === "active" ? "success" : "attention"}>{status}</Badge>}
                  </BlockStack>
                  <Text as="p">{plan.conversations}</Text>
                  <BlockStack gap="100">
                    {plan.features.map((feature) => (
                      <Text as="p" key={feature} tone="subdued">- {feature}</Text>
                    ))}
                  </BlockStack>
                  <Form method="post">
                    <input type="hidden" name="plan" value={slug} />
                    <Button submit variant={currentPlan === slug ? "secondary" : "primary"}>
                      {currentPlan === slug ? "Current plan" : `Choose ${plan.name}`}
                    </Button>
                  </Form>
                </BlockStack>
              </Card>
            ))}
          </InlineGrid>
        </Layout.Section>
      </Layout>
    </Page>
  );
}

import { json } from "@remix-run/node";
import { useLoaderData } from "@remix-run/react";
import {
  Badge,
  Banner,
  BlockStack,
  Button,
  Divider,
  InlineGrid,
  Layout,
  List,
  Page,
  Text,
} from "@shopify/polaris";
import { authenticate } from "../shopify.server";
import { prisma } from "../db.server";

const PLANS = {
  starter: {
    name: "Starter",
    price: 149,
    positioning: "AI Revenue Agent",
    tagline: "Voice and text AI for storefront shoppers",
    engagements: "500 AI engagements/mo",
    features: [
      "Voice AI agent for guided selling",
      "Text chat AI agent",
      "Lead capture and qualification",
      "Website, product, and service knowledge",
      "Multilingual shopper support",
      "Basic analytics and email support",
    ],
  },
  growth: {
    name: "Growth",
    price: 299,
    badge: "Most Popular",
    positioning: "Conversion OS",
    tagline: "Voice, text, and AI Telephony for growing businesses",
    engagements: "2,000 AI engagements/mo",
    features: [
      "Everything in Starter",
      "AI Telephony",
      "Call Us storefront widget",
      "Human escalation by phone and email",
      "Sales guidance, objections, upsells, and cross-sells",
      "Unlimited knowledge base",
      "Priority support",
    ],
  },
  pro: {
    name: "Scale",
    price: 499,
    positioning: "AI Sales Team",
    tagline: "Higher-volume AI sales coverage across website, voice, and phone",
    engagements: "5,000 AI engagements/mo",
    features: [
      "Everything in Growth",
      "Higher-volume AI engagement allowance",
      "Advanced workflows",
      "Priority orchestration",
      "Multi-location and team support ready",
      "Unlimited knowledge base",
      "Advanced analytics + summaries",
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

  const savedPlan = shop?.subscription?.plan || "starter";
  const currentPlan: keyof typeof PLANS = Object.prototype.hasOwnProperty.call(
    PLANS,
    savedPlan,
  )
    ? (savedPlan as keyof typeof PLANS)
    : "starter";
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
      subtitle="Choose the AI revenue plan that fits your customer volume and sales workflow."
    >
      <div className="omni-page-shell">
        <Layout>
          <Layout.Section>
            <div className="omni-hero-card">
              <div className="omni-hero-card__inner">
                <BlockStack gap="300">
                  <Badge tone="success">AI Revenue Agent</Badge>
                  <Text as="h2" variant="headingXl">
                    Sell, support, and recover shoppers across chat, voice, and phone.
                  </Text>
                  <Text as="p" tone="subdued">
                    Omniweb is positioned as an AI sales teammate, not a commodity chatbot. Every plan is built around guided buying, lead capture, escalation, and higher conversion.
                  </Text>
                </BlockStack>
              </div>
            </div>
          </Layout.Section>

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
            <div className="omni-value-strip">
              <div className="omni-value-pill">
                <div className="omni-value-pill__kicker">Conversion First</div>
                <Text as="p" fontWeight="semibold">
                  Guides buying decisions, handles objections, and recommends the next best product.
                </Text>
              </div>
              <div className="omni-value-pill">
                <div className="omni-value-pill__kicker">Multi-Channel</div>
                <Text as="p" fontWeight="semibold">
                  Website chat, voice, and AI phone coverage from the same brand experience.
                </Text>
              </div>
              <div className="omni-value-pill">
                <div className="omni-value-pill__kicker">Human Escalation</div>
                <Text as="p" fontWeight="semibold">
                  Sends complex requests to the owner or team by phone and email.
                </Text>
              </div>
            </div>
          </Layout.Section>

          <Layout.Section>
            <InlineGrid columns={{ xs: 1, md: 3 }} gap="400">
              {(
                Object.entries(PLANS) as [
                  string,
                  (typeof PLANS)[keyof typeof PLANS],
                ][]
              ).map(([slug, plan]) => {
                const isCurrent = currentPlan === slug;
                const isFeatured = "badge" in plan && Boolean(plan.badge);
                return (
                  <div
                    key={slug}
                    className={[
                      "omni-pricing-card",
                      isFeatured ? "omni-pricing-card--featured" : "",
                      isCurrent ? "omni-pricing-card--current" : "",
                    ].filter(Boolean).join(" ")}
                  >
                    <div className="omni-pricing-card__surface">
                      <BlockStack gap="400">
                      <BlockStack gap="200">
                        <Text as="h2" variant="headingLg" fontWeight="bold">
                          {plan.name}
                        </Text>
                        {"badge" in plan && plan.badge && (
                          <Badge tone="success">{plan.badge}</Badge>
                        )}
                        <Text as="p" fontWeight="semibold">
                          {plan.positioning}
                        </Text>
                        <Text as="p" tone="subdued">
                          {plan.tagline}
                        </Text>
                        <div className="omni-price-lockup">
                          <span className="omni-price-lockup__currency">$</span>
                          <span className="omni-price-lockup__amount">{plan.price}</span>
                          <span className="omni-price-lockup__period">/mo</span>
                        </div>
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
                        <div className="omni-engagement-chip">
                          {plan.engagements}
                        </div>
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
                    </div>
                  </div>
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

import { json } from "@remix-run/node";
import { useLoaderData } from "@remix-run/react";
import {
  Badge,
  BlockStack,
  Card,
  Divider,
  InlineGrid,
  InlineStack,
  Layout,
  Page,
  Text,
} from "@shopify/polaris";
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

function intentLabel(intent: string | null | undefined) {
  if (!intent) return "Storefront conversation";
  const map: Record<string, string> = {
    product_discovery: "Product discovery",
    cart_management: "Cart management",
    order_tracking: "Order tracking",
    customer_support: "Customer support",
    lead_capture: "Lead captured",
    appointment_booking: "Appointment booked",
    discount_request: "Discount requested",
  };
  return map[intent] ?? intent.replace(/_/g, " ");
}

function intentTone(intent: string | null | undefined): "success" | "info" | "attention" | undefined {
  if (!intent) return undefined;
  if (intent === "lead_capture" || intent === "appointment_booking") return "success";
  if (intent === "discount_request") return "attention";
  return "info";
}

function timeSince(dateStr: string | null | undefined) {
  if (!dateStr) return "—";
  const d = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - d.getTime();
  const mins = Math.floor(diffMs / 60000);
  if (mins < 1) return "Just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}

type Session = {
  id: string;
  status: string;
  shopper_email?: string | null;
  shopper_locale?: string | null;
  currency?: string | null;
  last_intent?: string | null;
  current_page_url?: string | null;
  messages: number;
  last_seen_at?: string | null;
  created_at?: string | null;
};

function pageSlug(url: string | null | undefined) {
  if (!url) return "Unknown page";
  try {
    const u = new URL(url);
    const path = u.pathname === "/" ? "Homepage" : u.pathname;
    return path;
  } catch {
    return url;
  }
}

export default function Analytics() {
  const { analytics, error } = useLoaderData<typeof loader>();

  const qualifiedSessions = analytics.recent_sessions.filter(
    (s: Session) => s.shopper_email || s.last_intent === "lead_capture"
  );

  return (
    <Page
      fullWidth
      title="Analytics"
      subtitle="Conversation usage, lead quality, and revenue-agent activity"
    >
      <div className="omni-page-shell">
      <Layout>
        <Layout.Section>
          <div className="omni-hero-card">
            <div className="omni-hero-card__inner">
              <BlockStack gap="200">
                <Text as="h2" variant="headingLg">
                  Storefront activity at a glance
                </Text>
                <Text as="p" tone="subdued">
                  Track conversations, captured leads, discount interest, and the most recent shopper sessions.
                </Text>
              </BlockStack>
              {error ? <Badge tone="critical">Engine unavailable</Badge> : <Badge tone="success">Live data</Badge>}
            </div>
          </div>
        </Layout.Section>

        {/* KPI strip */}
        <Layout.Section>
          <InlineGrid columns={{ xs: 2, md: 4 }} gap="400">
            <Card>
              <BlockStack gap="100">
                <div className="omni-card-accent" />
                <Text as="p" tone="subdued" variant="bodySm">Total conversations</Text>
                <Text as="p" variant="heading2xl">{analytics.conversations}</Text>
                <Text as="p" tone="subdued" variant="bodySm">
                  {analytics.active_sessions} active right now
                </Text>
              </BlockStack>
            </Card>
            <Card>
              <BlockStack gap="100">
                <div className="omni-card-accent" />
                <Text as="p" tone="subdued" variant="bodySm">Qualified leads</Text>
                <Text as="p" variant="heading2xl" tone={analytics.qualified_leads > 0 ? "success" : undefined}>
                  {analytics.qualified_leads}
                </Text>
                <Text as="p" tone="subdued" variant="bodySm">Emails captured</Text>
              </BlockStack>
            </Card>
            <Card>
              <BlockStack gap="100">
                <div className="omni-card-accent" />
                <Text as="p" tone="subdued" variant="bodySm">Discount requests</Text>
                <Text as="p" variant="heading2xl">{analytics.discount_requests}</Text>
                <Text as="p" tone="subdued" variant="bodySm">
                  {analytics.approved_discounts} approved
                </Text>
              </BlockStack>
            </Card>
            <Card>
              <BlockStack gap="100">
                <div className="omni-card-accent" />
                <Text as="p" tone="subdued" variant="bodySm">Avg. messages / session</Text>
                <Text as="p" variant="heading2xl">
                  {analytics.conversations > 0
                    ? Math.round(
                        analytics.recent_sessions.reduce((sum: number, s: Session) => sum + s.messages, 0) /
                          Math.max(analytics.recent_sessions.length, 1)
                      )
                    : 0}
                </Text>
                <Text as="p" tone="subdued" variant="bodySm">Last {analytics.recent_sessions.length} sessions</Text>
              </BlockStack>
            </Card>
          </InlineGrid>
        </Layout.Section>

        {/* Recent sessions */}
        <Layout.Section>
          <Card>
            <BlockStack gap="300">
              <InlineStack align="space-between">
                <Text as="h2" variant="headingMd">Recent sessions</Text>
                {error && (
                  <Badge tone="critical">Engine unavailable</Badge>
                )}
              </InlineStack>
              {analytics.recent_sessions.length === 0 ? (
                <BlockStack gap="200">
                  <Divider />
                  <Text as="p" tone="subdued">
                    No storefront assistant sessions yet. Once shoppers start chatting, their sessions will appear here.
                  </Text>
                </BlockStack>
              ) : (
                <div className="omni-scroll-list">
                {analytics.recent_sessions.map((session: Session, i: number) => (
                  <BlockStack gap="0" key={session.id}>
                    {i > 0 && <Divider />}
                    <div style={{ paddingBlock: "12px" }}>
                      <InlineStack align="space-between" blockAlign="start" gap="300" wrap={false}>
                        <BlockStack gap="100">
                          <InlineStack gap="200" blockAlign="center">
                            <Badge tone={intentTone(session.last_intent)}>
                              {intentLabel(session.last_intent)}
                            </Badge>
                            {session.shopper_locale && (
                              <Text as="span" tone="subdued" variant="bodySm">
                                {session.shopper_locale.toUpperCase()}
                              </Text>
                            )}
                          </InlineStack>
                          <Text as="p" tone="subdued" variant="bodySm">
                            {pageSlug(session.current_page_url)} · {session.messages} message{session.messages !== 1 ? "s" : ""}
                            {session.shopper_email ? ` · ${session.shopper_email}` : ""}
                          </Text>
                        </BlockStack>
                        <Text as="p" tone="subdued" variant="bodySm">
                          {timeSince(session.last_seen_at || session.created_at)}
                        </Text>
                      </InlineStack>
                    </div>
                  </BlockStack>
                ))}
                </div>
              )}
            </BlockStack>
          </Card>
        </Layout.Section>

        {/* Conversation summaries */}
        {qualifiedSessions.length > 0 && (
          <Layout.Section>
            <Card>
              <BlockStack gap="300">
                <BlockStack gap="100">
                  <Text as="h2" variant="headingMd">Conversation summaries</Text>
                  <Text as="p" tone="subdued">
                    Sessions where the shopper engaged enough to capture intent or contact info.
                  </Text>
                </BlockStack>
                {qualifiedSessions.map((session: Session, i: number) => (
                  <BlockStack gap="0" key={session.id}>
                    {i > 0 && <Divider />}
                    <div style={{ paddingBlock: "12px" }}>
                      <BlockStack gap="200">
                        <InlineStack align="space-between">
                          <InlineStack gap="200" blockAlign="center">
                            <Badge tone="success">{intentLabel(session.last_intent)}</Badge>
                            {session.currency && (
                              <Text as="span" tone="subdued" variant="bodySm">{session.currency}</Text>
                            )}
                          </InlineStack>
                          <Text as="p" tone="subdued" variant="bodySm">
                            {timeSince(session.last_seen_at || session.created_at)}
                          </Text>
                        </InlineStack>
                        <InlineGrid columns={2} gap="300">
                          {session.shopper_email && (
                            <BlockStack gap="0">
                              <Text as="p" variant="bodySm" tone="subdued">Contact</Text>
                              <Text as="p" fontWeight="semibold">{session.shopper_email}</Text>
                            </BlockStack>
                          )}
                          <BlockStack gap="0">
                            <Text as="p" variant="bodySm" tone="subdued">Page</Text>
                            <Text as="p" fontWeight="semibold">{pageSlug(session.current_page_url)}</Text>
                          </BlockStack>
                          <BlockStack gap="0">
                            <Text as="p" variant="bodySm" tone="subdued">Messages</Text>
                            <Text as="p" fontWeight="semibold">{session.messages}</Text>
                          </BlockStack>
                          {session.shopper_locale && (
                            <BlockStack gap="0">
                              <Text as="p" variant="bodySm" tone="subdued">Language</Text>
                              <Text as="p" fontWeight="semibold">{session.shopper_locale.toUpperCase()}</Text>
                            </BlockStack>
                          )}
                        </InlineGrid>
                      </BlockStack>
                    </div>
                  </BlockStack>
                ))}
              </BlockStack>
            </Card>
          </Layout.Section>
        )}
      </Layout>
      </div>
    </Page>
  );
}

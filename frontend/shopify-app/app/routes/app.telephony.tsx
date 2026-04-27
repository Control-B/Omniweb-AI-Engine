import { json } from "@remix-run/node";
import { Form, useActionData, useLoaderData, useNavigation } from "@remix-run/react";
import {
  Banner,
  BlockStack,
  Button,
  Card,
  FormLayout,
  InlineStack,
  Layout,
  Page,
  Text,
  TextField,
} from "@shopify/polaris";
import { useState } from "react";
import { authenticate } from "../shopify.server";
import { prisma } from "../db.server";
import { syncShopToEngine } from "../services/engine.server";
import { ensureStorefrontAccessToken } from "../services/storefront-token.server";

type TelephonySettings = {
  enabled?: boolean;
  retellAgentId?: string;
  phoneNumber?: string;
  handoffPhone?: string;
  handoffEmail?: string;
  handoffMessage?: string;
};

const DEFAULT_HANDOFF_MESSAGE =
  "Let me connect you with a human who can help with this directly.";

function settingsFromConfig(config: { widgetSettings?: unknown } | null | undefined): TelephonySettings {
  const widget = (config?.widgetSettings || {}) as { ai_telephony?: TelephonySettings };
  return widget.ai_telephony || {};
}

export async function loader({ request }: { request: Request }) {
  const { session } = await authenticate.admin(request);
  const shop = await prisma.shop.upsert({
    where: { shopDomain: session.shop },
    update: {},
    create: { shopDomain: session.shop, status: "installed" },
    include: { agentConfig: true, subscription: true },
  });
  return json({
    shop,
    settings: settingsFromConfig(shop.agentConfig),
  });
}

export async function action({ request }: { request: Request }) {
  const { admin, session } = await authenticate.admin(request);
  const form = await request.formData();

  const shop = await prisma.shop.upsert({
    where: { shopDomain: session.shop },
    update: { status: "installed" },
    create: { shopDomain: session.shop, status: "installed" },
    include: { agentConfig: true, subscription: true },
  });

  const existingWidget = ((shop.agentConfig?.widgetSettings || {}) as Record<string, unknown>) || {};
  const settings: TelephonySettings = {
    enabled: true,
    retellAgentId: String(form.get("retellAgentId") || "").trim(),
    phoneNumber: String(form.get("phoneNumber") || "").trim(),
    handoffPhone: String(form.get("handoffPhone") || "").trim(),
    handoffEmail: String(form.get("handoffEmail") || "").trim(),
    handoffMessage: String(form.get("handoffMessage") || DEFAULT_HANDOFF_MESSAGE).trim(),
  };

  const agentConfig = await prisma.agentConfig.upsert({
    where: { shopId: shop.id },
    update: {
      widgetSettings: {
        ...existingWidget,
        ai_telephony: settings,
      },
    },
    create: {
      shopId: shop.id,
      widgetSettings: {
        ai_telephony: settings,
      },
    },
  });

  try {
    const storefrontToken = await ensureStorefrontAccessToken({
      admin,
      shopId: shop.id,
      shopDomain: session.shop,
      encryptedToken: shop.encryptedStorefrontToken,
    });

    await syncShopToEngine({
      shop_domain: session.shop,
      engine_client_id: shop.engineClientId,
      admin_access_token: session.accessToken,
      storefront_access_token: storefrontToken,
      granted_scopes: (session.scope || "").split(",").map((s) => s.trim()).filter(Boolean),
      storefront_api_version: process.env.SHOPIFY_API_VERSION || "2026-07",
      plan: shop.subscription?.plan || "starter",
      subscription_status: shop.subscription?.status || "trialing",
      assistant_enabled: true,
      agent_config: {
        ...agentConfig,
        widgetSettings: { ...existingWidget, ai_telephony: settings },
        retellAgentId: settings.retellAgentId,
        handoffPhone: settings.handoffPhone,
        handoffEmail: settings.handoffEmail,
        handoffMessage: settings.handoffMessage,
      },
    });
  } catch (error) {
    console.error("[telephony] engine sync failed (non-fatal):", error);
  }

  return json({ saved: true });
}

export default function Telephony() {
  const { settings } = useLoaderData<typeof loader>();
  const actionData = useActionData<typeof action>();
  const nav = useNavigation();
  const [retellAgentId, setRetellAgentId] = useState(settings.retellAgentId || "");
  const [phoneNumber, setPhoneNumber] = useState(settings.phoneNumber || "");
  const [handoffPhone, setHandoffPhone] = useState(settings.handoffPhone || "");
  const [handoffEmail, setHandoffEmail] = useState(settings.handoffEmail || "");
  const [handoffMessage, setHandoffMessage] = useState(settings.handoffMessage || DEFAULT_HANDOFF_MESSAGE);

  return (
    <Page
      fullWidth
      title="AI Telephony"
      subtitle="Let shoppers request a phone call with the same AI agent, powered by Retell AI"
    >
      <div className="omni-page-shell">
        <Layout>
          <Layout.Section>
            <div className="omni-hero-card">
              <div className="omni-hero-card__inner">
                <BlockStack gap="200">
                  <Text as="h2" variant="headingLg">Add a Call Us AI phone widget.</Text>
                  <Text as="p" tone="subdued">
                    The customer enters their number, Retell calls them, and the AI explains products, services, bundles, objections, and checkout guidance just like the voice widget.
                  </Text>
                </BlockStack>
              </div>
            </div>
          </Layout.Section>

          {actionData?.saved && (
            <Layout.Section>
              <Banner title="AI Telephony saved" tone="success">
                <Text as="p">Your telephony settings were saved and synced to the engine.</Text>
              </Banner>
            </Layout.Section>
          )}

          <Layout.Section>
            <Card>
              <Form method="post">
                <BlockStack gap="400">
                  <div className="omni-card-accent" />
                  <Text as="h2" variant="headingMd">Retell AI phone setup</Text>
                  <FormLayout>
                    <TextField
                      label="Retell agent ID"
                      name="retellAgentId"
                      value={retellAgentId}
                      onChange={setRetellAgentId}
                      autoComplete="off"
                      placeholder="agent_xxxxxxxxx"
                      helpText="Use the same Retell agent brain as the AI voice experience."
                    />
                    <FormLayout.Group>
                      <TextField
                        label="AI telephone number"
                        name="phoneNumber"
                        value={phoneNumber}
                        onChange={setPhoneNumber}
                        autoComplete="tel"
                        placeholder="+15551234567"
                        helpText="The Retell/Twilio number calls customers from."
                      />
                      <TextField
                        label="Human escalation phone"
                        name="handoffPhone"
                        value={handoffPhone}
                        onChange={setHandoffPhone}
                        autoComplete="tel"
                        placeholder="+15557654321"
                        helpText="Owner or team number for human transfer/escalation."
                      />
                    </FormLayout.Group>
                    <TextField
                      label="Escalation email fallback"
                      name="handoffEmail"
                      value={handoffEmail}
                      onChange={setHandoffEmail}
                      autoComplete="email"
                      placeholder="owner@example.com"
                    />
                    <TextField
                      label="Escalation message"
                      name="handoffMessage"
                      value={handoffMessage}
                      onChange={setHandoffMessage}
                      multiline={3}
                      autoComplete="off"
                    />
                  </FormLayout>
                  <InlineStack align="end">
                    <Button submit variant="primary" loading={nav.state === "submitting"}>
                      Save AI Telephony
                    </Button>
                  </InlineStack>
                </BlockStack>
              </Form>
            </Card>
          </Layout.Section>

          <Layout.Section variant="oneThird">
            <Card>
              <BlockStack gap="300">
                <Text as="h2" variant="headingMd">Call Us widget behavior</Text>
                <Text as="p" tone="subdued">
                  This is separate from Ask AI. It appears as a Call Us option, collects the shopper phone number, and starts a Retell AI phone conversation.
                </Text>
                <Text as="p" tone="subdued">
                  If the AI cannot resolve the request, it uses the human escalation phone and fallback email you set here.
                </Text>
              </BlockStack>
            </Card>
          </Layout.Section>
        </Layout>
      </div>
    </Page>
  );
}

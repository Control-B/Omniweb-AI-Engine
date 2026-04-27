import { json, redirect } from "@remix-run/node";
import { Form, useLoaderData, useNavigation } from "@remix-run/react";
import { useState, useEffect } from "react";
import {
  Banner,
  BlockStack,
  Button,
  Card,
  ChoiceList,
  Divider,
  FormLayout,
  InlineStack,
  Layout,
  List,
  Page,
  Select,
  Text,
  TextField,
} from "@shopify/polaris";
import { authenticate } from "../shopify.server";
import { prisma } from "../db.server";
import { syncShopToEngine } from "../services/engine.server";
import { ensureStorefrontAccessToken } from "../services/storefront-token.server";

const LANGUAGE_CHOICES = [
  { label: "🌐 Auto (detect language)", value: "multi" },
  { label: "🇺🇸 English", value: "en" },
  { label: "🇪🇸 Spanish", value: "es" },
  { label: "🇫🇷 French", value: "fr" },
  { label: "🇩🇪 German", value: "de" },
  { label: "🇮🇹 Italian", value: "it" },
  { label: "🇵🇹 Portuguese", value: "pt" },
  { label: "🇳🇱 Dutch", value: "nl" },
  { label: "🇸🇪 Swedish", value: "sv" },
  { label: "🇷🇴 Romanian", value: "ro" },
  { label: "🇷🇺 Russian", value: "ru" },
  { label: "🇺🇦 Ukrainian", value: "uk" },
  { label: "🇵🇱 Polish", value: "pl" },
  { label: "🇸🇦 Arabic", value: "ar" },
  { label: "🇹🇷 Turkish", value: "tr" },
  { label: "🇮🇳 Hindi", value: "hi" },
  { label: "🇧🇩 Bengali", value: "bn" },
  { label: "🇨🇳 Chinese", value: "zh" },
  { label: "🇯🇵 Japanese", value: "ja" },
  { label: "🇰🇷 Korean", value: "ko" },
  { label: "🇮🇩 Indonesian", value: "id" },
  { label: "🇻🇳 Vietnamese", value: "vi" },
  { label: "🇵🇭 Filipino", value: "tl" },
  { label: "🇰🇪 Swahili", value: "sw" },
  { label: "🇸🇱 Krio", value: "kri" },
  { label: "🇮🇩 Sundanese", value: "su" },
];

const ALL_LANGUAGE_VALUES = LANGUAGE_CHOICES.map((l) => l.value);

const PRIMARY_GOAL_CHOICES = [
  { label: "All goals", value: "all" },
  { label: "Product Recommendations", value: "product_recommendations" },
  { label: "Customer Support & FAQs", value: "customer_support" },
  { label: "Cart Management & Reminders", value: "cart_management" },
  { label: "Lead Capture", value: "lead_capture" },
  { label: "Appointment Booking", value: "appointment_booking" },
  { label: "Order Tracking & Status", value: "order_tracking" },
  { label: "Multilingual Support", value: "multilingual_support" },
];

const ALL_GOAL_VALUES = PRIMARY_GOAL_CHOICES.map((g) => g.value);
const NON_ALL_GOAL_VALUES = ALL_GOAL_VALUES.filter((v) => v !== "all");

const RESPONSE_LENGTH_OPTIONS = [
  { label: "Brief – short, quick answers", value: "brief" },
  { label: "Moderate – balanced detail", value: "moderate" },
  { label: "Detailed – thorough explanations", value: "detailed" },
];

const DEFAULT_GREETING = "Thank you for visiting our website today... it will be my pleasure to help you";

export async function loader({ request }: { request: Request }) {
  const { session } = await authenticate.admin(request);
  const shop = await prisma.shop.upsert({
    where: { shopDomain: session.shop },
    update: {},
    create: { shopDomain: session.shop, status: "installed" },
    include: { agentConfig: true, subscription: true },
  });

  const engineUrl = process.env.ENGINE_URL || "https://omniweb-engine-rs6fr.ondigitalocean.app";
  return json({ shop, engineClientId: shop.engineClientId, engineUrl });
}

export async function action({ request }: { request: Request }) {
  const { admin, session } = await authenticate.admin(request);
  const form = await request.formData();

  const shop = await prisma.shop.upsert({
    where: { shopDomain: session.shop },
    update: { status: "installed" },
    create: { shopDomain: session.shop, status: "installed" },
    include: { subscription: true },
  });

  const languagesRaw = String(form.get("supportedLanguages") || "en");
  const goalsRaw = String(form.get("primaryGoals") || "all");

  const config = await prisma.agentConfig.upsert({
    where: { shopId: shop.id },
    update: {
      agentName: String(form.get("agentName") || "Omniweb AI"),
      businessName: String(form.get("businessName") || ""),
      greeting: String(form.get("greeting") || DEFAULT_GREETING),
      systemPrompt: String(form.get("systemPrompt") || ""),
      supportedLanguages: languagesRaw.split(",").map((l) => l.trim()).filter(Boolean),
    },
    create: {
      shopId: shop.id,
      agentName: String(form.get("agentName") || "Omniweb AI"),
      businessName: String(form.get("businessName") || ""),
      greeting: String(form.get("greeting") || DEFAULT_GREETING),
      systemPrompt: String(form.get("systemPrompt") || ""),
      supportedLanguages: ["en"],
    },
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
    plan: shop.subscription?.plan || "starter",
    subscription_status: shop.subscription?.status || "trialing",
    assistant_enabled: true,
    agent_config: { ...config, primaryGoals: goalsRaw, responseLength: form.get("responseLength") },
  });

  if (engineSync.client_id && engineSync.client_id !== shop.engineClientId) {
    await prisma.shop.update({
      where: { id: shop.id },
      data: { engineClientId: engineSync.client_id },
    });
  }

  return redirect("/app/agent?saved=1");
}

export default function AgentSettings() {
  const { shop, engineClientId, engineUrl } = useLoaderData<typeof loader>();
  const nav = useNavigation();
  const config = shop.agentConfig;

  const [agentName, setAgentName] = useState(config?.agentName || "Omniweb AI");
  const [businessName, setBusinessName] = useState(config?.businessName || "");
  const [greeting, setGreeting] = useState(config?.greeting || DEFAULT_GREETING);
  const [systemPrompt, setSystemPrompt] = useState(config?.systemPrompt || "");
  const [responseLength, setResponseLength] = useState("moderate");

  // Languages: multi-select with "All" toggle
  const savedLangs = config?.supportedLanguages || ["en"];
  const [selectedLangs, setSelectedLangs] = useState<string[]>(
    savedLangs.length === ALL_LANGUAGE_VALUES.length ? ALL_LANGUAGE_VALUES : savedLangs
  );

  // Primary goals: checkboxes with "All" at top
  const [selectedGoals, setSelectedGoals] = useState<string[]>(ALL_GOAL_VALUES);

  // Keep hidden input values in sync
  const [langsHidden, setLangsHidden] = useState(selectedLangs.filter((l) => l !== "all").join(","));
  const [goalsHidden, setGoalsHidden] = useState(selectedGoals.join(","));

  useEffect(() => {
    setLangsHidden(selectedLangs.filter((l) => l !== "all").join(","));
  }, [selectedLangs]);

  useEffect(() => {
    setGoalsHidden(selectedGoals.join(","));
  }, [selectedGoals]);

  const handleLangChange = (values: string[]) => {
    const hadAll = selectedLangs.includes("all");
    const hasAll = values.includes("all");
    if (!hadAll && hasAll) {
      setSelectedLangs(ALL_LANGUAGE_VALUES);
    } else if (hadAll && !hasAll) {
      setSelectedLangs([]);
    } else {
      const withoutAll = values.filter((v) => v !== "all");
      const allSelected = ALL_LANGUAGE_VALUES.filter((v) => v !== "all").every((v) => withoutAll.includes(v));
      setSelectedLangs(allSelected ? ALL_LANGUAGE_VALUES : withoutAll);
    }
  };

  const handleGoalChange = (values: string[]) => {
    const hadAll = selectedGoals.includes("all");
    const hasAll = values.includes("all");
    if (!hadAll && hasAll) {
      setSelectedGoals(ALL_GOAL_VALUES);
    } else if (hadAll && !hasAll) {
      setSelectedGoals([]);
    } else {
      const withoutAll = values.filter((v) => v !== "all");
      const allSelected = NON_ALL_GOAL_VALUES.every((v) => withoutAll.includes(v));
      setSelectedGoals(allSelected ? ALL_GOAL_VALUES : withoutAll);
    }
  };

  const testWidgetUrl = engineClientId ? `${engineUrl}/widget/${engineClientId}` : null;

  return (
    <Page
      fullWidth
      title="AI Agent Settings"
      subtitle="Configure the sales associate customers meet on your storefront"
    >
      <div className="omni-page-shell">
      <Layout>
        <Layout.Section>
          <div className="omni-hero-card">
            <div className="omni-hero-card__inner">
              <BlockStack gap="200">
                <Text as="h2" variant="headingLg">
                  Shape how your AI agent sells and supports.
                </Text>
                <Text as="p" tone="subdued">
                  Set the voice, welcome message, goals, languages, and operating rules that sync to the storefront widget.
                </Text>
              </BlockStack>
              {testWidgetUrl ? (
                <Button url={testWidgetUrl} target="_blank" variant="primary">
                  Test widget
                </Button>
              ) : (
                <Button disabled>Test after save</Button>
              )}
            </div>
          </div>
        </Layout.Section>

        <Layout.Section>
          <Form method="post">
            {/* Hidden serialized fields */}
            <input type="hidden" name="supportedLanguages" value={langsHidden} />
            <input type="hidden" name="primaryGoals" value={goalsHidden} />
            <input type="hidden" name="responseLength" value={responseLength} />

            <BlockStack gap="500">
              {/* Basic info */}
              <Card>
                <BlockStack gap="400">
                  <div className="omni-card-accent" />
                  <Text as="h2" variant="headingMd">Agent Identity</Text>
                  <FormLayout>
                    <FormLayout.Group>
                      <TextField
                        label="Agent name"
                        name="agentName"
                        value={agentName}
                        onChange={setAgentName}
                        autoComplete="off"
                        helpText="The name shoppers will see in the chat widget"
                      />
                      <TextField
                        label="Business name"
                        name="businessName"
                        value={businessName}
                        onChange={setBusinessName}
                        autoComplete="off"
                      />
                    </FormLayout.Group>
                    <TextField
                      label="Welcome message"
                      name="greeting"
                      value={greeting}
                      onChange={setGreeting}
                      multiline={2}
                      autoComplete="off"
                      helpText="The first message shoppers see when they open the chat"
                    />
                    <TextField
                      label="System instructions"
                      name="systemPrompt"
                      value={systemPrompt}
                      onChange={setSystemPrompt}
                      multiline={6}
                      autoComplete="off"
                      helpText="Describe your business, products, policies, and how the agent should behave"
                    />
                    <Select
                      label="Response length"
                      options={RESPONSE_LENGTH_OPTIONS}
                      value={responseLength}
                      onChange={setResponseLength}
                    />
                  </FormLayout>
                </BlockStack>
              </Card>

              {/* Primary Goals */}
              <Card>
                <BlockStack gap="400">
                  <div className="omni-card-accent" />
                  <BlockStack gap="100">
                    <Text as="h2" variant="headingMd">Primary Goals</Text>
                    <Text as="p" tone="subdued">Select what your AI agent should help shoppers accomplish</Text>
                  </BlockStack>
                  <ChoiceList
                    title="Goals"
                    titleHidden
                    allowMultiple
                    choices={PRIMARY_GOAL_CHOICES}
                    selected={selectedGoals}
                    onChange={handleGoalChange}
                  />
                </BlockStack>
              </Card>

              {/* Languages */}
              <Card>
                <BlockStack gap="400">
                  <div className="omni-card-accent" />
                  <BlockStack gap="100">
                    <Text as="h2" variant="headingMd">Supported Languages</Text>
                    <Text as="p" tone="subdued">
                      The widget will show a language picker to shoppers. Your agent will respond in the chosen language using ElevenLabs voice and Deepgram speech recognition.
                    </Text>
                  </BlockStack>
                  <ChoiceList
                    title="Languages"
                    titleHidden
                    allowMultiple
                    choices={LANGUAGE_CHOICES}
                    selected={selectedLangs}
                    onChange={handleLangChange}
                  />
                </BlockStack>
              </Card>

              {/* Financial Policy Agreement */}
              <Banner title="Financial Transaction Policy — Required" tone="warning">
                <BlockStack gap="200">
                  <Text as="p">By saving, you agree that the Omniweb AI agent will:</Text>
                  <List type="bullet">
                    <List.Item>✓ Add products to the shopper's cart</List.Item>
                    <List.Item>✓ Send cart abandonment reminders</List.Item>
                    <List.Item>✗ NOT process checkouts or complete payments</List.Item>
                    <List.Item>✗ NOT issue refunds or access billing information</List.Item>
                    <List.Item>✗ NOT handle any financial transactions</List.Item>
                  </List>
                  <Text as="p" tone="subdued">
                    Any financial request from a shopper will be immediately escalated to a human representative.
                  </Text>
                </BlockStack>
              </Banner>

              <Button
                submit
                variant="primary"
                size="large"
                loading={nav.state === "submitting"}
              >
                Save and sync agent
              </Button>
            </BlockStack>
          </Form>
        </Layout.Section>

        {/* Right sidebar */}
        <Layout.Section variant="oneThird">
          <BlockStack gap="400">
            <Card>
              <BlockStack gap="300">
                <Text as="h2" variant="headingMd">Runtime</Text>
                <Text as="p" tone="subdued">
                  These settings sync to the DigitalOcean AI Engine. The storefront widget uses the saved config for voice, text, multilingual replies, product guidance, and navigation.
                </Text>
              </BlockStack>
            </Card>

            {/* Test Agent */}
            <Card>
              <BlockStack gap="300">
                <Text as="h2" variant="headingMd">Test Your Agent</Text>
                <Text as="p" tone="subdued">
                  Open the voice + text widget to test your agent's responses, language switching, and greeting before shoppers see it.
                </Text>
                <Divider />
                {testWidgetUrl ? (
                  <InlineStack gap="200">
                    <Button
                      url={testWidgetUrl}
                      target="_blank"
                      variant="primary"
                    >
                      Open Voice Widget
                    </Button>
                    <Button
                      url={testWidgetUrl + "?mode=text"}
                      target="_blank"
                    >
                      Text Only
                    </Button>
                  </InlineStack>
                ) : (
                  <Text as="p" tone="subdued">
                    Save and sync your agent first to enable testing.
                  </Text>
                )}
              </BlockStack>
            </Card>
          </BlockStack>
        </Layout.Section>
      </Layout>
      </div>
    </Page>
  );
}

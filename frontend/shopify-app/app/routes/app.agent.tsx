import { json, redirect } from "@remix-run/node";
import { Form, useLoaderData, useNavigation } from "@remix-run/react";
import { useState } from "react";
import {
  BlockStack,
  Button,
  Card,
  FormLayout,
  Layout,
  Page,
  Select,
  Text,
  TextField,
} from "@shopify/polaris";
import { authenticate } from "../shopify.server";
import { prisma } from "../db.server";
import { syncShopToEngine } from "../services/engine.server";
import { ensureStorefrontAccessToken } from "../services/storefront-token.server";

export async function loader({ request }: { request: Request }) {
  const { session } = await authenticate.admin(request);
  const shop = await prisma.shop.upsert({
    where: { shopDomain: session.shop },
    update: {},
    create: { shopDomain: session.shop, status: "installed" },
    include: { agentConfig: true, subscription: true },
  });

  return json({ shop });
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

  const config = await prisma.agentConfig.upsert({
    where: { shopId: shop.id },
    update: {
      agentName: String(form.get("agentName") || "Omniweb AI"),
      businessName: String(form.get("businessName") || ""),
      greeting: String(form.get("greeting") || ""),
      systemPrompt: String(form.get("systemPrompt") || ""),
      supportedLanguages: String(form.get("supportedLanguages") || "en")
        .split(",")
        .map((lang) => lang.trim())
        .filter(Boolean),
    },
    create: {
      shopId: shop.id,
      agentName: String(form.get("agentName") || "Omniweb AI"),
      businessName: String(form.get("businessName") || ""),
      greeting: String(form.get("greeting") || ""),
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
    granted_scopes: (session.scope || "").split(",").map((scope) => scope.trim()).filter(Boolean),
    storefront_api_version: process.env.SHOPIFY_API_VERSION || "2026-07",
    plan: shop.subscription?.plan || "starter",
    subscription_status: shop.subscription?.status || "trialing",
    assistant_enabled: true,
    agent_config: config,
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
  const { shop } = useLoaderData<typeof loader>();
  const nav = useNavigation();
  const config = shop.agentConfig;
  const [agentName, setAgentName] = useState(config?.agentName || "Omniweb AI");
  const [businessName, setBusinessName] = useState(config?.businessName || "");
  const [greeting, setGreeting] = useState(config?.greeting || "");
  const [systemPrompt, setSystemPrompt] = useState(config?.systemPrompt || "");
  const [supportedLanguages, setSupportedLanguages] = useState((config?.supportedLanguages || ["en"]).join(","));

  return (
    <Page title="AI Agent Settings" subtitle="Configure the sales associate customers meet on your storefront">
      <Layout>
        <Layout.Section>
          <Card>
            <Form method="post">
              <BlockStack gap="500">
                <FormLayout>
                  <TextField label="Agent name" name="agentName" value={agentName} onChange={setAgentName} autoComplete="off" />
                  <TextField label="Business name" name="businessName" value={businessName} onChange={setBusinessName} autoComplete="off" />
                  <TextField label="Welcome message" name="greeting" value={greeting} onChange={setGreeting} multiline={3} autoComplete="off" />
                  <TextField label="System instructions" name="systemPrompt" value={systemPrompt} onChange={setSystemPrompt} multiline={6} autoComplete="off" />
                  <TextField label="Supported languages" name="supportedLanguages" value={supportedLanguages} onChange={setSupportedLanguages} helpText="Comma-separated language codes, for example: en,es,fr" autoComplete="off" />
                  <Select
                    label="Primary goal"
                    name="primaryGoal"
                    options={[
                      { label: "Increase sales", value: "sales" },
                      { label: "Product expert", value: "product_expert" },
                      { label: "Lead qualification", value: "lead_qualification" },
                    ]}
                  />
                </FormLayout>
                <Button submit variant="primary" loading={nav.state === "submitting"}>Save and sync agent</Button>
              </BlockStack>
            </Form>
          </Card>
        </Layout.Section>
        <Layout.Section variant="oneThird">
          <Card>
            <BlockStack gap="300">
              <Text as="h2" variant="headingMd">Runtime</Text>
              <Text as="p" tone="subdued">
                These settings sync to the DigitalOcean AI Engine. The storefront widget uses the saved config for voice, text, multilingual replies, product guidance, and navigation.
              </Text>
            </BlockStack>
          </Card>
        </Layout.Section>
      </Layout>
    </Page>
  );
}

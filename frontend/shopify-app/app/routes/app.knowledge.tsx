import { json, redirect } from "@remix-run/node";
import { Form, useLoaderData, useNavigation } from "@remix-run/react";
import { BlockStack, Button, Card, Layout, Page, Text, TextField } from "@shopify/polaris";
import { authenticate } from "../shopify.server";
import { prisma } from "../db.server";
import { enqueueKnowledgeIngestion } from "../services/engine.server";

export async function loader({ request }: { request: Request }) {
  const { session } = await authenticate.admin(request);
  const shop = await prisma.shop.findUnique({
    where: { shopDomain: session.shop },
    include: { knowledgeSources: { orderBy: { createdAt: "desc" } } },
  });
  return json({ sources: shop?.knowledgeSources || [] });
}

export async function action({ request }: { request: Request }) {
  const { session } = await authenticate.admin(request);
  const form = await request.formData();
  const url = String(form.get("url") || "").trim();
  if (!url) return redirect("/app/knowledge");

  const shop = await prisma.shop.upsert({
    where: { shopDomain: session.shop },
    update: {},
    create: { shopDomain: session.shop, status: "installed" },
  });

  const source = await prisma.knowledgeSource.create({
    data: { shopId: shop.id, type: "url", url, status: "queued" },
  });

  await enqueueKnowledgeIngestion({
    shop_domain: session.shop,
    source_id: source.id,
    url,
  });

  return redirect("/app/knowledge?queued=1");
}

export default function Knowledge() {
  const { sources } = useLoaderData<typeof loader>();
  const nav = useNavigation();

  return (
    <Page title="Knowledge Sources" subtitle="Add URLs the AI agent should learn from">
      <Layout>
        <Layout.Section>
          <Card>
            <Form method="post">
              <BlockStack gap="400">
                <TextField label="Website or page URL" name="url" placeholder="https://example.com/pages/faq" autoComplete="off" />
                <Button submit variant="primary" loading={nav.state === "submitting"}>Queue ingestion</Button>
              </BlockStack>
            </Form>
          </Card>
        </Layout.Section>
        <Layout.Section>
          <Card>
            <BlockStack gap="300">
              <Text as="h2" variant="headingMd">Sources</Text>
              {sources.length === 0 ? (
                <Text as="p" tone="subdued">No knowledge sources yet.</Text>
              ) : (
                sources.map((source: { id: string; url: string | null; status: string }) => (
                  <Text as="p" key={source.id}>{source.url} - {source.status}</Text>
                ))
              )}
            </BlockStack>
          </Card>
        </Layout.Section>
      </Layout>
    </Page>
  );
}

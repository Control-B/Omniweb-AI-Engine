import { json, redirect } from "@remix-run/node";
import { Form, useLoaderData, useNavigation, useSearchParams } from "@remix-run/react";
import {
  Badge,
  Banner,
  BlockStack,
  Button,
  Card,
  Divider,
  InlineStack,
  Layout,
  Page,
  Text,
  TextField,
} from "@shopify/polaris";
import { useState } from "react";
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

  const intent = String(form.get("intent") || "add");

  if (intent === "delete") {
    const id = String(form.get("id") || "");
    if (id) await prisma.knowledgeSource.delete({ where: { id } });
    return redirect("/app/knowledge");
  }

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

function statusTone(status: string): "success" | "attention" | "info" | "critical" {
  if (status === "ready" || status === "done") return "success";
  if (status === "queued" || status === "processing") return "attention";
  if (status === "error" || status === "failed") return "critical";
  return "info";
}

function statusLabel(status: string) {
  const map: Record<string, string> = {
    queued: "Queued",
    processing: "Processing…",
    ready: "Ready",
    done: "Ready",
    error: "Error",
    failed: "Failed",
  };
  return map[status] ?? status;
}

export default function Knowledge() {
  const { sources } = useLoaderData<typeof loader>();
  const nav = useNavigation();
  const [searchParams] = useSearchParams();
  const justQueued = searchParams.get("queued") === "1";
  const [url, setUrl] = useState("");

  return (
    <Page
      title="Knowledge Sources"
      subtitle="Add URLs the AI agent should learn from — FAQ pages, policies, product pages, and more"
    >
      <Layout>
        <Layout.Section>
          <BlockStack gap="400">
            {justQueued && (
              <Banner title="URL queued for ingestion" tone="success">
                <Text as="p">
                  Your URL has been added. The AI agent will process it within a few minutes and start using it to answer shoppers.
                </Text>
              </Banner>
            )}

            {/* Add new source */}
            <Card>
              <BlockStack gap="400">
                <BlockStack gap="100">
                  <Text as="h2" variant="headingMd">Add a knowledge URL</Text>
                  <Text as="p" tone="subdued">
                    Paste the full URL of any page you want your agent to learn from. Supports product pages, FAQ pages, shipping policies, returns policies, and blog posts.
                  </Text>
                </BlockStack>
                <Form method="post">
                  <input type="hidden" name="intent" value="add" />
                  <BlockStack gap="300">
                    <TextField
                      label="Website or page URL"
                      name="url"
                      value={url}
                      onChange={setUrl}
                      placeholder="https://yourstore.com/pages/faq"
                      autoComplete="off"
                      type="url"
                      helpText="The agent will crawl this page and index its content for answering shoppers."
                    />
                    <InlineStack>
                      <Button
                        submit
                        variant="primary"
                        loading={nav.state === "submitting"}
                        disabled={!url.trim()}
                      >
                        Add URL
                      </Button>
                    </InlineStack>
                  </BlockStack>
                </Form>
              </BlockStack>
            </Card>

            {/* Source list */}
            <Card>
              <BlockStack gap="300">
                <InlineStack align="space-between">
                  <Text as="h2" variant="headingMd">Indexed sources</Text>
                  <Badge>{String(sources.length)}</Badge>
                </InlineStack>
                {sources.length === 0 ? (
                  <BlockStack gap="200">
                    <Divider />
                    <Text as="p" tone="subdued">
                      No knowledge sources yet. Add your first URL above to get started.
                    </Text>
                  </BlockStack>
                ) : (
                  sources.map(
                    (source: { id: string; url: string | null; status: string; createdAt: string }, i: number) => (
                      <BlockStack gap="0" key={source.id}>
                        {i > 0 && <Divider />}
                        <div style={{ paddingBlock: "12px" }}>
                          <InlineStack align="space-between" blockAlign="center" gap="400">
                            <BlockStack gap="100">
                              <Text as="p" fontWeight="semibold" breakWord>
                                {source.url || "—"}
                              </Text>
                              <Text as="p" tone="subdued" variant="bodySm">
                                Added {new Date(source.createdAt).toLocaleDateString()}
                              </Text>
                            </BlockStack>
                            <InlineStack gap="200" blockAlign="center">
                              <Badge tone={statusTone(source.status)}>
                                {statusLabel(source.status)}
                              </Badge>
                              <Form method="post">
                                <input type="hidden" name="intent" value="delete" />
                                <input type="hidden" name="id" value={source.id} />
                                <Button
                                  submit
                                  variant="plain"
                                  tone="critical"
                                  size="slim"
                                >
                                  Remove
                                </Button>
                              </Form>
                            </InlineStack>
                          </InlineStack>
                        </div>
                      </BlockStack>
                    )
                  )
                )}
              </BlockStack>
            </Card>

            {/* Tips */}
            <Banner title="Tips for a better knowledge base" tone="info">
              <BlockStack gap="100">
                <Text as="p">• Add your FAQ page so the agent can answer common questions instantly.</Text>
                <Text as="p">• Add your shipping and returns policies to reduce support tickets.</Text>
                <Text as="p">• Add individual product pages for richer product recommendations.</Text>
                <Text as="p">• Sources are re-indexed automatically every 7 days.</Text>
              </BlockStack>
            </Banner>
          </BlockStack>
        </Layout.Section>
      </Layout>
    </Page>
  );
}

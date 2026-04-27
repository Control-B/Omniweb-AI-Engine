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

  if (intent === "update-details") {
    const id = String(form.get("id") || "");
    const details = String(form.get("details") || "").trim();
    if (id) {
      const source = await prisma.knowledgeSource.update({
        where: { id },
        data: { details, status: "queued" } as any,
      });
      if (source.url) {
        await enqueueKnowledgeIngestion({
          shop_domain: session.shop,
          source_id: source.id,
          url: source.url,
          details,
        });
      }
    }
    return redirect("/app/knowledge?updated=1");
  }

  const url = normalizeKnowledgeUrl(String(form.get("url") || ""));
  if (!url) return redirect("/app/knowledge?error=invalid-url");
  const details = String(form.get("details") || "").trim();

  const shop = await prisma.shop.upsert({
    where: { shopDomain: session.shop },
    update: {},
    create: { shopDomain: session.shop, status: "installed" },
  });

  const source = await prisma.knowledgeSource.create({
    data: { shopId: shop.id, type: "url", url, details, status: "queued" } as any,
  });

  await enqueueKnowledgeIngestion({
    shop_domain: session.shop,
    source_id: source.id,
    url,
    details,
  });

  return redirect("/app/knowledge?queued=1");
}

function statusTone(status: string): "success" | "attention" | "info" | "critical" {
  if (status === "ready" || status === "done") return "success";
  if (status === "queued" || status === "processing") return "info";
  if (status === "error" || status === "failed") return "critical";
  return "info";
}

function statusLabel(status: string) {
  const map: Record<string, string> = {
    queued: "Added — indexing",
    processing: "Indexing…",
    ready: "Indexed",
    done: "Indexed",
    error: "Error — retry",
    failed: "Error — retry",
  };
  return map[status] ?? status;
}

function normalizeKnowledgeUrl(value: string) {
  const trimmed = value.trim();
  if (!trimmed) return null;
  const withProtocol = /^https?:\/\//i.test(trimmed) ? trimmed : `https://${trimmed}`;

  try {
    const parsed = new URL(withProtocol);
    if (!parsed.hostname.includes(".")) return null;
    return parsed.toString();
  } catch {
    return null;
  }
}

function SourceDetailsForm({
  source,
  loading,
}: {
  source: { id: string; details?: string | null };
  loading: boolean;
}) {
  const [value, setValue] = useState(source.details || "");

  return (
    <Form method="post">
      <input type="hidden" name="intent" value="update-details" />
      <input type="hidden" name="id" value={source.id} />
      <BlockStack gap="200">
        <TextField
          label="Subscriber details"
          name="details"
          value={value}
          onChange={setValue}
          multiline={4}
          autoComplete="off"
          placeholder="Add product/service notes, recommendations, caveats, policies, and sales guidance for this URL."
          helpText="Update this whenever the page needs extra context. Saving will re-sync this source."
        />
        <InlineStack align="end">
          <Button submit size="slim" loading={loading}>
            Save details
          </Button>
        </InlineStack>
      </BlockStack>
    </Form>
  );
}

export default function Knowledge() {
  const { sources } = useLoaderData<typeof loader>();
  const nav = useNavigation();
  const [searchParams] = useSearchParams();
  const justQueued = searchParams.get("queued") === "1";
  const invalidUrl = searchParams.get("error") === "invalid-url";
  const justUpdated = searchParams.get("updated") === "1";
  const [url, setUrl] = useState("");
  const [details, setDetails] = useState("");

  return (
    <Page
      fullWidth
      title="Knowledge Sources"
      subtitle="Add URLs the AI agent should learn from — FAQ pages, policies, product pages, and more"
    >
      <div className="omni-page-shell">
      <Layout>
        <Layout.Section>
          <BlockStack gap="400">
            {justQueued && (
              <Banner title="URL added successfully" tone="success">
                <Text as="p">
                  Your URL has been saved and is being indexed now. It will appear below and the agent will start using it within a few minutes.
                </Text>
              </Banner>
            )}
            {invalidUrl && (
              <Banner title="Enter a valid page URL" tone="critical">
                <Text as="p">
                  Paste a store page such as your FAQ, shipping policy, returns policy, or product URL.
                </Text>
              </Banner>
            )}
            {justUpdated && (
              <Banner title="Knowledge details updated" tone="success">
                <Text as="p">
                  Your added instructions were saved and synced so the AI agent can use them with the indexed URL.
                </Text>
              </Banner>
            )}

            {/* Add new source */}
            <Card>
              <BlockStack gap="400">
                <BlockStack gap="100">
                  <Text as="h2" variant="headingMd">Add a knowledge URL</Text>
                  <Text as="p" tone="subdued">
                    Paste a page URL, then add the extra product, service, policy, or brand details that may not be fully written on the page.
                  </Text>
                </BlockStack>
                <Form method="post">
                  <input type="hidden" name="intent" value="add" />
                  <BlockStack gap="300">
                    <div className="omni-url-row">
                    <TextField
                      label="Website or page URL"
                      name="url"
                      value={url}
                      onChange={setUrl}
                      placeholder="yourstore.com/pages/faq"
                      autoComplete="url"
                      type="text"
                      helpText="The agent will crawl this page and index its content for answering shoppers."
                    />
                    <Button
                      submit
                      variant="primary"
                      loading={nav.state === "submitting"}
                      disabled={!url.trim()}
                    >
                      Add URL
                    </Button>
                    </div>
                    <TextField
                      label="Extra details for this source"
                      name="details"
                      value={details}
                      onChange={setDetails}
                      multiline={5}
                      autoComplete="off"
                      placeholder="Example: These products are best for sensitive skin. Mention the 30-day exchange policy. Recommend the starter bundle for first-time buyers."
                      helpText="Add the details shoppers should hear even if they are not obvious on the URL. This becomes part of the AI agent's knowledge."
                    />
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
                  <div className="omni-scroll-list">
                  {sources.map(
                    (source: { id: string; url: string | null; details?: string | null; status: string; createdAt: string }, i: number) => (
                      <BlockStack gap="0" key={source.id}>
                        {i > 0 && <Divider />}
                        <div style={{ paddingBlock: "12px" }}>
                          <BlockStack gap="300">
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
                          <SourceDetailsForm source={source} loading={nav.state === "submitting"} />
                          </BlockStack>
                        </div>
                      </BlockStack>
                    )
                  )}
                  </div>
                )}
              </BlockStack>
            </Card>
          </BlockStack>
        </Layout.Section>

        <Layout.Section variant="oneThird">
          <BlockStack gap="400">
            <Card>
              <BlockStack gap="300">
                <Text as="h2" variant="headingMd">What to add first</Text>
                <div className="omni-muted-panel">
                  <BlockStack gap="200">
                    <Text as="p">Start with pages shoppers ask about most: FAQs, shipping, returns, product care, sizing, and warranty policies.</Text>
                    <Text as="p" tone="subdued">Use public storefront URLs. Password-protected admin links cannot be indexed.</Text>
                    <Text as="p" tone="subdued">Add subscriber details for product benefits, service rules, sales guidance, and answers that are missing from the page.</Text>
                  </BlockStack>
                </div>
              </BlockStack>
            </Card>

            <Banner title="Tips for better answers" tone="info">
              <BlockStack gap="100">
                <Text as="p">Add one focused page per source.</Text>
                <Text as="p">Write details like you are training a new sales associate.</Text>
                <Text as="p">Keep policy pages updated before re-indexing.</Text>
                <Text as="p">Add product pages for richer recommendations.</Text>
              </BlockStack>
            </Banner>
          </BlockStack>
        </Layout.Section>
      </Layout>
      </div>
    </Page>
  );
}

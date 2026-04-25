import { z } from "zod";

const engineUrl = (process.env.OMNIWEB_ENGINE_URL || "").replace(/\/$/, "");
const engineSecret = process.env.OMNIWEB_ENGINE_SHARED_SECRET || "";

const EngineSyncPayload = z.object({
  shop_domain: z.string().min(1),
  engine_client_id: z.string().optional().nullable(),
  plan: z.string(),
  subscription_status: z.string(),
  assistant_enabled: z.boolean().default(true),
  agent_config: z.record(z.string(), z.unknown()).optional(),
});

export type EngineSyncPayload = z.infer<typeof EngineSyncPayload>;

async function engineFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  if (!engineUrl || !engineSecret) {
    throw new Error("Omniweb Engine URL or shared secret is not configured");
  }

  const response = await fetch(`${engineUrl}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      "X-Omniweb-Shopify-Secret": engineSecret,
      ...(init.headers || {}),
    },
  });

  if (!response.ok) {
    const body = await response.text();
    throw new Error(body || `Engine request failed (${response.status})`);
  }

  return (await response.json()) as T;
}

export async function syncShopToEngine(payload: EngineSyncPayload) {
  const body = EngineSyncPayload.parse(payload);
  return engineFetch<{ ok: boolean; client_id?: string }>("/api/shopify/engine/sync-shop", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function enqueueKnowledgeIngestion(input: {
  shop_domain: string;
  source_id: string;
  url: string;
}) {
  return engineFetch<{ ok: boolean; job_id?: string }>("/api/shopify/engine/knowledge-jobs", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

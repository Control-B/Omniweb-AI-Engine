import { z } from "zod";

const engineUrl = (process.env.OMNIWEB_ENGINE_URL || "").replace(/\/$/, "");
const engineSecret = process.env.OMNIWEB_ENGINE_SHARED_SECRET || "";

const EngineSyncPayload = z.object({
  shop_domain: z.string().min(1),
  engine_client_id: z.string().optional().nullable(),
  shop_name: z.string().optional().nullable(),
  shop_email: z.string().optional().nullable(),
  admin_access_token: z.string().optional().nullable(),
  storefront_access_token: z.string().optional().nullable(),
  granted_scopes: z.array(z.string()).optional(),
  storefront_api_version: z.string().optional().nullable(),
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
  return engineFetch<{ ok: boolean; client_id?: string; store_id?: string }>("/api/shopify/engine/sync-shop", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function syncSubscriptionToEngine(input: {
  shop_domain: string;
  plan: string;
  subscription_status: string;
  shopify_subscription_gid?: string | null;
}) {
  return engineFetch<{ ok: boolean; client_id?: string }>("/api/shopify/engine/sync-subscription", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export async function disableShopInEngine(input: {
  shop_domain: string;
  reason: string;
}) {
  return engineFetch<{ ok: boolean; client_id?: string }>("/api/shopify/engine/disable-store", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export async function forwardShopifyGdprToEngine(
  topic: "customers-data-request" | "customers-redact" | "shop-redact",
  payload: unknown,
) {
  return engineFetch<{ ok: boolean }>(`/api/shopify/engine/gdpr/${topic}`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function enqueueKnowledgeIngestion(input: {
  shop_domain: string;
  source_id: string;
  url: string;
  details?: string;
}) {
  return engineFetch<{ ok: boolean; job_id?: string }>("/api/shopify/engine/knowledge-jobs", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export type EngineAnalytics = {
  ok: boolean;
  conversations: number;
  active_sessions: number;
  qualified_leads: number;
  discount_requests: number;
  approved_discounts: number;
  recent_sessions: Array<{
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
  }>;
};

export async function getEngineAnalytics(shopDomain: string) {
  return engineFetch<EngineAnalytics>(
    `/api/shopify/engine/analytics?shop_domain=${encodeURIComponent(shopDomain)}`,
    { method: "GET" },
  );
}

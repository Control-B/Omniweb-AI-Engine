const DEFAULT_PRODUCTION_API_BASE = "https://omniweb-engine-rs6fr.ondigitalocean.app";

function normalizeApiBase(url: string): string {
  return url.replace(/\/$/, "");
}

function resolveApiBase(): string {
  const configured = process.env.NEXT_PUBLIC_API_URL?.trim();
  if (configured) return normalizeApiBase(configured);
  const engineUrl = process.env.NEXT_PUBLIC_ENGINE_URL?.trim();
  if (engineUrl) return normalizeApiBase(engineUrl);
  if (process.env.NODE_ENV === "development") return "http://localhost:8000";
  return DEFAULT_PRODUCTION_API_BASE;
}

function resolveApiBases(): string[] {
  // Prefer same-origin /api in browsers so admin pages avoid cross-origin preflight issues.
  const configured =
    process.env.NEXT_PUBLIC_API_URL?.trim() ||
    process.env.NEXT_PUBLIC_ENGINE_URL?.trim() ||
    "";
  const bases: string[] = [];
  if (typeof window !== "undefined" && window.location.origin) {
    bases.push(window.location.origin);
  }
  if (configured) bases.push(configured);
  if (process.env.NODE_ENV === "development") {
    bases.push("http://localhost:8000");
  } else {
    bases.push(DEFAULT_PRODUCTION_API_BASE);
  }
  return uniqueBases(bases);
}

function getApiBases(): string[] {
  return resolveApiBases();
}

function getPrimaryApiBase(): string {
  return getApiBases()[0] || DEFAULT_PRODUCTION_API_BASE;
}

// All backend routes live under /api
const API_PREFIX = "/api";

// ── Token management ─────────────────────────────────────────────────────────

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("omniweb_token");
}

export function setToken(token: string) {
  localStorage.setItem("omniweb_token", token);
}

export function clearToken() {
  localStorage.removeItem("omniweb_token");
}

// ── Admin token stash (for demo round-tripping) ──────────────────────────────

const ADMIN_TOKEN_KEY = "omniweb_admin_token_stash";

/** Save the current token before entering demo mode so we can restore it later. */
export function stashAdminToken() {
  const current = getToken();
  if (current) {
    localStorage.setItem(ADMIN_TOKEN_KEY, current);
  }
}

/** Restore the admin token stashed before demo mode. Returns true if restored. */
export function restoreAdminToken(): boolean {
  const stashed = localStorage.getItem(ADMIN_TOKEN_KEY);
  if (stashed) {
    setToken(stashed);
    localStorage.removeItem(ADMIN_TOKEN_KEY);
    return true;
  }
  return false;
}

/** Check if there's a stashed admin session (i.e. we're in demo mode). */
export function hasStashedAdminToken(): boolean {
  return !!localStorage.getItem(ADMIN_TOKEN_KEY);
}

export function parseJwt(token: string): Record<string, any> | null {
  try {
    const payload = token.split(".")[1];
    return JSON.parse(atob(payload));
  } catch {
    return null;
  }
}

// ── Fetch wrapper ────────────────────────────────────────────────────────────

async function apiFetch<T = any>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const bases = getApiBases();
  let lastError: Error | null = null;

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const message = body.detail || `API error ${res.status}`;

        // Retry on routing/infra-ish errors with next base.
        if (res.status === 404 || res.status === 502 || res.status === 503 || res.status === 504) {
          lastError = new Error(message);
          continue;
        }

        // For 401 on non-auth endpoints, clear token and redirect to login.
        if (res.status === 401 && !path.startsWith("/auth/")) {
          clearToken();
          if (typeof window !== "undefined") window.location.href = "/login";
        }
        throw new Error(message);
      }
      return res.json();
    } catch (err) {
      lastError = err instanceof Error ? err : new Error("Load failed");
      // Try next base only for transport-level failures.
      if (!(lastError instanceof TypeError)) {
        throw lastError;
      }
    }
  }
  throw lastError || new Error("Load failed");
}

// ── Auth ─────────────────────────────────────────────────────────────────────

export interface AuthResponse {
  access_token: string;
  token_type: string;
  client_id: string;
  email: string;
  plan: string;
  role: string;
  permissions?: string[];
}

export async function login(
  email: string,
  password: string,
  portal: "client" | "admin" = "client"
): Promise<AuthResponse> {
  const data = await apiFetch<AuthResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password, portal }),
  });
  setToken(data.access_token);
  return data;
}

export async function signup(body: {
  name: string;
  email: string;
  password: string;
  business_name?: string;
  business_type?: string;
  template_id?: string;
}): Promise<AuthResponse> {
  const data = await apiFetch<AuthResponse>("/auth/signup", {
    method: "POST",
    body: JSON.stringify(body),
  });
  setToken(data.access_token);
  return data;
}

export async function demoLogin(): Promise<AuthResponse> {
  const data = await apiFetch<AuthResponse>("/auth/demo-token", {
    method: "POST",
  });
  setToken(data.access_token);
  return data;
}

export function logout() {
  clearToken();
  if (typeof window !== "undefined") window.location.href = "/login";
}

// ── Profile ──────────────────────────────────────────────────────────────────

export interface Profile {
  client_id: string;
  name: string;
  email: string;
  plan: string;
  role: string;
  crm_webhook_url: string | null;
  notification_email: string | null;
  business_name: string | null;
  business_type: string | null;
  created_at: string | null;
}

export async function getProfile(): Promise<Profile> {
  return apiFetch<Profile>("/auth/profile");
}

export async function updateProfile(body: {
  name?: string;
  notification_email?: string;
  crm_webhook_url?: string;
  business_name?: string;
}): Promise<Profile> {
  return apiFetch<Profile>("/auth/profile", {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export async function changePassword(currentPassword: string, newPassword: string) {
  return apiFetch<{ ok: boolean; message: string }>("/auth/change-password", {
    method: "POST",
    body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
  });
}

export interface AdminUser {
  id: string;
  name: string;
  email: string;
  role: string;
  permissions: string[];
  is_active: boolean;
  created_at: string | null;
  invited_at: string | null;
  invite_accepted_at: string | null;
}

export async function requestPasswordReset(body: {
  email: string;
  portal?: "client" | "admin";
}) {
  return apiFetch<{ ok: boolean; message: string }>("/auth/forgot-password", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function resetPasswordWithToken(token: string, newPassword: string) {
  return apiFetch<{ ok: boolean; message: string }>("/auth/reset-password", {
    method: "POST",
    body: JSON.stringify({ token, new_password: newPassword }),
  });
}

export async function acceptInvite(token: string, password: string, name?: string) {
  return apiFetch<{ ok: boolean; message: string }>("/auth/accept-invite", {
    method: "POST",
    body: JSON.stringify({ token, password, name }),
  });
}

export async function getAdminUsers(): Promise<AdminUser[]> {
  return apiFetch<AdminUser[]>("/auth/admin/users");
}

export async function createAdminUser(body: {
  name: string;
  email: string;
  password: string;
  role: "admin" | "support";
  permissions?: string[];
}): Promise<AdminUser> {
  return apiFetch<AdminUser>("/auth/admin/users", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function inviteAdminUser(body: {
  name: string;
  email: string;
  role: "admin" | "support";
  permissions?: string[];
}): Promise<AdminUser> {
  return apiFetch<AdminUser>("/auth/admin/users/invite", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function setAdminUserStatus(userId: string, isActive: boolean): Promise<AdminUser> {
  return apiFetch<AdminUser>(`/auth/admin/users/${userId}/status`, {
    method: "POST",
    body: JSON.stringify({ is_active: isActive }),
  });
}

export async function updateAdminUser(
  userId: string,
  body: { role?: "admin" | "support"; permissions?: string[] }
): Promise<AdminUser> {
  return apiFetch<AdminUser>(`/auth/admin/users/${userId}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export async function sendAdminUserReset(userId: string): Promise<AdminUser> {
  return apiFetch<AdminUser>(`/auth/admin/users/${userId}/send-reset`, {
    method: "POST",
  });
}

export async function generateApiKey() {
  return apiFetch<{ api_key: string; note: string }>("/auth/api-key", {
    method: "POST",
  });
}

// ── Client data endpoints ────────────────────────────────────────────────────

export async function getAnalytics(clientId?: string) {
  const params = clientId ? `?client_id=${clientId}` : "";
  return apiFetch(`/analytics/summary${params}`);
}

export async function getWeeklyStats(clientId?: string) {
  const params = clientId ? `?client_id=${clientId}` : "";
  return apiFetch(`/analytics/weekly${params}`);
}

export async function getToolCallLogs(params?: {
  clientId?: string;
  toolName?: string;
  limit?: number;
  offset?: number;
}) {
  const q = new URLSearchParams();
  if (params?.clientId) q.set("client_id", params.clientId);
  if (params?.toolName) q.set("tool_name", params.toolName);
  if (params?.limit) q.set("limit", String(params.limit));
  if (params?.offset) q.set("offset", String(params.offset));
  return apiFetch(`/analytics/tool-calls?${q}`);
}

export async function getCalls(clientId?: string, limit = 50, offset = 0) {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  if (clientId) params.set("client_id", clientId);
  return apiFetch(`/calls?${params}`);
}

export async function getCall(callId: string) {
  return apiFetch(`/calls/${callId}`);
}

export async function syncCalls(clientId?: string) {
  const params = clientId ? `?client_id=${clientId}` : "";
  return apiFetch(`/calls/sync${params}`, { method: "POST" });
}

export async function getLeads(params?: {
  clientId?: string;
  status?: string;
  search?: string;
  sortBy?: string;
  limit?: number;
  offset?: number;
}) {
  const q = new URLSearchParams();
  if (params?.clientId) q.set("client_id", params.clientId);
  if (params?.status) q.set("status", params.status);
  if (params?.search) q.set("search", params.search);
  if (params?.sortBy) q.set("sort_by", params.sortBy);
  if (params?.limit) q.set("limit", String(params.limit));
  if (params?.offset) q.set("offset", String(params.offset));
  return apiFetch(`/leads?${q}`);
}

export async function getLead(leadId: string) {
  return apiFetch(`/leads/${leadId}`);
}

export async function updateLeadStatus(leadId: string, status: string) {
  return apiFetch(`/leads/${leadId}/status`, {
    method: "PATCH",
    body: JSON.stringify({ status }),
  });
}

export async function getAgentConfig(clientId: string) {
  return apiFetch(`/agent-config/${clientId}`);
}

export async function updateAgentConfig(clientId: string, body: Record<string, any>) {
  return apiFetch(`/agent-config/${clientId}`, {
    method: "PUT",
    body: JSON.stringify(body),
  });
}

export interface WidgetEmbedResponse {
  agent_id: string;
  embed_code: string;
  legacy_embed_code?: string | null;
  talk_url?: string | null;
  widget_url?: string | null;
  retell_agent_id?: string | null;
  embed_domain?: string | null;
  embed_expires_at?: string | null;
}

export async function getWidgetEmbed(clientId: string) {
  return apiFetch<WidgetEmbedResponse>(`/agent-config/${clientId}/widget`);
}

export async function startRetellPhoneCall(input: {
  clientId: string;
  toNumber: string;
  language?: string;
}) {
  return apiFetch<{
    ok: boolean;
    call_id?: string | null;
    agent_id: string;
    from_number: string;
    to_number: string;
  }>("/retell/phone-call", {
    method: "POST",
    body: JSON.stringify({
      client_id: input.clientId,
      to_number: input.toNumber,
      language: input.language,
    }),
  });
}

export async function getNumbers(clientId?: string) {
  const params = clientId ? `?client_id=${clientId}` : "";
  return apiFetch(`/numbers${params}`);
}

export async function searchAvailableNumbers(areaCode?: string, country = "US", limit = 20, numberType = "local") {
  const params = new URLSearchParams({ country, limit: String(limit), number_type: numberType });
  if (areaCode) params.set("area_code", areaCode);
  return apiFetch<{ numbers: any[] }>(`/numbers/available?${params}`);
}

export async function buyNumber(phoneNumber: string, friendlyName: string) {
  return apiFetch(`/numbers`, {
    method: "POST",
    body: JSON.stringify({ phone_number: phoneNumber, friendly_name: friendlyName }),
  });
}

export async function deleteNumber(numberId: string, releaseTwilio = false) {
  return apiFetch(`/numbers/${numberId}?release_twilio=${releaseTwilio}`, {
    method: "DELETE",
  });
}

export async function assignNumberToAgent(numberId: string) {
  return apiFetch(`/numbers/${numberId}/assign-agent`, { method: "POST" });
}

export async function setNumberMode(numberId: string, mode: "ai" | "forward", forwardTo?: string) {
  return apiFetch(`/numbers/${numberId}/mode`, {
    method: "POST",
    body: JSON.stringify({ mode, forward_to: forwardTo }),
  });
}

// ── Admin endpoints ──────────────────────────────────────────────────────────

export async function adminGetClients(params?: {
  search?: string;
  plan?: string;
  limit?: number;
  offset?: number;
}) {
  const q = new URLSearchParams();
  if (params?.search) q.set("search", params.search);
  if (params?.plan) q.set("plan", params.plan);
  if (params?.limit) q.set("limit", String(params.limit));
  if (params?.offset) q.set("offset", String(params.offset));
  return apiFetch(`/admin/clients?${q}`);
}

export async function adminGetClient(clientId: string) {
  return apiFetch(`/admin/clients/${clientId}`);
}

export async function adminPatchClient(clientId: string, body: Record<string, any>) {
  return apiFetch(`/admin/clients/${clientId}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export async function adminGetStats() {
  return apiFetch("/admin/stats");
}

export async function adminGetAgents() {
  return apiFetch("/admin/agents");
}

export async function adminGetConversations(params?: {
  channel?: string;
  status?: string;
  limit?: number;
  offset?: number;
}) {
  const q = new URLSearchParams();
  if (params?.channel) q.set("channel", params.channel);
  if (params?.status) q.set("status", params.status);
  if (params?.limit) q.set("limit", String(params.limit));
  if (params?.offset) q.set("offset", String(params.offset));
  return apiFetch(`/admin/conversations?${q}`);
}

export async function adminGetTemplates() {
  return apiFetch("/admin/templates");
}

export async function adminCreateTemplate(body: Record<string, any>) {
  return apiFetch("/admin/templates", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function adminUpdateTemplate(id: string, body: Record<string, any>) {
  return apiFetch(`/admin/templates/${id}`, {
    method: "PUT",
    body: JSON.stringify(body),
  });
}

export async function adminDeleteTemplate(id: string) {
  return apiFetch(`/admin/templates/${id}`, { method: "DELETE" });
}

export async function adminImpersonate(clientId: string) {
  return apiFetch<AuthResponse>(`/admin/impersonate/${clientId}`, {
    method: "POST",
  });
}

// ── Public endpoints ─────────────────────────────────────────────────────────

export async function getPublicTemplates(industry?: string) {
  const params = industry ? `?industry=${industry}` : "";
  return apiFetch(`/templates${params}`);
}

// ── Automations ──────────────────────────────────────────────────────────────

export interface AutomationStep {
  type: string;
  config: Record<string, string>;
}

export interface AutomationSequence {
  id: string;
  name: string;
  trigger: string;
  enabled: boolean;
  steps: AutomationStep[];
  created_at: string | null;
  updated_at: string | null;
}

export async function getAutomations(clientId?: string) {
  const params = clientId ? `?client_id=${clientId}` : "";
  return apiFetch<{ sequences: AutomationSequence[] }>(`/automations${params}`);
}

export async function createAutomation(body: {
  name: string;
  trigger: string;
  enabled: boolean;
  steps: AutomationStep[];
}) {
  return apiFetch<AutomationSequence>("/automations", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function updateAutomation(id: string, body: {
  name?: string;
  trigger?: string;
  enabled?: boolean;
  steps?: AutomationStep[];
}) {
  return apiFetch<AutomationSequence>(`/automations/${id}`, {
    method: "PUT",
    body: JSON.stringify(body),
  });
}

export async function deleteAutomation(id: string) {
  return apiFetch(`/automations/${id}`, { method: "DELETE" });
}

export interface SiteTemplateInstance {
  id: string;
  client_id: string;
  name: string;
  site_slug: string;
  public_slug: string;
  template_slug: string;
  status: "draft" | "published" | "archived";
  is_active: boolean;
  content: Record<string, any>;
  theme_overrides: Record<string, any>;
  agent_embed_config: Record<string, any>;
  created_at: string | null;
  updated_at: string | null;
}

export async function getSiteTemplateInstances(clientId?: string) {
  const params = clientId ? `?client_id=${clientId}` : "";
  return apiFetch<{ instances: SiteTemplateInstance[] }>(`/site-templates${params}`);
}

export async function createSiteTemplateInstance(body: {
  client_id?: string;
  name: string;
  site_slug: string;
  public_slug?: string;
  template_slug: string;
  status?: "draft" | "published" | "archived";
  content?: Record<string, any>;
  theme_overrides?: Record<string, any>;
  agent_embed_config?: Record<string, any>;
}) {
  return apiFetch<SiteTemplateInstance>("/site-templates", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function updateSiteTemplateInstance(
  id: string,
  body: {
    name?: string;
    site_slug?: string;
    public_slug?: string;
    status?: "draft" | "published" | "archived";
    is_active?: boolean;
    content?: Record<string, any>;
    theme_overrides?: Record<string, any>;
    agent_embed_config?: Record<string, any>;
  }
) {
  return apiFetch<SiteTemplateInstance>(`/site-templates/${id}`, {
    method: "PUT",
    body: JSON.stringify(body),
  });
}

export async function deleteSiteTemplateInstance(id: string) {
  return apiFetch(`/site-templates/${id}`, { method: "DELETE" });
}

export async function getPublicSiteTemplateInstance(publicSlug: string) {
  const res = await fetch(`${getPrimaryApiBase()}${API_PREFIX}/site-templates/public/${publicSlug}`, {
    cache: "no-store",
  });

  if (res.status === 404) {
    return null;
  }

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `API error ${res.status}`);
  }

  return (await res.json()) as SiteTemplateInstance;
}

// ── Knowledge Base ───────────────────────────────────────────────────────────

export async function getKnowledgeBase() {
  return apiFetch<{ documents: any[] }>("/knowledge-base");
}

export async function createKbFromText(text: string, name?: string) {
  return apiFetch("/knowledge-base/text", {
    method: "POST",
    body: JSON.stringify({ text, name }),
  });
}

export async function createKbFromUrl(url: string, name?: string) {
  return apiFetch("/knowledge-base/url", {
    method: "POST",
    body: JSON.stringify({ url, name }),
  });
}

export async function uploadKbFile(file: File, name?: string) {
  const token = getToken();
  const formData = new FormData();
  formData.append("file", file);
  if (name) formData.append("name", name);

  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${getPrimaryApiBase()}${API_PREFIX}/knowledge-base/file`, {
    method: "POST",
    headers,
    body: formData,
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Upload failed (${res.status})`);
  }

  return res.json();
}

export async function deleteKbDocument(docId: string) {
  return apiFetch(`/knowledge-base/${docId}`, { method: "DELETE" });
}

// ── SaaS workspace / widget ─────────────────────────────────────────────────

export interface WorkspaceResponse {
  workspace: {
    client_id: string;
    business_name: string | null;
    industry: string | null;
    website_url: string | null;
    website_domain: string | null;
    primary_goal: string | null;
    onboarding_completed_at: string | null;
  };
  widget: {
    public_widget_key: string | null;
    status: string;
    agent_name: string | null;
    welcome_message: string | null;
    theme_color: string;
    position: string;
  };
  widget_config: {
    business_instructions: string;
    tone: string;
    lead_questions: string[];
    call_to_action: string;
    knowledge_source_url: string;
  };
  trial: {
    subscription_status: string | null;
    trial_started_at: string | null;
    trial_ends_at: string | null;
    remaining: { days: number; hours: number; minutes: number; isExpired: boolean };
  };
  setup_progress: Record<string, boolean>;
  needs_onboarding: boolean;
}

export async function getMeWorkspace(): Promise<WorkspaceResponse> {
  return apiFetch<WorkspaceResponse>("/me/workspace");
}

export async function postOnboarding(body: {
  business_name: string;
  industry: string;
  website: string;
  primary_goal: string;
}): Promise<WorkspaceResponse> {
  return apiFetch<WorkspaceResponse>("/onboarding", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function patchWidgetConfig(body: Record<string, unknown>): Promise<WorkspaceResponse> {
  return apiFetch<WorkspaceResponse>("/widget/config", {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export async function getWidgetEmbedCode(): Promise<{
  public_widget_key: string;
  embed_snippet: string;
  script_url: string;
}> {
  return apiFetch("/widget/embed-code");
}

export async function postWidgetTest(): Promise<{ ok: boolean; preview_url: string; workspace?: WorkspaceResponse }> {
  return apiFetch("/widget/test", { method: "POST" });
}

export async function patchSetupProgress(body: {
  embed_installed?: boolean;
  subscription_activated?: boolean;
}): Promise<WorkspaceResponse> {
  return apiFetch<WorkspaceResponse>("/me/workspace/setup-progress", {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

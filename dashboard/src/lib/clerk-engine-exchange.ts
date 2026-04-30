import { getEngineApiBaseForClient, setToken } from "@/lib/api";

/**
 * Exchange a Clerk session JWT (from the dashboard web app) for the engine-issued
 * JWT stored in localStorage for the legacy client area.
 */
export async function exchangeClerkSessionForEngineToken(
  getClerkToken: () => Promise<string | null>
): Promise<string> {
  const ct = await getClerkToken();
  if (!ct) {
    throw new Error("No Clerk session token");
  }
  const base = getEngineApiBaseForClient();
  const res = await fetch(`${base}/api/auth/clerk-session`, {
    method: "POST",
    headers: {
      Accept: "application/json",
      Authorization: `Bearer ${ct}`,
    },
  });
  if (!res.ok) {
    const msg = await res.text().catch(() => "");
    throw new Error(msg || "Engine session exchange failed");
  }
  const data = (await res.json().catch(() => null)) as { access_token?: string } | null;
  if (!data?.access_token) {
    throw new Error("No engine access token in response");
  }
  return data.access_token;
}

/**
 * Fetches engine JWT, persists it, and returns it (caller can redirect after).
 */
export async function signIntoEngineWithClerk(
  getClerkToken: () => Promise<string | null>
): Promise<string> {
  const access = await exchangeClerkSessionForEngineToken(getClerkToken);
    setToken(access, "client");
  return access;
}

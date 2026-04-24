"use client";

import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  type ReactNode,
} from "react";
import { getToken, parseJwt, clearToken, logout as apiLogout } from "@/lib/api";

export type UserRole = "owner" | "admin" | "support" | "client";

export type UserPermission =
  | "*"
  | "overview.read"
  | "clients.read"
  | "clients.write"
  | "clients.impersonate"
  | "agents.read"
  | "conversations.read"
  | "templates.read"
  | "templates.write"
  | "team.read"
  | "team.manage";

export const PERMISSION_OPTIONS: {
  key: Exclude<UserPermission, "*">;
  label: string;
  description: string;
}[] = [
  { key: "overview.read", label: "Overview", description: "View platform KPIs and summary analytics." },
  { key: "clients.read", label: "Clients", description: "View tenant accounts and client records." },
  { key: "clients.write", label: "Client editing", description: "Change tenant status, plan, and profile fields." },
  { key: "clients.impersonate", label: "Client impersonation", description: "Access client dashboards as them for support." },
  { key: "agents.read", label: "Agents", description: "View cross-client agent configurations." },
  { key: "conversations.read", label: "Sessions", description: "View calls and conversations across tenants." },
  { key: "templates.read", label: "Templates", description: "View reusable agent templates." },
  { key: "templates.write", label: "Template editing", description: "Create, update, or archive templates." },
  { key: "team.read", label: "Team", description: "View internal staff members and invite state." },
  { key: "team.manage", label: "Team management", description: "Invite staff and change access or status." },
];

export const DEFAULT_ROLE_PERMISSIONS: Record<UserRole, UserPermission[]> = {
  owner: ["*"],
  admin: [
    "overview.read",
    "clients.read",
    "clients.write",
    "agents.read",
    "conversations.read",
    "templates.read",
    "templates.write",
  ],
  support: [
    "overview.read",
    "clients.read",
    "agents.read",
    "conversations.read",
    "templates.read",
  ],
  client: [],
};

export function isInternalRole(role: string | null | undefined): role is Exclude<UserRole, "client"> {
  return role === "owner" || role === "admin" || role === "support";
}

export interface User {
  client_id: string;
  email: string;
  name?: string;
  first_name?: string;
  plan: string;
  role: UserRole;
  permissions: UserPermission[];
}

interface AuthContextType {
  user: User | null;
  loading: boolean;
  logout: () => void;
  refresh: () => void;
}

const AuthContext = createContext<AuthContextType>({
  user: null,
  loading: true,
  logout: () => {},
  refresh: () => {},
});

export function useAuth() {
  return useContext(AuthContext);
}

export function hasPermission(
  user: User | null | undefined,
  permission: UserPermission
) {
  if (!user) return false;
  return user.permissions.includes("*") || user.permissions.includes(permission);
}

function readUser(): User | null {
  try {
    const token = getToken();
    if (!token) return null;
    const payload = parseJwt(token);
    if (!payload || (payload.exp && Number(payload.exp) * 1000 < Date.now())) {
      clearToken();
      return null;
    }
    const sub = payload.sub;
    if (typeof sub !== "string" || !sub) {
      clearToken();
      return null;
    }
    return {
      client_id: sub,
      email: typeof payload.email === "string" ? payload.email : "",
        name: typeof payload.name === "string" ? payload.name : undefined,
        first_name: typeof payload.first_name === "string" ? payload.first_name : undefined,
      plan: typeof payload.plan === "string" ? payload.plan : "",
      role: (payload.role || "client") as UserRole,
      permissions:
        payload.permissions ||
        DEFAULT_ROLE_PERMISSIONS[(payload.role || "client") as UserRole] ||
        [],
    };
  } catch {
    try {
      clearToken();
    } catch {
      /* ignore */
    }
    return null;
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  // Start null/loading on both server and client to avoid hydration mismatch,
  // then read localStorage in useEffect (client-only).
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(() => {
    try {
      setUser(readUser());
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const logout = useCallback(() => {
    apiLogout();
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, logout, refresh }}>
      {children}
    </AuthContext.Provider>
  );
}

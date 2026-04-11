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

export interface User {
  client_id: string;
  email: string;
  plan: string;
  role: "admin" | "client";
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

function readUser(): User | null {
  const token = getToken();
  if (!token) return null;
  const payload = parseJwt(token);
  if (!payload || (payload.exp && payload.exp * 1000 < Date.now())) {
    clearToken();
    return null;
  }
  return {
    client_id: payload.sub,
    email: payload.email,
    plan: payload.plan,
    role: payload.role || "client",
  };
}

export function AuthProvider({ children }: { children: ReactNode }) {
  // Start null/loading on both server and client to avoid hydration mismatch,
  // then read localStorage in useEffect (client-only).
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(() => {
    setUser(readUser());
    setLoading(false);
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

"use client";

import type { ReactNode } from "react";
import { AuthProvider } from "@/lib/auth-context";

function isPublicPath(path: string): boolean {
  // If middleware did not set x-omniweb-path, avoid forcing AuthProvider (prevents odd SSR/500 edge cases).
  if (!path) return true;
  if (path === "/landing" || path === "/login" || path === "/sign-in" || path.startsWith("/auth/") || path === "/demo" || path === "/health") return true;
  if (path === "/register" || path === "/sign-up" || path === "/logout" || path === "/sso-callback") return true;
  if (path === "/widget" || path.startsWith("/widget/")) return true;
  if (path.startsWith("/reset-password")) return true;
  if (path.startsWith("/site/")) return true;
  if (path.startsWith("/templates")) return true;
  return false;
}

/** Renders ``AuthProvider`` only when the request path is not public (see ``middleware.ts``). */
export function MaybeAuth({
  pathname,
  children,
}: {
  pathname: string;
  children: ReactNode;
}) {
  if (isPublicPath(pathname)) {
    return <>{children}</>;
  }
  return <AuthProvider>{children}</AuthProvider>;
}

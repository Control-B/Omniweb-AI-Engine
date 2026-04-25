"use client";

import type { ReactNode } from "react";
import { AuthProvider } from "@/lib/auth-context";

function isPublicPath(path: string): boolean {
  if (!path) return false;
  if (path === "/landing" || path === "/login" || path === "/demo" || path === "/health") return true;
  if (path === "/register" || path === "/logout" || path === "/sso-callback") return true;
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

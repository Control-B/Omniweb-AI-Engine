"use client";

import { useState } from "react";
import { Zap, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input, Label } from "@/components/ui/input";
import Link from "next/link";
import { login, requestPasswordReset } from "@/lib/api";
import { isInternalRole } from "@/lib/auth-context";
import { SIGN_IN_PATH } from "@/lib/auth-landing";

export default function LoginPage() {
  const [portal, setPortal] = useState<"client" | "admin">("admin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setNotice("");
    setLoading(true);

    try {
      const data = await login(email, password, portal);
      window.location.href = isInternalRole(data.role) ? "/admin" : "/dashboard";
      return;
    } catch (err: any) {
      setError(err.message || "Something went wrong");
      setLoading(false);
    }
  }

  async function handleForgotPassword() {
    if (!email.trim()) {
      setError("Enter your email first");
      return;
    }
    setLoading(true);
    setError("");
    setNotice("");
    try {
      const result = await requestPasswordReset({ email, portal });
      setNotice(result.message);
    } catch (err: any) {
      setError(err.message || "Failed to send reset email");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-background p-4">
      <div className="w-full max-w-sm space-y-6">
        {/* Logo */}
        <div className="flex flex-col items-center gap-3">
          <div className="flex items-center justify-center w-12 h-12 rounded-xl bg-primary text-primary-foreground">
            <Zap className="w-6 h-6" />
          </div>
          <div className="text-center">
            <h1 className="text-xl font-bold text-foreground">Omniweb AI</h1>
            <p className="text-sm text-muted-foreground mt-1">
              {portal === "admin"
                ? "Admin & team sign in"
                : "Client sign in"}
            </p>
            <p className="text-xs text-muted-foreground/80 mt-2 max-w-xs">
              {portal === "admin"
                ? "Use your internal team credentials to access the admin workspace."
                : "Client accounts sign in here, but new accounts are provisioned by Omniweb — no public signup on this surface."}
            </p>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-1 rounded-lg bg-secondary p-1">
          <button
            type="button"
            onClick={() => {
              setPortal("client");
              setError("");
            }}
            className={`rounded-md px-3 py-2 text-sm font-medium transition-colors ${
              portal === "client"
                ? "bg-background text-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            Client Portal
          </button>
          <button
            type="button"
            onClick={() => {
              setPortal("admin");
              setError("");
            }}
            className={`rounded-md px-3 py-2 text-sm font-medium transition-colors ${
              portal === "admin"
                ? "bg-background text-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            Admin Portal
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="email">Email</Label>
            <Input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@company.com"
              required
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="password">Password</Label>
            <Input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              required
              minLength={6}
            />
          </div>

          <div className="flex justify-end -mt-1">
            <button
              type="button"
              onClick={handleForgotPassword}
              className="text-xs text-primary hover:underline"
            >
              Forgot password?
            </button>
          </div>

          {error && (
            <div className="text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">
              {error}
            </div>
          )}

          {notice && (
            <div className="text-sm text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 rounded-lg px-3 py-2">
              {notice}
            </div>
          )}

          <Button type="submit" className="w-full" disabled={loading}>
            {loading && <Loader2 className="w-4 h-4 animate-spin" />}
            {portal === "admin" ? "Sign In to Admin" : "Sign In"}
          </Button>
        </form>

        <p className="text-center text-xs text-muted-foreground px-2 leading-relaxed">
          Omniweb subscriber?{" "}
          <Link href={SIGN_IN_PATH} className="text-primary underline">
            Clerk sign-in
          </Link>{" "}
          (same account as omniweb.ai).
        </p>

        <p className="text-center text-sm text-muted-foreground">
          {portal === "admin"
            ? "Admin accounts are created by the workspace owner and stored internally."
            : "Need an account? Contact Omniweb to be provisioned or receive an invite."}
        </p>

        {/* Demo shortcut */}
        <div className="flex items-center justify-center">
          <a
            href="/demo"
            className="text-sm text-primary hover:underline font-medium"
          >
            Try Demo Dashboard →
          </a>
        </div>

        {/* Legal links */}
        <div className="flex items-center justify-center gap-3 text-[11px] text-muted-foreground/60">
          <a
            href="https://omniweb.ai/terms"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-muted-foreground transition-colors"
          >
            Terms of Service
          </a>
          <span className="text-muted-foreground/30">·</span>
          <a
            href="https://omniweb.ai/privacy"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-muted-foreground transition-colors"
          >
            Privacy Policy
          </a>
        </div>
      </div>
    </div>
  );
}

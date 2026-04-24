"use client";

import { useEffect, useState } from "react";
import { Eye, EyeOff, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input, Label } from "@/components/ui/input";
import { getAdminBootstrapStatus, login, requestPasswordReset, type AdminBootstrapStatus } from "@/lib/api";
import { isInternalRole } from "@/lib/auth-context";

export default function LoginPage() {
  const [portal, setPortal] = useState<"client" | "admin">("admin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(false);
  const [forgotMode, setForgotMode] = useState(false);
  const [bootstrapStatus, setBootstrapStatus] = useState<AdminBootstrapStatus | null>(null);

  useEffect(() => {
    let cancelled = false;
    getAdminBootstrapStatus()
      .then((data) => { if (!cancelled) setBootstrapStatus(data); })
      .catch(() => {});
    return () => { cancelled = true; };
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setNotice("");
    setLoading(true);
    try {
      const data = await login(email, password, portal);
      window.location.href = isInternalRole(data.role) ? "/admin" : "/dashboard";
    } catch (err: any) {
      setError(err.message || "Invalid credentials");
      setLoading(false);
    }
  }

  async function handleForgotPassword(e: React.FormEvent) {
    e.preventDefault();
    if (!email.trim()) { setError("Enter your email first"); return; }
    setLoading(true);
    setError("");
    setNotice("");
    try {
      const result = await requestPasswordReset({ email, portal });
      setNotice(result.message);
      setForgotMode(false);
    } catch (err: any) {
      setError(err.message || "Failed to send reset email");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-background p-4">
      <div className="w-full max-w-sm space-y-6">

        {/* Omniweb AI Brand Mark */}
        <div className="flex flex-col items-center gap-3">
          <div className="relative flex items-center justify-center">
            <div className="w-14 h-14 rounded-full bg-gradient-to-br from-blue-500 to-cyan-400 shadow-[0_0_32px_rgba(59,130,246,0.45)]" />
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="w-5 h-5 rounded-full bg-white/20 backdrop-blur-sm" />
            </div>
          </div>
          <div className="text-center">
            <h1 className="text-xl font-bold text-foreground">Omniweb AI</h1>
            <p className="text-sm text-muted-foreground mt-0.5">
              {portal === "admin" ? "Admin & team sign in" : "Client portal"}
            </p>
          </div>
        </div>

        {/* Portal toggle */}
        <div className="grid grid-cols-2 gap-1 rounded-lg bg-secondary p-1">
          {(["client", "admin"] as const).map((p) => (
            <button
              key={p}
              type="button"
              onClick={() => { setPortal(p); setError(""); setNotice(""); setForgotMode(false); }}
              className={`rounded-md px-3 py-2 text-sm font-medium transition-colors ${
                portal === p
                  ? "bg-background text-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              {p === "client" ? "Client Portal" : "Admin Portal"}
            </button>
          ))}
        </div>

        {/* Form */}
        {forgotMode ? (
          <form onSubmit={handleForgotPassword} className="space-y-4">
            <div className="text-sm text-muted-foreground">
              Enter your email and we'll send you a reset link.
            </div>
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
            {error && (
              <div className="text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">{error}</div>
            )}
            {notice && (
              <div className="text-sm text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 rounded-lg px-3 py-2">{notice}</div>
            )}
            <Button type="submit" className="w-full" disabled={loading}>
              {loading && <Loader2 className="w-4 h-4 animate-spin" />}
              Send Reset Link
            </Button>
            <button
              type="button"
              onClick={() => { setForgotMode(false); setError(""); setNotice(""); }}
              className="w-full text-sm text-muted-foreground hover:text-foreground transition-colors text-center"
            >
              ← Back to sign in
            </button>
          </form>
        ) : (
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
              <div className="flex items-center justify-between">
                <Label htmlFor="password">Password</Label>
                <button
                  type="button"
                  onClick={() => { setForgotMode(true); setError(""); setNotice(""); }}
                  className="text-xs text-primary hover:underline"
                >
                  Forgot password?
                </button>
              </div>
              <div className="relative">
                <Input
                  id="password"
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  required
                  minLength={6}
                  className="pr-10"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((v) => !v)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                  tabIndex={-1}
                >
                  {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            {error && (
              <div className="text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">{error}</div>
            )}
            {notice && (
              <div className="text-sm text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 rounded-lg px-3 py-2">{notice}</div>
            )}

            <Button type="submit" className="w-full" disabled={loading}>
              {loading && <Loader2 className="w-4 h-4 animate-spin" />}
              {portal === "admin" ? "Sign in to Admin" : "Sign in"}
            </Button>
          </form>
        )}

        {/* Context hint */}
        <p className="text-center text-xs text-muted-foreground">
          {portal === "admin"
            ? bootstrapStatus?.bootstrap_open
              ? "No owner account exists yet."
              : "Admin accounts are managed by the workspace owner."
            : "Client accounts are provisioned by Omniweb."}
        </p>

        {/* Bootstrap + recover links */}
        <div className="flex flex-col items-center gap-2 text-sm">
          {portal === "admin" && bootstrapStatus?.bootstrap_open && (
            <a href="/admin/setup" className="text-primary hover:underline font-medium">
              Create Owner Account →
            </a>
          )}
          <a href="/reset-password" className="text-muted-foreground hover:text-foreground transition-colors">
            Use Invite / Recovery Code
          </a>
          <a href="/demo" className="text-muted-foreground hover:text-foreground transition-colors">
            Try Demo Dashboard
          </a>
        </div>

        {/* Legal */}
        <div className="flex items-center justify-center gap-3 text-[11px] text-muted-foreground/50">
          <a href="https://omniweb.ai/terms" target="_blank" rel="noopener noreferrer" className="hover:text-muted-foreground transition-colors">
            Terms
          </a>
          <span>·</span>
          <a href="https://omniweb.ai/privacy" target="_blank" rel="noopener noreferrer" className="hover:text-muted-foreground transition-colors">
            Privacy
          </a>
        </div>
      </div>
    </div>
  );
}

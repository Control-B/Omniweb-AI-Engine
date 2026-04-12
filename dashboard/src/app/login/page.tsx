"use client";

import { useState } from "react";
import { Zap, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input, Label } from "@/components/ui/input";
import { login, requestPasswordReset, signup } from "@/lib/api";

export default function LoginPage() {
  const [portal, setPortal] = useState<"client" | "admin">("admin");
  const [mode, setMode] = useState<"login" | "signup">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [businessName, setBusinessName] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setNotice("");
    setLoading(true);

    try {
      if (mode === "login") {
        const data = await login(email, password, portal);
        window.location.href = data.role === "admin" ? "/admin" : "/dashboard";
        return;
      } else {
        await signup({
          name,
          email,
          password,
          business_name: businessName || name,
        });
        window.location.href = "/dashboard";
        return;
      }
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
                : mode === "login"
                  ? "Client sign in"
                  : "Create your client account"}
            </p>
            <p className="text-xs text-muted-foreground/80 mt-2 max-w-xs">
              {portal === "admin"
                ? "Use your internal team credentials to access the admin workspace."
                : "Clients sign in with their own business email and password. Sign up creates a new client account in the database."}
            </p>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-1 rounded-lg bg-secondary p-1">
          <button
            type="button"
            onClick={() => {
              setPortal("client");
              setMode("login");
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
              setMode("login");
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
          {portal === "client" && mode === "signup" && (
            <>
              <div className="space-y-1.5">
                <Label htmlFor="name">Your Name</Label>
                <Input
                  id="name"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="John Smith"
                  required
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="business">Business Name</Label>
                <Input
                  id="business"
                  value={businessName}
                  onChange={(e) => setBusinessName(e.target.value)}
                  placeholder="Smith Auto Repair"
                />
              </div>
            </>
          )}
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

          {mode === "login" && (
            <div className="flex justify-end -mt-1">
              <button
                type="button"
                onClick={handleForgotPassword}
                className="text-xs text-primary hover:underline"
              >
                Forgot password?
              </button>
            </div>
          )}

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
            {mode === "login"
              ? portal === "admin"
                ? "Sign In to Admin"
                : "Sign In"
              : "Create Account"}
          </Button>
        </form>

        {/* Toggle */}
        {portal === "client" ? (
          <p className="text-center text-sm text-muted-foreground">
            {mode === "login" ? (
              <>
                Don&apos;t have an account?{" "}
                <button
                  onClick={() => { setMode("signup"); setError(""); }}
                  className="text-primary hover:underline font-medium"
                >
                  Sign up
                </button>
              </>
            ) : (
              <>
                Already have an account?{" "}
                <button
                  onClick={() => { setMode("login"); setError(""); }}
                  className="text-primary hover:underline font-medium"
                >
                  Sign in
                </button>
              </>
            )}
          </p>
        ) : (
          <p className="text-center text-sm text-muted-foreground">
            Admin accounts are created internally and stored in the database.
          </p>
        )}

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

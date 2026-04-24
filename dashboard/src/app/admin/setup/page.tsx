"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2, Eye, EyeOff, ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input, Label } from "@/components/ui/input";
import { adminSignup, getAdminBootstrapStatus } from "@/lib/api";

export default function AdminSetupPage() {
  const router = useRouter();
  const [checking, setChecking] = useState(true);
  const [bootstrapOpen, setBootstrapOpen] = useState(false);
  const [form, setForm] = useState({ name: "", email: "", password: "", confirm: "" });
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    getAdminBootstrapStatus()
      .then((status) => {
        if (!status.bootstrap_open) {
          router.replace("/login");
        } else {
          setBootstrapOpen(true);
        }
      })
      .catch(() => router.replace("/login"))
      .finally(() => setChecking(false));
  }, [router]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    if (form.password !== form.confirm) {
      setError("Passwords do not match");
      return;
    }
    if (form.password.length < 8) {
      setError("Password must be at least 8 characters");
      return;
    }
    setLoading(true);
    try {
      await adminSignup({ name: form.name, email: form.email, password: form.password });
      router.replace("/admin");
    } catch (err: any) {
      setError(err.message || "Failed to create owner account");
      setLoading(false);
    }
  }

  if (checking) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!bootstrapOpen) return null;

  return (
    <div className="min-h-screen flex items-center justify-center bg-background p-4">
      <div className="w-full max-w-sm space-y-6">
        <div className="flex flex-col items-center gap-3">
          <div className="flex items-center justify-center w-14 h-14 rounded-2xl bg-primary/10 border border-primary/20">
            <ShieldCheck className="w-7 h-7 text-primary" />
          </div>
          <div className="text-center">
            <h1 className="text-xl font-bold text-foreground">Create Owner Account</h1>
            <p className="text-sm text-muted-foreground mt-1">
              This is a one-time setup. The owner account has full platform access and cannot be deactivated.
            </p>
          </div>
        </div>

        <div className="rounded-lg border border-amber-500/20 bg-amber-500/5 px-4 py-3 text-sm text-amber-400">
          Once an owner account exists, this setup page will be permanently disabled.
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="name">Full Name</Label>
            <Input
              id="name"
              value={form.name}
              onChange={(e) => setForm((p) => ({ ...p, name: e.target.value }))}
              placeholder="Your Name"
              required
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="email">Email</Label>
            <Input
              id="email"
              type="email"
              value={form.email}
              onChange={(e) => setForm((p) => ({ ...p, email: e.target.value }))}
              placeholder="owner@omniweb.ai"
              required
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="password">Password</Label>
            <div className="relative">
              <Input
                id="password"
                type={showPassword ? "text" : "password"}
                value={form.password}
                onChange={(e) => setForm((p) => ({ ...p, password: e.target.value }))}
                placeholder="At least 8 characters"
                minLength={8}
                required
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

          <div className="space-y-1.5">
            <Label htmlFor="confirm">Confirm Password</Label>
            <div className="relative">
              <Input
                id="confirm"
                type={showConfirm ? "text" : "password"}
                value={form.confirm}
                onChange={(e) => setForm((p) => ({ ...p, confirm: e.target.value }))}
                placeholder="Repeat password"
                minLength={8}
                required
                className="pr-10"
              />
              <button
                type="button"
                onClick={() => setShowConfirm((v) => !v)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                tabIndex={-1}
              >
                {showConfirm ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
          </div>

          {error && (
            <div className="text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">
              {error}
            </div>
          )}

          <Button type="submit" className="w-full" disabled={loading}>
            {loading && <Loader2 className="w-4 h-4 animate-spin" />}
            {loading ? "Creating account..." : "Create Owner Account"}
          </Button>
        </form>

        <div className="flex items-center justify-center">
          <a href="/login" className="text-sm text-muted-foreground hover:text-foreground transition-colors">
            ← Back to Login
          </a>
        </div>
      </div>
    </div>
  );
}

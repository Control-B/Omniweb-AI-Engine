"use client";

import { useEffect, useState } from "react";
import { Loader2, Shield, Zap } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Label } from "@/components/ui/input";
import { adminSignup, getAdminBootstrapStatus, type AdminBootstrapStatus } from "@/lib/api";

export default function AdminSetupPage() {
  const [status, setStatus] = useState<AdminBootstrapStatus | null>(null);
  const [loadingStatus, setLoadingStatus] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [form, setForm] = useState({
    name: "",
    email: "",
    password: "",
  });

  useEffect(() => {
    let cancelled = false;

    async function loadStatus() {
      setLoadingStatus(true);
      try {
        const data = await getAdminBootstrapStatus();
        if (!cancelled) {
          setStatus(data);
        }
      } catch (err: any) {
        if (!cancelled) {
          setError(err.message || "Failed to load setup status");
        }
      } finally {
        if (!cancelled) {
          setLoadingStatus(false);
        }
      }
    }

    void loadStatus();
    return () => {
      cancelled = true;
    };
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError("");
    try {
      await adminSignup(form);
      window.location.href = "/admin";
    } catch (err: any) {
      setError(err.message || "Failed to create owner account");
      setSubmitting(false);
    }
  }

  if (loadingStatus) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background p-4">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background px-4 py-10">
      <div className="mx-auto max-w-md space-y-6">
        <div className="flex flex-col items-center gap-3 text-center">
          <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-primary text-primary-foreground">
            <Zap className="h-6 w-6" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-foreground">Set Up Admin Workspace</h1>
            <p className="mt-2 text-sm text-muted-foreground">
              Create the first owner account. After that, invite teammates from Admin → Team.
            </p>
          </div>
        </div>

        {!status?.bootstrap_open ? (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <Shield className="h-4 w-4" />
                Workspace already initialized
              </CardTitle>
              <CardDescription>
                An owner account already exists. Sign in or ask the owner to send you an invite.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <Button className="w-full" onClick={() => window.location.assign("/login")}>
                Go to Admin Sign In
              </Button>
              <Button variant="outline" className="w-full" onClick={() => window.location.assign("/widget-demo")}>
                Open Demo Website
              </Button>
            </CardContent>
          </Card>
        ) : (
          <Card>
            <CardHeader>
              <CardTitle>Create owner account</CardTitle>
              <CardDescription>
                This runs once per workspace. The first account becomes the owner with full team-management access.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <form className="space-y-4" onSubmit={handleSubmit}>
                <div className="space-y-1.5">
                  <Label htmlFor="name">Full Name</Label>
                  <Input
                    id="name"
                    value={form.name}
                    onChange={(e) => setForm((prev) => ({ ...prev, name: e.target.value }))}
                    placeholder="Your name"
                    required
                  />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="email">Work Email</Label>
                  <Input
                    id="email"
                    type="email"
                    value={form.email}
                    onChange={(e) => setForm((prev) => ({ ...prev, email: e.target.value }))}
                    placeholder="you@company.com"
                    required
                  />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="password">Password</Label>
                  <Input
                    id="password"
                    type="password"
                    value={form.password}
                    onChange={(e) => setForm((prev) => ({ ...prev, password: e.target.value }))}
                    placeholder="At least 6 characters"
                    minLength={6}
                    required
                  />
                </div>

                {error && (
                  <div className="rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                    {error}
                  </div>
                )}

                <Button type="submit" className="w-full" disabled={submitting}>
                  {submitting && <Loader2 className="h-4 w-4 animate-spin" />}
                  Create Owner Account
                </Button>
              </form>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}
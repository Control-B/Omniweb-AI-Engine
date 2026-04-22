"use client";

import { Suspense, useMemo, useState } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { Loader2, Lock, Shield, Zap } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input, Label } from "@/components/ui/input";
import { acceptInvite, resetPasswordWithToken } from "@/lib/api";

function ResetPasswordForm() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const queryToken = searchParams.get("token") || "";
  const initialMode = searchParams.get("mode") === "invite" ? "invite" : "reset";

  const [name, setName] = useState("");
  const [accessCode, setAccessCode] = useState(queryToken);
  const [mode, setMode] = useState<"invite" | "reset">(initialMode);
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const hasPrefilledToken = Boolean(queryToken);

  const title = useMemo(
    () => (mode === "invite" ? "Accept your admin invite" : "Reset your password"),
    [mode]
  );

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setSuccess("");

    const token = accessCode.trim();
    if (!token) {
      setError(hasPrefilledToken ? "This link is invalid or incomplete." : "Enter the recovery code shared by your owner or super admin.");
      return;
    }
    if (password.length < 6) {
      setError("Password must be at least 6 characters.");
      return;
    }
    if (password !== confirm) {
      setError("Passwords do not match.");
      return;
    }

    setLoading(true);
    try {
      const result = mode === "invite"
        ? await acceptInvite(token, password, name || undefined)
        : await resetPasswordWithToken(token, password);
      setSuccess(result.message || (mode === "invite" ? "Invite accepted." : "Password reset."));
      setTimeout(() => router.replace("/login"), 1200);
    } catch (err: any) {
      setError(err.message || "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-background p-4">
      <div className="w-full max-w-sm space-y-6">
        <div className="flex flex-col items-center gap-3 text-center">
          <div className="flex items-center justify-center w-12 h-12 rounded-xl bg-primary text-primary-foreground">
            {mode === "invite" ? <Shield className="w-6 h-6" /> : <Zap className="w-6 h-6" />}
          </div>
          <div>
            <h1 className="text-xl font-bold text-foreground">{title}</h1>
            <p className="text-sm text-muted-foreground mt-1">
              {mode === "invite"
                ? "Create your password to access the Omniweb admin workspace."
                : "Choose a new password for your Omniweb account."}
            </p>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          {!hasPrefilledToken && (
            <>
              <div className="space-y-1.5">
                <Label htmlFor="mode">Recovery mode</Label>
                <select
                  id="mode"
                  value={mode}
                  onChange={(e) => setMode(e.target.value === "invite" ? "invite" : "reset")}
                  className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground"
                >
                  <option value="reset">Reset existing account</option>
                  <option value="invite">Accept new invite</option>
                </select>
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="access-code">Recovery Code</Label>
                <Input
                  id="access-code"
                  value={accessCode}
                  onChange={(e) => setAccessCode(e.target.value)}
                  placeholder="Paste the code from your owner or super admin"
                  required
                />
                <p className="text-xs text-muted-foreground">
                  If email delivery failed, the owner can generate a manual invite or reset code from the super admin console.
                </p>
              </div>
            </>
          )}

          {mode === "invite" && (
            <div className="space-y-1.5">
              <Label htmlFor="name">Your Name</Label>
              <Input
                id="name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Jane Doe"
              />
            </div>
          )}
          <div className="space-y-1.5">
            <Label htmlFor="password">New Password</Label>
            <Input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              minLength={6}
              required
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="confirm">Confirm Password</Label>
            <Input
              id="confirm"
              type="password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              placeholder="••••••••"
              minLength={6}
              required
            />
          </div>

          {error && (
            <div className="text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">
              {error}
            </div>
          )}
          {success && (
            <div className="text-sm text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 rounded-lg px-3 py-2">
              {success} Redirecting to sign in…
            </div>
          )}

          <Button type="submit" className="w-full" disabled={loading}>
            {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Lock className="w-4 h-4" />}
            {mode === "invite" ? "Accept Invite" : "Reset Password"}
          </Button>

          <div className="text-center">
            <a href="/login" className="text-xs text-primary hover:underline">
              Back to sign in
            </a>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function ResetPasswordPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen flex items-center justify-center bg-background p-4">
          <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
        </div>
      }
    >
      <ResetPasswordForm />
    </Suspense>
  );
}

"use client";

import { useState } from "react";
import { Loader2, Lock } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Label } from "@/components/ui/input";
import { changePassword } from "@/lib/api";
import { cn } from "@/lib/utils";

export function ChangePasswordForm() {
  const [form, setForm] = useState({ current: "", next: "", confirm: "" });
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setMessage(null);

    if (form.next !== form.confirm) {
      setMessage({ type: "error", text: "New passwords do not match" });
      return;
    }

    if (form.next.length < 6) {
      setMessage({ type: "error", text: "Password must be at least 6 characters" });
      return;
    }

    setSaving(true);
    try {
      await changePassword(form.current, form.next);
      setForm({ current: "", next: "", confirm: "" });
      setMessage({ type: "success", text: "Password changed successfully" });
    } catch (err: any) {
      setMessage({ type: "error", text: err.message || "Failed to change password" });
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Lock className="w-4 h-4" />
          Change Password
        </CardTitle>
        <CardDescription>Update the password used for email/password sign in.</CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="current-password">Current Password</Label>
            <Input
              id="current-password"
              type="password"
              value={form.current}
              onChange={(e) => setForm((prev) => ({ ...prev, current: e.target.value }))}
              autoComplete="current-password"
              required
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="new-password">New Password</Label>
            <Input
              id="new-password"
              type="password"
              value={form.next}
              onChange={(e) => setForm((prev) => ({ ...prev, next: e.target.value }))}
              autoComplete="new-password"
              minLength={6}
              required
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="confirm-password">Confirm New Password</Label>
            <Input
              id="confirm-password"
              type="password"
              value={form.confirm}
              onChange={(e) => setForm((prev) => ({ ...prev, confirm: e.target.value }))}
              autoComplete="new-password"
              minLength={6}
              required
            />
          </div>

          {message && (
            <div
              className={cn(
                "text-sm rounded-lg px-3 py-2 border",
                message.type === "success"
                  ? "text-emerald-400 bg-emerald-500/10 border-emerald-500/20"
                  : "text-red-400 bg-red-500/10 border-red-500/20"
              )}
            >
              {message.text}
            </div>
          )}

          <Button type="submit" size="sm" variant="outline" disabled={saving}>
            {saving && <Loader2 className="w-4 h-4 animate-spin" />}
            Update Password
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}

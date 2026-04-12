"use client";

import { useEffect, useState } from "react";
import { AlertCircle, Loader2, Mail, RefreshCw, Shield, ShieldOff, UserPlus } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input, Label } from "@/components/ui/input";
import {
  createAdminUser,
  getAdminUsers,
  inviteAdminUser,
  sendAdminUserReset,
  setAdminUserStatus,
  type AdminUser,
} from "@/lib/api";

export function AdminTeam() {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [inviting, setInviting] = useState(false);
  const [busyUserId, setBusyUserId] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [form, setForm] = useState({ name: "", email: "", password: "" });
  const [inviteForm, setInviteForm] = useState({ name: "", email: "" });

  function upsertUser(nextUser: AdminUser) {
    setUsers((prev) => {
      const existing = prev.find((user) => user.id === nextUser.id);
      if (!existing) return [...prev, nextUser];
      return prev.map((user) => (user.id === nextUser.id ? nextUser : user));
    });
  }

  async function loadUsers() {
    setLoading(true);
    setError("");
    try {
      const data = await getAdminUsers();
      setUsers(data);
    } catch (err: any) {
      setError(err.message || "Failed to load admin users");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadUsers();
  }, []);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError("");
    setSuccess("");
    try {
      const created = await createAdminUser(form);
      upsertUser(created);
      setForm({ name: "", email: "", password: "" });
      setSuccess(`Admin login created for ${created.email}`);
    } catch (err: any) {
      setError(err.message || "Failed to create admin user");
    } finally {
      setSaving(false);
    }
  }

  async function handleInvite(e: React.FormEvent) {
    e.preventDefault();
    setInviting(true);
    setError("");
    setSuccess("");
    try {
      const invited = await inviteAdminUser(inviteForm);
      upsertUser(invited);
      setInviteForm({ name: "", email: "" });
      setSuccess(`Invite sent to ${invited.email}`);
    } catch (err: any) {
      setError(err.message || "Failed to send invite");
    } finally {
      setInviting(false);
    }
  }

  async function handleStatus(user: AdminUser, isActive: boolean) {
    setBusyUserId(user.id);
    setError("");
    setSuccess("");
    try {
      const updated = await setAdminUserStatus(user.id, isActive);
      upsertUser(updated);
      setSuccess(`${updated.email} is now ${isActive ? "active" : "inactive"}.`);
    } catch (err: any) {
      setError(err.message || "Failed to update user status");
    } finally {
      setBusyUserId(null);
    }
  }

  async function handleSendAccess(user: AdminUser) {
    setBusyUserId(user.id);
    setError("");
    setSuccess("");
    try {
      const updated = await sendAdminUserReset(user.id);
      upsertUser(updated);
      setSuccess(
        updated.invite_accepted_at
          ? `Reset link sent to ${updated.email}`
          : `Invite sent to ${updated.email}`
      );
    } catch (err: any) {
      setError(err.message || "Failed to send access email");
    } finally {
      setBusyUserId(null);
    }
  }

  return (
    <div className="p-6 space-y-6 max-w-[1100px]">
      <div>
        <h1 className="text-xl font-bold text-foreground">Admin Team</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Create separate email/password logins for internal admins and team members.
        </p>
      </div>

      {(error || success) && (
        <div className="space-y-2">
          {error && (
            <div className="flex items-center gap-2 rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
              <AlertCircle className="h-4 w-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}
          {success && (
            <div className="flex items-center gap-2 rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-400">
              <Shield className="h-4 w-4 shrink-0" />
              <span>{success}</span>
            </div>
          )}
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[380px,380px,1fr]">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Add Team Login</CardTitle>
            <CardDescription>
              Create a DB-backed admin account instantly with email and password.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form className="space-y-4" onSubmit={handleCreate}>
              <div className="space-y-1.5">
                <Label htmlFor="team-name">Full Name</Label>
                <Input
                  id="team-name"
                  value={form.name}
                  onChange={(e) => setForm((prev) => ({ ...prev, name: e.target.value }))}
                  placeholder="Jane Doe"
                  required
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="team-email">Email</Label>
                <Input
                  id="team-email"
                  type="email"
                  value={form.email}
                  onChange={(e) => setForm((prev) => ({ ...prev, email: e.target.value }))}
                  placeholder="jane@omniweb.ai"
                  required
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="team-password">Temporary Password</Label>
                <Input
                  id="team-password"
                  type="password"
                  value={form.password}
                  onChange={(e) => setForm((prev) => ({ ...prev, password: e.target.value }))}
                  placeholder="At least 6 characters"
                  minLength={6}
                  required
                />
              </div>
              <Button type="submit" className="w-full" disabled={saving}>
                {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <UserPlus className="h-4 w-4" />}
                {saving ? "Creating..." : "Create Admin Login"}
              </Button>
            </form>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Invite Team Member</CardTitle>
            <CardDescription>
              Email an invite link so a teammate can set their own password.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form className="space-y-4" onSubmit={handleInvite}>
              <div className="space-y-1.5">
                <Label htmlFor="invite-name">Full Name</Label>
                <Input
                  id="invite-name"
                  value={inviteForm.name}
                  onChange={(e) => setInviteForm((prev) => ({ ...prev, name: e.target.value }))}
                  placeholder="Jane Doe"
                  required
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="invite-email">Email</Label>
                <Input
                  id="invite-email"
                  type="email"
                  value={inviteForm.email}
                  onChange={(e) => setInviteForm((prev) => ({ ...prev, email: e.target.value }))}
                  placeholder="jane@omniweb.ai"
                  required
                />
              </div>
              <Button type="submit" className="w-full" disabled={inviting}>
                {inviting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Mail className="h-4 w-4" />}
                {inviting ? "Sending..." : "Send Invite"}
              </Button>
            </form>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Current Admin Logins</CardTitle>
            <CardDescription>
              Manage access for internal users, including pending invites and reset emails.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {loading ? (
              <div className="flex items-center justify-center py-10">
                <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
              </div>
            ) : users.length === 0 ? (
              <div className="rounded-lg border border-dashed border-border px-4 py-8 text-center text-sm text-muted-foreground">
                No admin users found.
              </div>
            ) : (
              <div className="space-y-2">
                {users.map((user) => (
                  <div
                    key={user.id}
                    className="rounded-lg border border-border px-4 py-3"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="truncate font-medium text-foreground">{user.name}</div>
                        <div className="truncate text-sm text-muted-foreground">{user.email}</div>
                        <div className="mt-1 flex flex-wrap items-center gap-2">
                          <Badge variant={user.is_active ? "success" : "secondary"}>
                            {user.is_active ? "Active" : "Inactive"}
                          </Badge>
                          <Badge variant="default">Admin</Badge>
                          {!user.invite_accepted_at && (
                            <Badge variant="warning">Invite Pending</Badge>
                          )}
                        </div>
                      </div>
                      <div className="flex flex-wrap gap-2 justify-end">
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => handleSendAccess(user)}
                          disabled={busyUserId === user.id}
                        >
                          {busyUserId === user.id ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
                          {user.invite_accepted_at ? "Send Reset" : "Resend Invite"}
                        </Button>
                        {user.is_active ? (
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => handleStatus(user, false)}
                            disabled={busyUserId === user.id}
                          >
                            <ShieldOff className="h-3.5 w-3.5" />
                            Deactivate
                          </Button>
                        ) : (
                          <Button
                            size="sm"
                            onClick={() => handleStatus(user, true)}
                            disabled={busyUserId === user.id}
                          >
                            <Shield className="h-3.5 w-3.5" />
                            Reactivate
                          </Button>
                        )}
                      </div>
                    </div>
                    <div className="mt-2 text-xs text-muted-foreground">
                      {user.invite_accepted_at
                        ? `Invite accepted ${new Date(user.invite_accepted_at).toLocaleDateString()}`
                        : user.invited_at
                          ? `Invite sent ${new Date(user.invited_at).toLocaleDateString()}`
                          : "Direct login created manually"}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

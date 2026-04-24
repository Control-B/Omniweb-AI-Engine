"use client";

import { useEffect, useState, useMemo } from "react";
import {
  DEFAULT_ROLE_PERMISSIONS,
  PERMISSION_OPTIONS,
  hasPermission,
  useAuth,
  type UserPermission,
} from "@/lib/auth-context";
import {
  createAdminUser,
  getAdminUsers,
  inviteAdminUser,
  sendAdminUserReset,
  setAdminUserStatus,
  updateAdminUser,
  type AdminUser,
} from "@/lib/api";
import {
  AlertCircle,
  Check,
  Copy,
  Eye,
  EyeOff,
  KeyRound,
  Loader2,
  Mail,
  RefreshCw,
  Search,
  Shield,
  ShieldOff,
  UserPlus,
  Users,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Label } from "@/components/ui/input";

type StaffRole = "admin" | "support";
type ScopedPermission = Exclude<UserPermission, "*">;
type Tab = "members" | "add" | "invite";

function roleDefaults(role: StaffRole): ScopedPermission[] {
  return DEFAULT_ROLE_PERMISSIONS[role].filter(
    (p): p is ScopedPermission => p !== "*"
  );
}

function togglePermission(current: ScopedPermission[], permission: ScopedPermission) {
  return current.includes(permission)
    ? current.filter((v) => v !== permission)
    : [...current, permission];
}

function sanitizePermissions(permissions?: string[]): ScopedPermission[] {
  const allowed = new Set(PERMISSION_OPTIONS.map((o) => o.key));
  return (permissions || []).filter((p): p is ScopedPermission => allowed.has(p as ScopedPermission));
}

function getInitials(name: string): string {
  return name
    .split(" ")
    .slice(0, 2)
    .map((n) => n[0])
    .join("")
    .toUpperCase();
}

function Avatar({ name, role }: { name: string; role: string }) {
  const colors: Record<string, string> = {
    owner: "bg-amber-500/20 text-amber-400 border-amber-500/30",
    admin: "bg-blue-500/20 text-blue-400 border-blue-500/30",
    support: "bg-purple-500/20 text-purple-400 border-purple-500/30",
  };
  const cls = colors[role] || "bg-secondary text-muted-foreground border-border";
  return (
    <div className={`w-9 h-9 rounded-full flex items-center justify-center text-xs font-semibold border shrink-0 ${cls}`}>
      {getInitials(name)}
    </div>
  );
}

function RoleBadge({ role }: { role: string }) {
  const map: Record<string, { label: string; cls: string }> = {
    owner: { label: "Owner", cls: "bg-amber-500/10 text-amber-400 border border-amber-500/20" },
    admin: { label: "Admin", cls: "bg-blue-500/10 text-blue-400 border border-blue-500/20" },
    support: { label: "Support", cls: "bg-purple-500/10 text-purple-400 border border-purple-500/20" },
  };
  const { label, cls } = map[role] || { label: role, cls: "bg-secondary text-muted-foreground border border-border" };
  return <span className={`inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium ${cls}`}>{label}</span>;
}

function PermissionChecklist({
  permissions,
  onToggle,
  disabled,
}: {
  permissions: ScopedPermission[];
  onToggle: (p: ScopedPermission) => void;
  disabled?: boolean;
}) {
  return (
    <div className="space-y-1.5">
      {PERMISSION_OPTIONS.map((option) => {
        const checked = permissions.includes(option.key);
        return (
          <label
            key={option.key}
            className={`flex items-start gap-3 p-2.5 rounded-lg border transition-colors cursor-pointer ${
              checked
                ? "border-primary/30 bg-primary/5"
                : "border-border hover:border-border/80 hover:bg-secondary/50"
            } ${disabled ? "opacity-50 cursor-not-allowed" : ""}`}
          >
            <div className={`mt-0.5 w-4 h-4 rounded border flex items-center justify-center shrink-0 transition-colors ${
              checked ? "bg-primary border-primary" : "border-input bg-background"
            }`}>
              {checked && <Check className="w-2.5 h-2.5 text-primary-foreground" />}
            </div>
            <input
              type="checkbox"
              checked={checked}
              onChange={() => !disabled && onToggle(option.key)}
              disabled={disabled}
              className="sr-only"
            />
            <span className="text-sm">
              <span className="font-medium text-foreground">{option.label}</span>
              <span className="block text-xs text-muted-foreground leading-tight mt-0.5">{option.description}</span>
            </span>
          </label>
        );
      })}
    </div>
  );
}

function ShareLinkBox({
  shareLink,
  onClose,
}: {
  shareLink: { url?: string | null; code?: string | null; label: string; mode: "invite" | "reset" };
  onClose: () => void;
}) {
  const [copiedUrl, setCopiedUrl] = useState(false);
  const [copiedCode, setCopiedCode] = useState(false);

  async function copy(text: string, setter: (v: boolean) => void) {
    await navigator.clipboard.writeText(text);
    setter(true);
    setTimeout(() => setter(false), 2000);
  }

  return (
    <div className="rounded-lg border border-primary/30 bg-primary/5 p-4 space-y-3">
      <div className="flex items-start justify-between">
        <div>
          <div className="text-sm font-medium text-foreground">Share link ready</div>
          <div className="text-xs text-muted-foreground mt-0.5">{shareLink.label}</div>
        </div>
        <button type="button" onClick={onClose} className="text-muted-foreground hover:text-foreground text-xs">
          Dismiss
        </button>
      </div>
      {shareLink.url && (
        <div className="flex gap-2 items-center">
          <div className="flex-1 rounded-md bg-secondary px-3 py-2 text-xs text-muted-foreground font-mono truncate">
            {shareLink.url}
          </div>
          <Button type="button" variant="outline" size="sm" onClick={() => copy(shareLink.url!, setCopiedUrl)}>
            {copiedUrl ? <Check className="h-3.5 w-3.5 text-green-500" /> : <Copy className="h-3.5 w-3.5" />}
          </Button>
        </div>
      )}
      {shareLink.code && (
        <div className="flex gap-2 items-center">
          <div className="flex-1 rounded-md bg-secondary px-3 py-2 text-xs text-muted-foreground font-mono truncate">
            {shareLink.code}
          </div>
          <Button type="button" variant="outline" size="sm" onClick={() => copy(shareLink.code!, setCopiedCode)}>
            {copiedCode ? <Check className="h-3.5 w-3.5 text-green-500" /> : <KeyRound className="h-3.5 w-3.5" />}
          </Button>
        </div>
      )}
      <p className="text-xs text-muted-foreground">
        If email is unavailable, open <span className="font-mono">/reset-password</span> and use the code above.
      </p>
    </div>
  );
}

export function AdminTeam() {
  const { user } = useAuth();
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [busyUserId, setBusyUserId] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [tab, setTab] = useState<Tab>("members");
  const [search, setSearch] = useState("");
  const [showPassword, setShowPassword] = useState(false);

  const [createForm, setCreateForm] = useState({
    name: "", email: "", password: "", role: "admin" as StaffRole,
    permissions: roleDefaults("admin"),
  });
  const [inviteForm, setInviteForm] = useState({
    name: "", email: "", role: "admin" as StaffRole,
    permissions: roleDefaults("admin"),
  });
  const [editingUserId, setEditingUserId] = useState<string | null>(null);
  const [editingRole, setEditingRole] = useState<StaffRole>("admin");
  const [editingPermissions, setEditingPermissions] = useState<ScopedPermission[]>(roleDefaults("admin"));
  const [shareLink, setShareLink] = useState<{ url?: string | null; code?: string | null; label: string; mode: "invite" | "reset" } | null>(null);

  const canViewTeam = hasPermission(user, "team.read");
  const canManageTeam = hasPermission(user, "team.manage");

  const stats = useMemo(() => ({
    total: users.length,
    active: users.filter((u) => u.is_active).length,
    pending: users.filter((u) => !u.invite_accepted_at).length,
    owners: users.filter((u) => u.role === "owner").length,
  }), [users]);

  const filtered = useMemo(() => {
    if (!search.trim()) return users;
    const q = search.toLowerCase();
    return users.filter((u) => u.name.toLowerCase().includes(q) || u.email.toLowerCase().includes(q) || u.role.includes(q));
  }, [users, search]);

  function upsert(next: AdminUser) {
    setUsers((prev) => {
      const idx = prev.findIndex((u) => u.id === next.id);
      if (idx === -1) return [...prev, next];
      return prev.map((u, i) => i === idx ? next : u);
    });
  }

  function notify(msg: string, isError = false) {
    if (isError) { setError(msg); setSuccess(""); }
    else { setSuccess(msg); setError(""); }
    setTimeout(() => { setError(""); setSuccess(""); }, 5000);
  }

  async function loadUsers() {
    setLoading(true);
    try {
      setUsers(await getAdminUsers());
    } catch (err: any) {
      notify(err.message || "Failed to load team", true);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void loadUsers(); }, []);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setShareLink(null);
    try {
      const created = await createAdminUser(createForm);
      upsert(created);
      setCreateForm({ name: "", email: "", password: "", role: "admin", permissions: roleDefaults("admin") });
      notify(`Login created for ${created.email}`);
      setTab("members");
    } catch (err: any) {
      notify(err.message || "Failed to create user", true);
    } finally {
      setSaving(false);
    }
  }

  async function handleInvite(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setShareLink(null);
    try {
      const invited = await inviteAdminUser(inviteForm);
      upsert(invited);
      setInviteForm({ name: "", email: "", role: "admin", permissions: roleDefaults("admin") });
      notify(`Invite sent to ${invited.email}`);
      if (invited.invite_url || invited.invite_code) {
        setShareLink({ url: invited.invite_url, code: invited.invite_code, label: `Share with ${invited.email}`, mode: "invite" });
      }
      setTab("members");
    } catch (err: any) {
      notify(err.message || "Failed to send invite", true);
    } finally {
      setSaving(false);
    }
  }

  async function handleStatus(member: AdminUser, isActive: boolean) {
    setBusyUserId(member.id);
    setShareLink(null);
    try {
      upsert(await setAdminUserStatus(member.id, isActive));
      notify(`${member.email} is now ${isActive ? "active" : "inactive"}`);
    } catch (err: any) {
      notify(err.message || "Failed to update status", true);
    } finally {
      setBusyUserId(null);
    }
  }

  async function handleSendAccess(member: AdminUser) {
    setBusyUserId(member.id);
    setShareLink(null);
    try {
      const updated = await sendAdminUserReset(member.id);
      upsert(updated);
      notify(updated.invite_accepted_at ? `Reset link created for ${updated.email}` : `Invite created for ${updated.email}`);
      if (updated.invite_url || updated.invite_code) {
        setShareLink({ url: updated.invite_url, code: updated.invite_code, label: `Share with ${updated.email}`, mode: "invite" });
      } else if (updated.reset_url || updated.reset_code) {
        setShareLink({ url: updated.reset_url, code: updated.reset_code, label: `Share with ${updated.email}`, mode: "reset" });
      }
    } catch (err: any) {
      notify(err.message || "Failed to send access", true);
    } finally {
      setBusyUserId(null);
    }
  }

  async function handleSavePermissions(member: AdminUser) {
    setBusyUserId(member.id);
    setShareLink(null);
    try {
      upsert(await updateAdminUser(member.id, { role: editingRole, permissions: editingPermissions }));
      setEditingUserId(null);
      notify(`Updated access for ${member.email}`);
    } catch (err: any) {
      notify(err.message || "Failed to update permissions", true);
    } finally {
      setBusyUserId(null);
    }
  }

  if (!canViewTeam) {
    return (
      <div className="p-6">
        <div className="rounded-lg border border-border bg-card px-4 py-3 text-sm text-muted-foreground">
          You do not have permission to view team access.
        </div>
      </div>
    );
  }

  const tabs: { id: Tab; label: string; icon: React.ReactNode }[] = [
    { id: "members", label: "Team Members", icon: <Users className="h-4 w-4" /> },
    { id: "add", label: "Add Login", icon: <UserPlus className="h-4 w-4" /> },
    { id: "invite", label: "Send Invite", icon: <Mail className="h-4 w-4" /> },
  ];

  return (
    <div className="p-6 space-y-6 max-w-3xl">
      {/* Header */}
      <div>
        <h1 className="text-xl font-bold text-foreground">Team Management</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Manage internal staff, assign permissions, and generate access credentials.
        </p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {[
          { label: "Total", value: stats.total },
          { label: "Active", value: stats.active },
          { label: "Pending", value: stats.pending },
          { label: "Owners", value: stats.owners },
        ].map(({ label, value }) => (
          <div key={label} className="rounded-lg border border-border bg-card px-4 py-3">
            <div className="text-xs text-muted-foreground">{label}</div>
            <div className="text-2xl font-bold text-foreground mt-1">{value}</div>
          </div>
        ))}
      </div>

      {/* Feedback banners */}
      {(error || success) && (
        <div>
          {error && (
            <div className="flex items-center gap-2 rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
              <AlertCircle className="h-4 w-4 shrink-0" /><span>{error}</span>
            </div>
          )}
          {success && (
            <div className="flex items-center gap-2 rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-400">
              <Shield className="h-4 w-4 shrink-0" /><span>{success}</span>
            </div>
          )}
        </div>
      )}

      {shareLink && <ShareLinkBox shareLink={shareLink} onClose={() => setShareLink(null)} />}

      {/* Tabs */}
      <div className="flex gap-1 border-b border-border">
        {tabs.map(({ id, label, icon }) => {
          if ((id === "add" || id === "invite") && !canManageTeam) return null;
          return (
            <button
              key={id}
              type="button"
              onClick={() => setTab(id)}
              className={`flex items-center gap-1.5 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors -mb-px ${
                tab === id
                  ? "border-primary text-foreground"
                  : "border-transparent text-muted-foreground hover:text-foreground"
              }`}
            >
              {icon}{label}
            </button>
          );
        })}
      </div>

      {/* Members Tab */}
      {tab === "members" && (
        <div className="space-y-4">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search by name, email, or role…"
              className="pl-9"
            />
          </div>

          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : filtered.length === 0 ? (
            <div className="rounded-lg border border-dashed border-border px-4 py-10 text-center text-sm text-muted-foreground">
              {search ? "No team members match your search." : "No team members yet. Add a login or send an invite."}
            </div>
          ) : (
            <div className="space-y-2">
              {filtered.map((member) => (
                <div key={member.id} className="rounded-lg border border-border bg-card">
                  <div className="flex items-start gap-3 px-4 py-3">
                    <Avatar name={member.name} role={member.role} />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-medium text-foreground text-sm">{member.name}</span>
                        <RoleBadge role={member.role} />
                        {!member.is_active && (
                          <span className="inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium bg-secondary text-muted-foreground border border-border">
                            Inactive
                          </span>
                        )}
                        {!member.invite_accepted_at && (
                          <span className="inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium bg-amber-500/10 text-amber-400 border border-amber-500/20">
                            Invite Pending
                          </span>
                        )}
                      </div>
                      <div className="text-xs text-muted-foreground mt-0.5">{member.email}</div>
                    </div>
                    {canManageTeam && member.role !== "owner" && (
                      <div className="flex items-center gap-1.5 shrink-0">
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => handleSendAccess(member)}
                          disabled={busyUserId === member.id}
                          title={member.invite_accepted_at ? "Send password reset" : "Resend invite"}
                        >
                          {busyUserId === member.id
                            ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
                            : <RefreshCw className="h-3.5 w-3.5" />
                          }
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => handleStatus(member, !member.is_active)}
                          disabled={busyUserId === member.id}
                          title={member.is_active ? "Deactivate" : "Activate"}
                        >
                          {member.is_active ? <ShieldOff className="h-3.5 w-3.5" /> : <Shield className="h-3.5 w-3.5" />}
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => {
                            if (editingUserId === member.id) {
                              setEditingUserId(null);
                            } else {
                              setEditingUserId(member.id);
                              setEditingRole(member.role as StaffRole);
                              const p = sanitizePermissions(member.permissions);
                              setEditingPermissions(p.length > 0 ? p : roleDefaults(member.role as StaffRole));
                            }
                          }}
                        >
                          {editingUserId === member.id ? "Cancel" : "Edit"}
                        </Button>
                      </div>
                    )}
                  </div>

                  {/* Inline edit panel */}
                  {editingUserId === member.id && (
                    <div className="border-t border-border px-4 py-4 space-y-4 bg-secondary/30">
                      <div className="space-y-1.5">
                        <Label>Role</Label>
                        <select
                          value={editingRole}
                          onChange={(e) => {
                            const r = e.target.value as StaffRole;
                            setEditingRole(r);
                            setEditingPermissions(roleDefaults(r));
                          }}
                          className="flex h-9 w-full max-w-[200px] rounded-md border border-input bg-background px-3 py-1.5 text-sm text-foreground"
                        >
                          <option value="admin">Admin</option>
                          <option value="support">Support</option>
                        </select>
                      </div>
                      <div className="space-y-1.5">
                        <Label>Permissions</Label>
                        <PermissionChecklist
                          permissions={editingPermissions}
                          onToggle={(p) => setEditingPermissions((prev) => togglePermission(prev, p))}
                        />
                      </div>
                      <div className="flex gap-2">
                        <Button
                          size="sm"
                          onClick={() => handleSavePermissions(member)}
                          disabled={busyUserId === member.id}
                        >
                          {busyUserId === member.id && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
                          Save Changes
                        </Button>
                        <Button size="sm" variant="outline" onClick={() => setEditingUserId(null)}>
                          Cancel
                        </Button>
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Add Login Tab */}
      {tab === "add" && canManageTeam && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Add Team Login</CardTitle>
            <CardDescription>
              Create an account with a temporary password. The user can change it after signing in.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form className="space-y-4" onSubmit={handleCreate}>
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <div className="space-y-1.5">
                  <Label htmlFor="add-name">Full Name</Label>
                  <Input
                    id="add-name"
                    value={createForm.name}
                    onChange={(e) => setCreateForm((p) => ({ ...p, name: e.target.value }))}
                    placeholder="Jane Doe"
                    required
                  />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="add-email">Email</Label>
                  <Input
                    id="add-email"
                    type="email"
                    value={createForm.email}
                    onChange={(e) => setCreateForm((p) => ({ ...p, email: e.target.value }))}
                    placeholder="jane@omniweb.ai"
                    required
                  />
                </div>
              </div>
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <div className="space-y-1.5">
                  <Label htmlFor="add-role">Role</Label>
                  <select
                    id="add-role"
                    value={createForm.role}
                    onChange={(e) => {
                      const role = e.target.value as StaffRole;
                      setCreateForm((p) => ({ ...p, role, permissions: roleDefaults(role) }));
                    }}
                    className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground"
                  >
                    <option value="admin">Admin</option>
                    <option value="support">Support</option>
                  </select>
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="add-password">Temporary Password</Label>
                  <div className="relative">
                    <Input
                      id="add-password"
                      type={showPassword ? "text" : "password"}
                      value={createForm.password}
                      onChange={(e) => setCreateForm((p) => ({ ...p, password: e.target.value }))}
                      placeholder="Min 6 characters"
                      minLength={6}
                      required
                      className="pr-10"
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword((v) => !v)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                      tabIndex={-1}
                    >
                      {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </button>
                  </div>
                </div>
              </div>
              <div className="space-y-1.5">
                <Label>Permissions</Label>
                <PermissionChecklist
                  permissions={createForm.permissions}
                  onToggle={(p) => setCreateForm((prev) => ({ ...prev, permissions: togglePermission(prev.permissions, p) }))}
                />
              </div>
              <Button type="submit" disabled={saving} className="w-full sm:w-auto">
                {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <UserPlus className="h-4 w-4" />}
                {saving ? "Creating..." : "Create Login"}
              </Button>
            </form>
          </CardContent>
        </Card>
      )}

      {/* Invite Tab */}
      {tab === "invite" && canManageTeam && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Send Team Invite</CardTitle>
            <CardDescription>
              Email an invite link so a teammate can set their own password. A backup code is also generated.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form className="space-y-4" onSubmit={handleInvite}>
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <div className="space-y-1.5">
                  <Label htmlFor="inv-name">Full Name</Label>
                  <Input
                    id="inv-name"
                    value={inviteForm.name}
                    onChange={(e) => setInviteForm((p) => ({ ...p, name: e.target.value }))}
                    placeholder="Jane Doe"
                    required
                  />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="inv-email">Email</Label>
                  <Input
                    id="inv-email"
                    type="email"
                    value={inviteForm.email}
                    onChange={(e) => setInviteForm((p) => ({ ...p, email: e.target.value }))}
                    placeholder="jane@omniweb.ai"
                    required
                  />
                </div>
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="inv-role">Role</Label>
                <select
                  id="inv-role"
                  value={inviteForm.role}
                  onChange={(e) => {
                    const role = e.target.value as StaffRole;
                    setInviteForm((p) => ({ ...p, role, permissions: roleDefaults(role) }));
                  }}
                  className="flex h-10 w-full max-w-[200px] rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground"
                >
                  <option value="admin">Admin</option>
                  <option value="support">Support</option>
                </select>
              </div>
              <div className="space-y-1.5">
                <Label>Permissions</Label>
                <PermissionChecklist
                  permissions={inviteForm.permissions}
                  onToggle={(p) => setInviteForm((prev) => ({ ...prev, permissions: togglePermission(prev.permissions, p) }))}
                />
              </div>
              <Button type="submit" disabled={saving} className="w-full sm:w-auto">
                {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Mail className="h-4 w-4" />}
                {saving ? "Sending..." : "Send Invite"}
              </Button>
            </form>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

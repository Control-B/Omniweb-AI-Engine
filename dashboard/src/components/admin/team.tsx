"use client";

import { useEffect, useState } from "react";
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
  Loader2,
  Mail,
  RefreshCw,
  Shield,
  ShieldOff,
  UserPlus,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input, Label } from "@/components/ui/input";

type StaffRole = "admin" | "support";
type ScopedPermission = Exclude<UserPermission, "*">;

function roleDefaults(role: StaffRole) {
  return DEFAULT_ROLE_PERMISSIONS[role].filter(
    (permission): permission is ScopedPermission => permission !== "*"
  );
}

function togglePermission(current: ScopedPermission[], permission: ScopedPermission) {
  return current.includes(permission)
    ? current.filter((value) => value !== permission)
    : [...current, permission];
}

function sanitizePermissions(permissions?: string[]) {
  const allowed = new Set(PERMISSION_OPTIONS.map((option) => option.key));
  return (permissions || []).filter(
    (permission): permission is ScopedPermission => allowed.has(permission as ScopedPermission)
  );
}

function PermissionChecklist({
  permissions,
  onToggle,
}: {
  permissions: ScopedPermission[];
  onToggle: (permission: ScopedPermission) => void;
}) {
  return (
    <div className="space-y-2 rounded-lg border border-border p-3">
      <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
        Permission scope
      </div>
      <div className="space-y-2">
        {PERMISSION_OPTIONS.map((option) => (
          <label key={option.key} className="flex items-start gap-2 text-sm">
            <input
              type="checkbox"
              checked={permissions.includes(option.key)}
              onChange={() => onToggle(option.key)}
              className="mt-0.5"
            />
            <span>
              <span className="font-medium text-foreground">{option.label}</span>
              <span className="block text-xs text-muted-foreground">
                {option.description}
              </span>
            </span>
          </label>
        ))}
      </div>
    </div>
  );
}

export function AdminTeam() {
  const { user } = useAuth();
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [inviting, setInviting] = useState(false);
  const [busyUserId, setBusyUserId] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [form, setForm] = useState({
    name: "",
    email: "",
    password: "",
    role: "admin" as StaffRole,
    permissions: roleDefaults("admin"),
  });
  const [inviteForm, setInviteForm] = useState({
    name: "",
    email: "",
    role: "admin" as StaffRole,
    permissions: roleDefaults("admin"),
  });
  const [editingUserId, setEditingUserId] = useState<string | null>(null);
  const [editingRole, setEditingRole] = useState<StaffRole>("admin");
  const [editingPermissions, setEditingPermissions] = useState<ScopedPermission[]>(
    roleDefaults("admin")
  );

  const canViewTeam = hasPermission(user, "team.read");
  const canManageTeam = hasPermission(user, "team.manage");

  function upsertUser(nextUser: AdminUser) {
    setUsers((prev) => {
      const existing = prev.find((entry) => entry.id === nextUser.id);
      if (!existing) return [...prev, nextUser];
      return prev.map((entry) => (entry.id === nextUser.id ? nextUser : entry));
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
    void loadUsers();
  }, []);

  function startEditing(nextUser: AdminUser) {
    if (nextUser.role === "owner") return;
    setEditingUserId(nextUser.id);
    setEditingRole(nextUser.role as StaffRole);
    const nextPermissions = sanitizePermissions(nextUser.permissions);
    setEditingPermissions(
      nextPermissions.length > 0
        ? nextPermissions
        : roleDefaults(nextUser.role as StaffRole)
    );
  }

  function cancelEditing() {
    setEditingUserId(null);
    setEditingRole("admin");
    setEditingPermissions(roleDefaults("admin"));
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError("");
    setSuccess("");
    try {
      const created = await createAdminUser(form);
      upsertUser(created);
      setForm({
        name: "",
        email: "",
        password: "",
        role: "admin",
        permissions: roleDefaults("admin"),
      });
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
      setInviteForm({
        name: "",
        email: "",
        role: "admin",
        permissions: roleDefaults("admin"),
      });
      setSuccess(`Invite sent to ${invited.email}`);
    } catch (err: any) {
      setError(err.message || "Failed to send invite");
    } finally {
      setInviting(false);
    }
  }

  async function handleStatus(member: AdminUser, isActive: boolean) {
    setBusyUserId(member.id);
    setError("");
    setSuccess("");
    try {
      const updated = await setAdminUserStatus(member.id, isActive);
      upsertUser(updated);
      setSuccess(`${updated.email} is now ${isActive ? "active" : "inactive"}.`);
    } catch (err: any) {
      setError(err.message || "Failed to update user status");
    } finally {
      setBusyUserId(null);
    }
  }

  async function handleSendAccess(member: AdminUser) {
    setBusyUserId(member.id);
    setError("");
    setSuccess("");
    try {
      const updated = await sendAdminUserReset(member.id);
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

  async function handleSavePermissions(member: AdminUser) {
    setBusyUserId(member.id);
    setError("");
    setSuccess("");
    try {
      const updated = await updateAdminUser(member.id, {
        role: editingRole,
        permissions: editingPermissions,
      });
      upsertUser(updated);
      cancelEditing();
      setSuccess(`Updated access for ${updated.email}`);
    } catch (err: any) {
      setError(err.message || "Failed to update team access");
    } finally {
      setBusyUserId(null);
    }
  }

  if (!canViewTeam) {
    return (
      <div className="p-6">
        <div className="rounded-lg border border-border bg-card px-4 py-3 text-sm text-muted-foreground">
          You do not have permission to view internal team access.
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6 max-w-[1200px]">
      <div>
        <h1 className="text-xl font-bold text-foreground">Admin Team</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Assign least-privilege access for internal staff members.
        </p>
      </div>

      {!canManageTeam && (
        <div className="rounded-lg border border-border bg-card px-4 py-3 text-sm text-muted-foreground">
          Your access is view-only. Ask a team manager to change internal permissions.
        </div>
      )}

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

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[390px,390px,1fr]">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Add Team Login</CardTitle>
            <CardDescription>
              Create an internal login instantly with a role and a scoped permission set.
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
                <Label htmlFor="team-role">Role</Label>
                <select
                  id="team-role"
                  value={form.role}
                  onChange={(e) => {
                    const role = e.target.value as StaffRole;
                    setForm((prev) => ({ ...prev, role, permissions: roleDefaults(role) }));
                  }}
                  className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground"
                >
                  <option value="admin">Admin</option>
                  <option value="support">Support</option>
                </select>
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
              <PermissionChecklist
                permissions={form.permissions}
                onToggle={(permission) =>
                  setForm((prev) => ({
                    ...prev,
                    permissions: togglePermission(prev.permissions, permission),
                  }))
                }
              />
              <Button type="submit" className="w-full" disabled={saving || !canManageTeam}>
                {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <UserPlus className="h-4 w-4" />}
                {saving ? "Creating..." : "Create Team Login"}
              </Button>
            </form>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Invite Team Member</CardTitle>
            <CardDescription>
              Email an invite link so a teammate can set their password with the assigned access scope.
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
                <Label htmlFor="invite-role">Role</Label>
                <select
                  id="invite-role"
                  value={inviteForm.role}
                  onChange={(e) => {
                    const role = e.target.value as StaffRole;
                    setInviteForm((prev) => ({ ...prev, role, permissions: roleDefaults(role) }));
                  }}
                  className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground"
                >
                  <option value="admin">Admin</option>
                  <option value="support">Support</option>
                </select>
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
              <PermissionChecklist
                permissions={inviteForm.permissions}
                onToggle={(permission) =>
                  setInviteForm((prev) => ({
                    ...prev,
                    permissions: togglePermission(prev.permissions, permission),
                  }))
                }
              />
              <Button type="submit" className="w-full" disabled={inviting || !canManageTeam}>
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
              Review access scopes, pending invites, and update permissions for each internal user.
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
              <div className="space-y-3">
                {users.map((member) => (
                  <div key={member.id} className="rounded-lg border border-border px-4 py-3">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="truncate font-medium text-foreground">{member.name}</div>
                        <div className="truncate text-sm text-muted-foreground">{member.email}</div>
                        <div className="mt-1 flex flex-wrap items-center gap-2">
                          <Badge variant={member.is_active ? "success" : "secondary"}>
                            {member.is_active ? "Active" : "Inactive"}
                          </Badge>
                          <Badge variant={member.role === "owner" ? "warning" : "default"}>
                            {member.role}
                          </Badge>
                          {!member.invite_accepted_at && (
                            <Badge variant="warning">Invite Pending</Badge>
                          )}
                        </div>
                      </div>
                      <div className="flex flex-wrap gap-2 justify-end">
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => handleSendAccess(member)}
                          disabled={busyUserId === member.id || !canManageTeam}
                        >
                          {busyUserId === member.id ? (
                            <Loader2 className="h-3.5 w-3.5 animate-spin" />
                          ) : (
                            <RefreshCw className="h-3.5 w-3.5" />
                          )}
                          {member.invite_accepted_at ? "Send Reset" : "Resend Invite"}
                        </Button>
                        {member.is_active ? (
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => handleStatus(member, false)}
                            disabled={busyUserId === member.id || !canManageTeam || member.role === "owner"}
                          >
                            <ShieldOff className="h-3.5 w-3.5" />
                            Deactivate
                          </Button>
                        ) : (
                          <Button
                            size="sm"
                            onClick={() => handleStatus(member, true)}
                            disabled={busyUserId === member.id || !canManageTeam}
                          >
                            <Shield className="h-3.5 w-3.5" />
                            Reactivate
                          </Button>
                        )}
                        {member.role !== "owner" && (
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => startEditing(member)}
                            disabled={busyUserId === member.id || !canManageTeam}
                          >
                            <Shield className="h-3.5 w-3.5" />
                            Edit access
                          </Button>
                        )}
                      </div>
                    </div>

                    <div className="mt-3 flex flex-wrap gap-2">
                      {(member.permissions || []).map((permission) => (
                        <Badge key={permission} variant="secondary">
                          {permission}
                        </Badge>
                      ))}
                    </div>

                    {editingUserId === member.id && (
                      <div className="mt-4 rounded-lg border border-border bg-background/60 p-4 space-y-4">
                        <div className="space-y-1.5 md:max-w-[200px]">
                          <Label htmlFor={`edit-role-${member.id}`}>Role</Label>
                          <select
                            id={`edit-role-${member.id}`}
                            value={editingRole}
                            onChange={(e) => {
                              const role = e.target.value as StaffRole;
                              setEditingRole(role);
                              setEditingPermissions(roleDefaults(role));
                            }}
                            className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground"
                          >
                            <option value="admin">Admin</option>
                            <option value="support">Support</option>
                          </select>
                        </div>
                        <PermissionChecklist
                          permissions={editingPermissions}
                          onToggle={(permission) =>
                            setEditingPermissions((prev) => togglePermission(prev, permission))
                          }
                        />
                        <div className="flex gap-2 justify-end">
                          <Button size="sm" variant="outline" onClick={cancelEditing} disabled={busyUserId === member.id}>
                            Cancel
                          </Button>
                          <Button size="sm" onClick={() => void handleSavePermissions(member)} disabled={busyUserId === member.id}>
                            {busyUserId === member.id ? (
                              <Loader2 className="h-3.5 w-3.5 animate-spin" />
                            ) : (
                              <Shield className="h-3.5 w-3.5" />
                            )}
                            Save access
                          </Button>
                        </div>
                      </div>
                    )}

                    <div className="mt-2 text-xs text-muted-foreground">
                      {member.invite_accepted_at
                        ? `Invite accepted ${new Date(member.invite_accepted_at).toLocaleDateString()}`
                        : member.invited_at
                          ? `Invite sent ${new Date(member.invited_at).toLocaleDateString()}`
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

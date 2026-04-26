"use client";

import { Shield } from "lucide-react";
import { ChangePasswordForm } from "@/components/account/change-password-form";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useAuth } from "@/lib/auth-context";

export function AdminAccount() {
  const { user } = useAuth();

  return (
    <div className="p-6 space-y-6 max-w-3xl">
      <div>
        <h1 className="text-xl font-bold text-foreground">Account</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Manage your admin profile and sign-in security.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Shield className="w-4 h-4" />
            Admin Profile
          </CardTitle>
          <CardDescription>This is the admin account currently signed in.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3 text-sm">
          <div className="grid gap-1">
            <span className="text-xs text-muted-foreground">Name</span>
            <span className="text-foreground">{user?.first_name || user?.name || "Not set"}</span>
          </div>
          <div className="grid gap-1">
            <span className="text-xs text-muted-foreground">Email</span>
            <span className="text-foreground">{user?.email}</span>
          </div>
          <div className="grid gap-1">
            <span className="text-xs text-muted-foreground">Role</span>
            <span className="text-foreground capitalize">{user?.role}</span>
          </div>
        </CardContent>
      </Card>

      <ChangePasswordForm />
    </div>
  );
}

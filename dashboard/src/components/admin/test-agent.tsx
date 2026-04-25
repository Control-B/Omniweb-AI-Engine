"use client";

import { useEffect, useState } from "react";

import { AgentConfigPage } from "@/components/pages/agent-config";
import { Button } from "@/components/ui/button";
import { Input, Label } from "@/components/ui/input";
import { hasPermission, useAuth } from "@/lib/auth-context";

const STORAGE_KEY = "omniweb_admin_test_agent_client_id";

export function AdminTestAgent() {
  const { user } = useAuth();
  const [draftClientId, setDraftClientId] = useState("");
  const [selectedClientId, setSelectedClientId] = useState("");

  useEffect(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY) || localStorage.getItem("omniweb_widget_demo_client_id") || "";
      if (saved) {
        setDraftClientId(saved);
        setSelectedClientId(saved);
      }
    } catch {
      /* ignore */
    }
  }, []);

  const canEdit = !!user && hasPermission(user, "clients.write");

  function loadClientAgent() {
    const nextClientId = draftClientId.trim();
    if (!nextClientId) return;
    setSelectedClientId(nextClientId);
    try {
      localStorage.setItem(STORAGE_KEY, nextClientId);
    } catch {
      /* ignore */
    }
  }

  return (
    <div className="p-6 max-w-[1400px]">
      <div className="mb-6 rounded-2xl border border-border bg-card p-6 space-y-4">
        <div>
          <h2 className="text-xl font-semibold text-foreground">Admin AI Agent Test</h2>
          <p className="text-sm text-muted-foreground mt-1">
            Load any client&apos;s AI Agent Configuration page from admin, then test the same widget and embed setup without leaving the admin workspace.
          </p>
        </div>

        <div className="flex flex-col gap-3 md:flex-row md:items-end">
          <div className="flex-1 space-y-1.5">
            <Label htmlFor="admin-test-agent-client-id">Client ID (UUID)</Label>
            <Input
              id="admin-test-agent-client-id"
              value={draftClientId}
              onChange={(event) => setDraftClientId(event.target.value)}
              placeholder="e.g. 550e8400-e29b-41d4-a716-446655440000"
            />
          </div>
          <Button onClick={loadClientAgent} disabled={!draftClientId.trim()}>
            Load Agent Page
          </Button>
        </div>
      </div>

      {selectedClientId ? (
        <AgentConfigPage
          clientId={selectedClientId}
          allowSave={canEdit}
          title="AI Agent Configuration"
          description="Review or manage the selected client&apos;s agent settings, widget embed, and test experience from admin."
          containerClassName="space-y-4 max-w-[900px]"
        />
      ) : (
        <div className="rounded-2xl border border-dashed border-border bg-card px-6 py-16 text-center text-sm text-muted-foreground">
          Enter a client UUID above to load the same AI Agent Configuration page used in the client dashboard.
        </div>
      )}
    </div>
  );
}
"use client";

import Link from "next/link";
import type { WorkspaceResponse } from "@/lib/api";

export function TrialBanner({ workspace }: { workspace: WorkspaceResponse | null }) {
  if (!workspace || workspace.needs_onboarding) return null;

  const { remaining } = workspace.trial;
  const sub = (workspace.trial.subscription_status || "").toLowerCase();

  if (sub === "active") return null;

  if (remaining.isExpired) {
    return (
      <div className="shrink-0 border-b border-amber-500/30 bg-amber-500/10 px-4 py-3 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <p className="text-sm text-amber-100">
          Your trial has ended. Upgrade to reactivate your AI agent.
        </p>
        <Link
          href="/dashboard/billing"
          className="inline-flex items-center justify-center rounded-lg bg-amber-500 px-4 py-2 text-sm font-semibold text-amber-950 hover:bg-amber-400 transition-colors"
        >
          Choose a plan
        </Link>
      </div>
    );
  }

  if (sub !== "trialing") return null;

  return (
    <div className="shrink-0 border-b border-amber-500/30 bg-amber-500/10 px-4 py-3 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
      <p className="text-sm text-amber-100">
        <span className="font-medium" aria-hidden>
          ⚠️
        </span>{" "}
        <span className="font-medium">Free trial</span> —{" "}
        <span className="tabular-nums font-semibold">
          {remaining.days} {remaining.days === 1 ? "day" : "days"} remaining
        </span>
        <span className="text-amber-100/80"> (7-day plan)</span>
      </p>
      <Link
        href="/dashboard/billing"
        className="inline-flex shrink-0 items-center justify-center rounded-lg border border-amber-400/40 bg-amber-500/20 px-3 py-1.5 text-sm font-semibold text-amber-50 hover:bg-amber-500/30 transition-colors"
      >
        Subscribe now
      </Link>
    </div>
  );
}

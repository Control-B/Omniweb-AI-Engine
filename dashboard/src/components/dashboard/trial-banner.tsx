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
          Upgrade with Stripe
        </Link>
      </div>
    );
  }

  if (sub !== "trialing") return null;

  return (
    <div className="shrink-0 border-b border-primary/20 bg-primary/10 px-4 py-3 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
      <p className="text-sm text-foreground">
        <span className="font-medium">Your 7-day trial is active.</span> Your AI revenue agent trial ends in{" "}
        <span className="tabular-nums font-semibold text-primary">
          {remaining.days} days, {remaining.hours} hours
        </span>
        .
      </p>
      <Link
        href="/dashboard/billing"
        className="text-sm font-medium text-primary hover:underline underline-offset-2 shrink-0"
      >
        Billing →
      </Link>
    </div>
  );
}

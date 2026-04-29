"use client";

import { WidgetTester } from "@/components/widget-tester";

/**
 * Public landing page to try the voice widget locally or in staging.
 * Widget route: ``/widget/{client_id}`` (UUID from your ``AgentConfig``).
 */
export default function LandingPage() {
  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-950 via-slate-900 to-slate-950 text-slate-100">
      <div className="mx-auto max-w-3xl px-4 py-12 sm:py-16">
        <p className="text-xs font-medium uppercase tracking-widest text-cyan-400/90 mb-3">
          Omniweb · Widget demo
        </p>
        <h1 className="text-3xl sm:text-4xl font-semibold tracking-tight text-white mb-4">
          Try the AI widget
        </h1>
        <p className="text-slate-400 text-base leading-relaxed mb-10">
          This page loads your embeddable assistant in an iframe. You need the Agent Engine running
          with realtime voice configured, and a real{" "}
          <code className="text-cyan-300/90 text-sm">client_id</code> (UUID) that exists in your
          database.
        </p>

        <WidgetTester
          showChecklist
          title="Try the AI widget"
          description="This page loads your embeddable assistant in an iframe so you can test it before deploying."
        />
      </div>
    </div>
  );
}

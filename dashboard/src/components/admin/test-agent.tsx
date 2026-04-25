"use client";

import { WidgetTester } from "@/components/widget-tester";

export function AdminTestAgent() {
  return (
    <div className="p-6 max-w-[1400px]">
      <WidgetTester
        title="Test AI Agent"
        description="Preview the live voice widget, talk to a client agent, and validate the mic/chat experience directly from admin."
        className="rounded-2xl border border-border bg-card p-6"
        previewClassName="w-full min-h-[min(78vh,720px)] bg-transparent"
      />
    </div>
  );
}
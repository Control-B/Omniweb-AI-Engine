"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Loader2, Sparkles } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input, Label } from "@/components/ui/input";
import { postOnboarding } from "@/lib/api";
import { useAuth, isInternalRole } from "@/lib/auth-context";
import { AUTH_HANDOFF_PATH } from "@/lib/auth-landing";

const GOALS: { value: string; label: string }[] = [
  { value: "capture_leads", label: "Capture leads" },
  { value: "answer_customer_questions", label: "Answer customer questions" },
  { value: "recommend_products", label: "Recommend products" },
  { value: "book_appointments", label: "Book appointments" },
  { value: "qualify_prospects", label: "Qualify prospects" },
  { value: "support_existing_customers", label: "Support existing customers" },
];

export default function OnboardingPage() {
  const router = useRouter();
  const { user, loading } = useAuth();
  const [businessName, setBusinessName] = useState("");
  const [industry, setIndustry] = useState("");
  const [website, setWebsite] = useState("");
  const [primaryGoal, setPrimaryGoal] = useState("capture_leads");
  const [err, setErr] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (loading) return;
    if (!user) router.replace(AUTH_HANDOFF_PATH);
    else if (isInternalRole(user.role)) router.replace("/landing");
  }, [user, loading, router]);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setErr("");
    if (!businessName.trim() || !industry.trim() || !website.trim()) {
      setErr("Business name, industry, and website are required.");
      return;
    }
    setSaving(true);
    try {
      await postOnboarding({
        business_name: businessName.trim(),
        industry: industry.trim(),
        website: website.trim(),
        primary_goal: primaryGoal,
      });
      try {
        localStorage.setItem("omniweb_setup_complete", "1");
      } catch {
        /* ignore */
      }
      router.replace("/agent-config");
    } catch (ex) {
      setErr(ex instanceof Error ? ex.message : "Could not save onboarding");
    } finally {
      setSaving(false);
    }
  }

  if (loading || !user) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col items-center justify-center p-6 bg-background">
      <div className="w-full max-w-lg space-y-6">
        <div className="text-center space-y-2">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-2xl bg-primary/10 mb-2">
            <Sparkles className="w-6 h-6 text-primary" />
          </div>
          <h1 className="text-2xl font-bold text-foreground">Welcome to Omniweb</h1>
          <p className="text-sm text-muted-foreground">
            Your AI revenue agent is ready to configure. Tell us about your business to start your 7-day trial.
          </p>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Business profile</CardTitle>
            <CardDescription>We&apos;ll spin up your widget and starter agent configuration.</CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={onSubmit} className="space-y-4">
              <div className="space-y-1.5">
                <Label>Business name *</Label>
                <Input
                  value={businessName}
                  onChange={(e) => setBusinessName(e.target.value)}
                  placeholder="e.g. Northwind Plumbing"
                  required
                />
              </div>
              <div className="space-y-1.5">
                <Label>Industry *</Label>
                <Input
                  value={industry}
                  onChange={(e) => setIndustry(e.target.value)}
                  placeholder="e.g. Home services, Dental, E-commerce"
                  required
                />
              </div>
              <div className="space-y-1.5">
                <Label>Website URL *</Label>
                <Input
                  value={website}
                  onChange={(e) => setWebsite(e.target.value)}
                  placeholder="example.com, www.example.com, or https://example.com"
                  required
                />
                <p className="text-[11px] text-muted-foreground">
                  We store a clean domain and full URL for your agent.
                </p>
              </div>
              <div className="space-y-1.5">
                <Label>Primary agent goal *</Label>
                <select
                  className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                  value={primaryGoal}
                  onChange={(e) => setPrimaryGoal(e.target.value)}
                >
                  {GOALS.map((g) => (
                    <option key={g.value} value={g.value}>
                      {g.label}
                    </option>
                  ))}
                </select>
              </div>
              {err && (
                <div className="text-sm text-destructive bg-destructive/10 border border-destructive/20 rounded-md px-3 py-2">
                  {err}
                </div>
              )}
              <Button type="submit" className="w-full" disabled={saving}>
                {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
                {saving ? "Saving…" : "Continue"}
              </Button>
            </form>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

"use client";

import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";

export default function BillingPage() {
  return (
    <div className="p-6 max-w-xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-foreground">Billing</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Upgrade to keep your AI agent live after your trial.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Stripe checkout</CardTitle>
          <CardDescription>Billing with Stripe is coming next.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-muted-foreground">
            {/* TODO: Create Stripe Checkout Session (server) and redirect to session.url */}
            When ready, this button will start a secure Checkout session. On success you&apos;ll return to{" "}
            <code className="text-xs bg-secondary px-1 rounded">/dashboard?billing=success</code>.
          </p>
          <Button
            type="button"
            disabled
            className="w-full sm:w-auto"
            title="TODO: wire Stripe Checkout session creation"
          >
            Continue to Stripe Checkout
          </Button>
          <p className="text-xs text-muted-foreground">
            TODO: connect STRIPE_SECRET_KEY, price IDs, and webhook to activate subscriptions.
          </p>
          <Link href="/dashboard" className="inline-block text-sm text-primary hover:underline">
            ← Back to dashboard
          </Link>
        </CardContent>
      </Card>
    </div>
  );
}

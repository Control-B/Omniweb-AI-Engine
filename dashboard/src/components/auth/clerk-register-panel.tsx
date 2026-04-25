"use client";

import { SignUp } from "@clerk/nextjs";

const clerkEnabled = Boolean(process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY?.trim());

export function ClerkRegisterPanel() {
  if (!clerkEnabled) {
    return (
      <div className="rounded-2xl border border-border bg-card p-5 text-sm text-muted-foreground">
        Clerk is not configured yet. Set `CLERK_PUBLISHABLE_KEY` (or `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`) in
        your env to enable self-serve sign up.
      </div>
    );
  }

  return (
    <div className="rounded-2xl border border-border bg-card/80 backdrop-blur p-4 shadow-sm">
      <div className="mb-4 text-center">
        <h2 className="text-sm font-semibold text-foreground">Create your Omniweb account</h2>
        <p className="mt-1 text-xs text-muted-foreground">
          Use your full name, email and password, or continue with a social provider.
        </p>
      </div>
      <div className="flex justify-center overflow-hidden">
        <SignUp
          routing="path"
          path="/register"
          signInUrl="/login"
          forceRedirectUrl="/sso-callback"
        />
      </div>
    </div>
  );
}

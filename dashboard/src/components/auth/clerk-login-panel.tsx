"use client";

import { SignIn } from "@clerk/nextjs";

const clerkEnabled = Boolean(process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY?.trim());

export function ClerkLoginPanel() {
  if (!clerkEnabled) return null;

  return (
    <div className="rounded-2xl border border-border bg-card/80 backdrop-blur p-4 shadow-sm">
      <div className="mb-4 text-center">
        <h2 className="text-sm font-semibold text-foreground">Continue with Omniweb</h2>
        <p className="mt-1 text-xs text-muted-foreground">
          Sign in with Google, another social provider, or your email and password.
        </p>
      </div>
      <div className="flex justify-center overflow-hidden">
        <SignIn
          routing="path"
          path="/login"
          signUpUrl="/register"
          forceRedirectUrl="/sso-callback"
        />
      </div>
    </div>
  );
}

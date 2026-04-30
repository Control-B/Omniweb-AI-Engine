"use client";

import { useEffect } from "react";
import { SignUp } from "@clerk/nextjs";
import Link from "next/link";
import { INTERNAL_LOGIN_PATH, SIGN_IN_PATH } from "@/lib/auth-landing";
import { clearSubscriberSession } from "@/lib/api";

const clerkEnabled = Boolean(process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY?.trim());

export default function SignUpPage() {
  useEffect(() => {
    clearSubscriberSession();
  }, []);

  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-background p-4">
      <div className="w-full max-w-md space-y-6">
        <div className="text-center">
          <h1 className="text-xl font-bold text-foreground">
            Start Your 7-Day AI Revenue Agent Trial
          </h1>
          <p className="text-sm text-muted-foreground mt-2">
            Create your account to configure your AI agent and install the widget on your site.
          </p>
        </div>
        {clerkEnabled ? (
          <div className="flex justify-center">
            <SignUp
              routing="path"
              path="/sign-up"
              signInUrl={SIGN_IN_PATH}
              fallbackRedirectUrl="/auth/clerk-continue"
            />
          </div>
        ) : (
          <div className="rounded-lg border border-border bg-card p-6 text-sm text-muted-foreground">
            Public sign-up is not configured on this deployment yet. Please contact Omniweb or
            use the{" "}
            <Link href={INTERNAL_LOGIN_PATH} className="text-primary underline">
              login page
            </Link>{" "}
            if your account has already been provisioned.
          </div>
        )}
        <p className="text-center text-sm text-muted-foreground">
          Already have an account?{" "}
          <Link href={SIGN_IN_PATH} className="text-primary hover:underline">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
}

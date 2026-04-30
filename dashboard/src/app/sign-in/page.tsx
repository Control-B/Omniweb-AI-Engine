"use client";

import { useEffect } from "react";
import { Loader2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { SignIn } from "@clerk/nextjs";
import { INTERNAL_LOGIN_PATH } from "@/lib/auth-landing";

const hasClerk =
  typeof process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY === "string" &&
  process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY.trim().length > 0;

export default function SubscriberSignInPage() {
  const router = useRouter();

  useEffect(() => {
    if (!hasClerk) {
      router.replace(INTERNAL_LOGIN_PATH);
    }
  }, [router]);

  if (!hasClerk) {
    return (
      <div className="flex min-h-dvh flex-col items-center justify-center gap-3">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-background p-4">
      <div className="w-full max-w-md space-y-6">
        <div className="text-center space-y-1">
          <h1 className="text-xl font-bold text-foreground">Omniweb</h1>
          <p className="text-sm text-muted-foreground">
            Sign in to manage your AI agent — same account as omniweb.ai.
          </p>
        </div>
        <div className="flex justify-center">
          <SignIn
            routing="path"
            path="/sign-in"
            signUpUrl="/sign-up"
            fallbackRedirectUrl="/auth/clerk-continue"
          />
        </div>
        <p className="text-center text-xs text-muted-foreground max-w-md mx-auto">
          New here? Subscribe at{" "}
          <a
            href="https://omniweb.ai/get-started"
            className="text-primary underline underline-offset-2"
            target="_blank"
            rel="noopener noreferrer"
          >
            omniweb.ai
          </a>
          , or create an account with <span className="text-foreground/90">Sign up</span> above.
        </p>
        <p className="text-center text-sm text-muted-foreground">
          <Link href={INTERNAL_LOGIN_PATH} className="text-primary hover:underline">
            Internal operator sign-in
          </Link>
        </p>
      </div>
    </div>
  );
}

import Link from "next/link";
import { ClerkRegisterPanel } from "@/components/auth/clerk-register-panel";

export default function RegisterPage() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-background p-4">
      <div className="w-full max-w-xl space-y-6">
        <div className="text-center">
          <h1 className="text-2xl font-bold text-foreground">Create your Omniweb workspace</h1>
          <p className="mt-2 text-sm text-muted-foreground">
            Start with Clerk sign up, then we&apos;ll provision your engine session automatically.
          </p>
        </div>
        <ClerkRegisterPanel />
        <p className="text-center text-sm text-muted-foreground">
          Already have an account? <Link href="/login" className="text-primary hover:underline">Sign in</Link>
        </p>
      </div>
    </div>
  );
}

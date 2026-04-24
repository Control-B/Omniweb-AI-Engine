"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { isInternalRole, useAuth } from "@/lib/auth-context";
import { Loader2 } from "lucide-react";

export default function Home() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [showEscape, setShowEscape] = useState(false);

  useEffect(() => {
    const t = window.setTimeout(() => setShowEscape(true), 5000);
    return () => window.clearTimeout(t);
  }, []);

  useEffect(() => {
    if (loading) return;
    if (!user) {
      router.replace("/login");
    } else if (isInternalRole(user.role)) {
      router.replace("/admin");
    } else {
      router.replace("/dashboard");
    }
  }, [user, loading, router]);

  return (
    <div className="min-h-screen flex flex-col items-center justify-center gap-4 p-6">
      <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
      {showEscape && loading && (
        <p className="text-center text-sm text-muted-foreground max-w-sm">
          Still here?{" "}
          <Link href="/login" className="text-primary underline underline-offset-2">
            Open login
          </Link>{" "}
          or{" "}
          <Link href="/landing" className="text-primary underline underline-offset-2">
            try the widget demo
          </Link>
          .
        </p>
      )}
    </div>
  );
}

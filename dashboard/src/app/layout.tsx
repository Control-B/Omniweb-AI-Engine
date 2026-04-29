import type { Metadata } from "next";
import { ClerkProvider } from "@clerk/nextjs";
import "./globals.css";
import { AuthProvider } from "@/lib/auth-context";

const clerkPublishableKey = process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY?.trim() ?? "";

export const metadata: Metadata = {
  title: "Omniweb AI — Dashboard",
  description: "AI-powered phone agent management platform",
  icons: {
    icon: [
      { url: "/icon.svg?v=20260411a", type: "image/svg+xml", sizes: "any" },
      { url: "/icon.png?v=20260411a", type: "image/png", sizes: "48x48" },
    ],
    shortcut: "/favicon.ico?v=20260411a",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const app = <AuthProvider>{children}</AuthProvider>;

  return (
    <html lang="en" className="dark">
      <body>
        {clerkPublishableKey ? (
          <ClerkProvider publishableKey={clerkPublishableKey}>{app}</ClerkProvider>
        ) : (
          app
        )}
      </body>
    </html>
  );
}

import type { Metadata } from "next";
import "./globals.css";
import { ClerkProvider } from "@clerk/nextjs";
import { AuthProvider } from "@/lib/auth-context";
import { resolvedClerkPublishableKey } from "@/lib/clerk-publishable";

const clerkPublishableKey = resolvedClerkPublishableKey();

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
  const content = <AuthProvider>{children}</AuthProvider>;

  return (
    <html lang="en" className="dark">
      <body>
        {clerkPublishableKey ? (
          <ClerkProvider publishableKey={clerkPublishableKey}>
            {content}
          </ClerkProvider>
        ) : (
          content
        )}
      </body>
    </html>
  );
}

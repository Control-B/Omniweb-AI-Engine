import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import { headers } from "next/headers";
import "./globals.css";
import { MaybeAuth } from "@/components/maybe-auth";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-sans",
  display: "swap",
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
  display: "swap",
});

export const dynamic = "force-dynamic";

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
  const pathname = headers().get("x-omniweb-path") || "";

  return (
    <html lang="en" className={`dark ${inter.variable} ${jetbrainsMono.variable}`}>
      <body>
        <MaybeAuth pathname={pathname}>{children}</MaybeAuth>
      </body>
    </html>
  );
}

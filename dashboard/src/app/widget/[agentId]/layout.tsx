import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Voice Assistant",
  description: "AI Voice Assistant powered by Omniweb",
};

export default function WidgetLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}

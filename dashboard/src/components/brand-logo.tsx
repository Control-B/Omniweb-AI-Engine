import Link from "next/link";
import { cn } from "@/lib/utils";

type OmniwebLogoProps = {
  href?: string;
  className?: string;
  textClassName?: string;
};

export function OmniwebLogo({ href = "/", className, textClassName }: OmniwebLogoProps) {
  return (
    <Link href={href} className={cn("inline-flex items-center gap-3", className)}>
      <span className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl border border-cyan-400/20 bg-gradient-to-br from-cyan-500/20 to-purple-500/20 text-sm font-semibold text-cyan-200 shadow-[0_10px_30px_rgba(34,211,238,0.12)]" aria-hidden="true">
        O
      </span>
      <span className={cn("text-xl font-bold tracking-tight text-foreground", textClassName)}>omniweb</span>
    </Link>
  );
}
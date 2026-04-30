"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { cn } from "@/lib/utils";
import { isInternalRole, useAuth } from "@/lib/auth-context";
import { hasStashedAdminToken, restoreAdminToken } from "@/lib/api";
import type { ClientPageId } from "@/lib/client-dashboard";
import { CLIENT_PAGES } from "@/lib/client-dashboard";
import {
  LayoutDashboard,
  Phone,
  Users,
  Bot,
  Hash,
  PanelsTopLeft,
  Settings,
  Zap,
  ChevronLeft,
  Workflow,
  LogOut,
  ArrowLeft,
  ArrowRightLeft,
  Code,
  MessageSquareText,
  CreditCard,
} from "lucide-react";
import { useState, useEffect } from "react";

const NAV_ITEMS: { id: ClientPageId; label: string; icon: React.ElementType }[] = [
  { id: "dashboard", label: "Dashboard", icon: LayoutDashboard },
  { id: "calls", label: "Calls", icon: Phone },
  { id: "leads", label: "Leads", icon: Users },
  { id: "agent", label: "AI Agent", icon: Bot },
  { id: "telephony", label: "AI Telephony", icon: Phone },
  { id: "numbers", label: "Phone Numbers", icon: Hash },
  { id: "sites", label: "Websites", icon: PanelsTopLeft },
  { id: "automations", label: "Automations", icon: Workflow },
  { id: "settings", label: "Settings", icon: Settings },
];

const WIDGET_LINKS: { href: string; label: string; icon: React.ElementType }[] = [
  { href: "/dashboard/widget/configure", label: "Configure AI Widget", icon: Bot },
  { href: "/dashboard/widget/test", label: "Test Widget", icon: MessageSquareText },
  { href: "/dashboard/widget/embed", label: "Get Embed Code", icon: Code },
];

interface ClientSidebarProps {
  pathname: string;
}

export function ClientSidebar({ pathname }: ClientSidebarProps) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { user, logout } = useAuth();
  const [collapsed, setCollapsed] = useState(false);
  const [showBackToAdmin, setShowBackToAdmin] = useState(false);
  const initials = user?.email?.slice(0, 2).toUpperCase() || "??";

  const qp = searchParams.get("page");
  const activeTab: ClientPageId =
    qp && CLIENT_PAGES.includes(qp as ClientPageId) ? (qp as ClientPageId) : "dashboard";
  const onWidgetRoute = pathname.startsWith("/dashboard/widget");
  const canOpenAdminDashboard = isInternalRole(user?.role) || showBackToAdmin;

  useEffect(() => {
    setShowBackToAdmin(hasStashedAdminToken());
  }, []);

  function go(id: ClientPageId) {
    if (id === "dashboard") router.push("/dashboard");
    else router.push(`/dashboard?page=${encodeURIComponent(id)}`);
  }

  return (
    <aside
      className={cn(
        "flex flex-col bg-sidebar border-r border-border transition-all duration-200",
        collapsed ? "w-[68px]" : "w-[240px]"
      )}
    >
      <div className="flex items-center gap-3 px-4 h-16 border-b border-border">
        <div className="flex items-center justify-center w-9 h-9 rounded-lg bg-primary text-primary-foreground font-bold text-sm shrink-0">
          <Zap className="w-5 h-5" />
        </div>
        {!collapsed && (
          <div className="flex flex-col min-w-0">
            <span className="font-semibold text-sm text-foreground truncate">Omniweb AI</span>
            <span className="text-[11px] text-muted-foreground truncate">Agent Engine</span>
          </div>
        )}
      </div>

      {!collapsed && (
        <div className="px-3 py-3">
          <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-sidebar-accent">
            <div className="w-7 h-7 rounded-full bg-blue-500/20 flex items-center justify-center text-blue-400 text-xs font-bold shrink-0">
              {initials}
            </div>
            <div className="min-w-0">
              <div className="text-xs font-medium text-foreground truncate">
                {user?.email}
              </div>
              <div className="text-[10px] text-muted-foreground capitalize">
                {user?.plan} Plan
              </div>
              <div className="text-[10px] text-muted-foreground capitalize">{user?.plan} Plan</div>
            </div>
          </div>
        </div>
      )}

      <nav className="flex-1 px-2 py-1 space-y-0.5 overflow-y-auto">
        {NAV_ITEMS.map((item) => {
          const isActive = !onWidgetRoute && activeTab === item.id;
          return (
            <button
              key={item.id}
              type="button"
              onClick={() => go(item.id)}
              className={cn(
                "flex items-center gap-3 w-full px-3 py-2.5 rounded-lg text-sm font-medium transition-colors",
                isActive
                  ? "bg-primary/10 text-primary"
                  : "text-muted-foreground hover:text-foreground hover:bg-sidebar-accent"
              )}
            >
              <item.icon className={cn("w-[18px] h-[18px] shrink-0", isActive && "text-primary")} />
              {!collapsed && <span>{item.label}</span>}
            </button>
          );
        })}

        {!collapsed && (
          <div className="pt-3 pb-1 px-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
            Revenue widget
          </div>
        )}
        {WIDGET_LINKS.map((w) => {
          const isActive = pathname === w.href || pathname.startsWith(w.href + "/");
          const inner = (
            <>
              <w.icon className={cn("w-[18px] h-[18px] shrink-0", isActive && "text-primary")} />
              {!collapsed && <span>{w.label}</span>}
            </>
          );
          return collapsed ? (
            <Link
              key={w.href}
              href={w.href}
              className={cn(
                "flex items-center justify-center w-full px-3 py-2.5 rounded-lg text-sm font-medium transition-colors",
                isActive
                  ? "bg-primary/10 text-primary"
                  : "text-muted-foreground hover:text-foreground hover:bg-sidebar-accent"
              )}
              title={w.label}
            >
              <w.icon className={cn("w-[18px] h-[18px]", isActive && "text-primary")} />
            </Link>
          ) : (
            <Link
              key={w.href}
              href={w.href}
              className={cn(
                "flex items-center gap-3 w-full px-3 py-2.5 rounded-lg text-sm font-medium transition-colors",
                isActive
                  ? "bg-primary/10 text-primary"
                  : "text-muted-foreground hover:text-foreground hover:bg-sidebar-accent"
              )}
            >
              {inner}
            </Link>
          );
        })}

        <Link
          href="/dashboard/billing"
          className={cn(
            "flex items-center gap-3 w-full px-3 py-2.5 rounded-lg text-sm font-medium transition-colors",
            pathname === "/dashboard/billing"
              ? "bg-primary/10 text-primary"
              : "text-muted-foreground hover:text-foreground hover:bg-sidebar-accent"
          )}
        >
          <CreditCard
            className={cn("w-[18px] h-[18px] shrink-0", pathname === "/dashboard/billing" && "text-primary")}
          />
          {!collapsed && <span>Billing</span>}
        </Link>
      </nav>

      <div className="px-2 py-3 border-t border-border space-y-0.5">
        {canOpenAdminDashboard && (
          <button
            type="button"
            onClick={() => {
              if (showBackToAdmin) {
                restoreAdminToken();
              }
              window.location.href = "/admin/dashboard";
            }}
            className="flex items-center gap-3 w-full px-3 py-2 rounded-lg text-sm text-primary hover:text-primary hover:bg-primary/10 transition-colors font-medium"
          >
            {showBackToAdmin ? (
              <ArrowLeft className="w-[18px] h-[18px]" />
            ) : (
              <ArrowRightLeft className="w-[18px] h-[18px]" />
            )}
            {!collapsed && <span>{showBackToAdmin ? "Back to Admin" : "Open Admin Dashboard"}</span>}
          </button>
        )}
        <button
          type="button"
          onClick={logout}
          className="flex items-center gap-3 w-full px-3 py-2 rounded-lg text-sm text-muted-foreground hover:text-foreground hover:bg-sidebar-accent transition-colors"
        >
          <LogOut className="w-[18px] h-[18px]" />
          {!collapsed && <span>Sign Out</span>}
        </button>
        <button
          type="button"
          onClick={() => setCollapsed(!collapsed)}
          className="flex items-center gap-3 w-full px-3 py-2 rounded-lg text-sm text-muted-foreground hover:text-foreground hover:bg-sidebar-accent transition-colors"
        >
          <ChevronLeft className={cn("w-[18px] h-[18px] transition-transform", collapsed && "rotate-180")} />
          {!collapsed && <span>Collapse</span>}
        </button>
        {!collapsed && (
          <div className="flex items-center gap-2 px-3 pt-1">
            <a
              href="https://omniweb.ai/terms"
              target="_blank"
              rel="noopener noreferrer"
              className="text-[10px] text-muted-foreground/60 hover:text-muted-foreground transition-colors"
            >
              Terms
            </a>
            <span className="text-[10px] text-muted-foreground/30">·</span>
            <a
              href="https://omniweb.ai/privacy"
              target="_blank"
              rel="noopener noreferrer"
              className="text-[10px] text-muted-foreground/60 hover:text-muted-foreground transition-colors"
            >
              Privacy
            </a>
          </div>
        )}
      </div>
    </aside>
  );
}

"use client";

import { cn } from "@/lib/utils";
import { useAuth } from "@/lib/auth-context";
import { hasStashedAdminToken, restoreAdminToken } from "@/lib/api";
import type { ClientPageId } from "@/app/dashboard/page";
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
} from "lucide-react";
import { useState, useEffect } from "react";

const NAV_ITEMS: { id: ClientPageId; label: string; icon: React.ElementType }[] = [
  { id: "dashboard", label: "Dashboard", icon: LayoutDashboard },
  { id: "calls", label: "Calls", icon: Phone },
  { id: "leads", label: "Leads", icon: Users },
  { id: "agent", label: "AI Agent", icon: Bot },
  { id: "numbers", label: "Phone Numbers", icon: Hash },
  { id: "sites", label: "Websites", icon: PanelsTopLeft },
  { id: "automations", label: "Automations", icon: Workflow },
  { id: "settings", label: "Settings", icon: Settings },
];

interface ClientSidebarProps {
  activePage: ClientPageId;
  onNavigate: (page: ClientPageId) => void;
}

export function ClientSidebar({ activePage, onNavigate }: ClientSidebarProps) {
  const { user, logout } = useAuth();
  const [collapsed, setCollapsed] = useState(false);
  const [showBackToAdmin, setShowBackToAdmin] = useState(false);
  const initials = user?.email?.slice(0, 2).toUpperCase() || "??";

  useEffect(() => {
    setShowBackToAdmin(hasStashedAdminToken());
  }, []);

  return (
    <aside
      className={cn(
        "flex flex-col bg-sidebar border-r border-border transition-all duration-200",
        collapsed ? "w-[68px]" : "w-[240px]"
      )}
    >
      {/* Logo */}
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

      {/* User info */}
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
            </div>
          </div>
        </div>
      )}

      {/* Navigation */}
      <nav className="flex-1 px-2 py-1 space-y-0.5">
        {NAV_ITEMS.map((item) => {
          const isActive = activePage === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onNavigate(item.id)}
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
      </nav>

      {/* Bottom */}
      <div className="px-2 py-3 border-t border-border space-y-0.5">
        {showBackToAdmin && (
          <button
            onClick={() => {
              restoreAdminToken();
              window.location.href = "/admin";
            }}
            className="flex items-center gap-3 w-full px-3 py-2 rounded-lg text-sm text-primary hover:text-primary hover:bg-primary/10 transition-colors font-medium"
          >
            <ArrowLeft className="w-[18px] h-[18px]" />
            {!collapsed && <span>Back to Admin</span>}
          </button>
        )}
        <button
          onClick={logout}
          className="flex items-center gap-3 w-full px-3 py-2 rounded-lg text-sm text-muted-foreground hover:text-foreground hover:bg-sidebar-accent transition-colors"
        >
          <LogOut className="w-[18px] h-[18px]" />
          {!collapsed && <span>Sign Out</span>}
        </button>
        <button
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

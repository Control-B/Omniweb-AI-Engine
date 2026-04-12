"use client";

import { cn } from "@/lib/utils";
import { useAuth } from "@/lib/auth-context";
import type { AdminPageId } from "@/app/admin/page";
import {
  BarChart3,
  Users,
  FileText,
  ChevronLeft,
  Zap,
  LogOut,
  Shield,
  Bot,
  MessageSquare,
  ExternalLink,
} from "lucide-react";
import { useState } from "react";

const NAV_ITEMS: { id: AdminPageId; label: string; icon: React.ElementType }[] = [
  { id: "overview", label: "Overview", icon: BarChart3 },
  { id: "agents", label: "Agents", icon: Bot },
  { id: "sessions", label: "Sessions", icon: MessageSquare },
  { id: "clients", label: "Clients", icon: Users },
  { id: "templates", label: "Templates", icon: FileText },
];

interface AdminSidebarProps {
  activePage: AdminPageId;
  onNavigate: (page: AdminPageId) => void;
}

export function AdminSidebar({ activePage, onNavigate }: AdminSidebarProps) {
  const { user, logout } = useAuth();
  const [collapsed, setCollapsed] = useState(false);

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
            <span className="text-[11px] text-muted-foreground truncate">Admin Panel</span>
          </div>
        )}
      </div>

      {/* Admin badge */}
      {!collapsed && (
        <div className="px-3 py-3">
          <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-primary/10 border border-primary/20">
            <Shield className="w-4 h-4 text-primary shrink-0" />
            <div className="min-w-0">
              <div className="text-xs font-medium text-foreground truncate">
                {user?.email}
              </div>
              <div className="text-[10px] text-primary font-medium">
                Administrator
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Navigation */}
      <nav className="flex-1 px-2 py-1 space-y-0.5">
        {NAV_ITEMS.map((item) => {
          const isActive =
            activePage === item.id ||
            (item.id === "clients" && activePage === "client-detail");
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
        <a
          href="/demo"
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-3 w-full px-3 py-2 rounded-lg text-sm text-muted-foreground hover:text-foreground hover:bg-sidebar-accent transition-colors"
        >
          <ExternalLink className="w-[18px] h-[18px]" />
          {!collapsed && <span>Demo Dashboard</span>}
        </a>
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
      </div>
    </aside>
  );
}

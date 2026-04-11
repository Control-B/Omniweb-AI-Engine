"use client";

import { useEffect, useState, useCallback } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { adminGetClients, adminImpersonate, setToken } from "@/lib/api";
import {
  Search,
  Loader2,
  AlertCircle,
  Eye,
  LogIn,
  ChevronLeft,
  ChevronRight,
  Users,
} from "lucide-react";

interface Client {
  id: string;
  name: string;
  email: string;
  business_name: string | null;
  business_type: string | null;
  plan: string;
  role: string;
  is_active: boolean;
  created_at: string;
}

interface AdminClientsProps {
  onViewClient: (clientId: string) => void;
}

const PAGE_SIZE = 20;

const planBadge: Record<string, "default" | "success" | "warning" | "secondary"> = {
  starter: "secondary",
  growth: "default",
  pro: "success",
  agency: "warning",
};

export function AdminClients({ onViewClient }: AdminClientsProps) {
  const [clients, setClients] = useState<Client[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [planFilter, setPlanFilter] = useState("");
  const [page, setPage] = useState(0);
  const [total, setTotal] = useState(0);

  const fetchClients = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const res = await adminGetClients({
        search: search || undefined,
        plan: planFilter || undefined,
        limit: PAGE_SIZE,
        offset: page * PAGE_SIZE,
      });
      setClients(res.clients || res);
      setTotal(res.total ?? (res.clients?.length || res.length || 0));
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [search, planFilter, page]);

  useEffect(() => {
    fetchClients();
  }, [fetchClients]);

  // debounce search
  const [searchInput, setSearchInput] = useState("");
  useEffect(() => {
    const t = setTimeout(() => {
      setSearch(searchInput);
      setPage(0);
    }, 400);
    return () => clearTimeout(t);
  }, [searchInput]);

  async function handleImpersonate(client: Client) {
    if (!confirm(`Impersonate ${client.email}? You'll be logged in as this client.`)) return;
    try {
      const data = await adminImpersonate(client.id);
      setToken(data.access_token);
      window.location.href = "/dashboard";
    } catch (e: any) {
      alert("Failed to impersonate: " + e.message);
    }
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-foreground">Clients</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Manage all tenant accounts
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Users className="w-4 h-4 text-muted-foreground" />
          <span className="text-sm text-muted-foreground">{total} total</span>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <Input
            placeholder="Search by name or email..."
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            className="pl-9"
          />
        </div>
        <select
          value={planFilter}
          onChange={(e) => { setPlanFilter(e.target.value); setPage(0); }}
          className="h-10 px-3 rounded-lg border border-border bg-card text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary/30"
        >
          <option value="">All Plans</option>
          <option value="starter">Starter</option>
          <option value="growth">Growth</option>
          <option value="pro">Pro</option>
          <option value="agency">Agency</option>
        </select>
      </div>

      {/* Error */}
      {error && (
        <div className="flex items-center gap-2 text-red-400 text-sm">
          <AlertCircle className="w-4 h-4" />
          {error}
        </div>
      )}

      {/* Table */}
      {loading ? (
        <div className="flex justify-center py-20">
          <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
        </div>
      ) : clients.length === 0 ? (
        <div className="text-center py-20 text-muted-foreground text-sm">
          No clients found.
        </div>
      ) : (
        <Card>
          <CardContent className="p-0">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border">
                    <th className="text-left px-4 py-3 text-xs font-medium text-muted-foreground uppercase tracking-wider">
                      Client
                    </th>
                    <th className="text-left px-4 py-3 text-xs font-medium text-muted-foreground uppercase tracking-wider">
                      Business
                    </th>
                    <th className="text-left px-4 py-3 text-xs font-medium text-muted-foreground uppercase tracking-wider">
                      Plan
                    </th>
                    <th className="text-left px-4 py-3 text-xs font-medium text-muted-foreground uppercase tracking-wider">
                      Role
                    </th>
                    <th className="text-left px-4 py-3 text-xs font-medium text-muted-foreground uppercase tracking-wider">
                      Status
                    </th>
                    <th className="text-left px-4 py-3 text-xs font-medium text-muted-foreground uppercase tracking-wider">
                      Joined
                    </th>
                    <th className="text-right px-4 py-3 text-xs font-medium text-muted-foreground uppercase tracking-wider">
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {clients.map((c) => (
                    <tr
                      key={c.id}
                      className="hover:bg-sidebar-accent/50 transition-colors"
                    >
                      <td className="px-4 py-3">
                        <div>
                          <div className="font-medium text-foreground">{c.name}</div>
                          <div className="text-xs text-muted-foreground">{c.email}</div>
                        </div>
                      </td>
                      <td className="px-4 py-3 text-muted-foreground">
                        {c.business_name || "—"}
                      </td>
                      <td className="px-4 py-3">
                        <Badge variant={planBadge[c.plan] || "secondary"}>{c.plan}</Badge>
                      </td>
                      <td className="px-4 py-3">
                        <Badge variant={c.role === "admin" ? "warning" : "outline"}>
                          {c.role}
                        </Badge>
                      </td>
                      <td className="px-4 py-3">
                        <Badge variant={c.is_active ? "success" : "destructive"}>
                          {c.is_active ? "Active" : "Inactive"}
                        </Badge>
                      </td>
                      <td className="px-4 py-3 text-muted-foreground text-xs">
                        {new Date(c.created_at).toLocaleDateString()}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center justify-end gap-1">
                          <button
                            onClick={() => onViewClient(c.id)}
                            className="p-2 rounded-lg text-muted-foreground hover:text-foreground hover:bg-sidebar-accent transition-colors"
                            title="View details"
                          >
                            <Eye className="w-4 h-4" />
                          </button>
                          {c.role !== "admin" && (
                            <button
                              onClick={() => handleImpersonate(c)}
                              className="p-2 rounded-lg text-muted-foreground hover:text-primary hover:bg-primary/10 transition-colors"
                              title="Impersonate"
                            >
                              <LogIn className="w-4 h-4" />
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Pagination */}
      {total > PAGE_SIZE && (
        <div className="flex items-center justify-between">
          <p className="text-xs text-muted-foreground">
            Showing {page * PAGE_SIZE + 1}–{Math.min((page + 1) * PAGE_SIZE, total)} of {total}
          </p>
          <div className="flex items-center gap-1">
            <button
              disabled={page === 0}
              onClick={() => setPage((p) => p - 1)}
              className="p-2 rounded-lg text-muted-foreground hover:text-foreground hover:bg-sidebar-accent disabled:opacity-30 disabled:pointer-events-none transition-colors"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <button
              disabled={(page + 1) * PAGE_SIZE >= total}
              onClick={() => setPage((p) => p + 1)}
              className="p-2 rounded-lg text-muted-foreground hover:text-foreground hover:bg-sidebar-accent disabled:opacity-30 disabled:pointer-events-none transition-colors"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

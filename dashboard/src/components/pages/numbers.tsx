"use client";

import { useEffect, useState, useCallback } from "react";
import {
  Phone, Plus, Trash2, Search, ExternalLink, Loader2,
  AlertCircle, CheckCircle2, MapPin, X, Link2, PhoneForwarded, Bot,
} from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input, Label } from "@/components/ui/input";
import { cn, formatPhone } from "@/lib/utils";
import {
  getNumbers, searchAvailableNumbers, buyNumber,
  deleteNumber, assignNumberToAgent, setNumberMode,
} from "@/lib/api";

/* ── Types ──────────────────────────────────────────────────────────────── */

interface PhoneNumberRecord {
  id: string;
  phone_number: string;
  friendly_name: string;
  is_active: boolean;
  twilio_sid?: string;
  area_code?: string;
  country?: string;
  mode?: string;       // "ai" | "forward"
  forward_to?: string; // E.164 number when mode="forward"
}

interface AvailableNumber {
  phone_number: string;
  friendly_name: string;
  location: string;
  capabilities?: { voice?: boolean; sms?: boolean };
  monthly_rate: number;
}

/* ── Component ──────────────────────────────────────────────────────────── */

export function NumbersPage() {
  const [numbers, setNumbers] = useState<PhoneNumberRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Search / Buy state
  const [showSearch, setShowSearch] = useState(false);
  const [areaCode, setAreaCode] = useState("");
  const [numberType, setNumberType] = useState<"local" | "toll_free">("local");
  const [searchResults, setSearchResults] = useState<AvailableNumber[]>([]);
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);

  // Buy state
  const [buyingNumber, setBuyingNumber] = useState<string | null>(null);
  const [friendlyName, setFriendlyName] = useState("");
  const [buyTarget, setBuyTarget] = useState<AvailableNumber | null>(null);

  // Action states
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null);

  // Mode-switching state
  const [modeEditing, setModeEditing] = useState<string | null>(null); // number id
  const [forwardInput, setForwardInput] = useState("");

  const loadNumbers = useCallback(async () => {
    try {
      setLoading(true);
      const res = await getNumbers();
      setNumbers(res.numbers || res || []);
      setError(null);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadNumbers(); }, [loadNumbers]);

  /* ── Search available numbers ──────────────────────────────────────── */

  async function handleSearch() {
    setSearching(true);
    setSearchError(null);
    setSearchResults([]);
    try {
      const res = await searchAvailableNumbers(areaCode || undefined, "US", 20, numberType);
      setSearchResults(res.numbers || []);
      if ((res.numbers || []).length === 0) {
        setSearchError("No numbers found. Try a different area code.");
      }
    } catch (e: any) {
      setSearchError(e.message);
    } finally {
      setSearching(false);
    }
  }

  /* ── Buy a number ──────────────────────────────────────────────────── */

  async function handleBuy() {
    if (!buyTarget) return;
    setBuyingNumber(buyTarget.phone_number);
    try {
      await buyNumber(buyTarget.phone_number, friendlyName || buyTarget.friendly_name || "AI Line");
      setSearchResults((prev) => prev.filter((n) => n.phone_number !== buyTarget.phone_number));
      setBuyTarget(null);
      setFriendlyName("");
      await loadNumbers();
    } catch (e: any) {
      setSearchError(`Failed to buy: ${e.message}`);
    } finally {
      setBuyingNumber(null);
    }
  }

  /* ── Delete a number ───────────────────────────────────────────────── */

  async function handleDelete(num: PhoneNumberRecord) {
    setActionLoading(num.id);
    setActionError(null);
    try {
      await deleteNumber(num.id, true);
      setNumbers((prev) => prev.filter((n) => n.id !== num.id));
      setDeleteConfirm(null);
    } catch (e: any) {
      setActionError(`Delete failed: ${e.message}`);
    } finally {
      setActionLoading(null);
    }
  }

  /* ── Assign to agent ───────────────────────────────────────────────── */

  async function handleAssign(num: PhoneNumberRecord) {
    setActionLoading(num.id);
    setActionError(null);
    try {
      await assignNumberToAgent(num.id);
      await loadNumbers();
    } catch (e: any) {
      setActionError(`Assign failed: ${e.message}`);
    } finally {
      setActionLoading(null);
    }
  }

  /* ── Switch mode (AI ↔ Forward) ────────────────────────────────────── */

  async function handleSetMode(num: PhoneNumberRecord, mode: "ai" | "forward") {
    if (mode === "forward" && !forwardInput.trim()) {
      setActionError("Enter a phone number to forward calls to.");
      return;
    }
    setActionLoading(num.id);
    setActionError(null);
    try {
      await setNumberMode(
        num.id,
        mode,
        mode === "forward" ? forwardInput.trim() : undefined,
      );
      setModeEditing(null);
      setForwardInput("");
      await loadNumbers();
    } catch (e: any) {
      setActionError(`Mode switch failed: ${e.message}`);
    } finally {
      setActionLoading(null);
    }
  }

  /* ── Render ─────────────────────────────────────────────────────────── */

  return (
    <div className="p-6 space-y-5 max-w-[960px]">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-foreground">Phone Numbers</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            Search, buy, and manage numbers for your AI agent
          </p>
        </div>
        <Button
          onClick={() => { setShowSearch(!showSearch); setSearchResults([]); setSearchError(null); setBuyTarget(null); }}
          className={cn(showSearch && "bg-primary/20 text-primary border-primary/30")}
          variant={showSearch ? "outline" : "default"}
          size="sm"
        >
          {showSearch ? <X className="w-4 h-4 mr-1.5" /> : <Plus className="w-4 h-4 mr-1.5" />}
          {showSearch ? "Close" : "Get a Number"}
        </Button>
      </div>

      {/* Action error toast */}
      {actionError && (
        <div className="flex items-center gap-2 p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span className="flex-1">{actionError}</span>
          <button onClick={() => setActionError(null)} className="text-red-300 hover:text-red-200">
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      {/* ── Search Panel ──────────────────────────────────────────── */}
      {showSearch && (
        <Card className="border-primary/20 bg-primary/[0.02]">
          <CardContent className="p-5 space-y-4">
            <div>
              <h3 className="text-sm font-semibold text-foreground">Search Available Numbers</h3>
              <p className="text-xs text-muted-foreground mt-0.5">
                Find a phone number from our inventory.
              </p>
            </div>

            {/* Number type toggle */}
            <div className="flex gap-1 p-0.5 bg-accent/50 rounded-lg w-fit">
              <button
                onClick={() => setNumberType("local")}
                className={cn(
                  "px-3 py-1.5 text-xs font-medium rounded-md transition-colors",
                  numberType === "local"
                    ? "bg-primary text-primary-foreground shadow-sm"
                    : "text-muted-foreground hover:text-foreground"
                )}
              >
                Local
              </button>
              <button
                onClick={() => setNumberType("toll_free")}
                className={cn(
                  "px-3 py-1.5 text-xs font-medium rounded-md transition-colors",
                  numberType === "toll_free"
                    ? "bg-primary text-primary-foreground shadow-sm"
                    : "text-muted-foreground hover:text-foreground"
                )}
              >
                Toll-Free
              </button>
            </div>

            <div className="flex gap-2">
              <div className="flex-1">
                <Input
                  placeholder={numberType === "toll_free" ? "Area code (e.g. 800, 888, 877)..." : "Area code (e.g. 212, 415, 305)..."}
                  value={areaCode}
                  onChange={(e) => setAreaCode(e.target.value.replace(/\D/g, "").slice(0, 3))}
                  className="font-mono"
                />
              </div>
              <Button onClick={handleSearch} disabled={searching} size="md">
                {searching ? <Loader2 className="w-4 h-4 animate-spin mr-1.5" /> : <Search className="w-4 h-4 mr-1.5" />}
                Search
              </Button>
            </div>

            {searchError && (
              <p className="text-xs text-red-400 flex items-center gap-1">
                <AlertCircle className="w-3.5 h-3.5" /> {searchError}
              </p>
            )}

            {/* Search results */}
            {searchResults.length > 0 && (
              <div className="space-y-2 max-h-[320px] overflow-y-auto pr-1">
                <p className="text-xs text-muted-foreground">{searchResults.length} numbers found</p>
                {searchResults.map((num) => (
                  <div
                    key={num.phone_number}
                    className={cn(
                      "flex items-center gap-3 p-3 rounded-lg border transition-colors",
                      buyTarget?.phone_number === num.phone_number
                        ? "border-primary/40 bg-primary/5"
                        : "border-border hover:border-border/80 hover:bg-accent/30"
                    )}
                  >
                    <div className="flex items-center justify-center w-9 h-9 rounded-lg bg-primary/10">
                      <Phone className="w-4 h-4 text-primary" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-semibold text-foreground font-mono">
                        {formatPhone(num.phone_number)}
                      </p>
                      {num.location && (
                        <p className="text-[11px] text-muted-foreground flex items-center gap-1 mt-0.5">
                          <MapPin className="w-3 h-3" /> {num.location}
                        </p>
                      )}
                    </div>
                    <div className="flex items-center gap-2">
                      {num.capabilities?.voice && (
                        <Badge variant="secondary" className="text-[9px]">Voice</Badge>
                      )}
                      {num.capabilities?.sms && (
                        <Badge variant="secondary" className="text-[9px]">SMS</Badge>
                      )}
                      {num.monthly_rate > 0 && (
                        <span className="text-xs text-muted-foreground">${num.monthly_rate}/mo</span>
                      )}
                      <Button
                        size="sm"
                        variant={buyTarget?.phone_number === num.phone_number ? "default" : "outline"}
                        onClick={() => {
                          setBuyTarget(buyTarget?.phone_number === num.phone_number ? null : num);
                          setFriendlyName("");
                        }}
                        disabled={buyingNumber === num.phone_number}
                      >
                        {buyingNumber === num.phone_number ? (
                          <Loader2 className="w-3.5 h-3.5 animate-spin" />
                        ) : buyTarget?.phone_number === num.phone_number ? (
                          "Selected"
                        ) : (
                          "Select"
                        )}
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Buy confirmation */}
            {buyTarget && (
              <div className="p-4 rounded-lg bg-card border border-border space-y-3">
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 text-primary" />
                  <span className="text-sm font-medium text-foreground">
                    Buy {formatPhone(buyTarget.phone_number)}
                  </span>
                </div>
                <div className="space-y-1.5">
                  <Label className="text-xs">Friendly Name</Label>
                  <Input
                    placeholder="e.g. Main Office, After Hours Line..."
                    value={friendlyName}
                    onChange={(e) => setFriendlyName(e.target.value)}
                  />
                </div>
                <div className="flex items-center gap-2">
                  <Button onClick={handleBuy} disabled={!!buyingNumber} size="sm">
                    {buyingNumber ? (
                      <><Loader2 className="w-3.5 h-3.5 animate-spin mr-1.5" /> Purchasing...</>
                    ) : (
                      <><Plus className="w-3.5 h-3.5 mr-1.5" /> Buy &amp; Connect to Agent</>
                    )}
                  </Button>
                  <Button variant="ghost" size="sm" onClick={() => setBuyTarget(null)}>
                    Cancel
                  </Button>
                </div>
                <p className="text-[10px] text-muted-foreground">
                  This will purchase the number (~$1.15/mo) and automatically connect it to your AI agent.
                </p>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* ── My Numbers ────────────────────────────────────────────── */}
      {loading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
        </div>
      ) : error ? (
        <div className="flex flex-col items-center py-12 gap-2">
          <AlertCircle className="w-6 h-6 text-red-400" />
          <p className="text-sm text-muted-foreground">{error}</p>
          <Button variant="ghost" size="sm" onClick={loadNumbers}>Retry</Button>
        </div>
      ) : numbers.length === 0 && !showSearch ? (
        <Card>
          <CardContent className="p-10 text-center">
            <Phone className="w-10 h-10 text-muted-foreground/30 mx-auto mb-4" />
            <p className="text-sm font-medium text-foreground">No phone numbers yet</p>
            <p className="text-xs text-muted-foreground mt-1 max-w-xs mx-auto">
              Get a phone number to let your AI agent answer calls. Click &quot;Get a Number&quot; above to search and buy.
            </p>
            <Button className="mt-4" size="sm" onClick={() => setShowSearch(true)}>
              <Plus className="w-4 h-4 mr-1.5" /> Get Your First Number
            </Button>
          </CardContent>
        </Card>
      ) : numbers.length > 0 ? (
        <div className="space-y-3">
          <h2 className="text-sm font-semibold text-foreground">
            My Numbers <span className="text-muted-foreground font-normal">({numbers.length})</span>
          </h2>
          {numbers.map((num) => (
            <Card key={num.id}>
              <CardContent className="p-5">
                <div className="flex items-center gap-4">
                  <div className={cn(
                    "flex items-center justify-center w-11 h-11 rounded-xl",
                    num.mode === "forward" ? "bg-amber-500/10" : "bg-primary/10",
                  )}>
                    {num.mode === "forward"
                      ? <PhoneForwarded className="w-5 h-5 text-amber-500" />
                      : <Bot className="w-5 h-5 text-primary" />
                    }
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <p className="text-base font-semibold text-foreground font-mono">
                        {formatPhone(num.phone_number)}
                      </p>
                      <Badge variant={num.is_active ? "success" : "secondary"}>
                        {num.is_active ? "active" : "inactive"}
                      </Badge>
                      {num.mode === "forward" ? (
                        <Badge variant="secondary" className="text-[9px] bg-amber-500/10 text-amber-500 border-amber-500/20">
                          <PhoneForwarded className="w-2.5 h-2.5 mr-0.5" /> Forwarding
                        </Badge>
                      ) : (
                        <Badge variant="default" className="text-[9px]">
                          <Bot className="w-2.5 h-2.5 mr-0.5" /> AI (Retell)
                        </Badge>
                      )}
                    </div>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      {num.friendly_name}
                      {num.mode === "forward" && num.forward_to && (
                        <span className="ml-1 text-amber-500">&rarr; {formatPhone(num.forward_to)}</span>
                      )}
                    </p>
                  </div>

                  <div className="flex items-center gap-2">
                    {/* Mode toggle button */}
                    {num.is_active && modeEditing !== num.id && (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => {
                          setModeEditing(num.id);
                          setForwardInput(num.forward_to || "");
                        }}
                        disabled={actionLoading === num.id}
                        className="text-xs"
                      >
                        {num.mode === "forward"
                          ? <><Bot className="w-3.5 h-3.5 mr-1" /> Switch to AI</>
                          : <><PhoneForwarded className="w-3.5 h-3.5 mr-1" /> Forward Calls</>
                        }
                      </Button>
                    )}

                    {/* Assign to agent (AI mode, not yet connected) */}
                    {num.is_active && num.mode !== "forward" && modeEditing !== num.id && (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleAssign(num)}
                        disabled={actionLoading === num.id}
                      >
                        {actionLoading === num.id ? (
                          <Loader2 className="w-3.5 h-3.5 animate-spin" />
                        ) : (
                          <><Link2 className="w-3.5 h-3.5 mr-1" /> Connect</>
                        )}
                      </Button>
                    )}

                    {/* Delete */}
                    {deleteConfirm === num.id ? (
                      <div className="flex items-center gap-1">
                        <Button
                          variant="destructive"
                          size="sm"
                          onClick={() => handleDelete(num)}
                          disabled={actionLoading === num.id}
                        >
                          {actionLoading === num.id ? (
                            <Loader2 className="w-3.5 h-3.5 animate-spin" />
                          ) : (
                            "Confirm"
                          )}
                        </Button>
                        <Button variant="ghost" size="sm" onClick={() => setDeleteConfirm(null)}>
                          Cancel
                        </Button>
                      </div>
                    ) : modeEditing !== num.id ? (
                      <Button
                        variant="ghost"
                        size="sm"
                        className="text-muted-foreground hover:text-red-400"
                        onClick={() => setDeleteConfirm(num.id)}
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </Button>
                    ) : null}
                  </div>
                </div>

                {/* Mode editing panel */}
                {modeEditing === num.id && (
                  <div className="mt-4 p-4 rounded-lg bg-accent/30 border border-border space-y-3">
                    {num.mode === "forward" ? (
                      <>
                        <p className="text-sm text-foreground">
                          Switch back to <strong>AI Agent</strong> mode? The AI agent will answer all calls on this number.
                        </p>
                        <div className="flex items-center gap-2">
                          <Button
                            size="sm"
                            onClick={() => handleSetMode(num, "ai")}
                            disabled={actionLoading === num.id}
                          >
                            {actionLoading === num.id
                              ? <><Loader2 className="w-3.5 h-3.5 animate-spin mr-1.5" /> Switching...</>
                              : <><Bot className="w-3.5 h-3.5 mr-1.5" /> Enable AI Agent</>
                            }
                          </Button>
                          <Button variant="ghost" size="sm" onClick={() => setModeEditing(null)}>
                            Cancel
                          </Button>
                        </div>
                      </>
                    ) : (
                      <>
                        <p className="text-sm text-foreground">
                          Forward calls to a real phone number. The AI agent will be disconnected.
                        </p>
                        <div className="space-y-1.5">
                          <Label className="text-xs">Forward calls to</Label>
                          <Input
                            placeholder="+15551234567"
                            value={forwardInput}
                            onChange={(e) => setForwardInput(e.target.value)}
                            className="font-mono max-w-xs"
                          />
                        </div>
                        <div className="flex items-center gap-2">
                          <Button
                            size="sm"
                            onClick={() => handleSetMode(num, "forward")}
                            disabled={actionLoading === num.id || !forwardInput.trim()}
                          >
                            {actionLoading === num.id
                              ? <><Loader2 className="w-3.5 h-3.5 animate-spin mr-1.5" /> Setting up...</>
                              : <><PhoneForwarded className="w-3.5 h-3.5 mr-1.5" /> Enable Forwarding</>
                            }
                          </Button>
                          <Button variant="ghost" size="sm" onClick={() => setModeEditing(null)}>
                            Cancel
                          </Button>
                        </div>
                        <p className="text-[10px] text-muted-foreground">
                          Enter the phone number you want calls forwarded to (e.g. your cell or office phone). Use format: +15551234567
                        </p>
                      </>
                    )}
                  </div>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      ) : null}

      {/* BYOC Card */}
      <Card className="border-dashed">
        <CardContent className="p-5">
          <div className="flex items-center gap-4">
            <div className="flex items-center justify-center w-11 h-11 rounded-xl bg-accent">
              <ExternalLink className="w-5 h-5 text-muted-foreground" />
            </div>
            <div className="flex-1">
              <p className="text-sm font-semibold text-foreground">
                Bring Your Own Number (BYOC)
              </p>
              <p className="text-xs text-muted-foreground mt-0.5">
                Already have a number with another carrier? Contact us to forward it to your AI agent.
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

"use client";

import { useState } from "react";
import { Phone, Plus, Trash2, Check, ExternalLink, Wifi } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input, Label } from "@/components/ui/input";
import { cn, formatPhone } from "@/lib/utils";
import { MOCK_NUMBERS, type PhoneNumberRecord } from "@/lib/mock-data";

const AVAILABLE_NUMBERS = [
  "+12125559101",
  "+12125559102",
  "+17185559201",
  "+19175559301",
  "+13475559401",
];

export function NumbersPage() {
  const [numbers, setNumbers] = useState(MOCK_NUMBERS);
  const [showBuy, setShowBuy] = useState(false);
  const [selectedAvailable, setSelectedAvailable] = useState<string | null>(null);
  const [friendlyName, setFriendlyName] = useState("");

  return (
    <div className="p-6 space-y-4 max-w-[900px]">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-foreground">Phone Numbers</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            Manage numbers connected to your AI agent
          </p>
        </div>
        <Button size="sm" onClick={() => setShowBuy(!showBuy)}>
          <Plus className="w-3.5 h-3.5" />
          Add Number
        </Button>
      </div>

      {/* Buy Number Panel */}
      {showBuy && (
        <Card className="border-primary/30">
          <CardHeader>
            <CardTitle>Get a New Number</CardTitle>
            <CardDescription>
              Purchase a phone number directly through LiveKit — $1/mo per number
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label>Available Numbers</Label>
              <div className="grid grid-cols-2 gap-2">
                {AVAILABLE_NUMBERS.map((num) => (
                  <button
                    key={num}
                    onClick={() => setSelectedAvailable(num)}
                    className={cn(
                      "flex items-center gap-2 p-3 rounded-lg border transition-colors text-left",
                      selectedAvailable === num
                        ? "border-primary bg-primary/5"
                        : "border-border hover:border-primary/30"
                    )}
                  >
                    <Phone className="w-4 h-4 text-muted-foreground" />
                    <span className="text-sm font-mono font-medium">{formatPhone(num)}</span>
                    {selectedAvailable === num && (
                      <Check className="w-4 h-4 text-primary ml-auto" />
                    )}
                  </button>
                ))}
              </div>
            </div>
            {selectedAvailable && (
              <div className="space-y-3">
                <div className="space-y-1.5">
                  <Label>Friendly Name</Label>
                  <Input
                    value={friendlyName}
                    onChange={(e) => setFriendlyName(e.target.value)}
                    placeholder="e.g. Main Office Line"
                  />
                </div>
                <div className="flex gap-2">
                  <Button size="sm" onClick={() => {
                    setNumbers([
                      ...numbers,
                      {
                        id: `n${Date.now()}`,
                        phone_number: selectedAvailable,
                        friendly_name: friendlyName || "New Number",
                        is_active: true,
                        livekit_sip_trunk_id: `ST_${Date.now()}`,
                        monthly_rate: 1.0,
                        total_calls: 0,
                      },
                    ]);
                    setShowBuy(false);
                    setSelectedAvailable(null);
                    setFriendlyName("");
                  }}>
                    <Check className="w-3.5 h-3.5" />
                    Purchase & Activate
                  </Button>
                  <Button size="sm" variant="outline" onClick={() => setShowBuy(false)}>
                    Cancel
                  </Button>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Active Numbers */}
      <div className="space-y-3">
        {numbers.map((num) => (
          <Card key={num.id}>
            <CardContent className="p-5">
              <div className="flex items-center gap-4">
                <div className="flex items-center justify-center w-11 h-11 rounded-xl bg-primary/10">
                  <Phone className="w-5 h-5 text-primary" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <p className="text-base font-semibold text-foreground font-mono">
                      {formatPhone(num.phone_number)}
                    </p>
                    <Badge variant={num.is_active ? "success" : "secondary"}>
                      {num.is_active ? "active" : "inactive"}
                    </Badge>
                  </div>
                  <p className="text-xs text-muted-foreground mt-0.5">{num.friendly_name}</p>
                </div>
                <div className="hidden md:flex items-center gap-6 text-center">
                  <div>
                    <p className="text-sm font-bold text-foreground">{num.total_calls}</p>
                    <p className="text-[10px] text-muted-foreground">Total Calls</p>
                  </div>
                  <div>
                    <p className="text-sm font-bold text-foreground">${num.monthly_rate}/mo</p>
                    <p className="text-[10px] text-muted-foreground">Cost</p>
                  </div>
                </div>
                <div className="flex items-center gap-1.5">
                  <div className="flex items-center gap-1 text-[11px] text-emerald-400">
                    <Wifi className="w-3 h-3" />
                    SIP
                  </div>
                  <Button variant="ghost" size="icon" className="text-muted-foreground hover:text-destructive">
                    <Trash2 className="w-4 h-4" />
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

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
                Already have a number with another carrier? Forward it to LiveKit&apos;s SIP trunk to use with your AI agent.
              </p>
            </div>
            <Button variant="outline" size="sm">
              Set Up BYOC
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

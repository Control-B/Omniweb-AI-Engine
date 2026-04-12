"use client";

import { useEffect, useState } from "react";
import { Phone, Plus, Trash2, Check, ExternalLink, Wifi, Loader2, AlertCircle } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input, Label } from "@/components/ui/input";
import { cn, formatPhone } from "@/lib/utils";
import { getNumbers } from "@/lib/api";

interface PhoneNumberRecord {
  id: string;
  phone_number: string;
  friendly_name: string;
  is_active: boolean;
  livekit_sip_trunk_id?: string;
  monthly_rate?: number;
  total_calls?: number;
}

export function NumbersPage() {
  const [numbers, setNumbers] = useState<PhoneNumberRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        setLoading(true);
        const res = await getNumbers();
        setNumbers(res.numbers || res || []);
      } catch (e: any) {
        setError(e.message);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  return (
    <div className="p-6 space-y-4 max-w-[900px]">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-foreground">Phone Numbers</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            Manage numbers connected to your AI agent
          </p>
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
        </div>
      ) : error ? (
        <div className="flex flex-col items-center py-12 gap-2">
          <AlertCircle className="w-6 h-6 text-red-400" />
          <p className="text-sm text-muted-foreground">{error}</p>
        </div>
      ) : numbers.length === 0 ? (
        <Card>
          <CardContent className="p-8 text-center">
            <Phone className="w-8 h-8 text-muted-foreground/40 mx-auto mb-3" />
            <p className="text-sm text-foreground font-medium">No phone numbers configured</p>
            <p className="text-xs text-muted-foreground mt-1">
              Phone numbers will appear here once provisioned for your AI agent
            </p>
          </CardContent>
        </Card>
      ) : (
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
                    {num.total_calls != null && (
                      <div>
                        <p className="text-sm font-bold text-foreground">{num.total_calls}</p>
                        <p className="text-[10px] text-muted-foreground">Total Calls</p>
                      </div>
                    )}
                    {num.monthly_rate != null && (
                      <div>
                        <p className="text-sm font-bold text-foreground">${num.monthly_rate}/mo</p>
                        <p className="text-[10px] text-muted-foreground">Cost</p>
                      </div>
                    )}
                  </div>
                  {num.livekit_sip_trunk_id && (
                    <div className="flex items-center gap-1 text-[11px] text-emerald-400">
                      <Wifi className="w-3 h-3" />
                      SIP
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

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
                Already have a number with another carrier? Forward it to your SIP trunk to use with your AI agent.
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

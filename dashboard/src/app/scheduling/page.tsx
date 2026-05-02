"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { CalendarDays, Loader2, RefreshCw, ShieldCheck } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Label } from "@/components/ui/input";
import {
  getSchedulingAvailability,
  getSchedulingStatus,
  updateSchedulingConfig,
  type SchedulingSlot,
  type SchedulingStatus,
} from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { AUTH_HANDOFF_PATH } from "@/lib/auth-landing";

const bookingModes = [
  { value: "manual", label: "Manual" },
  { value: "ai-assisted", label: "AI-assisted" },
  { value: "ai auto-book", label: "AI auto-book" },
];

export default function SchedulingPage() {
  const { user, loading } = useAuth();
  const [status, setStatus] = useState<SchedulingStatus | null>(null);
  const [slots, setSlots] = useState<SchedulingSlot[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [calcomUserId, setCalcomUserId] = useState("");
  const [defaultEventTypeId, setDefaultEventTypeId] = useState("");
  const [eventTypeIds, setEventTypeIds] = useState("");
  const [bookingMode, setBookingMode] = useState("ai-assisted");

  useEffect(() => {
    if (!loading && !user) window.location.href = AUTH_HANDOFF_PATH;
  }, [loading, user]);

  async function load() {
    setRefreshing(true);
    setError(null);
    try {
      const data = await getSchedulingStatus();
      setStatus(data);
      setCalcomUserId(data.config.calcomUserId || "");
      setDefaultEventTypeId(data.config.defaultEventTypeId || "");
      setEventTypeIds((data.config.eventTypeIds || []).join(", "));
      setBookingMode(data.config.bookingMode || "ai-assisted");

      const eventTypeId = data.config.defaultEventTypeId || data.eventTypes[0]?.id;
      if (eventTypeId && data.health.ok) {
        const availability = await getSchedulingAvailability({ eventTypeId });
        setSlots(availability.slots || []);
      } else {
        setSlots([]);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load scheduling");
    } finally {
      setRefreshing(false);
    }
  }

  useEffect(() => {
    if (user) void load();
  }, [user]);

  async function saveConfig() {
    setSaving(true);
    setError(null);
    try {
      const data = await updateSchedulingConfig({
        calcom_user_id: calcomUserId,
        default_event_type_id: defaultEventTypeId,
        event_type_ids: eventTypeIds.split(",").map((item) => item.trim()).filter(Boolean),
        booking_mode: bookingMode as "manual" | "ai-assisted" | "ai auto-book",
        status: defaultEventTypeId ? "connected" : "disabled",
      });
      setStatus(data);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to save scheduling config");
    } finally {
      setSaving(false);
    }
  }

  const statusVariant = useMemo<"success" | "destructive" | "warning">(() => {
    if (status?.status === "connected") return "success";
    if (status?.status === "error") return "destructive";
    return "warning";
  }, [status?.status]);

  if (loading || (!user && !error)) {
    return (
      <div className="min-h-screen bg-slate-950 text-slate-100 flex items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-cyan-300" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <main className="mx-auto flex w-full max-w-6xl flex-col gap-6 px-4 py-8">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-xs font-medium uppercase tracking-widest text-cyan-300">Omniweb AI Scheduling</p>
            <h1 className="mt-2 text-3xl font-semibold tracking-tight text-white">Internal Cal.diy Scheduling</h1>
            <p className="mt-2 max-w-2xl text-sm text-slate-400">
              Cal.diy is treated as a private scheduling engine. The dashboard talks only to Omniweb backend APIs.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" onClick={() => void load()} disabled={refreshing}>
              {refreshing ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
              Refresh
            </Button>
            <Button asChild variant="ghost">
              <Link href="/landing">Back</Link>
            </Button>
          </div>
        </div>

        {error && (
          <Card className="border-red-500/40 bg-red-950/30">
            <CardContent className="pt-5 text-sm text-red-200">{error}</CardContent>
          </Card>
        )}

        <div className="grid gap-4 md:grid-cols-3">
          <Card className="bg-slate-900/70">
            <CardHeader>
              <CardTitle>Status</CardTitle>
              <CardDescription>Backend to Cal.diy private API</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <Badge variant={statusVariant}>{status?.status || "loading"}</Badge>
              <p className="text-sm text-slate-300">{status?.health.message || "Checking internal scheduler..."}</p>
            </CardContent>
          </Card>

          <Card className="bg-slate-900/70">
            <CardHeader>
              <CardTitle>Security Model</CardTitle>
              <CardDescription>No external API keys</CardDescription>
            </CardHeader>
            <CardContent className="space-y-2 text-sm text-slate-300">
              <div className="flex items-center gap-2"><ShieldCheck className="h-4 w-4 text-emerald-300" /> Server-to-server only</div>
              <div className="flex items-center gap-2"><ShieldCheck className="h-4 w-4 text-emerald-300" /> Internal service header</div>
              <div className="flex items-center gap-2"><ShieldCheck className="h-4 w-4 text-emerald-300" /> Tenant event validation</div>
            </CardContent>
          </Card>

          <Card className="bg-slate-900/70">
            <CardHeader>
              <CardTitle>Booking Mode</CardTitle>
              <CardDescription>How Omniweb AI books appointments</CardDescription>
            </CardHeader>
            <CardContent>
              <select
                className="h-9 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 text-sm text-slate-100"
                value={bookingMode}
                onChange={(event) => setBookingMode(event.target.value)}
              >
                {bookingModes.map((mode) => (
                  <option key={mode.value} value={mode.value}>{mode.label}</option>
                ))}
              </select>
            </CardContent>
          </Card>
        </div>

        <div className="grid gap-4 lg:grid-cols-[1fr_1.2fr]">
          <Card className="bg-slate-900/70">
            <CardHeader>
              <CardTitle>Tenant Mapping</CardTitle>
              <CardDescription>Map this Omniweb tenant to its Cal.diy user and event types.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-1.5">
                <Label>Cal.diy user ID</Label>
                <Input value={calcomUserId} onChange={(event) => setCalcomUserId(event.target.value)} placeholder="calcom user id" />
              </div>
              <div className="space-y-1.5">
                <Label>Default event type ID</Label>
                <Input value={defaultEventTypeId} onChange={(event) => setDefaultEventTypeId(event.target.value)} placeholder="event type id" />
              </div>
              <div className="space-y-1.5">
                <Label>Allowed event type IDs</Label>
                <Input value={eventTypeIds} onChange={(event) => setEventTypeIds(event.target.value)} placeholder="123, 456" />
              </div>
              <Button onClick={() => void saveConfig()} disabled={saving}>
                {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                Save Scheduling Config
              </Button>
            </CardContent>
          </Card>

          <Card className="bg-slate-900/70">
            <CardHeader>
              <CardTitle>Availability Preview</CardTitle>
              <CardDescription>Live slots from the internal Cal.diy API.</CardDescription>
            </CardHeader>
            <CardContent>
              {slots.length ? (
                <div className="grid gap-2 sm:grid-cols-2">
                  {slots.slice(0, 6).map((slot) => (
                    <div key={`${slot.start}-${slot.end || ""}`} className="rounded-lg border border-slate-800 bg-slate-950/70 p-3 text-sm">
                      <div className="flex items-center gap-2 text-slate-100">
                        <CalendarDays className="h-4 w-4 text-cyan-300" />
                        {slot.start}
                      </div>
                      {slot.end && <div className="mt-1 text-xs text-slate-500">Ends {slot.end}</div>}
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-slate-400">No preview slots available yet. Connect a tenant event type and refresh.</p>
              )}
            </CardContent>
          </Card>
        </div>

        <div className="grid gap-4 lg:grid-cols-2">
          <Card className="bg-slate-900/70">
            <CardHeader>
              <CardTitle>Event Types</CardTitle>
              <CardDescription>Allowed events visible to this tenant.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-2">
              {status?.eventTypes.length ? status.eventTypes.map((eventType) => (
                <div key={eventType.id} className="flex items-center justify-between rounded-lg border border-slate-800 p-3">
                  <div>
                    <div className="text-sm font-medium text-slate-100">{eventType.title}</div>
                    <div className="text-xs text-slate-500">ID {eventType.id}</div>
                  </div>
                  {eventType.length && <Badge variant="outline">{eventType.length} min</Badge>}
                </div>
              )) : (
                <p className="text-sm text-slate-400">No event types returned yet.</p>
              )}
            </CardContent>
          </Card>

          <Card className="bg-slate-900/70">
            <CardHeader>
              <CardTitle>Recent Bookings</CardTitle>
              <CardDescription>Bookings created by Omniweb AI for this tenant.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-2">
              {status?.recentBookings.length ? status.recentBookings.map((booking) => (
                <div key={booking.id} className="rounded-lg border border-slate-800 p-3">
                  <div className="flex items-center justify-between gap-3">
                    <div className="text-sm font-medium text-slate-100">{booking.attendeeName}</div>
                    <Badge variant={booking.status === "confirmed" ? "success" : "outline"}>{booking.status}</Badge>
                  </div>
                  <div className="mt-1 text-xs text-slate-400">{booking.startTime || "No start time"} · {booking.attendeeEmail}</div>
                </div>
              )) : (
                <p className="text-sm text-slate-400">No bookings created yet.</p>
              )}
            </CardContent>
          </Card>
        </div>
      </main>
    </div>
  );
}

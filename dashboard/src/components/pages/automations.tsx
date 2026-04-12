"use client";

import { useState, useEffect, useCallback } from "react";
import {
  Zap,
  Plus,
  Trash2,
  ChevronDown,
  ChevronUp,
  Clock,
  MessageSquare,
  PhoneOutgoing,
  GripVertical,
  Power,
  Loader2,
  Save,
} from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input, Label } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import {
  getAutomations,
  createAutomation,
  updateAutomation,
  deleteAutomation,
  type AutomationStep,
  type AutomationSequence,
} from "@/lib/api";

/* ── Types ── */
type TriggerType = "after_call" | "missed_call" | "new_lead" | "manual";
type StepType = "sms" | "wait" | "call";

interface Step {
  id: string;
  type: StepType;
  config: Record<string, string>;
}

interface Sequence {
  id: string;
  name: string;
  trigger: TriggerType;
  enabled: boolean;
  steps: Step[];
  _dirty?: boolean;
  _isNew?: boolean;
}

const TRIGGER_LABELS: Record<TriggerType, string> = {
  after_call: "After Call Ends",
  missed_call: "Missed Call",
  new_lead: "New Lead Captured",
  manual: "Manual Trigger",
};

const STEP_ICONS: Record<StepType, React.ElementType> = {
  sms: MessageSquare,
  wait: Clock,
  call: PhoneOutgoing,
};

/* ── Step Editor ── */
function StepCard({
  step,
  onUpdate,
  onDelete,
}: {
  step: Step;
  onUpdate: (s: Step) => void;
  onDelete: () => void;
}) {
  const Icon = STEP_ICONS[step.type];

  return (
    <div className="flex items-start gap-3 p-3 rounded-lg border bg-accent/30">
      <div className="mt-0.5 text-muted-foreground cursor-grab">
        <GripVertical className="w-4 h-4" />
      </div>
      <div
        className={cn(
          "flex items-center justify-center w-8 h-8 rounded-lg shrink-0",
          step.type === "sms" && "bg-blue-500/10 text-blue-400",
          step.type === "wait" && "bg-amber-500/10 text-amber-400",
          step.type === "call" && "bg-emerald-500/10 text-emerald-400"
        )}
      >
        <Icon className="w-4 h-4" />
      </div>
      <div className="flex-1 min-w-0 space-y-2">
        {step.type === "sms" && (
          <textarea
            value={step.config.body || ""}
            onChange={(e) =>
              onUpdate({ ...step, config: { ...step.config, body: e.target.value } })
            }
            rows={3}
            className="w-full text-xs bg-background border rounded-lg p-2 resize-none focus:outline-none focus:ring-1 focus:ring-primary"
            placeholder="SMS message body…"
          />
        )}
        {step.type === "wait" && (
          <div className="flex items-center gap-2">
            <span className="text-xs text-muted-foreground">Wait</span>
            <Input
              value={step.config.minutes || ""}
              onChange={(e) =>
                onUpdate({ ...step, config: { ...step.config, minutes: e.target.value } })
              }
              className="w-20 h-7 text-xs"
            />
            <span className="text-xs text-muted-foreground">minutes</span>
          </div>
        )}
        {step.type === "call" && (
          <div className="space-y-1">
            <p className="text-xs font-medium text-foreground">Automated Callback</p>
            <Input
              value={step.config.note || ""}
              onChange={(e) =>
                onUpdate({ ...step, config: { ...step.config, note: e.target.value } })
              }
              placeholder="Internal note…"
              className="h-7 text-xs"
            />
          </div>
        )}
      </div>
      <button onClick={onDelete} className="p-1 hover:text-destructive text-muted-foreground">
        <Trash2 className="w-3.5 h-3.5" />
      </button>
    </div>
  );
}

/* ── Sequence Card ── */
function SequenceCard({
  seq,
  onUpdate,
  onDelete,
  onSave,
  saving,
}: {
  seq: Sequence;
  onUpdate: (s: Sequence) => void;
  onDelete: () => void;
  onSave: () => void;
  saving: boolean;
}) {
  const [open, setOpen] = useState(!!seq._isNew);

  const updateStep = (idx: number, step: Step) => {
    const steps = [...seq.steps];
    steps[idx] = step;
    onUpdate({ ...seq, steps, _dirty: true });
  };
  const deleteStep = (idx: number) => {
    onUpdate({ ...seq, steps: seq.steps.filter((_, i) => i !== idx), _dirty: true });
  };
  const addStep = (type: StepType) => {
    const defaults: Record<StepType, Record<string, string>> = {
      sms: { body: "" },
      wait: { minutes: "5" },
      call: { note: "" },
    };
    onUpdate({
      ...seq,
      steps: [
        ...seq.steps,
        { id: `s_${Date.now()}`, type, config: defaults[type] },
      ],
      _dirty: true,
    });
  };

  return (
    <Card className={cn(!seq.enabled && "opacity-60")}>
      <CardContent className="p-5">
        {/* Header */}
        <div className="flex items-center gap-3">
          <button
            onClick={() => onUpdate({ ...seq, enabled: !seq.enabled, _dirty: true })}
            className={cn(
              "p-1.5 rounded-lg transition-colors",
              seq.enabled
                ? "bg-emerald-500/10 text-emerald-400"
                : "bg-muted text-muted-foreground"
            )}
          >
            <Power className="w-4 h-4" />
          </button>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <p className="text-sm font-semibold text-foreground">{seq.name}</p>
              <Badge variant={seq.enabled ? "success" : "secondary"}>
                {seq.enabled ? "on" : "off"}
              </Badge>
              {seq._dirty && (
                <Badge variant="outline" className="text-amber-400 border-amber-400/30">
                  unsaved
                </Badge>
              )}
            </div>
            <p className="text-[11px] text-muted-foreground">
              Trigger: {TRIGGER_LABELS[seq.trigger]} · {seq.steps.length} step
              {seq.steps.length !== 1 && "s"}
            </p>
          </div>
          <div className="flex items-center gap-1.5">
            {seq._dirty && (
              <Button variant="default" size="sm" onClick={onSave} disabled={saving}>
                {saving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />}
                Save
              </Button>
            )}
            <Button variant="ghost" size="icon" onClick={() => setOpen(!open)}>
              {open ? (
                <ChevronUp className="w-4 h-4" />
              ) : (
                <ChevronDown className="w-4 h-4" />
              )}
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="text-muted-foreground hover:text-destructive"
              onClick={onDelete}
            >
              <Trash2 className="w-4 h-4" />
            </Button>
          </div>
        </div>

        {/* Steps */}
        {open && (
          <div className="mt-4 space-y-3">
            {/* Trigger Selector */}
            <div className="space-y-1.5">
              <Label>Trigger</Label>
              <div className="flex gap-2 flex-wrap">
                {(Object.keys(TRIGGER_LABELS) as TriggerType[]).map((t) => (
                  <button
                    key={t}
                    onClick={() => onUpdate({ ...seq, trigger: t, _dirty: true })}
                    className={cn(
                      "px-3 py-1.5 rounded-lg border text-xs font-medium transition-colors",
                      seq.trigger === t
                        ? "border-primary bg-primary/10 text-primary"
                        : "border-border text-muted-foreground hover:border-primary/30"
                    )}
                  >
                    {TRIGGER_LABELS[t]}
                  </button>
                ))}
              </div>
            </div>

            {/* Sequence Name */}
            <div className="space-y-1.5">
              <Label>Sequence Name</Label>
              <Input
                value={seq.name}
                onChange={(e) => onUpdate({ ...seq, name: e.target.value, _dirty: true })}
                className="h-8 text-sm"
              />
            </div>

            {/* Steps List */}
            <div className="space-y-2">
              <Label>Steps</Label>
              {seq.steps.map((step, idx) => (
                <div key={step.id} className="relative">
                  {idx > 0 && (
                    <div className="absolute -top-1.5 left-[29px] w-px h-3 bg-border" />
                  )}
                  <StepCard
                    step={step}
                    onUpdate={(s) => updateStep(idx, s)}
                    onDelete={() => deleteStep(idx)}
                  />
                </div>
              ))}
            </div>

            {/* Add Step */}
            <div className="flex gap-2 pt-1">
              {(["sms", "wait", "call"] as StepType[]).map((type) => {
                const Icon = STEP_ICONS[type];
                return (
                  <Button
                    key={type}
                    variant="outline"
                    size="sm"
                    onClick={() => addStep(type)}
                    className="text-xs"
                  >
                    <Icon className="w-3 h-3" />
                    + {type.toUpperCase()}
                  </Button>
                );
              })}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

/* ── Main ── */
export function AutomationsPage() {
  const [sequences, setSequences] = useState<Sequence[]>([]);
  const [loading, setLoading] = useState(true);
  const [savingId, setSavingId] = useState<string | null>(null);

  // Convert backend steps to frontend format
  const toFrontendSteps = (backendSteps: any[]): Step[] =>
    (backendSteps || []).map((s: any, i: number) => ({
      id: `s_${i}_${Date.now()}`,
      type: s.type || "sms",
      config: {
        ...(s.type === "sms" ? { body: s.template || s.body || s.config?.body || "" } : {}),
        ...(s.type === "wait" ? { minutes: String(s.delay_minutes || s.minutes || s.config?.minutes || "5") } : {}),
        ...(s.type === "call" ? { note: s.note || s.config?.note || "" } : {}),
      },
    }));

  const loadSequences = useCallback(async () => {
    try {
      const data = await getAutomations();
      setSequences(
        data.sequences.map((s) => ({
          id: s.id,
          name: s.name,
          trigger: s.trigger as TriggerType,
          enabled: s.enabled,
          steps: toFrontendSteps(s.steps),
        }))
      );
    } catch {
      // If API fails, start empty
      setSequences([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadSequences();
  }, [loadSequences]);

  const updateSeq = (idx: number, seq: Sequence) => {
    const updated = [...sequences];
    updated[idx] = seq;
    setSequences(updated);
  };

  const handleSave = async (idx: number) => {
    const seq = sequences[idx];
    setSavingId(seq.id);
    try {
      const payload = {
        name: seq.name,
        trigger: seq.trigger,
        enabled: seq.enabled,
        steps: seq.steps.map((s) => ({ type: s.type, config: s.config })),
      };

      if (seq._isNew) {
        const created = await createAutomation(payload);
        const updated = [...sequences];
        updated[idx] = {
          ...seq,
          id: created.id,
          _dirty: false,
          _isNew: false,
        };
        setSequences(updated);
      } else {
        await updateAutomation(seq.id, payload);
        const updated = [...sequences];
        updated[idx] = { ...seq, _dirty: false };
        setSequences(updated);
      }
    } catch {
      // Error handled by apiFetch
    } finally {
      setSavingId(null);
    }
  };

  const handleDelete = async (idx: number) => {
    const seq = sequences[idx];
    if (!seq._isNew) {
      try {
        await deleteAutomation(seq.id);
      } catch {
        return;
      }
    }
    setSequences(sequences.filter((_, i) => i !== idx));
  };

  const addSequence = () => {
    setSequences([
      ...sequences,
      {
        id: `new_${Date.now()}`,
        name: "New Sequence",
        trigger: "manual",
        enabled: false,
        steps: [],
        _dirty: true,
        _isNew: true,
      },
    ]);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="p-6 space-y-4 max-w-[900px]">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-foreground">Automations</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            Set up SMS sequences and automated callbacks triggered by call events
          </p>
        </div>
        <Button size="sm" onClick={addSequence}>
          <Plus className="w-3.5 h-3.5" />
          New Sequence
        </Button>
      </div>

      {/* Info Banner */}
      <div className="flex items-start gap-3 p-4 rounded-xl bg-primary/5 border border-primary/20">
        <Zap className="w-5 h-5 text-primary mt-0.5 shrink-0" />
        <div>
          <p className="text-sm font-medium text-foreground">How Automations Work</p>
          <p className="text-xs text-muted-foreground mt-0.5">
            Sequences fire automatically based on triggers — after a call, on a missed call, or
            when a new lead is captured. Each step runs in order with delays you define. SMS
            messages support template variables like{" "}
            <code className="text-[11px] bg-accent px-1 py-0.5 rounded">{"{{customer_name}}"}</code>,{" "}
            <code className="text-[11px] bg-accent px-1 py-0.5 rounded">{"{{business_name}}"}</code>, and{" "}
            <code className="text-[11px] bg-accent px-1 py-0.5 rounded">{"{{booking_url}}"}</code>.
          </p>
        </div>
      </div>

      {/* Sequences */}
      <div className="space-y-3">
        {sequences.map((seq, idx) => (
          <SequenceCard
            key={seq.id}
            seq={seq}
            onUpdate={(s) => updateSeq(idx, s)}
            onDelete={() => handleDelete(idx)}
            onSave={() => handleSave(idx)}
            saving={savingId === seq.id}
          />
        ))}
      </div>

      {sequences.length === 0 && (
        <Card>
          <CardContent className="p-10 text-center">
            <Zap className="w-10 h-10 text-muted-foreground mx-auto mb-3 opacity-40" />
            <p className="text-sm font-medium text-foreground">No automations yet</p>
            <p className="text-xs text-muted-foreground mt-1">
              Create your first sequence to start automating follow-ups
            </p>
            <Button size="sm" className="mt-4" onClick={addSequence}>
              <Plus className="w-3.5 h-3.5" />
              Create Sequence
            </Button>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

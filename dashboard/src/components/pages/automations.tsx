"use client";

import { useState } from "react";
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
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input, Label } from "@/components/ui/input";
import { cn } from "@/lib/utils";

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

/* ── Seed Data ── */
const INITIAL_SEQUENCES: Sequence[] = [
  {
    id: "seq_1",
    name: "Post-Call Follow-Up",
    trigger: "after_call",
    enabled: true,
    steps: [
      { id: "s1", type: "wait", config: { minutes: "5" } },
      {
        id: "s2",
        type: "sms",
        config: {
          body: "Thanks for calling {{business_name}}! We've noted your request for {{services}}. A team member will follow up shortly.",
        },
      },
      { id: "s3", type: "wait", config: { minutes: "1440" } },
      {
        id: "s4",
        type: "sms",
        config: {
          body: "Hi {{customer_name}}, just checking in — were you able to get everything sorted? Reply here or call us back anytime.",
        },
      },
    ],
  },
  {
    id: "seq_2",
    name: "Missed Call Recovery",
    trigger: "missed_call",
    enabled: true,
    steps: [
      { id: "s5", type: "wait", config: { minutes: "1" } },
      {
        id: "s6",
        type: "sms",
        config: {
          body: "Sorry we missed your call to {{business_name}}! You can book online at {{booking_url}} or we'll try you back shortly.",
        },
      },
      { id: "s7", type: "wait", config: { minutes: "30" } },
      { id: "s8", type: "call", config: { note: "Automated callback attempt" } },
    ],
  },
  {
    id: "seq_3",
    name: "New Lead Nurture",
    trigger: "new_lead",
    enabled: false,
    steps: [
      { id: "s9", type: "wait", config: { minutes: "60" } },
      {
        id: "s10",
        type: "sms",
        config: {
          body: "Hi {{customer_name}}, thanks for your interest in {{business_name}}. We'd love to help — reply BOOK to schedule a time.",
        },
      },
    ],
  },
];

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
}: {
  seq: Sequence;
  onUpdate: (s: Sequence) => void;
  onDelete: () => void;
}) {
  const [open, setOpen] = useState(false);

  const updateStep = (idx: number, step: Step) => {
    const steps = [...seq.steps];
    steps[idx] = step;
    onUpdate({ ...seq, steps });
  };
  const deleteStep = (idx: number) => {
    onUpdate({ ...seq, steps: seq.steps.filter((_, i) => i !== idx) });
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
    });
  };

  return (
    <Card className={cn(!seq.enabled && "opacity-60")}>
      <CardContent className="p-5">
        {/* Header */}
        <div className="flex items-center gap-3">
          <button
            onClick={() => onUpdate({ ...seq, enabled: !seq.enabled })}
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
            </div>
            <p className="text-[11px] text-muted-foreground">
              Trigger: {TRIGGER_LABELS[seq.trigger]} · {seq.steps.length} step
              {seq.steps.length !== 1 && "s"}
            </p>
          </div>
          <div className="flex items-center gap-1.5">
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
                    onClick={() => onUpdate({ ...seq, trigger: t })}
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
                onChange={(e) => onUpdate({ ...seq, name: e.target.value })}
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
  const [sequences, setSequences] = useState<Sequence[]>(INITIAL_SEQUENCES);

  const updateSeq = (idx: number, seq: Sequence) => {
    const updated = [...sequences];
    updated[idx] = seq;
    setSequences(updated);
  };

  const deleteSeq = (idx: number) => {
    setSequences(sequences.filter((_, i) => i !== idx));
  };

  const addSequence = () => {
    setSequences([
      ...sequences,
      {
        id: `seq_${Date.now()}`,
        name: "New Sequence",
        trigger: "manual",
        enabled: false,
        steps: [],
      },
    ]);
  };

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
            onDelete={() => deleteSeq(idx)}
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

"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { hasPermission, useAuth } from "@/lib/auth-context";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import {
  adminGetTemplates,
  adminCreateTemplate,
  adminUpdateTemplate,
  adminDeleteTemplate,
} from "@/lib/api";
import {
  Plus,
  Loader2,
  AlertCircle,
  Pencil,
  Trash2,
  X,
  Check,
  FileText,
  Star,
} from "lucide-react";

const LANGUAGE_OPTIONS = [
  { code: "en", label: "English", flag: "🇺🇸" },
  { code: "es", label: "Spanish", flag: "🇪🇸" },
  { code: "fr", label: "French", flag: "🇫🇷" },
  { code: "de", label: "German", flag: "🇩🇪" },
  { code: "ar", label: "Arabic", flag: "🇸🇦" },
  { code: "hi", label: "Hindi", flag: "🇮🇳" },
  { code: "pt", label: "Portuguese", flag: "🇧🇷" },
  { code: "it", label: "Italian", flag: "🇮🇹" },
  { code: "ja", label: "Japanese", flag: "🇯🇵" },
  { code: "ko", label: "Korean", flag: "🇰🇷" },
  { code: "zh", label: "Chinese", flag: "🇨🇳" },
  { code: "nl", label: "Dutch", flag: "🇳🇱" },
  { code: "pl", label: "Polish", flag: "🇵🇱" },
  { code: "ru", label: "Russian", flag: "🇷🇺" },
  { code: "tr", label: "Turkish", flag: "🇹🇷" },
  { code: "uk", label: "Ukrainian", flag: "🇺🇦" },
];

const ALL_LANGUAGE_CODES = LANGUAGE_OPTIONS.map(l => l.code);

interface Template {
  id: string;
  name: string;
  description: string | null;
  industry: string | null;
  agent_name: string;
  greeting: string;
  supported_languages: string[];
  system_prompt: string | null;
  is_default: boolean;
  is_active: boolean;
  created_at: string;
}

const EMPTY_FORM: Omit<Template, "id" | "created_at"> = {
  name: "",
  description: "",
  industry: "",
  agent_name: "",
  greeting: "",
  supported_languages: ALL_LANGUAGE_CODES,
  system_prompt: "",
  is_default: false,
  is_active: true,
};

export function AdminTemplates() {
  const { user } = useAuth();
  const [templates, setTemplates] = useState<Template[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const canWriteTemplates = hasPermission(user, "templates.write");

  async function fetchTemplates() {
    setLoading(true);
    try {
      const res = await adminGetTemplates();
      setTemplates(Array.isArray(res) ? res : res.templates || []);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    fetchTemplates();
  }, []);

  function openCreate() {
    setForm({ ...EMPTY_FORM });
    setEditingId(null);
    setShowForm(true);
  }

  function openEdit(t: Template) {
    setForm({
      name: t.name,
      description: t.description || "",
      industry: t.industry || "",
      agent_name: t.agent_name,
      greeting: t.greeting,
      supported_languages: t.supported_languages ?? ["en"],
      system_prompt: t.system_prompt || "",
      is_default: t.is_default,
      is_active: t.is_active,
    });
    setEditingId(t.id);
    setShowForm(true);
  }

  function closeForm() {
    setShowForm(false);
    setEditingId(null);
  }

  async function handleSave() {
    setSaving(true);
    try {
      if (editingId) {
        await adminUpdateTemplate(editingId, form);
      } else {
        await adminCreateTemplate(form);
      }
      closeForm();
      fetchTemplates();
    } catch (e: any) {
      alert("Failed to save: " + e.message);
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(t: Template) {
    if (!confirm(`Delete template "${t.name}"? This cannot be undone.`)) return;
    try {
      await adminDeleteTemplate(t.id);
      fetchTemplates();
    } catch (e: any) {
      alert("Failed to delete: " + e.message);
    }
  }

  function updateField(key: string, value: any) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-foreground">Agent Templates</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Pre-built agent configurations for new clients
          </p>
        </div>
        <button
          onClick={openCreate}
            disabled={!canWriteTemplates}
            className="flex items-center gap-2 h-9 px-4 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 transition-colors disabled:opacity-50"
        >
          <Plus className="w-4 h-4" />
          New Template
        </button>
      </div>

        <Card className="border-cyan-500/20 bg-gradient-to-r from-cyan-500/5 via-transparent to-violet-500/5">
          <CardContent className="flex flex-col gap-4 p-5 md:flex-row md:items-center md:justify-between">
            <div>
              <div className="text-sm font-semibold text-foreground">Website template system</div>
              <p className="mt-1 text-sm text-muted-foreground">
                The first Webflow-inspired site-template scaffold is now live, including a premium sample layout and an embedded Omniweb AI agent zone.
              </p>
            </div>
            <Link
              href="/templates"
              className="inline-flex h-10 items-center justify-center rounded-lg border border-cyan-400/20 bg-cyan-400/10 px-4 text-sm font-medium text-foreground transition-colors hover:bg-cyan-400/20"
            >
              Open website templates
            </Link>
          </CardContent>
        </Card>

      {error && (
        <div className="flex items-center gap-2 text-red-400 text-sm">
          <AlertCircle className="w-4 h-4" />
          {error}
        </div>
      )}

      {/* Form */}
      {showForm && canWriteTemplates && (
        <Card className="border-primary/30">
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle>{editingId ? "Edit Template" : "Create Template"}</CardTitle>
              <button
                onClick={closeForm}
                className="p-1.5 rounded-lg text-muted-foreground hover:text-foreground hover:bg-sidebar-accent transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="text-xs text-muted-foreground font-medium block mb-1.5">
                  Template Name *
                </label>
                <Input
                  value={form.name}
                  onChange={(e) => updateField("name", e.target.value)}
                  placeholder="e.g. Auto Mechanic"
                />
              </div>
              <div>
                <label className="text-xs text-muted-foreground font-medium block mb-1.5">
                  Industry
                </label>
                <Input
                  value={form.industry || ""}
                  onChange={(e) => updateField("industry", e.target.value)}
                  placeholder="e.g. Automotive"
                />
              </div>
              <div>
                <label className="text-xs text-muted-foreground font-medium block mb-1.5">
                  Agent Name *
                </label>
                <Input
                  value={form.agent_name}
                  onChange={(e) => updateField("agent_name", e.target.value)}
                  placeholder="e.g. Max"
                />
              </div>
              <div>
                <label className="text-xs text-muted-foreground font-medium block mb-1.5">
                  Languages ({form.supported_languages.length} selected)
                </label>
                <div className="flex flex-wrap gap-1.5">
                  {LANGUAGE_OPTIONS.map((lang) => {
                    const on = form.supported_languages.includes(lang.code);
                    return (
                      <button
                        key={lang.code}
                        type="button"
                        onClick={() => {
                          if (lang.code === "en") return;
                          const next = on
                            ? form.supported_languages.filter((c: string) => c !== lang.code)
                            : [...form.supported_languages, lang.code];
                          updateField("supported_languages", next);
                        }}
                        className={`inline-flex items-center gap-1 px-2 py-1 rounded-md border text-xs transition-colors ${
                          on
                            ? "border-primary bg-primary/10 text-foreground"
                            : "border-border text-muted-foreground hover:border-muted-foreground/50"
                        } ${lang.code === "en" ? "cursor-default" : "cursor-pointer"}`}
                      >
                        <span>{lang.flag}</span>
                        <span>{lang.code.toUpperCase()}</span>
                      </button>
                    );
                  })}
                </div>
              </div>
              <div className="md:col-span-2">
                <label className="text-xs text-muted-foreground font-medium block mb-1.5">
                  Description
                </label>
                <Input
                  value={form.description || ""}
                  onChange={(e) => updateField("description", e.target.value)}
                  placeholder="Brief description of this template"
                />
              </div>
              <div className="md:col-span-2">
                <label className="text-xs text-muted-foreground font-medium block mb-1.5">
                  Greeting Message *
                </label>
                <textarea
                  value={form.greeting}
                  onChange={(e) => updateField("greeting", e.target.value)}
                  placeholder="Hello! Thanks for calling..."
                  rows={3}
                  className="w-full px-3 py-2 rounded-lg border border-border bg-card text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/30 resize-none"
                />
              </div>
              <div className="md:col-span-2">
                <label className="text-xs text-muted-foreground font-medium block mb-1.5">
                  System Prompt
                </label>
                <textarea
                  value={form.system_prompt || ""}
                  onChange={(e) => updateField("system_prompt", e.target.value)}
                  placeholder="You are a helpful AI assistant..."
                  rows={4}
                  className="w-full px-3 py-2 rounded-lg border border-border bg-card text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/30 resize-none"
                />
              </div>
              <div className="md:col-span-2 flex items-center gap-6">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={form.is_default}
                    onChange={(e) => updateField("is_default", e.target.checked)}
                    className="w-4 h-4 rounded border-border accent-primary"
                  />
                  <span className="text-sm text-foreground">Default template</span>
                </label>
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={form.is_active}
                    onChange={(e) => updateField("is_active", e.target.checked)}
                    className="w-4 h-4 rounded border-border accent-primary"
                  />
                  <span className="text-sm text-foreground">Active</span>
                </label>
              </div>
            </div>
            <div className="flex justify-end gap-3 mt-6">
              <button
                onClick={closeForm}
                className="h-9 px-4 rounded-lg border border-border text-sm text-muted-foreground hover:text-foreground hover:bg-sidebar-accent transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleSave}
                disabled={saving || !form.name || !form.agent_name || !form.greeting}
                className="flex items-center gap-2 h-9 px-4 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 disabled:opacity-50 transition-colors"
              >
                {saving ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Check className="w-4 h-4" />
                )}
                {editingId ? "Update" : "Create"}
              </button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Template list */}
      {templates.length === 0 ? (
        <div className="text-center py-20 text-muted-foreground text-sm">
          No templates yet. Create one to get started.
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {templates.map((t) => (
            <Card
              key={t.id}
              className={`relative ${!t.is_active ? "opacity-60" : ""}`}
            >
              <CardContent className="p-5">
                {/* Default star */}
                {t.is_default && (
                  <div className="absolute top-3 right-3">
                    <Star className="w-4 h-4 text-amber-400 fill-amber-400" />
                  </div>
                )}

                <div className="flex items-start gap-3 mb-4">
                  <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center shrink-0">
                    <FileText className="w-5 h-5 text-primary" />
                  </div>
                  <div className="min-w-0">
                    <h3 className="text-sm font-semibold text-foreground truncate">{t.name}</h3>
                    {t.industry && (
                      <Badge variant="outline" className="mt-1">{t.industry}</Badge>
                    )}
                  </div>
                </div>

                {t.description && (
                  <p className="text-xs text-muted-foreground mb-3 line-clamp-2">
                    {t.description}
                  </p>
                )}

                <div className="space-y-2 mb-4">
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-muted-foreground">Agent</span>
                    <span className="text-foreground font-medium">{t.agent_name}</span>
                  </div>
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-muted-foreground">Languages</span>
                    <span className="text-foreground font-medium">{t.supported_languages?.length ?? 1} enabled</span>
                  </div>
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-muted-foreground">Status</span>
                    <Badge variant={t.is_active ? "success" : "secondary"} className="text-[10px]">
                      {t.is_active ? "Active" : "Inactive"}
                    </Badge>
                  </div>
                </div>

                <div className="flex items-center gap-2 pt-3 border-t border-border">
                  <button
                    onClick={() => openEdit(t)}
                      disabled={!canWriteTemplates}
                      className="flex-1 flex items-center justify-center gap-1.5 h-8 rounded-lg text-xs text-muted-foreground hover:text-foreground hover:bg-sidebar-accent transition-colors disabled:opacity-50"
                  >
                    <Pencil className="w-3.5 h-3.5" />
                    Edit
                  </button>
                  <button
                    onClick={() => handleDelete(t)}
                      disabled={!canWriteTemplates}
                      className="flex-1 flex items-center justify-center gap-1.5 h-8 rounded-lg text-xs text-muted-foreground hover:text-red-400 hover:bg-red-500/10 transition-colors disabled:opacity-50"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                    Delete
                  </button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}

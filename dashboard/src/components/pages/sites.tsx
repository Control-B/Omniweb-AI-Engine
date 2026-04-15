"use client";

import { useEffect, useMemo, useState } from "react";
import {
  createSiteTemplateInstance,
  deleteSiteTemplateInstance,
  getSiteTemplateInstances,
  updateSiteTemplateInstance,
  type SiteTemplateInstance,
} from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { siteTemplates, getSiteTemplate } from "@/lib/site-templates/registry";
import {
  applyInstanceToTemplate,
  createTemplateInstanceDraft,
  normalizeAgentConfig,
  normalizeInstanceContent,
  slugify,
} from "@/lib/site-templates/instance-utils";
import { TemplateRenderer } from "@/components/site-templates/template-renderer";
import { Badge } from "@/components/ui/badge";
import { Check, Copy, ExternalLink, Loader2, MonitorSmartphone, Plus, Save, Trash2 } from "lucide-react";

interface EditableState {
  name: string;
  site_slug: string;
  public_slug: string;
  status: "draft" | "published" | "archived";
  content: Record<string, any>;
  agent_embed_config: Record<string, any>;
}

export function SitesPage() {
  const [instances, setInstances] = useState<SiteTemplateInstance[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [form, setForm] = useState<EditableState | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [copiedKey, setCopiedKey] = useState<"embed" | "public" | null>(null);

  async function loadInstances() {
    setLoading(true);
    setError("");
    try {
      const response = await getSiteTemplateInstances();
      const nextInstances = response.instances || [];
      setInstances(nextInstances);
      if (!selectedId && nextInstances[0]) {
        selectInstance(nextInstances[0]);
      }
    } catch (err: any) {
      setError(err.message || "Failed to load website instances");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadInstances();
  }, []);

  function selectInstance(instance: SiteTemplateInstance) {
    const template = getSiteTemplate(instance.template_slug);
    if (!template) return;
    setSelectedId(instance.id);
    setForm({
      name: instance.name,
      site_slug: instance.site_slug,
        public_slug: instance.public_slug || instance.site_slug,
      status: instance.status,
      content: normalizeInstanceContent(instance, template),
      agent_embed_config: normalizeAgentConfig(instance, template),
    });
  }

  async function handleCreate(templateSlug: string) {
    const template = getSiteTemplate(templateSlug);
    if (!template) return;
    setSaving(true);
    setError("");
    try {
      const draft = createTemplateInstanceDraft(template);
      const suffix = String(Date.now()).slice(-6);
      const created = await createSiteTemplateInstance({
        ...draft,
        name: `${template.name} ${instances.length + 1}`,
        site_slug: slugify(`${template.slug}-${suffix}`),
          public_slug: slugify(`${template.slug}-${suffix}`),
      });
      const next = [created, ...instances];
      setInstances(next);
      selectInstance(created);
    } catch (err: any) {
      setError(err.message || "Failed to create website");
    } finally {
      setSaving(false);
    }
  }

  async function handleSave() {
    if (!selectedId || !form) return;
    setSaving(true);
    setError("");
    try {
      const updated = await updateSiteTemplateInstance(selectedId, form);
      const next = instances.map((instance) => (instance.id === updated.id ? updated : instance));
      setInstances(next);
      selectInstance(updated);
    } catch (err: any) {
      setError(err.message || "Failed to save website");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    if (!selectedId) return;
    if (!confirm("Delete this website instance?")) return;
    setSaving(true);
    try {
      await deleteSiteTemplateInstance(selectedId);
      const next = instances.filter((instance) => instance.id !== selectedId);
      setInstances(next);
      setSelectedId(null);
      if (next[0]) {
        selectInstance(next[0]);
      } else {
        setForm(null);
      }
    } catch (err: any) {
      setError(err.message || "Failed to delete website");
    } finally {
      setSaving(false);
    }
  }

  const selectedInstance = instances.find((instance) => instance.id === selectedId) || null;
  const selectedTemplate = selectedInstance ? getSiteTemplate(selectedInstance.template_slug) : null;

  const previewTemplate = useMemo(() => {
    if (!selectedInstance || !selectedTemplate || !form) return null;
    return applyInstanceToTemplate(
      selectedTemplate,
      {
        ...selectedInstance,
        name: form.name,
        site_slug: form.site_slug,
          public_slug: form.public_slug,
        status: form.status,
        content: form.content,
        agent_embed_config: form.agent_embed_config,
      }
    );
  }, [selectedInstance, selectedTemplate, form]);

  async function copySnippet() {
    if (!form?.agent_embed_config?.embedSnippet) return;
    await navigator.clipboard.writeText(form.agent_embed_config.embedSnippet);
      setCopiedKey("embed");
      setTimeout(() => setCopiedKey(null), 1500);
  }

    const publicUrl = useMemo(() => {
      if (typeof window === "undefined" || !form?.public_slug) return "";
      return `${window.location.origin}/site/${form.public_slug}`;
    }, [form?.public_slug]);

    const isPublished = form?.status === "published";

    async function copyPublicUrl() {
      if (!publicUrl || !isPublished) return;
      await navigator.clipboard.writeText(publicUrl);
      setCopiedKey("public");
      setTimeout(() => setCopiedKey(null), 1500);
    }

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Website Builder</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Clone a premium coded template, customize the messaging, and embed the Omniweb AI agent per client.
          </p>
        </div>
      </div>

      {error && (
        <div className="rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      )}

      <div className="grid gap-6 xl:grid-cols-[280px_minmax(0,1fr)]">
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <Plus className="h-4 w-4" />
                Start from template
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {siteTemplates.map((template) => (
                <button
                  key={template.slug}
                  onClick={() => void handleCreate(template.slug)}
                  disabled={saving}
                  className="w-full rounded-2xl border border-border bg-background p-4 text-left transition hover:border-primary/40 hover:bg-accent/40"
                >
                  <div className="text-sm font-semibold text-foreground">{template.name}</div>
                  <div className="mt-1 text-xs text-muted-foreground">{template.description}</div>
                </button>
              ))}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <MonitorSmartphone className="h-4 w-4" />
                Saved websites
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {loading ? (
                <div className="flex items-center justify-center py-8 text-muted-foreground">
                  <Loader2 className="h-5 w-5 animate-spin" />
                </div>
              ) : instances.length === 0 ? (
                <p className="text-sm text-muted-foreground">No client website instances yet.</p>
              ) : (
                instances.map((instance) => (
                  <button
                    key={instance.id}
                    onClick={() => selectInstance(instance)}
                    className={`w-full rounded-2xl border p-4 text-left transition ${selectedId === instance.id ? "border-primary bg-primary/5" : "border-border bg-background hover:border-primary/30"}`}
                  >
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <div className="text-sm font-semibold text-foreground">{instance.name}</div>
                        <div className="mt-1 text-xs text-muted-foreground">/{instance.site_slug}</div>
                      </div>
                      <Badge variant={instance.status === "published" ? "success" : "secondary"}>
                        {instance.status}
                      </Badge>
                    </div>
                  </button>
                ))
              )}
            </CardContent>
          </Card>
        </div>

        <div className="space-y-6">
          {!form || !selectedTemplate ? (
            <Card>
              <CardContent className="py-16 text-center text-muted-foreground">
                Create a site from one of the templates to start customizing it.
              </CardContent>
            </Card>
          ) : (
            <>
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center justify-between gap-3 text-base">
                    <span>Edit website</span>
                    <div className="flex items-center gap-2">
                      <Button variant="outline" size="sm" onClick={() => void copySnippet()}>
                          {copiedKey === "embed" ? <Check className="mr-2 h-4 w-4" /> : <Copy className="mr-2 h-4 w-4" />}
                        Copy embed
                      </Button>
                        <Button variant="outline" size="sm" onClick={() => void copyPublicUrl()} disabled={!isPublished || !publicUrl}>
                          {copiedKey === "public" ? <Check className="mr-2 h-4 w-4" /> : <ExternalLink className="mr-2 h-4 w-4" />}
                          Copy public URL
                        </Button>
                        <a
                          href={isPublished ? publicUrl : undefined}
                          target="_blank"
                          rel="noopener noreferrer"
                          aria-disabled={!isPublished || !publicUrl}
                          className={`inline-flex h-8 items-center justify-center gap-1.5 rounded-lg border border-border bg-transparent px-3 text-xs font-medium transition-colors ${isPublished && publicUrl ? "hover:bg-accent" : "pointer-events-none opacity-50"}`}
                        >
                          <ExternalLink className="h-4 w-4" />
                          Open live site
                        </a>
                      <Button variant="outline" size="sm" onClick={handleDelete} disabled={saving}>
                        <Trash2 className="mr-2 h-4 w-4" />
                        Delete
                      </Button>
                      <Button size="sm" onClick={() => void handleSave()} disabled={saving}>
                        {saving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Save className="mr-2 h-4 w-4" />}
                        Save
                      </Button>
                    </div>
                  </CardTitle>
                </CardHeader>
                <CardContent className="grid gap-6 lg:grid-cols-2">
                  <div className="space-y-4">
                    <label className="block text-sm font-medium text-foreground">
                      Website name
                      <Input className="mt-1.5" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
                    </label>
                    <label className="block text-sm font-medium text-foreground">
                      Site slug
                      <Input className="mt-1.5" value={form.site_slug} onChange={(e) => setForm({ ...form, site_slug: slugify(e.target.value) })} />
                    </label>
                      <label className="block text-sm font-medium text-foreground">
                        Public URL slug
                        <Input className="mt-1.5" value={form.public_slug} onChange={(e) => setForm({ ...form, public_slug: slugify(e.target.value) })} />
                      </label>
                    <label className="block text-sm font-medium text-foreground">
                      Status
                      <select
                        className="mt-1.5 h-10 w-full rounded-md border border-input bg-background px-3 text-sm"
                        value={form.status}
                        onChange={(e) => setForm({ ...form, status: e.target.value as EditableState["status"] })}
                      >
                        <option value="draft">Draft</option>
                        <option value="published">Published</option>
                        <option value="archived">Archived</option>
                      </select>
                    </label>
                      <div className="rounded-2xl border border-border bg-muted/20 px-4 py-3 text-sm text-muted-foreground">
                        {isPublished ? (
                          <span>Live URL: <span className="font-mono text-foreground">{publicUrl}</span></span>
                        ) : (
                          <span>Publish this website to activate its public URL.</span>
                        )}
                      </div>
                    <label className="block text-sm font-medium text-foreground">
                      Hero heading
                      <textarea className="mt-1.5 min-h-24 w-full rounded-md border border-input bg-background px-3 py-2 text-sm" value={form.content.heroHeading || ""} onChange={(e) => setForm({ ...form, content: { ...form.content, heroHeading: e.target.value } })} />
                    </label>
                    <label className="block text-sm font-medium text-foreground">
                      Hero subheading
                      <textarea className="mt-1.5 min-h-28 w-full rounded-md border border-input bg-background px-3 py-2 text-sm" value={form.content.heroSubheading || ""} onChange={(e) => setForm({ ...form, content: { ...form.content, heroSubheading: e.target.value } })} />
                    </label>
                  </div>

                  <div className="space-y-4">
                    <label className="block text-sm font-medium text-foreground">
                      Primary CTA
                      <Input className="mt-1.5" value={form.content.primaryCta || ""} onChange={(e) => setForm({ ...form, content: { ...form.content, primaryCta: e.target.value } })} />
                    </label>
                    <label className="block text-sm font-medium text-foreground">
                      Secondary CTA
                      <Input className="mt-1.5" value={form.content.secondaryCta || ""} onChange={(e) => setForm({ ...form, content: { ...form.content, secondaryCta: e.target.value } })} />
                    </label>
                    <label className="block text-sm font-medium text-foreground">
                      Agent block title
                      <Input className="mt-1.5" value={form.agent_embed_config.title || ""} onChange={(e) => setForm({ ...form, agent_embed_config: { ...form.agent_embed_config, title: e.target.value } })} />
                    </label>
                    <label className="block text-sm font-medium text-foreground">
                      Agent block description
                      <textarea className="mt-1.5 min-h-24 w-full rounded-md border border-input bg-background px-3 py-2 text-sm" value={form.agent_embed_config.description || ""} onChange={(e) => setForm({ ...form, agent_embed_config: { ...form.agent_embed_config, description: e.target.value } })} />
                    </label>
                    <label className="block text-sm font-medium text-foreground">
                      Embed snippet
                      <textarea className="mt-1.5 min-h-28 w-full rounded-md border border-input bg-background px-3 py-2 font-mono text-xs" value={form.agent_embed_config.embedSnippet || ""} onChange={(e) => setForm({ ...form, agent_embed_config: { ...form.agent_embed_config, embedSnippet: e.target.value } })} />
                    </label>
                  </div>
                </CardContent>
              </Card>

              {previewTemplate && (
                <Card className="overflow-hidden">
                  <CardHeader>
                    <CardTitle className="flex items-center justify-between gap-3 text-base">
                      <span>Live preview</span>
                      <a href={`/templates/${selectedTemplate.slug}`} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-2 text-sm text-primary hover:underline">
                        Base template
                        <ExternalLink className="h-4 w-4" />
                      </a>
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="p-0">
                    <div className="max-h-[900px] overflow-auto border-t border-border">
                      <TemplateRenderer template={previewTemplate} />
                    </div>
                  </CardContent>
                </Card>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

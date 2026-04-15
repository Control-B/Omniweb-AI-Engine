import type { SiteTemplateInstance } from "@/lib/api";
import type { SiteTemplate } from "@/lib/site-templates/types";

export interface SiteTemplateEditableContent {
  businessName: string;
  heroHeading: string;
  heroSubheading: string;
  primaryCta: string;
  secondaryCta: string;
  ctaHeading: string;
  ctaDescription: string;
}

export interface SiteTemplateEditableAgentConfig {
  title: string;
  description: string;
  buttonLabel: string;
  embedSnippet: string;
  placementHint: string;
}

export function slugify(value: string): string {
  return value
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 60);
}

export function createTemplateInstanceDraft(template: SiteTemplate) {
  return {
    name: `${template.name} Site`,
    site_slug: slugify(template.slug),
    template_slug: template.slug,
    status: "draft" as const,
    content: {
      businessName: template.industry,
      heroHeading: template.hero.heading,
      heroSubheading: template.hero.subheading,
      primaryCta: template.hero.primaryCta,
      secondaryCta: template.hero.secondaryCta,
      ctaHeading:
        template.sections.find((section) => section.type === "cta")?.heading ?? "Launch this site",
      ctaDescription:
        template.sections.find((section) => section.type === "cta")?.description ?? "Customize this site and connect your AI agent.",
    },
    theme_overrides: {},
    agent_embed_config: { ...template.agentEmbed },
  };
}

export function normalizeInstanceContent(instance: SiteTemplateInstance, template: SiteTemplate) {
  const draft = createTemplateInstanceDraft(template);
  return {
    ...draft.content,
    ...(instance.content || {}),
  } as SiteTemplateEditableContent;
}

export function normalizeAgentConfig(instance: SiteTemplateInstance, template: SiteTemplate) {
  const draft = createTemplateInstanceDraft(template);
  return {
    ...draft.agent_embed_config,
    ...(instance.agent_embed_config || {}),
  } as SiteTemplateEditableAgentConfig;
}

export function applyInstanceToTemplate(template: SiteTemplate, instance: SiteTemplateInstance): SiteTemplate {
  const content = normalizeInstanceContent(instance, template);
  const agentEmbed = normalizeAgentConfig(instance, template);

  return {
    ...template,
    hero: {
      ...template.hero,
      heading: content.heroHeading,
      subheading: content.heroSubheading,
      primaryCta: content.primaryCta,
      secondaryCta: content.secondaryCta,
    },
    agentEmbed,
    sections: template.sections.map((section) => {
      if (section.type === "cta") {
        return {
          ...section,
          heading: content.ctaHeading,
          description: content.ctaDescription,
          primaryCta: content.primaryCta,
          secondaryCta: content.secondaryCta,
        };
      }
      return section;
    }),
  };
}

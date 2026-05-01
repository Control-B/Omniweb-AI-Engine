export type SiteTemplateSection =
  | HeroSection
  | StatsSection
  | FeaturesSection
  | TestimonialSection
  | FaqSection
  | CtaSection
  | AgentEmbedSection;

export interface TemplateTheme {
  primary: string;
  secondary: string;
  accent: string;
  surface: string;
  text: string;
  mutedText: string;
}

export interface TemplateNavItem {
  label: string;
  href: string;
}

export interface TemplateAgentEmbedConfig {
  title: string;
  description: string;
  buttonLabel: string;
  embedSnippet: string;
  placementHint: string;
}

export interface SiteTemplate {
  slug: string;
  name: string;
  category: string;
  description: string;
  industry: string;
  thumbnailLabel: string;
  theme: TemplateTheme;
  nav: TemplateNavItem[];
  hero: HeroSection;
  sections: SiteTemplateSection[];
  agentEmbed: TemplateAgentEmbedConfig;
}

export interface HeroSection {
  type: "hero";
  eyebrow: string;
  heading: string;
  subheading: string;
  primaryCta: string;
  secondaryCta: string;
  highlights: string[];
}

export interface StatsSection {
  type: "stats";
  items: Array<{
    label: string;
    value: string;
  }>;
}

export interface FeaturesSection {
  type: "features";
  eyebrow?: string;
  heading: string;
  description?: string;
  items: Array<{
    title: string;
    description: string;
  }>;
}

export interface TestimonialSection {
  type: "testimonials";
  heading: string;
  items: Array<{
    quote: string;
    name: string;
    role: string;
  }>;
}

export interface FaqSection {
  type: "faq";
  heading: string;
  items: Array<{
    question: string;
    answer: string;
  }>;
}

export interface CtaSection {
  type: "cta";
  heading: string;
  description: string;
  primaryCta: string;
  secondaryCta?: string;
}

export interface AgentEmbedSection {
  type: "agent-embed";
  heading: string;
  description: string;
  bullets: string[];
}

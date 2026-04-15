import { plumbingPremiumTemplate } from "@/lib/site-templates/templates/plumbing-premium";
import type { SiteTemplate } from "@/lib/site-templates/types";

export const siteTemplates: SiteTemplate[] = [plumbingPremiumTemplate];

export function getSiteTemplate(slug: string): SiteTemplate | undefined {
  return siteTemplates.find((template) => template.slug === slug);
}

import { notFound } from "next/navigation";
import { TemplateRenderer } from "@/components/site-templates/template-renderer";
import { getPublicSiteTemplateInstance } from "@/lib/api";
import { applyInstanceToTemplate } from "@/lib/site-templates/instance-utils";
import { getSiteTemplate } from "@/lib/site-templates/registry";

export const dynamic = "force-dynamic";

export default async function PublicSitePage({
  params,
}: {
  params: { publicSlug: string };
}) {
  const instance = await getPublicSiteTemplateInstance(params.publicSlug);

  if (!instance) {
    notFound();
  }

  const template = getSiteTemplate(instance.template_slug);

  if (!template) {
    notFound();
  }

  const publishedTemplate = applyInstanceToTemplate(template, instance);

  return <TemplateRenderer template={publishedTemplate} />;
}
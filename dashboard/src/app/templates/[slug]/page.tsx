import { notFound } from "next/navigation";
import { TemplateRenderer } from "@/components/site-templates/template-renderer";
import { getSiteTemplate } from "@/lib/site-templates/registry";

export default function TemplatePreviewPage({
  params,
}: {
  params: { slug: string };
}) {
  const template = getSiteTemplate(params.slug);

  if (!template) {
    notFound();
  }

  return <TemplateRenderer template={template} />;
}

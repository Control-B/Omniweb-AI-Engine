import Link from "next/link";
import { siteTemplates } from "@/lib/site-templates/registry";

export default function TemplatesIndexPage() {
  return (
    <div className="min-h-screen bg-slate-950 px-6 py-16 text-white sm:px-8 lg:px-10">
      <div className="mx-auto max-w-6xl">
        <div className="max-w-3xl">
          <div className="text-sm uppercase tracking-[0.25em] text-cyan-300">Website template system</div>
          <h1 className="mt-4 text-4xl font-semibold sm:text-5xl">
            Webflow-inspired site templates with the Omniweb AI agent built in.
          </h1>
          <p className="mt-5 text-lg leading-8 text-slate-300">
            This is the first coded scaffold for the website-builder direction: premium reusable sections, data-driven content, and a dedicated AI embed zone for each client site.
          </p>
        </div>

        <div className="mt-12 grid gap-6 lg:grid-cols-2">
          {siteTemplates.map((template) => (
            <article key={template.slug} className="overflow-hidden rounded-[2rem] border border-white/10 bg-gradient-to-br from-slate-900 via-slate-950 to-slate-950">
              <div className="border-b border-white/10 bg-[radial-gradient(circle_at_top_left,rgba(109,94,248,0.35),transparent_40%),radial-gradient(circle_at_bottom_right,rgba(56,189,248,0.22),transparent_35%)] px-6 py-8">
                <div className="inline-flex rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs uppercase tracking-[0.2em] text-cyan-300">
                  {template.category}
                </div>
                <h2 className="mt-5 text-3xl font-semibold">{template.name}</h2>
                <p className="mt-3 max-w-2xl text-sm leading-7 text-slate-300">{template.description}</p>
              </div>
              <div className="px-6 py-6">
                <div className="rounded-[1.5rem] border border-white/10 bg-black/20 p-5">
                  <div className="text-sm uppercase tracking-[0.2em] text-slate-500">Preview notes</div>
                  <div className="mt-3 text-sm text-slate-300">{template.thumbnailLabel}</div>
                  <div className="mt-4 flex flex-wrap gap-2">
                    {template.hero.highlights.map((item) => (
                      <span key={item} className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-slate-300">
                        {item}
                      </span>
                    ))}
                  </div>
                </div>
                <div className="mt-6 flex items-center justify-between">
                  <div>
                    <div className="text-xs uppercase tracking-[0.2em] text-slate-500">Industry</div>
                    <div className="mt-1 text-sm text-white">{template.industry}</div>
                  </div>
                  <Link href={`/templates/${template.slug}`} className="rounded-full bg-white px-4 py-2.5 text-sm font-semibold text-slate-950 transition hover:bg-slate-200">
                    Open preview
                  </Link>
                </div>
              </div>
            </article>
          ))}
        </div>
      </div>
    </div>
  );
}

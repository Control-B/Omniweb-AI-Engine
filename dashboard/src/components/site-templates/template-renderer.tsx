import Link from "next/link";
import type {
  AgentEmbedSection,
  CtaSection,
  FaqSection,
  FeaturesSection,
  SiteTemplate,
  SiteTemplateSection,
  StatsSection,
  TestimonialSection,
} from "@/lib/site-templates/types";

function SectionContainer({
  id,
  children,
}: {
  id?: string;
  children: React.ReactNode;
}) {
  return (
    <section id={id} className="mx-auto w-full max-w-6xl px-6 py-16 sm:px-8 lg:px-10">
      {children}
    </section>
  );
}

function renderSection(section: SiteTemplateSection) {
  switch (section.type) {
    case "stats":
      return <StatsBlock section={section} />;
    case "features":
      return <FeaturesBlock section={section} />;
    case "testimonials":
      return <TestimonialsBlock section={section} />;
    case "faq":
      return <FaqBlock section={section} />;
    case "cta":
      return <CtaBlock section={section} />;
    case "agent-embed":
      return <AgentEmbedBlock section={section} />;
    default:
      return null;
  }
}

function StatsBlock({ section }: { section: StatsSection }) {
  return (
    <SectionContainer>
      <div className="grid gap-4 md:grid-cols-3">
        {section.items.map((item) => (
          <div key={item.label} className="rounded-3xl border border-white/10 bg-white/5 p-6 backdrop-blur-sm">
            <div className="text-3xl font-semibold text-white">{item.value}</div>
            <div className="mt-2 text-sm text-slate-400">{item.label}</div>
          </div>
        ))}
      </div>
    </SectionContainer>
  );
}

function FeaturesBlock({ section }: { section: FeaturesSection }) {
  const anchorId = section.eyebrow?.startsWith("#") ? section.eyebrow.slice(1) : undefined;

  return (
    <SectionContainer id={anchorId}>
      <div className="max-w-3xl">
        {section.eyebrow && <div className="mb-3 text-sm uppercase tracking-[0.25em] text-cyan-300">{section.eyebrow.replace(/^#/, "")}</div>}
        <h2 className="text-3xl font-semibold text-white sm:text-4xl">{section.heading}</h2>
        {section.description && <p className="mt-4 text-lg text-slate-300">{section.description}</p>}
      </div>
      <div className="mt-10 grid gap-5 md:grid-cols-3">
        {section.items.map((item) => (
          <div key={item.title} className="rounded-3xl border border-white/10 bg-slate-950/40 p-6 shadow-[0_0_0_1px_rgba(255,255,255,0.02)]">
            <h3 className="text-lg font-semibold text-white">{item.title}</h3>
            <p className="mt-3 text-sm leading-6 text-slate-400">{item.description}</p>
          </div>
        ))}
      </div>
    </SectionContainer>
  );
}

function TestimonialsBlock({ section }: { section: TestimonialSection }) {
  return (
    <SectionContainer id="reviews">
      <h2 className="text-3xl font-semibold text-white sm:text-4xl">{section.heading}</h2>
      <div className="mt-10 grid gap-5 lg:grid-cols-2">
        {section.items.map((item) => (
          <div key={item.name} className="rounded-3xl border border-white/10 bg-white/5 p-8">
            <p className="text-lg leading-8 text-slate-200">“{item.quote}”</p>
            <div className="mt-6 text-sm text-slate-400">
              <div className="font-medium text-white">{item.name}</div>
              <div>{item.role}</div>
            </div>
          </div>
        ))}
      </div>
    </SectionContainer>
  );
}

function FaqBlock({ section }: { section: FaqSection }) {
  const heading = section.heading.replace(/^#faq\s*/i, "");
  return (
    <SectionContainer id="faq">
      <h2 className="text-3xl font-semibold text-white sm:text-4xl">{heading}</h2>
      <div className="mt-8 space-y-4">
        {section.items.map((item) => (
          <div key={item.question} className="rounded-2xl border border-white/10 bg-slate-950/40 p-5">
            <h3 className="text-base font-semibold text-white">{item.question}</h3>
            <p className="mt-2 text-sm leading-6 text-slate-400">{item.answer}</p>
          </div>
        ))}
      </div>
    </SectionContainer>
  );
}

function CtaBlock({ section }: { section: CtaSection }) {
  return (
    <SectionContainer>
      <div className="rounded-[2rem] border border-violet-400/20 bg-gradient-to-br from-violet-500/20 via-slate-900 to-cyan-500/10 p-8 shadow-2xl shadow-violet-900/20">
        <h2 className="text-3xl font-semibold text-white sm:text-4xl">{section.heading}</h2>
        <p className="mt-4 max-w-2xl text-lg text-slate-300">{section.description}</p>
        <div className="mt-8 flex flex-wrap gap-3">
          <button className="rounded-full bg-white px-5 py-3 text-sm font-semibold text-slate-950 transition hover:bg-slate-200">
            {section.primaryCta}
          </button>
          {section.secondaryCta && (
            <Link href="/demo" className="rounded-full border border-white/15 px-5 py-3 text-sm font-semibold text-white transition hover:bg-white/5">
              {section.secondaryCta}
            </Link>
          )}
        </div>
      </div>
    </SectionContainer>
  );
}

function AgentEmbedBlock({ section }: { section: AgentEmbedSection }) {
  return (
    <SectionContainer>
      <div className="grid gap-6 lg:grid-cols-[1.3fr_0.9fr] lg:items-start">
        <div>
          <h2 className="text-3xl font-semibold text-white sm:text-4xl">{section.heading}</h2>
          <p className="mt-4 max-w-2xl text-lg text-slate-300">{section.description}</p>
          <ul className="mt-6 space-y-3 text-sm text-slate-300">
            {section.bullets.map((bullet) => (
              <li key={bullet} className="flex items-start gap-3">
                <span className="mt-1 inline-block h-2 w-2 rounded-full bg-cyan-300" />
                <span>{bullet}</span>
              </li>
            ))}
          </ul>
        </div>
        <div className="rounded-[1.75rem] border border-cyan-400/20 bg-slate-950/60 p-6 backdrop-blur-sm">
          <div className="text-xs uppercase tracking-[0.25em] text-cyan-300">Embedded agent zone</div>
          <div className="mt-4 rounded-2xl border border-white/10 bg-gradient-to-br from-slate-900 via-slate-900 to-violet-950/50 p-5">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-base font-semibold text-white">Omniweb Voice Agent</div>
                <div className="text-sm text-slate-400">Ready to answer questions and book leads</div>
              </div>
              <div className="h-3 w-3 rounded-full bg-emerald-400 shadow-[0_0_16px_rgba(52,211,153,0.85)]" />
            </div>
            <div className="mt-6 rounded-2xl border border-white/10 bg-black/30 p-4 text-sm text-slate-300">
              “Hi — I’m your 24/7 AI front desk. Ask about pricing, availability, or book service now.”
            </div>
            <Link href="/demo" className="mt-5 inline-flex rounded-full bg-violet-500 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-violet-400">
              Preview agent demo
            </Link>
          </div>
        </div>
      </div>
    </SectionContainer>
  );
}

export function TemplateRenderer({ template }: { template: SiteTemplate }) {
  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top,#172554_0%,#0B1020_38%,#040712_100%)] text-white">
      <header className="sticky top-0 z-20 border-b border-white/10 bg-slate-950/70 backdrop-blur-xl">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4 sm:px-8 lg:px-10">
          <div>
            <div className="text-sm uppercase tracking-[0.25em] text-cyan-300">Omniweb Templates</div>
            <div className="text-xl font-semibold text-white">{template.name}</div>
          </div>
          <nav className="hidden gap-6 text-sm text-slate-300 md:flex">
            {template.nav.map((item) => (
              <a key={item.href} href={item.href} className="transition hover:text-white">
                {item.label}
              </a>
            ))}
          </nav>
          <Link href="/templates" className="rounded-full border border-white/10 px-4 py-2 text-sm text-white transition hover:bg-white/5">
            All templates
          </Link>
        </div>
      </header>

      <SectionContainer>
        <div className="grid gap-10 lg:grid-cols-[1.1fr_0.9fr] lg:items-center">
          <div>
            <div className="text-sm uppercase tracking-[0.25em] text-cyan-300">{template.hero.eyebrow}</div>
            <h1 className="mt-4 text-5xl font-semibold leading-tight text-white sm:text-6xl">
              {template.hero.heading}
            </h1>
            <p className="mt-6 max-w-2xl text-lg leading-8 text-slate-300">{template.hero.subheading}</p>
            <div className="mt-8 flex flex-wrap gap-3">
              <button className="rounded-full bg-white px-5 py-3 text-sm font-semibold text-slate-950 transition hover:bg-slate-200">
                {template.hero.primaryCta}
              </button>
              <Link href="/demo" className="rounded-full border border-white/10 px-5 py-3 text-sm font-semibold text-white transition hover:bg-white/5">
                {template.hero.secondaryCta}
              </Link>
            </div>
            <div className="mt-8 flex flex-wrap gap-3">
              {template.hero.highlights.map((highlight) => (
                <span key={highlight} className="rounded-full border border-white/10 bg-white/5 px-3 py-1.5 text-xs uppercase tracking-[0.16em] text-slate-300">
                  {highlight}
                </span>
              ))}
            </div>
          </div>

          <div className="rounded-[2rem] border border-white/10 bg-white/5 p-6 shadow-[0_20px_80px_rgba(14,165,233,0.12)] backdrop-blur-sm">
            <div className="rounded-[1.5rem] border border-white/10 bg-slate-950/80 p-6">
              <div className="flex items-center justify-between">
                <div>
                  <div className="text-sm uppercase tracking-[0.25em] text-cyan-300">AI Agent Embed</div>
                  <div className="mt-2 text-xl font-semibold text-white">{template.agentEmbed.title}</div>
                </div>
                <div className="rounded-full border border-emerald-400/30 bg-emerald-400/10 px-3 py-1 text-xs font-medium text-emerald-300">
                  Live-ready
                </div>
              </div>
              <p className="mt-4 text-sm leading-6 text-slate-400">{template.agentEmbed.description}</p>
              <div className="mt-5 rounded-2xl border border-white/10 bg-black/30 p-4 font-mono text-xs leading-6 text-slate-300">
                {template.agentEmbed.embedSnippet}
              </div>
              <div className="mt-4 text-xs uppercase tracking-[0.2em] text-slate-500">{template.agentEmbed.placementHint}</div>
              <Link href="/demo" className="mt-6 inline-flex rounded-full bg-violet-500 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-violet-400">
                {template.agentEmbed.buttonLabel}
              </Link>
            </div>
          </div>
        </div>
      </SectionContainer>

      {template.sections.map((section, index) => (
        <div key={`${section.type}-${index}`}>{renderSection(section)}</div>
      ))}
    </div>
  );
}

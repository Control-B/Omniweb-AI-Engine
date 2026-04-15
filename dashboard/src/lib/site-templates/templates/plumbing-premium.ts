import type { SiteTemplate } from "@/lib/site-templates/types";

export const plumbingPremiumTemplate: SiteTemplate = {
  slug: "plumbing-premium",
  name: "Plumbing Premium",
  category: "Home Services",
  description:
    "A dark, modern service-business template inspired by premium Webflow layouts with an always-available AI booking agent.",
  industry: "Plumbing",
  thumbnailLabel: "Premium dark service site",
  theme: {
    primary: "#6D5EF8",
    secondary: "#121A2B",
    accent: "#38BDF8",
    surface: "#0B1020",
    text: "#F8FAFC",
    mutedText: "#94A3B8",
  },
  nav: [
    { label: "Services", href: "#services" },
    { label: "Why Us", href: "#why-us" },
    { label: "Reviews", href: "#reviews" },
    { label: "FAQ", href: "#faq" },
  ],
  hero: {
    type: "hero",
    eyebrow: "24/7 AI receptionist + booking agent",
    heading: "A service-business website that converts visitors while you sleep.",
    subheading:
      "Pair a high-end Webflow-style site with an embedded Omniweb AI agent that answers questions, books jobs, and captures leads in real time.",
    primaryCta: "Launch this template",
    secondaryCta: "Preview AI agent flow",
    highlights: [
      "Embedded voice + chat agent",
      "After-hours lead capture",
      "High-trust service design",
      "Fast client customization",
    ],
  },
  sections: [
    {
      type: "stats",
      items: [
        { label: "Lead response time", value: "< 5 sec" },
        { label: "Missed calls recovered", value: "+38%" },
        { label: "Bookings automated", value: "67%" },
      ],
    },
    {
      type: "features",
      eyebrow: "#services",
      heading: "Built for local service brands that need speed and trust.",
      description:
        "Every section is code-driven, easy to clone, and ready to be customized for plumbers, HVAC, legal, med spas, clinics, and more.",
      items: [
        {
          title: "Conversion-first hero",
          description: "Clear value proposition, strong CTA hierarchy, and trust badges above the fold.",
        },
        {
          title: "Embedded AI agent block",
          description: "A dedicated section and sticky CTA slot for the Omniweb voice + chat assistant.",
        },
        {
          title: "Reusable section schema",
          description: "Sections are defined in TypeScript data so teams can clone and customize safely.",
        },
      ],
    },
    {
      type: "agent-embed",
      heading: "The AI agent is part of the template, not an afterthought.",
      description:
        "Each website template reserves a premium interaction zone for the Omniweb agent so visitors can ask questions, qualify themselves, and book instantly.",
      bullets: [
        "Sticky desktop CTA + mobile-safe prompt",
        "Custom greeting, brand colors, and industry prompt",
        "Supports multilingual chat and voice handoff",
      ],
    },
    {
      type: "features",
      eyebrow: "#why-us",
      heading: "How this template system scales across the SaaS.",
      items: [
        {
          title: "Template registry",
          description: "Admins can preview coded templates and use them as starting points for client builds.",
        },
        {
          title: "Agent-aware sections",
          description: "Every template can inject the right embed code, greeting strategy, and CTA copy for the attached agent.",
        },
        {
          title: "Fast industry cloning",
          description: "Switch copy, palette, services, and proof sections without redesigning from scratch.",
        },
      ],
    },
    {
      type: "testimonials",
      heading: "Templates that feel custom, not generic.",
      items: [
        {
          quote:
            "We launched a full plumbing site with the AI booking assistant in one week, and the experience looks better than most agency builds.",
          name: "Megan Lopez",
          role: "Founder, Northline Plumbing",
        },
        {
          quote:
            "The embedded agent converts late-night traffic that used to bounce. It feels like a real front-desk rep on the website.",
          name: "Jordan Patel",
          role: "COO, Apex Home Services",
        },
      ],
    },
    {
      type: "faq",
      heading: "#faq Frequently asked questions",
      items: [
        {
          question: "Can I swap the visual style for another industry?",
          answer: "Yes. The data model is industry-agnostic, so new templates can reuse the same components with different content and styling.",
        },
        {
          question: "How does the agent get embedded?",
          answer: "Each template includes an agent embed config with a CTA zone and script snippet placeholder that can be mapped to a client-specific widget.",
        },
        {
          question: "Can clients customize sections later?",
          answer: "That is the next layer: these coded templates become the structured basis for a visual editor and saved client variants.",
        },
      ],
    },
    {
      type: "cta",
      heading: "Turn this into your first premium client-site system.",
      description:
        "Use this scaffold as the basis for multiple verticals, then connect saved client content and live widget IDs from the CRM.",
      primaryCta: "Use this template",
      secondaryCta: "Open live agent demo",
    },
  ],
  agentEmbed: {
    title: "Embedded Omniweb Agent",
    description:
      "This slot becomes the live voice/chat assistant for the selected client site. The code snippet below is intentionally data-driven so it can be swapped per customer.",
    buttonLabel: "Preview agent experience",
    placementHint: "Recommended placement: lower-right sticky bubble + hero CTA inline preview card.",
    embedSnippet: `<script src=\"https://omniweb.ai/widget.js\" data-client=\"{{CLIENT_ID}}\" data-template=\"plumbing-premium\" async></script>`,
  },
};

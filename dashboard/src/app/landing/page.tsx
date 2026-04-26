"use client";

import Link from "next/link";
import { useState } from "react";
import { Check, Zap, Globe2, Mic, MessageSquare, ShoppingCart, BarChart3, Shield, ChevronRight } from "lucide-react";

const PLANS = [
  {
    id: "starter",
    label: "Starter",
    price: "$149",
    period: "/mo",
    tagline: "Perfect for small Shopify stores",
    highlight: false,
    color: "border-slate-700 bg-slate-900/60",
    badgeColor: "bg-slate-800 text-slate-300",
    btnClass: "bg-white/10 hover:bg-white/20 text-white border border-white/20",
    features: [
      "1 AI storefront agent",
      "500 conversations / month",
      "Text chat + Voice mode",
      "10 languages supported",
      "Knowledge base (5 docs)",
      "Basic analytics dashboard",
      "Email support",
    ],
  },
  {
    id: "growth",
    label: "Growth",
    price: "$299",
    period: "/mo",
    tagline: "For growing stores & teams",
    highlight: true,
    color: "border-violet-500/60 bg-gradient-to-b from-violet-950/80 to-slate-900/80",
    badgeColor: "bg-violet-600 text-white",
    btnClass: "bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 text-white shadow-lg shadow-violet-500/25",
    features: [
      "3 AI storefront agents",
      "2,000 conversations / month",
      "Text chat + Voice mode",
      "All 26 languages",
      "Unlimited knowledge base docs",
      "Advanced analytics + conversation summaries",
      "Native Shopify app embed",
      "Priority email & chat support",
    ],
  },
  {
    id: "pro",
    label: "Pro",
    price: "$499",
    period: "/mo",
    tagline: "For agencies & high-volume stores",
    highlight: false,
    color: "border-emerald-700/50 bg-slate-900/60",
    badgeColor: "bg-emerald-800 text-emerald-200",
    btnClass: "bg-white/10 hover:bg-white/20 text-white border border-white/20",
    features: [
      "Unlimited AI agents",
      "Unlimited conversations",
      "Text chat + Voice mode",
      "All 26 languages",
      "Unlimited knowledge base",
      "Full analytics suite",
      "White-label widget",
      "Multi-store support",
      "Custom integrations",
      "Dedicated account support",
    ],
  },
];

const FEATURES = [
  { icon: Mic, title: "Voice + Text AI", desc: "Shoppers can chat by typing or speaking in their native language — your agent replies in kind." },
  { icon: Globe2, title: "26 Languages", desc: "Auto-detect or let shoppers choose. ElevenLabs TTS delivers natural-sounding speech in every language." },
  { icon: ShoppingCart, title: "Cart-Aware", desc: "The agent adds products, reminds shoppers about abandoned carts, and answers product questions — without touching finances." },
  { icon: Shield, title: "Human Escalation", desc: "Any checkout, refund, or financial request is immediately escalated to a human rep — zero financial risk." },
  { icon: BarChart3, title: "Conversation Summaries", desc: "Every session generates an AI summary so you see exactly what shoppers asked, their intent, and lead score." },
  { icon: MessageSquare, title: "Knowledge Base", desc: "Upload PDFs, paste URLs, or add text. Your agent uses your docs to answer product and policy questions accurately." },
];

export default function LandingPage() {
  const [annual, setAnnual] = useState(false);

  const discount = (price: string) => {
    const n = parseInt(price.replace("$", ""));
    return `$${Math.round(n * 0.8)}`;
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 antialiased">
      {/* Nav */}
      <nav className="border-b border-white/[0.06] px-6 py-4 flex items-center justify-between max-w-7xl mx-auto">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center">
            <Zap className="w-4 h-4 text-white" />
          </div>
          <span className="font-bold text-white text-lg">Omniweb AI</span>
        </div>
        <div className="flex items-center gap-3">
          <Link href="/login" className="text-sm text-slate-400 hover:text-white transition-colors">Sign in</Link>
          <Link href="/register" className="px-4 py-2 rounded-full bg-white text-slate-900 text-sm font-semibold hover:bg-slate-100 transition-colors">
            Get started
          </Link>
        </div>
      </nav>

      {/* Hero */}
      <section className="py-20 px-6 text-center max-w-4xl mx-auto">
        <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full border border-indigo-500/30 bg-indigo-500/10 text-indigo-300 text-xs font-semibold uppercase tracking-wider mb-8">
          <Zap className="w-3.5 h-3.5" />
          AI-Powered Shopify Storefront Agent
        </div>
        <h1 className="text-4xl sm:text-5xl lg:text-6xl font-extrabold tracking-tight text-white mb-6 leading-tight">
          Your store, speaking{" "}
          <span className="bg-gradient-to-r from-indigo-400 via-violet-400 to-pink-400 bg-clip-text text-transparent">
            every language
          </span>
        </h1>
        <p className="text-lg text-slate-400 max-w-2xl mx-auto mb-10 leading-relaxed">
          Omniweb AI adds a voice and text agent to your Shopify store. It answers questions, recommends products, manages carts, and captures leads — 24/7, in 26 languages.
        </p>
        <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
          <Link
            href="/register"
            className="flex items-center gap-2 px-8 py-3.5 rounded-full bg-gradient-to-r from-indigo-600 to-violet-600 text-white font-bold text-sm hover:from-indigo-500 hover:to-violet-500 shadow-xl shadow-indigo-500/30 transition-all hover:scale-105"
          >
            Start free trial <ChevronRight className="w-4 h-4" />
          </Link>
          <Link
            href="/demo"
            className="flex items-center gap-2 px-8 py-3.5 rounded-full border border-white/15 text-slate-300 font-semibold text-sm hover:bg-white/5 transition-colors"
          >
            Live demo →
          </Link>
        </div>
      </section>

      {/* Features grid */}
      <section className="py-16 px-6 max-w-6xl mx-auto">
        <div className="text-center mb-12">
          <h2 className="text-2xl sm:text-3xl font-bold text-white mb-3">Everything your shoppers need</h2>
          <p className="text-slate-400">Built for Shopify. Designed for conversions.</p>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
          {FEATURES.map(({ icon: Icon, title, desc }) => (
            <div key={title} className="rounded-2xl border border-white/[0.07] bg-slate-900/50 p-6 space-y-3 hover:border-indigo-500/30 transition-colors">
              <div className="w-10 h-10 rounded-xl bg-indigo-500/10 flex items-center justify-center">
                <Icon className="w-5 h-5 text-indigo-400" />
              </div>
              <h3 className="font-semibold text-white">{title}</h3>
              <p className="text-sm text-slate-400 leading-relaxed">{desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Pricing */}
      <section className="py-16 px-6 max-w-6xl mx-auto">
        <div className="text-center mb-12">
          <h2 className="text-2xl sm:text-3xl font-bold text-white mb-3">Simple, transparent pricing</h2>
          <p className="text-slate-400 mb-6">No hidden fees. Cancel any time.</p>
          {/* Annual toggle */}
          <div className="inline-flex items-center gap-3 p-1 rounded-full border border-white/10 bg-slate-900">
            <button
              onClick={() => setAnnual(false)}
              className={`px-4 py-1.5 rounded-full text-sm font-medium transition-all ${!annual ? "bg-white text-slate-900" : "text-slate-400 hover:text-white"}`}
            >
              Monthly
            </button>
            <button
              onClick={() => setAnnual(true)}
              className={`px-4 py-1.5 rounded-full text-sm font-medium transition-all ${annual ? "bg-white text-slate-900" : "text-slate-400 hover:text-white"}`}
            >
              Annual <span className="text-emerald-400 text-xs font-bold ml-1">-20%</span>
            </button>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 items-start">
          {PLANS.map((plan) => (
            <div
              key={plan.id}
              className={`relative rounded-2xl border p-7 space-y-6 ${plan.color} ${plan.highlight ? "scale-[1.03] shadow-2xl shadow-violet-500/20 z-10" : ""} transition-all`}
            >
              {plan.highlight && (
                <div className="absolute -top-4 left-1/2 -translate-x-1/2">
                  <span className="px-4 py-1 rounded-full text-[10px] font-extrabold uppercase tracking-widest bg-gradient-to-r from-violet-600 to-indigo-600 text-white shadow-lg">
                    Most Popular
                  </span>
                </div>
              )}

              <div>
                <div className="flex items-center justify-between mb-1">
                  <span className={`text-xs font-bold uppercase tracking-widest px-2.5 py-1 rounded-full ${plan.badgeColor}`}>
                    {plan.label}
                  </span>
                </div>
                <p className="text-slate-400 text-sm mt-2">{plan.tagline}</p>
              </div>

              <div className="flex items-end gap-1">
                <span className="text-4xl font-extrabold text-white">
                  {annual ? discount(plan.price) : plan.price}
                </span>
                <span className="text-slate-400 text-sm mb-1.5">/mo</span>
                {annual && (
                  <span className="ml-2 text-xs text-emerald-400 font-semibold mb-1.5">billed annually</span>
                )}
              </div>

              <ul className="space-y-2.5">
                {plan.features.map((f) => (
                  <li key={f} className="flex items-start gap-2.5 text-sm text-slate-300">
                    <Check className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
                    {f}
                  </li>
                ))}
              </ul>

              <Link
                href="/register"
                className={`block w-full py-3 text-center rounded-xl font-bold text-sm transition-all ${plan.btnClass}`}
              >
                Get started
              </Link>
            </div>
          ))}
        </div>
      </section>

      {/* Financial Policy callout */}
      <section className="py-12 px-6 max-w-3xl mx-auto">
        <div className="rounded-2xl border border-amber-500/20 bg-amber-500/[0.05] p-7 text-center space-y-3">
          <Shield className="w-8 h-8 text-amber-400 mx-auto" />
          <h3 className="font-bold text-white">Zero Financial Risk — By Design</h3>
          <p className="text-sm text-slate-400 leading-relaxed max-w-lg mx-auto">
            Your Omniweb AI agent can add products to carts and send cart reminders, but it <strong className="text-white">cannot process checkouts, issue refunds, or handle any financial transactions</strong>. Every financial request is escalated to a human representative immediately.
          </p>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-white/[0.06] py-10 px-6 text-center">
        <div className="flex items-center justify-center gap-2 mb-4">
          <div className="w-6 h-6 rounded-md bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center">
            <Zap className="w-3.5 h-3.5 text-white" />
          </div>
          <span className="font-semibold text-white">Omniweb AI</span>
        </div>
        <p className="text-xs text-slate-600">
          © {new Date().getFullYear()} Omniweb AI. All rights reserved. ·{" "}
          <a href="https://omniweb.ai/terms" target="_blank" rel="noopener noreferrer" className="hover:text-slate-400 transition-colors">Terms</a>
          {" · "}
          <a href="https://omniweb.ai/privacy" target="_blank" rel="noopener noreferrer" className="hover:text-slate-400 transition-colors">Privacy</a>
        </p>
      </footer>
    </div>
  );
}

'use client';

import Link from "next/link";
import { Activity, AlertTriangle, ArrowRight, CheckCircle2, KeyRound, PlayCircle, Server, Workflow } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { SiteHeader } from "@/components/site-header";
import { SiteFooter } from "@/components/site-footer";
import { PageIntro } from "@/components/page-intro";
import { usePageTitle } from "@/components/use-page-title";

const surfaces = [
  {
    title: "Frontend shell",
    status: "Online",
    detail: "Landing, docs, pricing, dashboard, projects, analyze, playground, and CAD routes are reachable in the app.",
    tone: "text-emerald-700 bg-emerald-50 border-emerald-200",
  },
  {
    title: "Analysis API",
    status: "Backend-dependent",
    detail: "Interactive analysis still depends on NEXT_PUBLIC_API_URL or a local backend at http://localhost:8000.",
    tone: "text-amber-800 bg-amber-50 border-amber-200",
  },
  {
    title: "Trust boundary",
    status: "Explicit",
    detail: "The frontend now says what is real, what is mocked, and what still needs backend reachability.",
    tone: "text-sky-800 bg-sky-50 border-sky-200",
  },
];

const nextSteps = [
  {
    title: "Create or review API keys",
    href: "/dashboard/keys",
    icon: KeyRound,
    copy: "Start with credentials before you try to make the rest of the product feel real.",
  },
  {
    title: "Run the playground",
    href: "/playground",
    icon: PlayCircle,
    copy: "Use a real file and see whether the backend contract is reachable right now.",
  },
  {
    title: "Read the implementation docs",
    href: "/docs",
    icon: Workflow,
    copy: "Check endpoints, request shape, and frontend assumptions against the documented contract.",
  },
];

export default function StatusPage() {
  usePageTitle("Status | Circuit.AI");
  return (
    <div className="min-h-screen bg-[#edf2f7] text-slate-950">
      <SiteHeader />

      <main>
        <PageIntro
          eyebrow="Platform status"
          title="What is live, what is simulated, and what still needs backend wiring."
          description="This page exists so the frontend does not quietly overclaim. It should help users understand the real operating boundary of the product at any given moment."
          actions={
            <Button asChild className="rounded-full bg-slate-900 text-white hover:bg-slate-800">
              <Link href="/playground">
                Open playground
                <ArrowRight className="ml-2 h-4 w-4" />
              </Link>
            </Button>
          }
          aside={
            <div className="space-y-4">
              <div className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">Why this route matters</div>
              <div className="rounded-3xl border border-slate-200 bg-slate-50 p-4 text-sm leading-6 text-slate-600">
                Strong backends with fragmented frontend history need one place where current truth beats stale implication.
              </div>
            </div>
          }
        />

        <section className="mx-auto max-w-7xl px-4 py-12 sm:px-6 lg:px-8">
          <div className="grid gap-6 lg:grid-cols-3">
            {surfaces.map((surface) => (
              <Card key={surface.title} className={`rounded-[1.75rem] border shadow-[0_18px_40px_rgba(15,23,42,0.04)] ${surface.tone}`}>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-xl">
                    {surface.status === "Online" ? <CheckCircle2 className="h-5 w-5" /> : <AlertTriangle className="h-5 w-5" />}
                    {surface.title}
                  </CardTitle>
                  <CardDescription className="text-current/80">{surface.status}</CardDescription>
                </CardHeader>
                <CardContent className="text-sm leading-6 text-current/90">
                  {surface.detail}
                </CardContent>
              </Card>
            ))}
          </div>

          <div className="mt-8 grid gap-6 lg:grid-cols-[1.35fr_1fr]">
            <Card className="rounded-[2rem] border-slate-200/80 bg-white/90 shadow-[0_24px_55px_rgba(15,23,42,0.05)]">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-2xl text-slate-950">
                  <Server className="h-5 w-5 text-slate-700" />
                  Backend expectation
                </CardTitle>
                <CardDescription className="text-base leading-7 text-slate-600">
                  The frontend currently expects a reachable analysis service for live results.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4 text-sm text-slate-700">
                <div className="rounded-[1.5rem] border border-slate-200 bg-slate-50 p-4">
                  <div className="font-semibold text-slate-900">Default target</div>
                  <div className="mt-1 font-mono text-xs text-slate-600">http://localhost:8000/analyze</div>
                </div>
                <div className="rounded-[1.5rem] border border-slate-200 bg-slate-50 p-4">
                  <div className="font-semibold text-slate-900">Override</div>
                  <div className="mt-1 text-slate-600">
                    Set <code className="rounded bg-white px-1.5 py-0.5 text-xs">NEXT_PUBLIC_API_URL</code> to move playground and analysis routes to the backend you actually want to test.
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card className="rounded-[2rem] border-slate-200/80 bg-[#0f172a] text-slate-100 shadow-[0_26px_70px_rgba(15,23,42,0.18)]">
              <CardHeader>
                <CardTitle className="text-2xl text-white">Recommended flow</CardTitle>
                <CardDescription className="text-base leading-7 text-slate-300">
                  Use the product in this order when the system is still consolidating.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                {nextSteps.map((step) => {
                  const Icon = step.icon;
                  return (
                    <Link
                      key={step.title}
                      href={step.href}
                      className="block rounded-[1.5rem] border border-white/10 bg-white/5 p-4 transition-transform hover:-translate-y-1"
                    >
                      <div className="flex items-center gap-3 text-white">
                        <Icon className="h-4 w-4" />
                        <span className="font-semibold">{step.title}</span>
                      </div>
                      <p className="mt-2 text-sm leading-6 text-slate-300">{step.copy}</p>
                    </Link>
                  );
                })}
              </CardContent>
            </Card>
          </div>
        </section>
      </main>

      <SiteFooter />
    </div>
  );
}

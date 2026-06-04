"use client";

import Link from "next/link";
import {
  Activity,
  ArrowRight,
  CircuitBoard,
  Download,
  Eye,
  KeyRound,
  PackageCheck,
  PlayCircle,
  ShieldCheck,
  Workflow,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { SiteHeader } from "@/components/site-header";
import { SiteFooter } from "@/components/site-footer";
import { PageIntro } from "@/components/page-intro";
import { usePageTitle } from "@/components/use-page-title";

const commandCards = [
  {
    href: "/dashboard/keys",
    title: "API keys",
    copy: "Start here when you need the rest of the frontend to stop guessing about auth.",
    icon: KeyRound,
  },
  {
    href: "/playground",
    title: "Playground",
    copy: "Run a request against the actual backend target before you build UX assumptions on top of it.",
    icon: PlayCircle,
  },
  {
    href: "/status",
    title: "Status",
    copy: "Check what is live, simulated, or backend-dependent right now.",
    icon: ShieldCheck,
  },
  {
    href: "/analyze",
    title: "Workbench",
    copy: "Move into the shared studio shell when image-level analysis needs downstream component, project, and CAD context.",
    icon: CircuitBoard,
  },
];

const demoSignals = [
  { label: "Analyses surfaced", value: "24", note: "Demo telemetry" },
  { label: "Components identified", value: "156", note: "Sample data" },
  { label: "Projects created", value: "8", note: "Sample data" },
  { label: "Value generated", value: "$45.67", note: "Sample data" },
];

export default function DashboardPage() {
  usePageTitle("Dashboard | Circuit.AI");
  return (
    <div className="min-h-screen bg-[#edf2f7] text-slate-950">
      <SiteHeader />

      <main>
        <PageIntro
          eyebrow="Control surface"
          title="Use the dashboard as a control surface, not a fake analytics wall."
          description="This frontend still contains demo telemetry, but the page should already help users reach the real trust anchors: auth, request validation, platform status, and deeper engineering surfaces."
          actions={
            <>
              <Button asChild className="rounded-full bg-slate-900 text-white hover:bg-slate-800">
                <Link href="/dashboard/keys">
                  <KeyRound className="mr-2 h-4 w-4" />
                  Manage API keys
                </Link>
              </Button>
              <Button asChild variant="outline" className="rounded-full border-slate-300 bg-white/80">
                <Link href="/status">
                  <ShieldCheck className="mr-2 h-4 w-4" />
                  Review status
                </Link>
              </Button>
            </>
          }
          aside={
            <div className="space-y-4">
              <div className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">Frontend rule</div>
              <div className="rounded-3xl border border-slate-200 bg-slate-50 p-4">
                <div className="flex items-center gap-2 text-sm font-semibold text-slate-900">
                  <Workflow className="h-4 w-4 text-slate-700" />
                  What this page should do
                </div>
                <p className="mt-2 text-sm leading-6 text-slate-600">
                  Keep the user oriented. They should know where to get a key, where to validate a request, where to inspect backend truth, and where the advanced workspace begins.
                </p>
              </div>
            </div>
          }
        />

        <section className="mx-auto max-w-7xl px-4 py-12 sm:px-6 lg:px-8">
          <div className="grid gap-6 lg:grid-cols-[0.9fr_1.1fr]">
            <Card className="rounded-[2rem] border-slate-200/80 bg-[#0f172a] text-slate-100 shadow-[0_26px_70px_rgba(15,23,42,0.18)]">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-2xl text-white">
                  <Activity className="h-5 w-5 text-cyan-300" />
                  Command paths
                </CardTitle>
                <CardDescription className="text-base leading-7 text-slate-300">
                  These are the routes that currently matter most for a trustworthy frontend.
                </CardDescription>
              </CardHeader>
              <CardContent className="grid gap-4">
                {commandCards.map((card) => {
                  const Icon = card.icon;
                  return (
                    <Link key={card.title} href={card.href} className="group rounded-[1.5rem] border border-white/10 bg-white/5 p-5 transition-transform hover:-translate-y-1">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3 text-white">
                          <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-white/10">
                            <Icon className="h-5 w-5" />
                          </div>
                          <div className="text-lg font-semibold">{card.title}</div>
                        </div>
                        <ArrowRight className="h-4 w-4 text-slate-400 transition-transform group-hover:translate-x-1" />
                      </div>
                      <p className="mt-3 text-sm leading-6 text-slate-300">{card.copy}</p>
                    </Link>
                  );
                })}
              </CardContent>
            </Card>

            <div className="grid gap-6">
              <div className="grid gap-4 sm:grid-cols-2">
                {demoSignals.map((signal) => (
                  <Card key={signal.label} className="rounded-[1.5rem] border-slate-200/80 bg-white/90 shadow-[0_18px_40px_rgba(15,23,42,0.05)]">
                    <CardHeader className="pb-2">
                      <CardDescription className="text-sm uppercase tracking-[0.16em] text-slate-500">{signal.label}</CardDescription>
                      <CardTitle className="text-4xl text-slate-950">{signal.value}</CardTitle>
                    </CardHeader>
                    <CardContent className="text-sm text-slate-500">{signal.note}</CardContent>
                  </Card>
                ))}
              </div>

              <Card className="rounded-[2rem] border-slate-200/80 bg-white/90 shadow-[0_24px_55px_rgba(15,23,42,0.05)]">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-2xl text-slate-950">
                    <PackageCheck className="h-5 w-5 text-slate-700" />
                    Why the dashboard exists
                  </CardTitle>
                  <CardDescription className="text-base leading-7 text-slate-600">
                    It should bridge the user from abstract product promises into concrete, reachable surfaces.
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4 text-sm leading-6 text-slate-600">
                  <p>The current metrics are still demo data. That is fine as long as the page is honest about it and routes the user to the real control points instead of pretending the shell is already a finished operating center.</p>
                  <div className="grid gap-3 sm:grid-cols-2">
                    <Link href="/playground" className="rounded-[1.25rem] border border-slate-200 bg-slate-50 p-4 transition-colors hover:bg-slate-100">
                      <div className="flex items-center gap-2 text-sm font-semibold text-slate-900">
                        <PlayCircle className="h-4 w-4" />
                        Validate a live request
                      </div>
                    </Link>
                    <Link href="/docs" className="rounded-[1.25rem] border border-slate-200 bg-slate-50 p-4 transition-colors hover:bg-slate-100">
                      <div className="flex items-center gap-2 text-sm font-semibold text-slate-900">
                        <Eye className="h-4 w-4" />
                        Read the contract
                      </div>
                    </Link>
                    <Link href="/projects" className="rounded-[1.25rem] border border-slate-200 bg-slate-50 p-4 transition-colors hover:bg-slate-100">
                      <div className="flex items-center gap-2 text-sm font-semibold text-slate-900">
                        <CircuitBoard className="h-4 w-4" />
                        Browse project templates
                      </div>
                    </Link>
                    <Link href="/dashboard/keys" className="rounded-[1.25rem] border border-slate-200 bg-slate-50 p-4 transition-colors hover:bg-slate-100">
                      <div className="flex items-center gap-2 text-sm font-semibold text-slate-900">
                        <Download className="h-4 w-4" />
                        Issue credentials
                      </div>
                    </Link>
                  </div>
                </CardContent>
              </Card>
            </div>
          </div>
        </section>
      </main>

      <SiteFooter />
    </div>
  );
}

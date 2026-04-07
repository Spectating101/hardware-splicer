'use client';

import { useState } from 'react';
import Link from 'next/link';
import { motion } from 'framer-motion';
import {
  ArrowRight,
  Bot,
  Check,
  CircuitBoard,
  Code,
  Copy,
  Factory,
  KeyRound,
  PackageCheck,
  Radar,
  ShieldCheck,
  Sparkles,
  Terminal,
  Wrench,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { SiteHeader } from '@/components/site-header';
import { SiteFooter } from '@/components/site-footer';
import { usePageTitle } from '@/components/use-page-title';

const capabilityLayers = [
  {
    icon: Radar,
    title: 'Vision and forensic analysis',
    copy: 'Board imaging, component detection, OCR enrichment, and confidence-scored findings for salvage, repair, and engineering triage.',
  },
  {
    icon: CircuitBoard,
    title: 'KiCad-aware validation',
    copy: 'Geometry parsing, rule checks, issue surfacing, and design context that can push beyond image-only inspection.',
  },
  {
    icon: PackageCheck,
    title: 'Minting and procurement lock',
    copy: 'BOM synthesis, lock-ratio visibility, action plans, and artifact bundles for deterministic operator review.',
  },
  {
    icon: Factory,
    title: 'Repair and fabrication loop',
    copy: 'The stack is designed to extend from recommendations into CAM, robotic repair, and guided execution surfaces.',
  },
];

const productSurfaces = [
  {
    href: '/analyze',
    title: 'Workbench',
    copy: 'Open the shared studio shell and move from board inspection into component, project, and CAD views.',
    accent: 'border-slate-900 bg-slate-900 text-white',
  },
  {
    href: '/dashboard/keys',
    title: 'API keys',
    copy: 'Issue and manage credentials so the rest of the stack has a clean trust boundary.',
    accent: 'border-cyan-200 bg-cyan-50 text-cyan-900',
  },
  {
    href: '/playground',
    title: 'Playground',
    copy: 'Run a request end to end, inspect payload shape, and confirm which backend target is actually live.',
    accent: 'border-orange-200 bg-orange-50 text-orange-900',
  },
  {
    href: '/docs',
    title: 'Documentation',
    copy: 'Keep the frontend honest about auth, endpoints, request contracts, and SDK expectations.',
    accent: 'border-slate-200 bg-white text-slate-900',
  },
  {
    href: '/status',
    title: 'Status',
    copy: 'Make the current trust boundary explicit: what is live, what is mocked, and what still depends on backend availability.',
    accent: 'border-emerald-200 bg-emerald-50 text-emerald-900',
  },
];

const workflowSteps = [
  {
    title: 'Inspect',
    copy: 'Start from a PCB image or design artifact and recover structured signal from it.',
  },
  {
    title: 'Validate',
    copy: 'Surface issues, confidence, readiness, and lock gaps instead of dumping raw backend output.',
  },
  {
    title: 'Mint',
    copy: 'Package BOM, artifact, and evidence flows so an operator can make a go or no-go decision.',
  },
  {
    title: 'Act',
    copy: 'Carry the system forward into repair, fabrication, or engineering follow-up instead of stopping at analysis.',
  },
];

const curlExample = `curl -X POST "https://api.circuit-ai.com/analyze" \\
  -H "Authorization: Bearer YOUR_API_KEY" \\
  -H "Content-Type: multipart/form-data" \\
  -F "image=@pcb_image.jpg"`;

const pythonExample = `import circuitai

client = circuitai.Client(api_key="YOUR_API_KEY")
result = client.analyze_pcb("pcb_image.jpg")

print(result.total_value)
for component in result.components:
    print(component.name, component.confidence)`;

export default function HomePage() {
  usePageTitle('Circuit.AI | PCB Intelligence Platform');
  const [copiedCode, setCopiedCode] = useState<string | null>(null);

  const copyToClipboard = (code: string, id: string) => {
    navigator.clipboard.writeText(code);
    setCopiedCode(id);
    setTimeout(() => setCopiedCode(null), 1600);
  };

  return (
    <div className="min-h-screen bg-[#edf2f7] text-slate-950">
      <SiteHeader />

      <main>
        <section className="relative overflow-hidden border-b border-slate-200/80 bg-[radial-gradient(circle_at_top_left,rgba(14,165,233,0.20),transparent_28%),radial-gradient(circle_at_80%_18%,rgba(249,115,22,0.18),transparent_24%),linear-gradient(180deg,#fbfdff_0%,#edf4fa_60%,#edf2f7_100%)]">
          <div className="mx-auto grid max-w-7xl gap-10 px-4 py-14 sm:px-6 lg:grid-cols-[1.15fr_0.85fr] lg:px-8 lg:py-20">
            <div>
              <div className="mb-5 inline-flex items-center rounded-full border border-slate-200 bg-white/80 px-3 py-1 text-xs font-semibold uppercase tracking-[0.26em] text-slate-600 shadow-sm">
                Hardware intelligence stack
              </div>
              <motion.h1
                initial={{ opacity: 0, y: 18 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.55 }}
                className="max-w-4xl text-5xl font-semibold tracking-tight text-slate-950 sm:text-6xl"
              >
                One frontend for PCB inspection, validation, minting, and the path to fabrication.
              </motion.h1>
              <motion.p
                initial={{ opacity: 0, y: 18 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.55, delay: 0.08 }}
                className="mt-6 max-w-3xl text-lg leading-8 text-slate-600"
              >
                Circuit.AI is not just an image-analysis demo. The backend already spans vision, KiCad-aware validation,
                procurement lock, and operator-facing evidence flows. The frontend should make that depth legible, trustworthy,
                and usable.
              </motion.p>

              <motion.div
                initial={{ opacity: 0, y: 18 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.55, delay: 0.16 }}
                className="mt-8 flex flex-wrap gap-3"
              >
                <Button asChild size="lg" className="rounded-full bg-slate-900 text-white hover:bg-slate-800">
                  <Link href="/analyze">
                    <CircuitBoard className="mr-2 h-5 w-5" />
                    Open workbench
                  </Link>
                </Button>
                <Button asChild size="lg" variant="outline" className="rounded-full border-slate-300 bg-white/80 text-slate-900 hover:bg-white">
                  <Link href="/playground">
                    <Terminal className="mr-2 h-5 w-5" />
                    Validate request
                  </Link>
                </Button>
                <Button asChild size="lg" variant="outline" className="rounded-full border-slate-300 bg-white/80 text-slate-900 hover:bg-white">
                  <Link href="/dashboard/keys">
                    <KeyRound className="mr-2 h-5 w-5" />
                    Issue API keys
                  </Link>
                </Button>
              </motion.div>

              <div className="mt-10 grid gap-4 sm:grid-cols-3">
                {[
                  ['Vision + OCR', 'Board imagery into structured findings'],
                  ['Validation + gating', 'Issues, confidence, and readiness surfaced explicitly'],
                  ['Minting + execution', 'Artifacts and next-step packages for operators'],
                ].map(([title, copy]) => (
                  <div key={title} className="rounded-3xl border border-slate-200/80 bg-white/80 p-4 shadow-[0_18px_40px_rgba(15,23,42,0.04)]">
                    <div className="text-sm font-semibold text-slate-900">{title}</div>
                    <p className="mt-2 text-sm leading-6 text-slate-600">{copy}</p>
                  </div>
                ))}
              </div>
            </div>

            <motion.div
              initial={{ opacity: 0, scale: 0.98 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ duration: 0.6, delay: 0.12 }}
              className="rounded-[2rem] border border-slate-200/80 bg-[#0f172a] p-6 text-slate-100 shadow-[0_30px_80px_rgba(15,23,42,0.22)]"
            >
              <div className="flex items-center justify-between">
                <div>
                  <div className="text-xs font-semibold uppercase tracking-[0.24em] text-cyan-300">System view</div>
                  <div className="mt-2 text-2xl font-semibold text-white">Inspect to act</div>
                </div>
                <div className="rounded-full border border-cyan-400/30 bg-cyan-400/10 px-3 py-1 text-xs font-medium text-cyan-200">
                  Backend-depth aware
                </div>
              </div>

              <div className="mt-6 space-y-4">
                {workflowSteps.map((step, index) => (
                  <div key={step.title} className="flex gap-4 rounded-3xl border border-white/10 bg-white/5 p-4">
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-white/10 text-sm font-semibold text-white">
                      0{index + 1}
                    </div>
                    <div>
                      <div className="text-sm font-semibold text-white">{step.title}</div>
                      <p className="mt-1 text-sm leading-6 text-slate-300">{step.copy}</p>
                    </div>
                  </div>
                ))}
              </div>

              <div className="mt-6 grid gap-3 sm:grid-cols-2">
                <div className="rounded-3xl border border-white/10 bg-white/5 p-4">
                  <div className="flex items-center gap-2 text-sm font-semibold text-white">
                    <ShieldCheck className="h-4 w-4 text-emerald-300" />
                    Trust boundary
                  </div>
                  <p className="mt-2 text-sm leading-6 text-slate-300">
                    Keys, docs, and backend status are first-class instead of hidden under broken buttons or implied magic.
                  </p>
                </div>
                <div className="rounded-3xl border border-white/10 bg-white/5 p-4">
                  <div className="flex items-center gap-2 text-sm font-semibold text-white">
                    <Bot className="h-4 w-4 text-orange-300" />
                    Future-facing
                  </div>
                  <p className="mt-2 text-sm leading-6 text-slate-300">
                    The surface is ready to grow into CAD, repair orchestration, and operator-grade evidence review.
                  </p>
                </div>
              </div>
            </motion.div>
          </div>
        </section>

        <section className="mx-auto max-w-7xl px-4 py-14 sm:px-6 lg:px-8">
          <div className="mb-8 flex items-end justify-between gap-4">
            <div>
              <div className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">Capability layers</div>
              <h2 className="mt-3 text-3xl font-semibold tracking-tight text-slate-950">The backend already has more depth than the current frontend lets on.</h2>
            </div>
            <Button asChild variant="outline" className="hidden rounded-full border-slate-300 bg-white md:flex">
              <Link href="/status">
                See platform status
                <ArrowRight className="ml-2 h-4 w-4" />
              </Link>
            </Button>
          </div>

          <div className="grid gap-6 md:grid-cols-2 xl:grid-cols-4">
            {capabilityLayers.map((layer) => {
              const Icon = layer.icon;
              return (
                <Card key={layer.title} className="rounded-[1.75rem] border-slate-200/80 bg-white/85 shadow-[0_20px_55px_rgba(15,23,42,0.05)]">
                  <CardHeader>
                    <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-2xl bg-slate-900 text-white">
                      <Icon className="h-5 w-5" />
                    </div>
                    <CardTitle className="text-xl text-slate-950">{layer.title}</CardTitle>
                    <CardDescription className="text-base leading-7 text-slate-600">{layer.copy}</CardDescription>
                  </CardHeader>
                </Card>
              );
            })}
          </div>
        </section>

        <section className="border-y border-slate-200/80 bg-white/70">
          <div className="mx-auto max-w-7xl px-4 py-14 sm:px-6 lg:px-8">
            <div className="grid gap-8 lg:grid-cols-[0.9fr_1.1fr]">
              <div>
                <div className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">Public surfaces</div>
                <h2 className="mt-3 text-3xl font-semibold tracking-tight text-slate-950">The public frontend should guide users into the right depth, not dump them into disconnected pages.</h2>
                <p className="mt-4 max-w-2xl text-base leading-7 text-slate-600">
                  These are the routes that matter first: establish trust, expose the contract, verify a live request path, and keep the system honest about what depends on backend availability.
                </p>
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                {productSurfaces.map((surface) => (
                  <Link
                    key={surface.title}
                    href={surface.href}
                    className={`group rounded-[1.75rem] border p-5 shadow-[0_16px_36px_rgba(15,23,42,0.04)] transition-transform hover:-translate-y-1 ${surface.accent}`}
                  >
                    <div className="flex items-center justify-between">
                      <div className="text-lg font-semibold">{surface.title}</div>
                      <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
                    </div>
                    <p className="mt-3 text-sm leading-6 text-current/75">{surface.copy}</p>
                  </Link>
                ))}
              </div>
            </div>
          </div>
        </section>

        <section className="mx-auto max-w-7xl px-4 py-14 sm:px-6 lg:px-8">
          <div className="grid gap-8 lg:grid-cols-[1fr_1fr]">
            <Card className="rounded-[2rem] border-slate-200/80 bg-[#0f172a] text-slate-100 shadow-[0_28px_70px_rgba(15,23,42,0.18)]">
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 text-sm font-semibold text-cyan-300">
                    <Terminal className="h-4 w-4" />
                    API example
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => copyToClipboard(curlExample, 'curl')}
                    className="text-slate-300 hover:bg-white/10 hover:text-white"
                  >
                    {copiedCode === 'curl' ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
                  </Button>
                </div>
                <CardTitle className="text-2xl text-white">Start with the contract the backend actually serves</CardTitle>
                <CardDescription className="text-base leading-7 text-slate-300">
                  The frontend should always make the live request shape obvious. That is the shortest path from trust to integration.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <pre className="overflow-x-auto rounded-[1.5rem] border border-white/10 bg-black/30 p-5 text-sm leading-7 text-cyan-100">
                  <code>{curlExample}</code>
                </pre>
              </CardContent>
            </Card>

            <div className="grid gap-6">
              <Card className="rounded-[2rem] border-slate-200/80 bg-white/85 shadow-[0_20px_55px_rgba(15,23,42,0.05)]">
                <CardHeader>
                  <div className="flex items-center gap-2 text-sm font-semibold text-slate-600">
                    <Code className="h-4 w-4" />
                    SDK snapshot
                  </div>
                  <CardTitle className="text-2xl text-slate-950">Python first, then deeper surfaces</CardTitle>
                </CardHeader>
                <CardContent>
                  <pre className="overflow-x-auto rounded-[1.5rem] border border-slate-200 bg-slate-950 p-5 text-sm leading-7 text-emerald-300">
                    <code>{pythonExample}</code>
                  </pre>
                </CardContent>
              </Card>

              <div className="grid gap-4 sm:grid-cols-2">
                {[
                  { icon: Sparkles, title: 'Why this matters', copy: 'The frontend should help users understand what the system is for and what they should do next.' },
                  { icon: Wrench, title: 'Where this leads', copy: 'The same product surface can eventually bridge analysis, validation, minting, repair, and fabrication execution.' },
                ].map((item) => {
                  const Icon = item.icon;
                  return (
                    <Card key={item.title} className="rounded-[1.5rem] border-slate-200/80 bg-white/85 shadow-[0_18px_40px_rgba(15,23,42,0.04)]">
                      <CardHeader>
                        <div className="mb-3 flex h-11 w-11 items-center justify-center rounded-2xl bg-slate-100 text-slate-900">
                          <Icon className="h-5 w-5" />
                        </div>
                        <CardTitle className="text-xl text-slate-950">{item.title}</CardTitle>
                        <CardDescription className="text-base leading-7 text-slate-600">{item.copy}</CardDescription>
                      </CardHeader>
                    </Card>
                  );
                })}
              </div>
            </div>
          </div>
        </section>
      </main>

      <SiteFooter />
    </div>
  );
}

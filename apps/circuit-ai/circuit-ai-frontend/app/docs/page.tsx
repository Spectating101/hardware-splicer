'use client';

import { useState } from 'react';
import Link from 'next/link';
import { Check, Copy, ExternalLink, Globe, KeyRound, PlayCircle, Server, Workflow } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { SiteHeader } from '@/components/site-header';
import { SiteFooter } from '@/components/site-footer';
import { PageIntro } from '@/components/page-intro';
import { usePageTitle } from '@/components/use-page-title';

const endpoints = [
  {
    method: 'POST',
    path: '/analyze',
    description: 'Primary PCB analysis entrypoint for uploaded board images and circuit findings.',
    example: `curl -X POST "https://api.circuit-ai.com/analyze" \\
  -H "Authorization: Bearer YOUR_API_KEY" \\
  -H "Content-Type: multipart/form-data" \\
  -F "file=@pcb_image.jpg"`,
  },
  {
    method: 'POST',
    path: '/analyze/netlist',
    description: 'KiCad netlist analysis for electrical rule checks and issue surfacing.',
    example: `curl -X POST "https://api.circuit-ai.com/analyze/netlist" \\
  -H "Authorization: Bearer YOUR_API_KEY" \\
  -H "Content-Type: multipart/form-data" \\
  -F "file=@board.net"`,
  },
  {
    method: 'GET',
    path: '/components',
    description: 'Component search and enrichment for frontend detail views and educational overlays.',
    example: `curl -X GET "https://api.circuit-ai.com/components?search=arduino" \\
  -H "Authorization: Bearer YOUR_API_KEY"`,
  },
  {
    method: 'GET',
    path: '/projects',
    description: 'Project recommendations based on detected inventory, salvageability, or educational fit.',
    example: `curl -X GET "https://api.circuit-ai.com/projects?components=arduino,led,resistor" \\
  -H "Authorization: Bearer YOUR_API_KEY"`,
  },
  {
    method: 'GET',
    path: '/educational',
    description: 'Human-facing explanation layer for component classes and recovery targets.',
    example: `curl -X GET "https://api.circuit-ai.com/educational" \\
  -H "Authorization: Bearer YOUR_API_KEY"`,
  },
  {
    method: 'GET',
    path: '/repair',
    description: 'Repair guidance the frontend can use to turn findings into remediation or operator action.',
    example: `curl -X GET "https://api.circuit-ai.com/repair" \\
  -H "Authorization: Bearer YOUR_API_KEY"`,
  },
  {
    method: 'GET',
    path: '/statistics',
    description: 'Platform telemetry and usage stats for operational dashboards and status surfaces.',
    example: `curl -X GET "https://api.circuit-ai.com/statistics" \\
  -H "Authorization: Bearer YOUR_API_KEY"`,
  },
];

const quickStart = [
  'Create a key in API Keys so the request path is authenticated before any frontend experimentation.',
  'Run the playground against the actual backend target you want to validate.',
  'Treat docs, status, and playground together as one trust surface, not three separate pages.',
];

export default function DocsPage() {
  usePageTitle('Docs | Circuit.AI');
  const [copiedCode, setCopiedCode] = useState<string | null>(null);

  const copyToClipboard = (code: string, id: string) => {
    navigator.clipboard.writeText(code);
    setCopiedCode(id);
    setTimeout(() => setCopiedCode(null), 1500);
  };

  return (
    <div className="min-h-screen bg-[#edf2f7] text-slate-950">
      <SiteHeader />

      <main>
        <PageIntro
          eyebrow="Implementation docs"
          title="Documentation that matches the actual integration path."
          description="This is the place where the frontend should stop bluffing. It should tell you exactly how auth works, which endpoints exist, and how to verify the backend target before you commit UI behavior to it."
          actions={
            <>
              <Button asChild className="rounded-full bg-slate-900 text-white hover:bg-slate-800">
                <Link href="/dashboard/keys">
                  <KeyRound className="mr-2 h-4 w-4" />
                  Open API keys
                </Link>
              </Button>
              <Button asChild variant="outline" className="rounded-full border-slate-300 bg-white/80">
                <Link href="/playground">
                  <PlayCircle className="mr-2 h-4 w-4" />
                  Validate in playground
                </Link>
              </Button>
            </>
          }
          aside={
            <div className="space-y-4">
              <div className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">Quick start</div>
              {quickStart.map((item, index) => (
                <div key={item} className="flex gap-3 rounded-3xl border border-slate-200 bg-slate-50 p-4">
                  <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-2xl bg-slate-900 text-sm font-semibold text-white">
                    {index + 1}
                  </div>
                  <p className="text-sm leading-6 text-slate-600">{item}</p>
                </div>
              ))}
            </div>
          }
        />

        <section className="mx-auto max-w-7xl px-4 py-12 sm:px-6 lg:px-8">
          <div className="grid gap-8 lg:grid-cols-[0.85fr_1.15fr]">
            <div className="space-y-6">
              <Card className="rounded-[1.75rem] border-slate-200/80 bg-white/85 shadow-[0_18px_42px_rgba(15,23,42,0.05)]">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-xl text-slate-950">
                    <Workflow className="h-5 w-5 text-slate-700" />
                    How to use this doc set
                  </CardTitle>
                  <CardDescription className="text-base leading-7 text-slate-600">
                    Treat this as a contract reference, not marketing copy.
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-3 text-sm leading-6 text-slate-600">
                  <p>Keep the frontend aligned to real backend behavior. If a request path is backend-dependent, surface that clearly instead of burying it behind optimistic UI.</p>
                  <p>Use the status page when you need a current read on what is live versus what still needs a running backend.</p>
                </CardContent>
              </Card>

              <Card className="rounded-[1.75rem] border-slate-200/80 bg-[#0f172a] text-slate-100 shadow-[0_24px_60px_rgba(15,23,42,0.16)]">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-xl text-white">
                    <Server className="h-5 w-5 text-cyan-300" />
                    Auth header
                  </CardTitle>
                  <CardDescription className="text-base leading-7 text-slate-300">
                    Every request should look explicit and boring in the best possible way.
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="relative overflow-hidden rounded-[1.5rem] border border-white/10 bg-black/25 p-5">
                    <pre className="overflow-x-auto text-sm leading-7 text-cyan-100">
                      <code>Authorization: Bearer YOUR_API_KEY</code>
                    </pre>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="absolute right-3 top-3 text-slate-300 hover:bg-white/10 hover:text-white"
                      onClick={() => copyToClipboard('Authorization: Bearer YOUR_API_KEY', 'auth')}
                    >
                      {copiedCode === 'auth' ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
                    </Button>
                  </div>
                </CardContent>
              </Card>
            </div>

            <div className="space-y-6">
              {endpoints.map((endpoint, index) => (
                <Card key={endpoint.path} className="rounded-[1.75rem] border-slate-200/80 bg-white/85 shadow-[0_20px_45px_rgba(15,23,42,0.05)]">
                  <CardHeader>
                    <div className="flex flex-wrap items-center gap-3">
                      <span className={`rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] ${
                        endpoint.method === 'POST' ? 'bg-emerald-100 text-emerald-800' : 'bg-cyan-100 text-cyan-800'
                      }`}>
                        {endpoint.method}
                      </span>
                      <code className="rounded-full bg-slate-100 px-3 py-1 text-sm text-slate-900">{endpoint.path}</code>
                    </div>
                    <CardTitle className="text-2xl text-slate-950">{endpoint.path}</CardTitle>
                    <CardDescription className="text-base leading-7 text-slate-600">
                      {endpoint.description}
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="relative overflow-hidden rounded-[1.5rem] border border-slate-200 bg-slate-950 p-5">
                      <pre className="overflow-x-auto text-sm leading-7 text-emerald-300">
                        <code>{endpoint.example}</code>
                      </pre>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="absolute right-3 top-3 text-slate-300 hover:bg-white/10 hover:text-white"
                        onClick={() => copyToClipboard(endpoint.example, `endpoint-${index}`)}
                      >
                        {copiedCode === `endpoint-${index}` ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              ))}

              <div className="grid gap-4 sm:grid-cols-2">
                <Link href="/playground" className="rounded-[1.5rem] border border-slate-200 bg-white/85 p-5 shadow-[0_16px_38px_rgba(15,23,42,0.04)] transition-transform hover:-translate-y-1">
                  <div className="flex items-center gap-2 text-sm font-semibold text-slate-900">
                    <ExternalLink className="h-4 w-4" />
                    Playground
                  </div>
                  <p className="mt-3 text-sm leading-6 text-slate-600">Use the playground when you need to prove a request path with a real file and visible backend dependency.</p>
                </Link>
                <Link href="/status" className="rounded-[1.5rem] border border-slate-200 bg-white/85 p-5 shadow-[0_16px_38px_rgba(15,23,42,0.04)] transition-transform hover:-translate-y-1">
                  <div className="flex items-center gap-2 text-sm font-semibold text-slate-900">
                    <Globe className="h-4 w-4" />
                    Status
                  </div>
                  <p className="mt-3 text-sm leading-6 text-slate-600">Use status when you need a clean answer about what the frontend can show without a live backend behind it.</p>
                </Link>
              </div>
            </div>
          </div>
        </section>
      </main>

      <SiteFooter />
    </div>
  );
}

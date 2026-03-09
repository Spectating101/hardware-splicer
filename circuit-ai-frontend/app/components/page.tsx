'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import {
  BookOpen,
  CircuitBoard,
  Cpu,
  LoaderCircle,
  RefreshCcw,
  ShieldCheck,
  Sparkles,
  Wrench,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { SiteHeader } from '@/components/site-header';
import { SiteFooter } from '@/components/site-footer';
import { PageIntro } from '@/components/page-intro';
import { usePageTitle } from '@/components/use-page-title';

type ComponentResponse = {
  total_components?: number;
  component_types?: string[];
  last_updated?: string;
};

type EducationalResponse = {
  total_content?: number;
  content?: Array<{
    title?: string;
    difficulty?: string;
    component_type?: string;
    estimated_time?: string;
  }>;
};

type RepairResponse = {
  total_guides?: number;
  guides?: Array<{
    component_type?: string;
    issue?: string;
    difficulty?: string;
    success_rate?: number;
  }>;
};

const fallbackTypes = ['ic_chip', 'capacitor', 'resistor', 'connector', 'transformer', 'diode'];

export default function ComponentsPage() {
  usePageTitle('Component Intelligence | Circuit.AI');
  const apiBaseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
  const [componentData, setComponentData] = useState<ComponentResponse | null>(null);
  const [educationData, setEducationData] = useState<EducationalResponse | null>(null);
  const [repairData, setRepairData] = useState<RepairResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    async function load() {
      setLoading(true);
      setErrorMessage(null);

      try {
        const [componentsRes, educationRes, repairRes] = await Promise.all([
          fetch(`${apiBaseUrl}/components`, { cache: 'no-store' }),
          fetch(`${apiBaseUrl}/educational`, { cache: 'no-store' }),
          fetch(`${apiBaseUrl}/repair`, { cache: 'no-store' }),
        ]);

        const [componentsJson, educationJson, repairJson] = await Promise.all([
          componentsRes.ok ? componentsRes.json() : Promise.resolve({}),
          educationRes.ok ? educationRes.json() : Promise.resolve({}),
          repairRes.ok ? repairRes.json() : Promise.resolve({}),
        ]);

        if (!active) return;
        setComponentData(componentsJson);
        setEducationData(educationJson);
        setRepairData(repairJson);

        if (!componentsRes.ok && !educationRes.ok && !repairRes.ok) {
          setErrorMessage(`Could not load live component intelligence from ${apiBaseUrl}. Showing a fallback summary instead.`);
        }
      } catch (error) {
        if (!active) return;
        console.error('Failed to load component intelligence', error);
        setErrorMessage(`Could not load live component intelligence from ${apiBaseUrl}. Showing a fallback summary instead.`);
      } finally {
        if (active) setLoading(false);
      }
    }

    load();
    return () => {
      active = false;
    };
  }, [apiBaseUrl]);

  const componentTypes = useMemo(
    () => componentData?.component_types?.length ? componentData.component_types : fallbackTypes,
    [componentData],
  );
  const educationalItems = educationData?.content || [];
  const repairGuides = repairData?.guides || [];

  return (
    <div className="min-h-screen bg-[#edf2f7] text-slate-950">
      <SiteHeader />

      <main>
        <PageIntro
          eyebrow="Component intelligence"
          title="Turn detections into usable engineering, educational, and repair context."
          description="The backend already exposes more than a flat component list. This route should show how the platform can enrich parts with educational context, repair guidance, and a clearer map of what the system actually knows."
          actions={
            <>
              <Button asChild className="rounded-full bg-slate-900 text-white hover:bg-slate-800">
                <Link href="/analyze">
                  <CircuitBoard className="mr-2 h-4 w-4" />
                  Analyze a board
                </Link>
              </Button>
              <Button asChild variant="outline" className="rounded-full border-slate-300 bg-white/80">
                <Link href="/docs">
                  <BookOpen className="mr-2 h-4 w-4" />
                  Inspect endpoints
                </Link>
              </Button>
            </>
          }
          aside={
            <div className="space-y-4">
              <div className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">Current source</div>
              <div className="rounded-3xl border border-slate-200 bg-slate-50 p-4 text-sm leading-6 text-slate-600">
                This page reads from <code className="rounded bg-white px-1.5 py-0.5 text-xs text-slate-700">/components</code>, <code className="rounded bg-white px-1.5 py-0.5 text-xs text-slate-700">/educational</code>, and <code className="rounded bg-white px-1.5 py-0.5 text-xs text-slate-700">/repair</code> when the backend is reachable.
              </div>
            </div>
          }
        />

        <section className="mx-auto max-w-7xl px-4 py-12 sm:px-6 lg:px-8">
          {errorMessage ? (
            <div className="mb-6 rounded-[1.5rem] border border-amber-200 bg-amber-50 p-4 text-sm leading-6 text-amber-800">
              {errorMessage}
            </div>
          ) : null}

          <div className="grid gap-4 sm:grid-cols-3">
            <Card className="rounded-[1.5rem] border-slate-200/80 bg-white/90 shadow-[0_18px_38px_rgba(15,23,42,0.04)]">
              <CardHeader className="pb-2">
                <CardDescription className="text-xs uppercase tracking-[0.16em] text-slate-500">Tracked types</CardDescription>
                <CardTitle className="text-4xl text-slate-950">
                  {loading ? <LoaderCircle className="h-8 w-8 animate-spin text-slate-400" /> : componentData?.total_components || componentTypes.length}
                </CardTitle>
              </CardHeader>
            </Card>
            <Card className="rounded-[1.5rem] border-slate-200/80 bg-white/90 shadow-[0_18px_38px_rgba(15,23,42,0.04)]">
              <CardHeader className="pb-2">
                <CardDescription className="text-xs uppercase tracking-[0.16em] text-slate-500">Educational overlays</CardDescription>
                <CardTitle className="text-4xl text-slate-950">{educationData?.total_content || educationalItems.length || 0}</CardTitle>
              </CardHeader>
            </Card>
            <Card className="rounded-[1.5rem] border-slate-200/80 bg-white/90 shadow-[0_18px_38px_rgba(15,23,42,0.04)]">
              <CardHeader className="pb-2">
                <CardDescription className="text-xs uppercase tracking-[0.16em] text-slate-500">Repair guides</CardDescription>
                <CardTitle className="text-4xl text-slate-950">{repairData?.total_guides || repairGuides.length || 0}</CardTitle>
              </CardHeader>
            </Card>
          </div>

          <div className="mt-8 grid gap-6 lg:grid-cols-[1.05fr_0.95fr]">
            <Card className="rounded-[2rem] border-slate-200/80 bg-white/90 shadow-[0_24px_55px_rgba(15,23,42,0.05)]">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-2xl text-slate-950">
                  <Cpu className="h-5 w-5 text-slate-700" />
                  Known component types
                </CardTitle>
                <CardDescription className="text-base leading-7 text-slate-600">
                  This is the inventory layer the frontend can use for enrichment, explanations, and operator guidance.
                </CardDescription>
              </CardHeader>
              <CardContent className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                {componentTypes.map((type) => (
                  <div key={type} className="rounded-[1.5rem] border border-slate-200 bg-slate-50 p-4">
                    <div className="text-sm font-semibold text-slate-900">{type.replaceAll('_', ' ')}</div>
                    <p className="mt-2 text-sm leading-6 text-slate-600">
                      Candidate anchor for detection overlays, part intelligence, and salvage or replacement workflows.
                    </p>
                  </div>
                ))}
              </CardContent>
            </Card>

            <Card className="rounded-[2rem] border-slate-200/80 bg-[#0f172a] text-slate-100 shadow-[0_24px_65px_rgba(15,23,42,0.18)]">
              <CardHeader>
                <CardTitle className="text-2xl text-white">Why this route matters</CardTitle>
                <CardDescription className="text-base leading-7 text-slate-300">
                  A strong frontend turns raw detections into understandable next steps.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-3 text-sm leading-6 text-slate-300">
                <div className="rounded-[1.5rem] border border-white/10 bg-white/5 p-4">
                  <div className="flex items-center gap-2 font-semibold text-white">
                    <Sparkles className="h-4 w-4 text-cyan-300" />
                    Education
                  </div>
                  <p className="mt-2">Explain what a component does and why it matters without forcing the user to leave the workflow.</p>
                </div>
                <div className="rounded-[1.5rem] border border-white/10 bg-white/5 p-4">
                  <div className="flex items-center gap-2 font-semibold text-white">
                    <Wrench className="h-4 w-4 text-orange-300" />
                    Repair
                  </div>
                  <p className="mt-2">Use issue-specific guidance to bridge from diagnosis into actual remediation or fabrication decisions.</p>
                </div>
                <div className="rounded-[1.5rem] border border-white/10 bg-white/5 p-4">
                  <div className="flex items-center gap-2 font-semibold text-white">
                    <ShieldCheck className="h-4 w-4 text-emerald-300" />
                    Honesty
                  </div>
                  <p className="mt-2">If the backend is unreachable, say so and preserve a fallback surface instead of leaving the route empty.</p>
                </div>
              </CardContent>
            </Card>
          </div>

          <div className="mt-8 grid gap-6 lg:grid-cols-2">
            <Card className="rounded-[2rem] border-slate-200/80 bg-white/90 shadow-[0_24px_55px_rgba(15,23,42,0.05)]">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-2xl text-slate-950">
                  <BookOpen className="h-5 w-5 text-slate-700" />
                  Educational content
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {educationalItems.length ? educationalItems.slice(0, 6).map((item, index) => (
                  <div key={`${item.title || 'educational'}-${index}`} className="rounded-[1.5rem] border border-slate-200 bg-slate-50 p-4">
                    <div className="flex flex-wrap items-center gap-2">
                      <div className="text-sm font-semibold text-slate-900">{item.title || 'Untitled content'}</div>
                      {item.difficulty ? (
                        <span className="rounded-full bg-white px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] text-slate-600">
                          {item.difficulty}
                        </span>
                      ) : null}
                    </div>
                    <p className="mt-2 text-sm leading-6 text-slate-600">
                      {item.component_type ? `${item.component_type.replaceAll('_', ' ')} focus` : 'Component-focused material'}
                      {item.estimated_time ? ` • ${item.estimated_time}` : ''}
                    </p>
                  </div>
                )) : (
                  <div className="rounded-[1.5rem] border border-slate-200 bg-slate-50 p-4 text-sm leading-6 text-slate-600">
                    No live educational content was returned. The backend hook exists, so the route is prepared for it when populated.
                  </div>
                )}
              </CardContent>
            </Card>

            <Card className="rounded-[2rem] border-slate-200/80 bg-white/90 shadow-[0_24px_55px_rgba(15,23,42,0.05)]">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-2xl text-slate-950">
                  <RefreshCcw className="h-5 w-5 text-slate-700" />
                  Repair guidance
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {repairGuides.length ? repairGuides.slice(0, 6).map((guide, index) => (
                  <div key={`${guide.component_type || 'repair'}-${guide.issue || index}`} className="rounded-[1.5rem] border border-slate-200 bg-slate-50 p-4">
                    <div className="text-sm font-semibold text-slate-900">
                      {guide.component_type ? guide.component_type.replaceAll('_', ' ') : 'Component'} {guide.issue ? `• ${guide.issue}` : ''}
                    </div>
                    <p className="mt-2 text-sm leading-6 text-slate-600">
                      {guide.difficulty ? `${guide.difficulty} difficulty` : 'Difficulty unavailable'}
                      {guide.success_rate !== undefined ? ` • ${Math.round(guide.success_rate * 100)}% success rate` : ''}
                    </p>
                  </div>
                )) : (
                  <div className="rounded-[1.5rem] border border-slate-200 bg-slate-50 p-4 text-sm leading-6 text-slate-600">
                    No live repair guidance was returned. The route still preserves the intended surface and backend expectation.
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </section>
      </main>

      <SiteFooter />
    </div>
  );
}

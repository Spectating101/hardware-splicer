'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import {
  ArrowRight,
  CircuitBoard,
  Layers3,
  LoaderCircle,
  PackageCheck,
  Sparkles,
  Target,
  Wrench,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { SiteHeader } from '@/components/site-header';
import { SiteFooter } from '@/components/site-footer';
import { PageIntro } from '@/components/page-intro';
import { usePageTitle } from '@/components/use-page-title';

type ProjectItem = {
  id?: string;
  name?: string;
  difficulty?: string;
  category?: string;
  estimated_cost?: number;
  score?: number;
};

type ProjectResponse = {
  total_projects?: number;
  projects?: ProjectItem[];
};

const orchestrationLanes = [
  {
    title: 'Recovery and salvage',
    copy: 'Map detected boards and components into realistic reuse or teardown programs.',
  },
  {
    title: 'Educational builds',
    copy: 'Turn identified inventory into guided projects with clear difficulty and cost posture.',
  },
  {
    title: 'Minting and procurement',
    copy: 'Package the board state into deterministic next steps for BOM and operator review.',
  },
];

const fallbackProjects: ProjectItem[] = [
  { id: 'weather_station', name: 'Arduino Weather Station', difficulty: 'beginner', category: 'education', estimated_cost: 15, score: 0.91 },
  { id: 'audio_amplifier', name: 'Simple Audio Amplifier', difficulty: 'intermediate', category: 'repair', estimated_cost: 25, score: 0.84 },
  { id: 'power_supply', name: 'Variable Power Supply', difficulty: 'intermediate', category: 'fabrication', estimated_cost: 35, score: 0.8 },
];

export default function ProjectsPage() {
  usePageTitle('Project Orchestration | Circuit.AI');
  const apiBaseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
  const [projectData, setProjectData] = useState<ProjectResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    async function load() {
      setLoading(true);
      setErrorMessage(null);

      try {
        const response = await fetch(`${apiBaseUrl}/projects`, { cache: 'no-store' });
        const payload = response.ok ? await response.json() : {};

        if (!active) return;
        setProjectData(payload);

        if (!response.ok) {
          setErrorMessage(`Could not load live project templates from ${apiBaseUrl}/projects. Showing a curated fallback list instead.`);
        }
      } catch (error) {
        if (!active) return;
        console.error('Failed to load project templates', error);
        setErrorMessage(`Could not load live project templates from ${apiBaseUrl}/projects. Showing a curated fallback list instead.`);
      } finally {
        if (active) setLoading(false);
      }
    }

    load();
    return () => {
      active = false;
    };
  }, [apiBaseUrl]);

  const projects = useMemo(
    () => projectData?.projects?.length ? projectData.projects : fallbackProjects,
    [projectData],
  );

  return (
    <div className="min-h-screen bg-[#edf2f7] text-slate-950">
      <SiteHeader />

      <main>
        <PageIntro
          eyebrow="Project orchestration"
          title="Project templates should prove the system can turn intelligence into action."
          description="This route is where recovered parts, analysis results, and educational or fabrication intent start converging. Instead of a generic template gallery, it should read like the planning layer of the broader stack."
          actions={
            <>
              <Button asChild className="rounded-full bg-slate-900 text-white hover:bg-slate-800">
                <Link href="/components">
                  <Layers3 className="mr-2 h-4 w-4" />
                  Inspect components
                </Link>
              </Button>
              <Button asChild variant="outline" className="rounded-full border-slate-300 bg-white/80">
                <Link href="/cad">
                  <CircuitBoard className="mr-2 h-4 w-4" />
                  Open CAD workspace
                </Link>
              </Button>
            </>
          }
          aside={
            <div className="space-y-4">
              <div className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">Backend source</div>
              <div className="rounded-3xl border border-slate-200 bg-slate-50 p-4 text-sm leading-6 text-slate-600">
                Live data is read from <code className="rounded bg-white px-1.5 py-0.5 text-xs text-slate-700">/projects</code>. If the backend is unavailable, the route falls back without hiding that fact.
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
                <CardDescription className="text-xs uppercase tracking-[0.16em] text-slate-500">Project templates</CardDescription>
                <CardTitle className="text-4xl text-slate-950">
                  {loading ? <LoaderCircle className="h-8 w-8 animate-spin text-slate-400" /> : projectData?.total_projects || projects.length}
                </CardTitle>
              </CardHeader>
            </Card>
            <Card className="rounded-[1.5rem] border-slate-200/80 bg-white/90 shadow-[0_18px_38px_rgba(15,23,42,0.04)]">
              <CardHeader className="pb-2">
                <CardDescription className="text-xs uppercase tracking-[0.16em] text-slate-500">Primary direction</CardDescription>
                <CardTitle className="text-2xl text-slate-950">Education + recovery</CardTitle>
              </CardHeader>
            </Card>
            <Card className="rounded-[1.5rem] border-slate-200/80 bg-white/90 shadow-[0_18px_38px_rgba(15,23,42,0.04)]">
              <CardHeader className="pb-2">
                <CardDescription className="text-xs uppercase tracking-[0.16em] text-slate-500">Downstream path</CardDescription>
                <CardTitle className="text-2xl text-slate-950">Minting + CAD</CardTitle>
              </CardHeader>
            </Card>
          </div>

          <div className="mt-8 grid gap-6 lg:grid-cols-[0.9fr_1.1fr]">
            <Card className="rounded-[2rem] border-slate-200/80 bg-[#0f172a] text-slate-100 shadow-[0_24px_65px_rgba(15,23,42,0.18)]">
              <CardHeader>
                <CardTitle className="text-2xl text-white">Project lanes</CardTitle>
                <CardDescription className="text-base leading-7 text-slate-300">
                  These are the ways project recommendations can reinforce the full product promise.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                {orchestrationLanes.map((lane) => (
                  <div key={lane.title} className="rounded-[1.5rem] border border-white/10 bg-white/5 p-4">
                    <div className="text-sm font-semibold text-white">{lane.title}</div>
                    <p className="mt-2 text-sm leading-6 text-slate-300">{lane.copy}</p>
                  </div>
                ))}
              </CardContent>
            </Card>

            <div className="grid gap-4">
              {projects.map((project, index) => (
                <Card key={project.id || `${project.name || 'project'}-${index}`} className="rounded-[1.75rem] border-slate-200/80 bg-white/90 shadow-[0_20px_45px_rgba(15,23,42,0.05)]">
                  <CardHeader>
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div>
                        <CardTitle className="text-2xl text-slate-950">{project.name || 'Unnamed project'}</CardTitle>
                        <CardDescription className="mt-2 text-base leading-7 text-slate-600">
                          {project.category ? `${project.category} workflow` : 'Project workflow candidate'}
                        </CardDescription>
                      </div>
                      {project.difficulty ? (
                        <div className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] text-slate-700">
                          {project.difficulty}
                        </div>
                      ) : null}
                    </div>
                  </CardHeader>
                  <CardContent className="grid gap-4 lg:grid-cols-[1fr_auto] lg:items-end">
                    <div className="grid gap-3 sm:grid-cols-3">
                      <div className="rounded-[1.25rem] bg-slate-50 p-4">
                        <div className="flex items-center gap-2 text-xs uppercase tracking-[0.16em] text-slate-500">
                          <PackageCheck className="h-4 w-4" />
                          Estimated cost
                        </div>
                        <div className="mt-2 text-2xl font-semibold text-slate-950">
                          {project.estimated_cost !== undefined ? `$${project.estimated_cost}` : 'Pending'}
                        </div>
                      </div>
                      <div className="rounded-[1.25rem] bg-slate-50 p-4">
                        <div className="flex items-center gap-2 text-xs uppercase tracking-[0.16em] text-slate-500">
                          <Target className="h-4 w-4" />
                          Score
                        </div>
                        <div className="mt-2 text-2xl font-semibold text-slate-950">
                          {project.score !== undefined ? `${Math.round(project.score * 100)}%` : 'N/A'}
                        </div>
                      </div>
                      <div className="rounded-[1.25rem] bg-slate-50 p-4">
                        <div className="flex items-center gap-2 text-xs uppercase tracking-[0.16em] text-slate-500">
                          <Wrench className="h-4 w-4" />
                          Outcome
                        </div>
                        <div className="mt-2 text-sm font-semibold text-slate-900">
                          {project.category ? `${project.category} ready` : 'Review next step'}
                        </div>
                      </div>
                    </div>

                    <Button asChild variant="outline" className="rounded-full">
                      <Link href="/analyze">
                        Use with analysis
                        <ArrowRight className="ml-2 h-4 w-4" />
                      </Link>
                    </Button>
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>

          <section className="mt-8 grid gap-6 lg:grid-cols-3">
            <Card className="rounded-[1.75rem] border-slate-200/80 bg-white/90 shadow-[0_18px_40px_rgba(15,23,42,0.04)]">
              <CardHeader>
                <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-2xl bg-slate-100 text-slate-900">
                  <Sparkles className="h-5 w-5" />
                </div>
                <CardTitle className="text-xl text-slate-950">Synergy target</CardTitle>
                <CardDescription className="text-base leading-7 text-slate-600">
                  Keep project recommendations connected to component intelligence, analysis evidence, and fabrication follow-through.
                </CardDescription>
              </CardHeader>
            </Card>
            <Card className="rounded-[1.75rem] border-slate-200/80 bg-white/90 shadow-[0_18px_40px_rgba(15,23,42,0.04)]">
              <CardHeader>
                <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-2xl bg-slate-100 text-slate-900">
                  <Layers3 className="h-5 w-5" />
                </div>
                <CardTitle className="text-xl text-slate-950">Inventory continuity</CardTitle>
                <CardDescription className="text-base leading-7 text-slate-600">
                  Detected or recovered parts should influence what projects appear plausible, not just what looks nice in a catalog.
                </CardDescription>
              </CardHeader>
            </Card>
            <Card className="rounded-[1.75rem] border-slate-200/80 bg-white/90 shadow-[0_18px_40px_rgba(15,23,42,0.04)]">
              <CardHeader>
                <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-2xl bg-slate-100 text-slate-900">
                  <CircuitBoard className="h-5 w-5" />
                </div>
                <CardTitle className="text-xl text-slate-950">Operator handoff</CardTitle>
                <CardDescription className="text-base leading-7 text-slate-600">
                  The path should continue into CAD, validation, or minting, not terminate at a dead-end project card.
                </CardDescription>
              </CardHeader>
            </Card>
          </section>
        </section>
      </main>

      <SiteFooter />
    </div>
  );
}

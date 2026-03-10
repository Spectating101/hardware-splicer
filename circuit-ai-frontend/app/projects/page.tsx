'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { ArrowRight, CircuitBoard, Layers3, LoaderCircle, PackageCheck, Sparkles, Target, Wrench } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { StudioShell } from '@/components/studio-shell';
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

const navItems = [
  { href: '/', label: 'Overview' },
  { href: '/analyze', label: 'Analyze' },
  { href: '/components', label: 'Components' },
  { href: '/projects', label: 'Projects' },
  { href: '/cad', label: 'CAD' },
];

const orchestrationLanes = [
  'Recovery and salvage',
  'Educational builds',
  'Minting and procurement',
];

const fallbackProjects: ProjectItem[] = [
  { id: 'weather_station', name: 'Arduino Weather Station', difficulty: 'beginner', category: 'education', estimated_cost: 15, score: 0.91 },
  { id: 'audio_amplifier', name: 'Simple Audio Amplifier', difficulty: 'intermediate', category: 'repair', estimated_cost: 25, score: 0.84 },
  { id: 'power_supply', name: 'Variable Power Supply', difficulty: 'intermediate', category: 'fabrication', estimated_cost: 35, score: 0.8 },
];

function panelHeading(eyebrow: string, title: string) {
  return (
    <div className="mb-4">
      <div className="text-[11px] font-semibold uppercase tracking-[0.24em] text-slate-500">{eyebrow}</div>
      <div className="mt-2 text-sm font-semibold text-white">{title}</div>
    </div>
  );
}

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
          setErrorMessage(`Live project templates are unavailable at ${apiBaseUrl}/projects. Curated fallback set loaded.`);
        }
      } catch (error) {
        if (!active) return;
        console.error('Failed to load project templates', error);
        setErrorMessage(`Live project templates are unavailable at ${apiBaseUrl}/projects. Curated fallback set loaded.`);
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
    <StudioShell
      eyebrow="Workbench"
      title="Plan downstream actions from a fixed project dock."
      description="Projects should feel like a decision board inside the same workspace, not a long template page. The center stays on candidate paths while the rails hold context and next moves."
      status={loading ? 'Refreshing project board' : `${projectData?.total_projects || projects.length} project paths available`}
      activeHref="/projects"
      navItems={navItems}
      actions={
        <>
          <Button asChild className="rounded-full bg-white text-slate-950 hover:bg-slate-100">
            <Link href="/components">
              <Layers3 className="mr-2 h-4 w-4" />
              Component dock
            </Link>
          </Button>
          <Button asChild variant="outline" className="rounded-full border-white/15 bg-white/5 text-white hover:bg-white/10">
            <Link href="/cad">
              <CircuitBoard className="mr-2 h-4 w-4" />
              CAD workspace
            </Link>
          </Button>
        </>
      }
      left={
        <div className="space-y-5">
          <div className="rounded-[1.5rem] border border-white/10 bg-[linear-gradient(180deg,#0c1730,#091323)] p-4">
            {panelHeading('Lanes', 'Planning tracks')}
            <div className="space-y-2">
              {orchestrationLanes.map((lane) => (
                <div key={lane} className="rounded-[1rem] border border-white/8 bg-[#081423] px-3 py-3 text-sm text-slate-300">
                  {lane}
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-[1.5rem] border border-white/10 bg-[linear-gradient(180deg,#0c1730,#091323)] p-4">
            {panelHeading('Counts', 'Board summary')}
            <div className="grid gap-3">
              <div className="rounded-[1rem] border border-white/8 bg-[#081423] p-3">
                <div className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Templates</div>
                <div className="mt-2 text-lg font-semibold text-white">
                  {loading ? <LoaderCircle className="h-5 w-5 animate-spin text-slate-400" /> : projectData?.total_projects || projects.length}
                </div>
              </div>
              <div className="rounded-[1rem] border border-white/8 bg-[#081423] p-3">
                <div className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Primary direction</div>
                <div className="mt-2 text-lg font-semibold text-white">Education + recovery</div>
              </div>
            </div>
          </div>

          {errorMessage ? (
            <div className="rounded-[1.5rem] border border-amber-400/20 bg-amber-500/10 p-4 text-sm leading-6 text-amber-100">
              {errorMessage}
            </div>
          ) : null}
        </div>
      }
      main={
        <div className="grid h-full gap-px bg-white/5 lg:grid-rows-[72px_minmax(0,1fr)]">
          <div className="flex items-center justify-between bg-[#0d1628] px-5">
            <div>
              <div className="text-[11px] uppercase tracking-[0.22em] text-slate-500">Decision board</div>
              <div className="mt-1 text-sm font-semibold text-white">Project candidates</div>
            </div>
            <div className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-slate-300">
              {loading ? 'Syncing' : 'Studio planning view'}
            </div>
          </div>

          <div className="min-h-0 overflow-y-auto bg-[#09111f] p-4">
            <div className="grid gap-5 xl:grid-cols-2">
              {projects.map((project, index) => (
                <div key={project.id || `${project.name || 'project'}-${index}`} className="rounded-[1.6rem] border border-white/10 bg-[linear-gradient(180deg,#0f1b35,#091423)] p-5 transition-all hover:-translate-y-0.5 hover:border-cyan-300/30 hover:bg-[linear-gradient(180deg,#122244,#0b1730)]">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="text-lg font-semibold text-white">{project.name || 'Unnamed project'}</div>
                      <div className="mt-1 text-sm text-slate-300">
                        {project.category ? `${project.category} pathway` : 'Planning pathway'}
                      </div>
                    </div>
                    {project.difficulty ? (
                      <div className="rounded-full border border-white/10 bg-[#081423] px-3 py-1 text-xs uppercase tracking-[0.16em] text-cyan-200">
                        {project.difficulty}
                      </div>
                    ) : null}
                  </div>

                  <div className="mt-5 grid gap-3 sm:grid-cols-3">
                    <div className="rounded-[1rem] border border-white/8 bg-[#081423] p-3">
                      <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-slate-500">
                        <PackageCheck className="h-3.5 w-3.5" />
                        Cost
                      </div>
                      <div className="mt-2 text-lg font-semibold text-white">
                        {project.estimated_cost !== undefined ? `$${project.estimated_cost}` : 'Pending'}
                      </div>
                    </div>
                    <div className="rounded-[1rem] border border-white/8 bg-[#081423] p-3">
                      <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-slate-500">
                        <Target className="h-3.5 w-3.5" />
                        Score
                      </div>
                      <div className="mt-2 text-lg font-semibold text-white">
                        {project.score !== undefined ? `${Math.round(project.score * 100)}%` : 'N/A'}
                      </div>
                    </div>
                    <div className="rounded-[1rem] border border-white/8 bg-[#081423] p-3">
                      <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-slate-500">
                        <Wrench className="h-3.5 w-3.5" />
                        Outcome
                      </div>
                      <div className="mt-2 text-sm font-semibold text-white">
                        {project.category ? `${project.category} ready` : 'Review next step'}
                      </div>
                    </div>
                  </div>

                  <div className="mt-5 flex items-center justify-between gap-3">
                    <div className="text-xs uppercase tracking-[0.2em] text-slate-500">candidate path</div>
                    <Button asChild variant="outline" className="rounded-full border-white/10 bg-cyan-300/10 text-cyan-100 hover:bg-cyan-300/20">
                      <Link href="/analyze">
                        Use with analysis
                        <ArrowRight className="ml-2 h-4 w-4" />
                      </Link>
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      }
      right={
        <div className="space-y-4">
          <div className="rounded-[1.5rem] border border-white/10 bg-[linear-gradient(180deg,#0c1730,#091323)] p-4">
            <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-white">
              <Sparkles className="h-4 w-4 text-cyan-300" />
              Planning notes
            </div>
            <div className="space-y-3">
              {[
                'Keep project selection tied to component intelligence rather than treating this like a template marketplace.',
                'A chosen path should continue naturally into CAD or operator surfaces.',
                'The workspace should preserve the active board and detected inventory across route changes.',
              ].map((note) => (
                <div key={note} className="rounded-[1rem] border border-white/8 bg-[#081423] p-3 text-sm leading-6 text-slate-400">
                  {note}
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-[1.5rem] border border-white/10 bg-[linear-gradient(180deg,#0c1730,#091323)] p-4">
            <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-white">
              <CircuitBoard className="h-4 w-4 text-cyan-300" />
              Next moves
            </div>
            <div className="space-y-2">
              {[
                ['/analyze', 'Return to board analysis'],
                ['/components', 'Inspect component intelligence'],
                ['/cad', 'Open CAD workspace'],
              ].map(([href, label]) => (
                <Link key={href} href={href} className="block rounded-[1rem] border border-white/8 bg-[#081423] px-3 py-3 text-sm text-slate-300 transition-colors hover:bg-white/10 hover:text-white">
                  {label}
                </Link>
              ))}
            </div>
          </div>
        </div>
      }
    />
  );
}

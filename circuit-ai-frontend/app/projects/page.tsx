'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { ArrowRight, CircuitBoard, Layers3, LoaderCircle, PackageCheck, Sparkles, Target, Wrench } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { CopilotDock } from '@/components/copilot-dock';
import { StudioShell } from '@/components/studio-shell';
import { useStudioRuntime } from '@/components/studio-runtime';
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

function projectKey(project: ProjectItem, index: number) {
  return project.id || `${project.name || 'project'}-${index}`;
}

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
  const { setFocusedProject } = useStudioRuntime();
  const apiBaseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
  const [projectData, setProjectData] = useState<ProjectResponse | null>(null);
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null);
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
  const activeProject = useMemo(() => {
    const selected = projects.find((project, index) => projectKey(project, index) === selectedProjectId);
    return selected || projects[0] || null;
  }, [projects, selectedProjectId]);
  const activeProjectKey = useMemo(
    () => (activeProject ? projectKey(activeProject, projects.indexOf(activeProject)) : null),
    [activeProject, projects],
  );
  const projectLanes = useMemo(
    () => [
      { label: 'Recovery', items: projects.filter((_, index) => index % 3 === 0) },
      { label: 'Build', items: projects.filter((_, index) => index % 3 === 1) },
      { label: 'Launch', items: projects.filter((_, index) => index % 3 === 2) },
    ],
    [projects],
  );

  useEffect(() => {
    setFocusedProject(activeProject?.name || null);
  }, [activeProject, setFocusedProject]);

  return (
    <StudioShell
      eyebrow="Workbench"
      title="Plan downstream actions from a project board."
      description="Candidate paths live on a selectable planning board, while route context and deeper notes stay docked instead of pushing the screen vertical."
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
        <div className="grid h-full grid-rows-[44px_minmax(0,1fr)] bg-white/5">
          <div className="flex items-center justify-between border-b border-white/8 bg-[#08111e] px-4">
            <div className="flex items-center gap-2">
              {['Board', 'Rank', 'Routes'].map((item, index) => (
                <button
                  key={item}
                  type="button"
                  className={`rounded-lg px-3 py-1.5 text-xs font-medium ${index === 0 ? 'bg-cyan-300/15 text-cyan-100' : 'text-slate-400 hover:bg-white/6 hover:text-white'}`}
                >
                  {item}
                </button>
              ))}
            </div>
            <div className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-slate-300">
              {loading ? 'Syncing' : 'Board ready'}
            </div>
          </div>

          <div className="relative min-h-0 overflow-hidden bg-[radial-gradient(circle_at_top,rgba(34,211,238,0.10),transparent_24%),linear-gradient(180deg,#0b1323_0%,#0b1627_100%)] p-3">
            <div className="pointer-events-none absolute bottom-4 right-4 z-10 hidden max-w-sm rounded-[1rem] border border-white/10 bg-[#081423]/88 p-3 text-sm leading-6 text-slate-300 backdrop-blur xl:block">
              Select one route, compare it against the others, then use the lower tray for metrics and next actions.
            </div>

            <div className="grid h-full grid-rows-[76px_minmax(0,1fr)] overflow-hidden rounded-[1.25rem] border border-white/10 bg-[#09111d]">
              <div className="flex items-center justify-between border-b border-white/10 px-4">
                <div>
                  <div className="text-[11px] uppercase tracking-[0.22em] text-slate-500">Decision board</div>
                  <div className="mt-1 text-sm font-semibold text-white">Candidate paths</div>
                </div>
                <div className="rounded-full border border-cyan-300/20 bg-cyan-300/10 px-3 py-1 text-xs text-cyan-100">
                  {activeProject?.name || 'No project selected'}
                </div>
              </div>

              <div className="min-h-0 overflow-x-auto overflow-y-hidden p-4">
                <div className="grid min-h-full min-w-[980px] gap-4 xl:grid-cols-3">
                  {projectLanes.map((lane) => (
                    <div key={lane.label} className="flex min-h-full flex-col rounded-[1.2rem] border border-white/10 bg-[linear-gradient(180deg,#0d1728,#09111f)] p-3">
                      <div className="mb-3 flex items-center justify-between">
                        <div className="text-sm font-semibold text-white">{lane.label}</div>
                        <div className="rounded-full bg-[#081423] px-2.5 py-1 text-[11px] text-slate-400">{lane.items.length}</div>
                      </div>
                      <div className="space-y-3">
                        {lane.items.map((project, index) => {
                          const key = projectKey(project, projects.indexOf(project));
                          return (
                            <button
                              key={key}
                              type="button"
                              onClick={() => setSelectedProjectId(key)}
                              className={`w-full rounded-[1.15rem] border p-4 text-left transition-all ${
                                key === activeProjectKey
                                  ? 'border-cyan-300/35 bg-[linear-gradient(180deg,#132344,#0d1a31)] shadow-[0_24px_44px_rgba(8,145,178,0.16)]'
                                  : 'border-white/10 bg-[linear-gradient(180deg,#0f1b35,#091423)] hover:-translate-y-0.5 hover:border-white/18 hover:bg-[linear-gradient(180deg,#122244,#0b1730)]'
                              }`}
                            >
                              <div className="flex items-start justify-between gap-3">
                                <div>
                                  <div className="text-base font-semibold text-white">{project.name || 'Unnamed project'}</div>
                                  <div className="mt-1 text-sm text-slate-300">
                                    {project.category ? `${project.category} pathway` : 'Planning pathway'}
                                  </div>
                                </div>
                                {project.difficulty ? (
                                  <div className={`rounded-full px-3 py-1 text-[11px] uppercase tracking-[0.16em] ${key === activeProjectKey ? 'bg-cyan-300/14 text-cyan-100' : 'bg-[#081423] text-slate-400'}`}>
                                    {project.difficulty}
                                  </div>
                                ) : null}
                              </div>

                              <div className="mt-4 grid gap-2 sm:grid-cols-2">
                                <div className="rounded-[0.9rem] border border-white/8 bg-[#081423] p-3">
                                  <div className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Cost</div>
                                  <div className="mt-2 text-sm font-semibold text-white">
                                    {project.estimated_cost !== undefined ? `$${project.estimated_cost}` : 'Pending'}
                                  </div>
                                </div>
                                <div className="rounded-[0.9rem] border border-white/8 bg-[#081423] p-3">
                                  <div className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Score</div>
                                  <div className="mt-2 text-sm font-semibold text-white">
                                    {project.score !== undefined ? `${Math.round(project.score * 100)}%` : 'N/A'}
                                  </div>
                                </div>
                              </div>
                            </button>
                          );
                        })}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      }
      bottom={
        <div className="grid h-full grid-rows-[40px_minmax(0,1fr)]">
          <div className="flex items-center gap-2 border-b border-white/8 bg-[#08111d] px-4">
            {['Selected route', 'Metrics', 'Actions'].map((item, index) => (
              <button
                key={item}
                type="button"
                className={`rounded-lg px-3 py-1.5 text-xs font-medium ${index === 0 ? 'bg-cyan-300/15 text-cyan-100' : 'text-slate-400 hover:bg-white/6 hover:text-white'}`}
              >
                {item}
              </button>
            ))}
          </div>

          <div className="grid min-h-0 gap-px lg:grid-cols-[minmax(0,1fr)_320px]">
            <div className="min-h-0 overflow-y-auto bg-[#07101d] p-4">
              {activeProject ? (
                <div className="grid gap-3 xl:grid-cols-3">
                  <div className="rounded-[1rem] border border-white/10 bg-[linear-gradient(180deg,#0c1730,#091323)] p-4">
                    <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-slate-500">
                      <PackageCheck className="h-3.5 w-3.5" />
                      Cost
                    </div>
                    <div className="mt-3 text-xl font-semibold text-white">
                      {activeProject.estimated_cost !== undefined ? `$${activeProject.estimated_cost}` : 'Pending'}
                    </div>
                  </div>
                  <div className="rounded-[1rem] border border-white/10 bg-[linear-gradient(180deg,#0c1730,#091323)] p-4">
                    <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-slate-500">
                      <Target className="h-3.5 w-3.5" />
                      Suitability
                    </div>
                    <div className="mt-3 text-xl font-semibold text-white">
                      {activeProject.score !== undefined ? `${Math.round(activeProject.score * 100)}%` : 'N/A'}
                    </div>
                  </div>
                  <div className="rounded-[1rem] border border-white/10 bg-[linear-gradient(180deg,#0c1730,#091323)] p-4">
                    <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-slate-500">
                      <Wrench className="h-3.5 w-3.5" />
                      Outcome
                    </div>
                    <div className="mt-3 text-xl font-semibold text-white">
                      {activeProject.category ? `${activeProject.category} ready` : 'Review'}
                    </div>
                  </div>
                </div>
              ) : (
                <div className="rounded-[1rem] border border-white/10 bg-[linear-gradient(180deg,#0c1730,#091323)] p-4 text-sm text-slate-400">
                  Select a project card to populate the lower tray.
                </div>
              )}
            </div>

            <div className="min-h-0 overflow-y-auto bg-[#07101d] p-4">
              <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-white">
                <ArrowRight className="h-4 w-4 text-cyan-300" />
                Next actions
              </div>
              <div className="space-y-2">
                {[
                  ['Use with analysis', '/analyze'],
                  ['Inspect components', '/components'],
                  ['Move into CAD', '/cad'],
                ].map(([label, href]) => (
                  <Link key={href} href={href} className="block rounded-[1rem] border border-white/10 bg-[linear-gradient(180deg,#0c1730,#091323)] px-3 py-3 text-sm text-slate-300 transition-colors hover:bg-white/10 hover:text-white">
                    {label}
                  </Link>
                ))}
              </div>
            </div>
          </div>
        </div>
      }
      right={
        <CopilotDock
          modeLabel="Projects"
          objective="Use the agent to compare candidate paths, justify the selected route, and move the design toward a buildable outcome without leaving the shared workspace."
          status={loading ? 'Syncing' : activeProject?.name || 'No path'}
          messages={[
            {
              role: 'agent',
              body: activeProject
                ? `The current route focus is ${activeProject.name}. I can compare it against the other paths and explain why it should advance or be rejected.`
                : 'Select a route card and I will turn it into a concrete next action.',
            },
            {
              role: 'user',
              body: activeProject
                ? `Defend ${activeProject.name} against the other candidates and tell me whether it should go to CAD now.`
                : 'Prepare the strongest path from the current board state.',
            },
            errorMessage
              ? {
                  role: 'system',
                  body: errorMessage,
                }
              : {
                  role: 'agent',
                  body: 'Use the lower tray for route metrics and next actions. The center board should stay focused on comparing candidates at a glance.',
                },
          ]}
          prompts={[
            'Compare all routes',
            'Why this route?',
            'Prepare CAD handoff',
            'Ask for cheaper option',
          ]}
          links={[
            { href: '/analyze', label: 'Return to analysis' },
            { href: '/cad', label: 'Open CAD workspace' },
          ]}
          footer={
            <div className="rounded-[0.95rem] border border-white/10 bg-[#0b1628] p-3 text-sm leading-6 text-slate-300">
              Loaded routes: {projectData?.total_projects || projects.length}. Planning lanes: {orchestrationLanes.length}. Focused route: {activeProject?.name || 'None'}.
            </div>
          }
        />
      }
    />
  );
}

'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { ArrowRight, CircuitBoard, Layers3, LoaderCircle, PackageCheck, Target, Wrench } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { CopilotDock } from '@/components/copilot-dock';
import { StudioCommandBar } from '@/components/studio-command-bar';
import { StudioShell } from '@/components/studio-shell';
import { useStudioRuntime } from '@/components/studio-runtime';
import { usePageTitle } from '@/components/use-page-title';
import { WorkbenchCanvas, type WorkbenchCanvasNode } from '@/components/workbench-canvas';
import { getProxyErrorMessage, isProxyFailure, readJsonPayload, type ProxyErrorPayload } from '@/lib/proxy-client';

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
const routePositions = [
  { x: '16%', y: '18%' },
  { x: '72%', y: '18%' },
  { x: '16%', y: '66%' },
  { x: '70%', y: '68%' },
  { x: '44%', y: '12%' },
  { x: '42%', y: '74%' },
];

const routeTones = ['cyan', 'amber', 'emerald', 'slate', 'cyan', 'amber'] as const;

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
  const backendTarget = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
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
        const response = await fetch('/api/proxy/projects', { cache: 'no-store' });
        const payload = await readJsonPayload<ProjectResponse | ProxyErrorPayload>(response);
        const unavailable = isProxyFailure(payload);

        if (!active) return;
        setProjectData(unavailable ? null : payload as ProjectResponse | null);

        if (unavailable) {
          setErrorMessage(
            getProxyErrorMessage(
              payload,
              `Live project templates are unavailable at ${backendTarget}/projects. Curated fallback set loaded.`,
            ),
          );
        }
      } catch {
        if (!active) return;
        setErrorMessage(`Live project templates are unavailable at ${backendTarget}/projects. Curated fallback set loaded.`);
      } finally {
        if (active) setLoading(false);
      }
    }

    load();
    return () => {
      active = false;
    };
  }, [backendTarget]);

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
  const stageNodes = useMemo<WorkbenchCanvasNode[]>(
    () => projects.slice(0, routePositions.length).map((project, index) => {
      const key = projectKey(project, index);
      return {
        id: key,
        title: project.name || 'Unnamed project',
        description: project.category
          ? `${project.category} pathway${project.score !== undefined ? ` • ${Math.round(project.score * 100)}% suitability` : ''}`
          : 'Selectable route candidate for the active board state.',
        badge: project.difficulty || `route ${index + 1}`,
        x: routePositions[index]?.x || '50%',
        y: routePositions[index]?.y || '50%',
        tone: routeTones[index % routeTones.length],
        active: key === activeProjectKey,
        onClick: () => setSelectedProjectId(key),
      };
    }),
    [activeProjectKey, projects],
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
      commandBar={(
        <StudioCommandBar
          modeLabel="Projects"
          objective="Compare downstream routes on one decision stage and let the agent defend which path deserves fabrication or CAD time."
          context={activeProject ? `Selected route: ${activeProject.name}.` : 'No route selected yet.'}
          status={loading ? 'syncing' : 'decision ready'}
          badges={['decision-first', 'cost-aware', 'cad-bound']}
        />
      )}
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
        <WorkbenchCanvas
          toolbar={['Board', 'Rank', 'Routes']}
          activeToolbar="Board"
          toolbarStatus={loading ? 'Syncing' : 'Board ready'}
          stageLabel="Decision board"
          stageTitle="Compare routes on the same workbench plane."
          stageSummary="Candidate paths should orbit one shared board state so the user can compare cost, suitability, and next action without switching mental models."
          badge={activeProject?.name || 'No route selected'}
          metrics={[
            { label: 'Routes', value: String(projectData?.total_projects || projects.length), tone: 'cyan' },
            { label: 'Primary direction', value: activeProject?.category || 'Review', tone: 'amber' },
            { label: 'Suitability', value: activeProject?.score !== undefined ? `${Math.round(activeProject.score * 100)}%` : 'N/A', tone: 'emerald' },
          ]}
          notes={[
            'Keep candidate routes visible together. Selection should sharpen the decision, not send the user to a different page mode.',
            'The tray owns metrics and next steps. The stage owns comparison and confidence.',
          ]}
          actions={[
            { href: '/components', label: 'Component dock' },
            { href: '/cad', label: 'CAD workspace' },
          ]}
          nodes={stageNodes}
        >
          <div className="w-full max-w-2xl rounded-[1.4rem] border border-white/12 bg-[linear-gradient(180deg,rgba(10,20,35,0.92),rgba(7,17,30,0.96))] p-6 shadow-[0_28px_70px_rgba(2,6,23,0.44)]">
            <div className="flex items-start justify-between gap-4">
              <div>
                <div className="text-[11px] uppercase tracking-[0.22em] text-slate-500">Selected route</div>
                <div className="mt-2 text-2xl font-semibold text-white">{activeProject?.name || 'No project selected'}</div>
                <div className="mt-2 max-w-xl text-sm leading-6 text-slate-300">
                  {activeProject?.category
                    ? `${activeProject.category} pathway prepared for deeper justification, cost review, and CAD handoff.`
                    : 'Pick a candidate route and the board will keep the comparison stable around it.'}
                </div>
              </div>
              {activeProject?.difficulty ? (
                <div className="rounded-full border border-cyan-300/20 bg-cyan-300/10 px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-cyan-100">
                  {activeProject.difficulty}
                </div>
              ) : null}
            </div>

            <div className="mt-6 grid gap-3 sm:grid-cols-3">
              <div className="rounded-[1rem] border border-white/10 bg-[#081423] p-4">
                <div className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Estimated cost</div>
                <div className="mt-2 text-xl font-semibold text-white">
                  {activeProject?.estimated_cost !== undefined ? `$${activeProject.estimated_cost}` : 'Pending'}
                </div>
              </div>
              <div className="rounded-[1rem] border border-white/10 bg-[#081423] p-4">
                <div className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Suitability</div>
                <div className="mt-2 text-xl font-semibold text-white">
                  {activeProject?.score !== undefined ? `${Math.round(activeProject.score * 100)}%` : 'N/A'}
                </div>
              </div>
              <div className="rounded-[1rem] border border-white/10 bg-[#081423] p-4">
                <div className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Best next move</div>
                <div className="mt-2 text-xl font-semibold text-white">
                  {activeProject?.category === 'fabrication' ? 'Move to CAD' : 'Compare and refine'}
                </div>
              </div>
            </div>

            <div className="mt-5 flex flex-wrap gap-2">
              {projectLanes.map((lane) => (
                <div key={lane.label} className="rounded-full border border-white/10 bg-[#081423] px-3 py-2 text-xs text-slate-300">
                  {lane.label} • {lane.items.length}
                </div>
              ))}
            </div>
          </div>
        </WorkbenchCanvas>
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

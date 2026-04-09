'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Link from 'next/link';
import {
  Activity,
  ArrowRight,
  ChevronRight,
  CircuitBoard,
  FileUp,
  Layers,
  LoaderCircle,
  PackageCheck,
  Sparkles,
  Wrench,
  Zap,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { CopilotDock } from '@/components/copilot-dock';
import { IssuesPanel } from '@/components/cad/issues-panel';
import { PcbViewport } from '@/components/cad/pcb-viewport';
import { TreePanel } from '@/components/cad/tree-panel';
import { StudioCommandBar } from '@/components/studio-command-bar';
import { StudioShell } from '@/components/studio-shell';
import { useStudioRuntime } from '@/components/studio-runtime';
import { usePageTitle } from '@/components/use-page-title';
import { WorkbenchCanvas, type WorkbenchCanvasNode } from '@/components/workbench-canvas';
import { demoValidation } from '@/lib/cad-demo';
import {
  createProject,
  getActiveProjectId,
  loadProjects,
  saveProjects,
  setActiveProjectId,
  touchProject,
  upsertProject,
  type CadProject,
} from '@/lib/cad-project';
import type { PcbGeometry, ValidateKiCadResponse, ValidationIssue } from '@/lib/cad-types';
import { isProxyFailure } from '@/lib/proxy-client';

type SelectionState = {
  footprintRef: string | null;
};

const navItems = [
  { href: '/', label: 'Overview' },
  { href: '/analyze', label: 'Analyze' },
  { href: '/components', label: 'Components' },
  { href: '/projects', label: 'Projects' },
  { href: '/cad', label: 'CAD' },
];

const stagePositions = [
  { x: '14%', y: '18%' },
  { x: '72%', y: '18%' },
  { x: '16%', y: '68%' },
  { x: '70%', y: '70%' },
  { x: '42%', y: '12%' },
  { x: '42%', y: '76%' },
];

const stageTones = ['cyan', 'amber', 'emerald', 'slate', 'cyan', 'amber'] as const;

function panelHeading(eyebrow: string, title: string) {
  return (
    <div className="mb-4">
      <div className="text-[11px] font-semibold uppercase tracking-[0.24em] text-slate-500">{eyebrow}</div>
      <div className="mt-2 text-sm font-semibold text-white">{title}</div>
    </div>
  );
}

function sourceLabel(project: CadProject | null) {
  if (!project) return 'No source';
  if (project.source.type === 'kicad') return `KiCad import • ${project.source.filename}`;
  if (project.source.type === 'demo') return 'Intelligence demo';
  if (project.source.type === 'template') return `Template • ${project.source.templateId}`;
  return 'Blank workspace';
}

function projectNameFromFile(filename: string) {
  return filename.replace(/\.[^.]+$/, '') || filename;
}

export default function CadPage() {
  usePageTitle('Spatial CAD Workspace | Circuit.AI');

  const {
    setArtifactName,
    setAnalysisMode,
    setDetectionCount,
    setFocusedComponent,
    setFocusedProject,
  } = useStudioRuntime();

  const fileInputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [geometry, setGeometry] = useState<PcbGeometry | null>(null);
  const [issues, setIssues] = useState<ValidationIssue[]>([]);
  const [status, setStatus] = useState('idle');
  const [busy, setBusy] = useState(false);
  const [projects, setProjects] = useState<CadProject[]>([]);
  const [activeProject, setActiveProject] = useState<CadProject | null>(null);
  const [showStart, setShowStart] = useState(true);
  const [activeView, setActiveView] = useState<'design' | 'fab'>('design');
  const [fabMode, setFabMode] = useState<'robot' | 'manual'>('manual');
  const [selectedRef, setSelectedRef] = useState<string | null>(null);

  const activateProject = useCallback((project: CadProject, nextProjects?: CadProject[]) => {
    const openedProject = touchProject(project);
    setProjects((currentProjects) => {
      const persistedProjects = upsertProject(nextProjects ?? currentProjects, openedProject);
      saveProjects(persistedProjects);
      return persistedProjects;
    });
    setActiveProject(openedProject);
    setActiveProjectId(openedProject.id);
    setShowStart(false);
    return openedProject;
  }, []);

  useEffect(() => {
    const storedProjects = loadProjects();
    const activeId = getActiveProjectId();
    const project = (activeId && storedProjects.find((item) => item.id === activeId)) || storedProjects[0] || null;
    if (project) {
      activateProject(project, storedProjects);
      return;
    }
    setProjects(storedProjects);
  }, [activateProject]);

  useEffect(() => {
    setArtifactName(file?.name || null);
  }, [file, setArtifactName]);

  useEffect(() => {
    setAnalysisMode(activeView === 'fab' ? `fab-${fabMode}` : 'spatial-design');
  }, [activeView, fabMode, setAnalysisMode]);

  useEffect(() => {
    setDetectionCount(issues.length || null);
  }, [issues.length, setDetectionCount]);

  useEffect(() => {
    setFocusedComponent(selectedRef);
  }, [selectedRef, setFocusedComponent]);

  useEffect(() => {
    setFocusedProject(activeProject?.name || null);
  }, [activeProject, setFocusedProject]);

  const selectedFootprint = useMemo(
    () => geometry?.footprints.find((footprint) => footprint.ref === selectedRef) || null,
    [geometry, selectedRef],
  );

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const nextFile = event.target.files?.[0] || null;
    setFile(nextFile);

    if (!nextFile) return;

    const nextProjectName = projectNameFromFile(nextFile.name);
    const draftProject = activeProject
      ? {
          ...activeProject,
          name: nextProjectName,
          source: { type: 'kicad', filename: nextFile.name } as const,
        }
      : createProject(nextProjectName, { type: 'kicad', filename: nextFile.name });

    activateProject(draftProject, upsertProject(projects, draftProject));
    setStatus('staged');
  };

  const handleValidate = async () => {
    if (!file) return;

    setBusy(true);
    setStatus('validating');

    try {
      const formData = new FormData();
      formData.set('kicad_file', file, file.name);

      const response = await fetch('/api/proxy/validate-kicad', { method: 'POST', body: formData });
      const payload = await response.json() as ValidateKiCadResponse | { error?: string; ok?: boolean };

      if (isProxyFailure(payload)) {
        throw new Error(payload.error || 'Validation failed.');
      }

      const result = payload as ValidateKiCadResponse;
      setGeometry(result.pcb_geometry ?? null);
      setIssues(result.validation.issues || []);
      setStatus(result.manufacturing_ready ? 'ready' : 'review');
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : 'Validation request failed.';
      setGeometry(null);
      setIssues([
        {
          severity: 'error',
          component: file.name,
          issue: 'Validation request failed',
          solution: message,
        },
      ]);
      setStatus('error');
    } finally {
      setBusy(false);
    }
  };

  const handleLoadDemo = () => {
    const demoProject = activeProject ?? createProject('Intelligence Demo', { type: 'demo' });
    const nextProjects = activeProject ? projects : upsertProject(projects, demoProject);
    activateProject(demoProject, nextProjects);
    setFile(null);
    setSelectedRef(null);
    setActiveView('design');
    setFabMode('manual');
    setGeometry(demoValidation.pcb_geometry ?? null);
    setIssues(demoValidation.validation.issues);
    setStatus('ready');
  };

  const startNewProject = (name: string) => {
    const project = createProject(name);
    activateProject(project, upsertProject(projects, project));
    setFile(null);
    setGeometry(null);
    setIssues([]);
    setSelectedRef(null);
    setStatus('idle');
    setActiveView('design');
    setFabMode('manual');
  };

  const stageNodes = useMemo<WorkbenchCanvasNode[]>(() => {
    const nodes: WorkbenchCanvasNode[] = [
      {
        id: 'project',
        title: activeProject?.name || 'Spatial workspace',
        description: sourceLabel(activeProject),
        badge: activeProject?.source.type || 'blank',
        x: stagePositions[0].x,
        y: stagePositions[0].y,
        tone: stageTones[0],
      },
      {
        id: 'selection',
        title: selectedRef || 'No component focus',
        description: selectedFootprint
          ? `${selectedFootprint.value || 'Unnamed value'} • ${selectedFootprint.footprint}`
          : 'Pick a footprint in the viewport or from the tree to lock a spatial focus.',
        badge: selectedRef ? 'focus' : 'idle',
        x: stagePositions[1].x,
        y: stagePositions[1].y,
        tone: stageTones[1],
      },
      {
        id: 'issues',
        title: issues.length ? `${issues.length} validation issues` : 'No validation issues',
        description: issues.length
          ? `Most recent severity: ${String(issues[0]?.severity || 'unknown').toUpperCase()}. Use the tray to triage and queue fixes.`
          : 'Validate the imported board to populate constraints, issues, and downstream readiness.',
        badge: status,
        x: stagePositions[2].x,
        y: stagePositions[2].y,
        tone: issues.length ? 'amber' : 'emerald',
      },
      {
        id: 'view',
        title: activeView === 'design' ? 'Design orbit' : 'Fabrication orbit',
        description: activeView === 'design'
          ? 'Inspect placement, select parts, and keep geometry central.'
          : 'Shift the same board into execution context without leaving the workspace.',
        badge: activeView,
        x: stagePositions[3].x,
        y: stagePositions[3].y,
        tone: stageTones[3],
        onClick: () => setActiveView((current) => current === 'design' ? 'fab' : 'design'),
      },
      {
        id: 'fab-mode',
        title: activeView === 'fab' ? `${fabMode} execution` : 'Fabrication queue',
        description: activeView === 'fab'
          ? fabMode === 'manual'
            ? 'Operator-guided repair steps are active.'
            : 'Robot path staging is active for this board.'
          : 'Switch into fabrication mode to expose manual and robotic execution branches.',
        badge: activeView === 'fab' ? fabMode : 'standby',
        x: stagePositions[4].x,
        y: stagePositions[4].y,
        tone: stageTones[4],
        onClick: () => setFabMode((current) => current === 'manual' ? 'robot' : 'manual'),
      },
      {
        id: 'footprints',
        title: geometry ? `${geometry.footprints.length} footprints` : 'No geometry loaded',
        description: geometry
          ? `${geometry.nets.length} nets available for spatial reasoning and downstream inspection.`
          : 'Import a KiCad board or load the demo to make the 3D board stage live.',
        badge: geometry ? 'geometry' : 'awaiting',
        x: stagePositions[5].x,
        y: stagePositions[5].y,
        tone: stageTones[5],
      },
    ];

    return nodes;
  }, [activeProject, activeView, fabMode, geometry, issues, selectedFootprint, selectedRef, status]);

  const recentProjects = useMemo(
    () => [...projects].sort((a, b) => b.lastOpenedAt.localeCompare(a.lastOpenedAt)).slice(0, 5),
    [projects],
  );

  if (showStart) {
    return (
      <div className="min-h-screen overflow-hidden bg-[radial-gradient(circle_at_top_left,rgba(34,211,238,0.10),transparent_20%),radial-gradient(circle_at_82%_12%,rgba(249,115,22,0.10),transparent_18%),linear-gradient(180deg,#02050a_0%,#040a12_100%)] px-4 py-8 text-slate-100 sm:px-6 lg:px-8">
        <div className="mx-auto grid max-w-6xl gap-8 lg:grid-cols-[1.08fr_0.92fr]">
          <div className="rounded-[2rem] border border-white/10 bg-[#060b13]/92 p-8 shadow-[0_35px_80px_rgba(0,0,0,0.42)]">
            <div className="inline-flex items-center rounded-full border border-cyan-300/20 bg-cyan-300/10 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.22em] text-cyan-100">
              Spatial workbench
            </div>
            <h1 className="mt-6 max-w-3xl text-4xl font-semibold tracking-tight text-white sm:text-5xl">
              Start where board intelligence turns into a spatial engine.
            </h1>
            <p className="mt-5 max-w-2xl text-base leading-7 text-slate-300">
              This route should feel like the point where analysis, component knowledge, and project planning condense into one live board stage for geometry, fit, repair, and fabrication.
            </p>

            <div className="mt-8 grid gap-4 sm:grid-cols-2">
              <button
                type="button"
                onClick={() => startNewProject('New Design')}
                className="group rounded-[1.6rem] border border-white/10 bg-[linear-gradient(180deg,#0d1728,#09111f)] p-5 text-left transition-transform hover:-translate-y-1"
              >
                <div className="flex items-center justify-between">
                  <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-white/6 text-cyan-200">
                    <CircuitBoard className="h-5 w-5" />
                  </div>
                  <ChevronRight className="h-4 w-4 text-slate-500 transition-transform group-hover:translate-x-1 group-hover:text-white" />
                </div>
                <div className="mt-5 text-lg font-semibold text-white">Create blank workspace</div>
                <div className="mt-2 text-sm leading-6 text-slate-400">
                  Open a clean spatial shell and stage the board geometry when you are ready.
                </div>
              </button>

              <button
                type="button"
                onClick={handleLoadDemo}
                className="group rounded-[1.6rem] border border-cyan-300/22 bg-[linear-gradient(180deg,#12304a,#0c192b)] p-5 text-left transition-transform hover:-translate-y-1"
              >
                <div className="flex items-center justify-between">
                  <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-cyan-300/12 text-cyan-100">
                    <Zap className="h-5 w-5" />
                  </div>
                  <ChevronRight className="h-4 w-4 text-cyan-200 transition-transform group-hover:translate-x-1" />
                </div>
                <div className="mt-5 text-lg font-semibold text-white">Load intelligence demo</div>
                <div className="mt-2 text-sm leading-6 text-slate-300">
                  Open a pre-filled board state so the spatial shell, issues, and component focus are immediately visible.
                </div>
              </button>
            </div>

            <div className="mt-8 grid gap-3 sm:grid-cols-3">
              {[
                ['Board-first', 'The center stage stays spatial and persistent.'],
                ['Agent-assisted', 'AI stays in the work loop instead of outside it.'],
                ['Fab-aware', 'Manual and robotic execution belong in the same shell.'],
              ].map(([title, copy]) => (
                <div key={title} className="rounded-[1.3rem] border border-white/8 bg-white/[0.03] p-4">
                  <div className="text-sm font-semibold text-white">{title}</div>
                  <div className="mt-2 text-sm leading-6 text-slate-400">{copy}</div>
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-[2rem] border border-white/10 bg-[#060b13]/88 p-6 shadow-[0_35px_80px_rgba(0,0,0,0.35)]">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-500">Recent missions</div>
                <div className="mt-2 text-xl font-semibold text-white">Resume spatial context</div>
              </div>
              <div className="rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-xs text-slate-300">
                {recentProjects.length} recent
              </div>
            </div>

            <div className="mt-6 space-y-3">
              {recentProjects.length ? recentProjects.map((project) => (
                <button
                  key={project.id}
                  type="button"
                  onClick={() => activateProject(project, projects)}
                  className="w-full rounded-[1.25rem] border border-white/10 bg-[linear-gradient(180deg,#0d1728,#09111f)] px-4 py-4 text-left transition-colors hover:border-white/18 hover:bg-[linear-gradient(180deg,#11203a,#0b1730)]"
                >
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <div className="text-sm font-semibold text-white">{project.name}</div>
                      <div className="mt-1 text-xs uppercase tracking-[0.16em] text-slate-500">{sourceLabel(project)}</div>
                    </div>
                    <ArrowRight className="h-4 w-4 text-slate-500" />
                  </div>
                </button>
              )) : (
                <div className="rounded-[1.25rem] border border-white/10 bg-[linear-gradient(180deg,#0d1728,#09111f)] p-4 text-sm leading-6 text-slate-400">
                  No recent projects yet. Start a blank workspace or load the demo to seed the spatial history.
                </div>
              )}
            </div>

            <div className="mt-6 rounded-[1.4rem] border border-white/10 bg-[#08111d] p-5">
              <div className="text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-500">Why this route exists</div>
              <div className="mt-3 text-sm leading-7 text-slate-300">
                CAD here should not be decorative 3D. It should be the place where geometry, issues, part focus, fit, and execution converge without losing the upstream board intelligence.
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <StudioShell
      eyebrow="Workbench"
      title="Drive the board through a spatial editor, not a separate CAD silo."
      description="The same workbench now carries geometry, validation, part focus, and fabrication context so the spatial route extends the product instead of splitting from it."
      status={activeProject ? `Active workspace: ${activeProject.name}` : 'No active workspace'}
      commandBar={(
        <StudioCommandBar
          modeLabel="CAD"
          objective="Keep geometry live while the agent explains fit, selection, validation, and the next fabrication move."
          context={activeProject ? `${activeProject.name} • ${sourceLabel(activeProject)}` : 'No workspace active.'}
          status={busy ? 'validating' : geometry ? 'viewport live' : 'stage primed'}
          badges={['spatial-first', 'kicad-aware', 'fab-linked']}
        />
      )}
      defaultBottomOpen={true}
      activeHref="/cad"
      navItems={navItems}
      actions={
        <>
          <Button type="button" onClick={handleLoadDemo} className="rounded-full bg-white text-slate-950 hover:bg-slate-100">
            <Zap className="mr-2 h-4 w-4" />
            Demo board
          </Button>
          <Button asChild variant="outline" className="rounded-full border-white/15 bg-white/5 text-white hover:bg-white/10">
            <Link href="/projects">
              <Sparkles className="mr-2 h-4 w-4" />
              Project board
            </Link>
          </Button>
        </>
      }
      left={
        <div className="space-y-5">
          <div className="rounded-[1.5rem] border border-white/10 bg-[linear-gradient(180deg,#0c1730,#091323)] p-4">
            {panelHeading('Workspace', 'Mission state')}
            <div className="space-y-3">
              <div className="rounded-[1rem] border border-white/8 bg-[#081423] p-3">
                <div className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Project</div>
                <div className="mt-2 text-sm font-semibold text-white">{activeProject?.name || 'No active project'}</div>
                <div className="mt-2 text-sm leading-6 text-slate-400">{sourceLabel(activeProject)}</div>
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                <div className="rounded-[1rem] border border-white/8 bg-[#081423] p-3">
                  <div className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Status</div>
                  <div className="mt-2 text-lg font-semibold text-white">{status.toUpperCase()}</div>
                </div>
                <div className="rounded-[1rem] border border-white/8 bg-[#081423] p-3">
                  <div className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Geometry</div>
                  <div className="mt-2 text-lg font-semibold text-white">{geometry ? `${geometry.footprints.length} parts` : 'Pending'}</div>
                </div>
              </div>
            </div>
          </div>

          <div>
            {panelHeading('Import', 'Board intake')}
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              className="editor-dropzone flex w-full flex-col items-center justify-center px-4 py-6 text-center"
            >
              <FileUp className="mb-3 h-7 w-7 text-cyan-200" />
              <div className="text-sm font-medium text-white">{file ? file.name : 'Import KiCad board'}</div>
              <div className="mt-1 text-xs text-slate-400">
                {file ? `Ready to validate • ${(file.size / 1024).toFixed(0)} KB` : '.kicad_pcb and compatible board files'}
              </div>
            </button>
            <input
              ref={fileInputRef}
              type="file"
              accept=".kicad_pcb,.zip,.json"
              onChange={handleFileSelect}
              className="hidden"
            />
          </div>

          <div className="editor-subpanel rounded-[1.5rem] p-4">
            <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-white">
              <Layers className="h-4 w-4 text-cyan-300" />
              Stage modes
            </div>
            <div className="grid gap-2">
              <button
                type="button"
                onClick={() => setActiveView('design')}
                className={`rounded-[1rem] border px-3 py-3 text-left text-sm ${activeView === 'design' ? 'border-cyan-300/30 bg-cyan-300/10 text-cyan-100' : 'border-white/8 bg-[#081423] text-slate-300'}`}
              >
                Spatial design orbit
              </button>
              <button
                type="button"
                onClick={() => setActiveView('fab')}
                className={`rounded-[1rem] border px-3 py-3 text-left text-sm ${activeView === 'fab' ? 'border-amber-300/30 bg-amber-300/10 text-amber-100' : 'border-white/8 bg-[#081423] text-slate-300'}`}
              >
                Fabrication orbit
              </button>
            </div>

            {activeView === 'fab' ? (
              <div className="mt-4 grid gap-2 sm:grid-cols-2">
                <button
                  type="button"
                  onClick={() => setFabMode('manual')}
                  className={`rounded-[1rem] border px-3 py-3 text-sm ${fabMode === 'manual' ? 'border-white/15 bg-white text-slate-950' : 'border-white/8 bg-[#081423] text-slate-300'}`}
                >
                  Manual
                </button>
                <button
                  type="button"
                  onClick={() => setFabMode('robot')}
                  className={`rounded-[1rem] border px-3 py-3 text-sm ${fabMode === 'robot' ? 'border-orange-300/30 bg-orange-300/12 text-orange-100' : 'border-white/8 bg-[#081423] text-slate-300'}`}
                >
                  Robot
                </button>
              </div>
            ) : null}
          </div>

          <div className="rounded-[1.5rem] border border-white/10 bg-[linear-gradient(180deg,#0c1730,#091323)] p-4">
            {panelHeading('Navigator', 'Footprint tree')}
            <div className="h-64 overflow-hidden rounded-[1rem] border border-white/8 bg-[#081423]">
              <TreePanel
                geometry={geometry}
                selectedRef={selectedRef ?? undefined}
                onSelectRef={(ref) => setSelectedRef(ref)}
              />
            </div>
          </div>

          <Button
            type="button"
            onClick={handleValidate}
            disabled={!file || busy}
            className="editor-button-primary w-full rounded-full"
          >
            {busy ? <LoaderCircle className="mr-2 h-4 w-4 animate-spin" /> : <Wrench className="mr-2 h-4 w-4" />}
            {busy ? 'Validating geometry…' : 'Validate board'}
          </Button>

          <div className="rounded-[1.5rem] border border-white/8 bg-[#08111f] p-4 text-sm leading-6 text-slate-300">
            Treat this route as the spatial continuation of the same system. Geometry, issues, and execution should stay in one loop instead of opening a second product.
          </div>
        </div>
      }
      main={
        <WorkbenchCanvas
          toolbar={['Spatial', 'Assembly', 'Fabrication']}
          activeToolbar={activeView === 'design' ? 'Spatial' : 'Fabrication'}
          toolbarStatus={busy ? 'Validating board' : geometry ? 'Viewport live' : 'Awaiting geometry'}
          stageLabel="Spatial CAD"
          stageTitle="Keep the board spatial, selected, and downstream-aware."
          stageSummary="This stage should let the user orbit geometry, isolate parts, understand validation pressure, and move into fabrication without leaving the workbench grammar."
          badge={activeProject?.name || 'No workspace'}
          metrics={[
            { label: 'Project', value: activeProject?.name || 'None', tone: 'cyan' },
            { label: 'Issues', value: String(issues.length), tone: issues.length ? 'amber' : 'emerald' },
            { label: 'Selection', value: selectedRef || 'None', tone: 'slate' },
          ]}
          notes={[
            'The viewport is interactive here. Orbit, select, and inspect should all happen without losing the shared shell.',
            activeView === 'fab'
              ? `Fabrication mode is active. ${fabMode === 'manual' ? 'Manual instructions are foregrounded.' : 'Robot execution is foregrounded.'}`
              : 'Stay in design orbit until the geometry and issue state are stable enough to hand off.',
          ]}
          actions={[
            { href: '/analyze', label: 'Return to analyze' },
            { href: '/projects', label: 'Route board' },
          ]}
          nodes={stageNodes}
          contentInteractive={true}
        >
          <div className="h-full w-full overflow-hidden rounded-[1.25rem] border border-white/12 bg-[#04070c] shadow-[0_30px_70px_rgba(2,6,23,0.5)]">
            <PcbViewport
              geometry={geometry}
              issues={issues}
              selection={{ footprintRef: selectedRef }}
              onSelectionChange={({ footprintRef }: SelectionState) => setSelectedRef(footprintRef)}
            />
          </div>
        </WorkbenchCanvas>
      }
      bottom={
        <div className="grid h-full grid-rows-[40px_minmax(0,1fr)]">
          <div className="flex items-center gap-2 border-b border-white/8 bg-[#08111d] px-4">
            {['Issues', 'Projects', 'Fabrication'].map((item, index) => (
              <button
                key={item}
                type="button"
                className={`rounded-lg px-3 py-1.5 text-xs font-medium ${index === 0 ? 'bg-cyan-300/15 text-cyan-100' : 'text-slate-400 hover:bg-white/6 hover:text-white'}`}
              >
                {item}
              </button>
            ))}
          </div>

          <div className="grid min-h-0 gap-px lg:grid-cols-[minmax(0,1.1fr)_minmax(0,0.9fr)_280px]">
            <div className="min-h-0 overflow-hidden bg-[#07101d] p-4">
              <div className="h-full">
                <IssuesPanel issues={issues} onFocusComponent={(component) => setSelectedRef(component)} />
              </div>
            </div>

            <div className="min-h-0 overflow-y-auto bg-[#07101d] p-4">
              <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-white">
                <PackageCheck className="h-4 w-4 text-cyan-300" />
                Project stack
              </div>
              <div className="space-y-3">
                {recentProjects.map((project) => (
                  <button
                    key={project.id}
                    type="button"
                    onClick={() => activateProject(project, projects)}
                    className={`w-full rounded-[1rem] border px-3 py-3 text-left transition-colors ${
                      project.id === activeProject?.id
                        ? 'border-cyan-300/30 bg-cyan-300/10 text-cyan-100'
                        : 'border-white/10 bg-[linear-gradient(180deg,#0c1730,#091323)] text-slate-300 hover:border-white/18'
                    }`}
                  >
                    <div className="text-sm font-semibold">{project.name}</div>
                    <div className="mt-1 text-xs uppercase tracking-[0.16em] text-slate-500">{sourceLabel(project)}</div>
                  </button>
                ))}
              </div>
            </div>

            <div className="min-h-0 overflow-y-auto bg-[#07101d] p-4">
              <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-white">
                <Activity className="h-4 w-4 text-cyan-300" />
                Fab queue
              </div>
              <div className="space-y-3">
                {(activeView === 'fab'
                  ? fabMode === 'manual'
                    ? ['Heat target pad', 'Apply flux', 'Lift component carefully']
                    : ['Prepare robot path', 'Verify nozzle clearance', 'Queue execution packet']
                  : ['Validate board geometry', 'Select suspect component', 'Choose fabrication orbit']
                ).map((step) => (
                  <div key={step} className="rounded-[1rem] border border-white/10 bg-[linear-gradient(180deg,#0c1730,#091323)] p-3 text-sm text-slate-300">
                    {step}
                  </div>
                ))}
                <Link
                  href="/projects"
                  className="block rounded-[1rem] border border-white/10 bg-[linear-gradient(180deg,#0c1730,#091323)] px-3 py-3 text-sm text-slate-300 transition-colors hover:border-white/18 hover:text-white"
                >
                  Hand route back to project board
                </Link>
              </div>
            </div>
          </div>
        </div>
      }
      right={
        <CopilotDock
          modeLabel="CAD"
          objective="Use the agent to explain selected geometry, justify spatial decisions, and move the board into fabrication or repair without breaking context."
          status={busy ? 'Validating' : selectedRef || status}
          messages={[
            {
              role: 'agent',
              body: activeProject
                ? `The current spatial focus is ${activeProject.name}. I can explain board geometry, selected parts, fit questions, and the strongest next execution move.`
                : 'Open a workspace or load the demo and I will anchor the spatial reasoning around it.',
            },
            {
              role: 'user',
              body: selectedRef
                ? `Tell me what ${selectedRef} means in this geometry and whether it changes the fabrication path.`
                : 'Keep the board stable and tell me what should be spatially inspected next.',
            },
            issues.length
              ? {
                  role: 'system',
                  body: `${issues.length} validation issues are active. The lower tray owns detailed triage while this dock narrates the consequences.`,
                }
              : {
                  role: 'agent',
                  body: activeView === 'fab'
                    ? 'Fabrication mode is active. Use this dock for execution reasoning while the stage remains spatial.'
                    : 'Stay in design orbit until geometry and issue pressure are clear enough to branch with confidence.',
                },
          ]}
          prompts={[
            'Explain selected part in 3D',
            'Prepare fabrication handoff',
            'Highlight highest-risk issue',
            'Ask whether robot mode is viable',
          ]}
          links={[
            { href: '/analyze', label: 'Return to analysis' },
            { href: '/projects', label: 'Open project routes' },
          ]}
          footer={
            <div className="rounded-[0.95rem] border border-white/10 bg-[#0b1628] p-3 text-sm leading-6 text-slate-300">
              <div>Project: {activeProject?.name || 'None'}</div>
              <div>Selection: {selectedRef || 'None'}</div>
              <div>Geometry: {geometry ? `${geometry.footprints.length} footprints • ${geometry.nets.length} nets` : 'No board loaded'}</div>
            </div>
          }
        />
      }
    />
  );
}

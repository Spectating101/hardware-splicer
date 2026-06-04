'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Link from 'next/link';
import {
  FileUp,
  Layers,
  LoaderCircle,
  PackageCheck,
  Wrench,
  Zap,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { IssuesPanel } from '@/components/cad/issues-panel';
import { PcbViewport } from '@/components/cad/pcb-viewport';
import { TreePanel } from '@/components/cad/tree-panel';
import { useStudioRuntime } from '@/components/studio-runtime';
import { usePageTitle } from '@/components/use-page-title';
import { demoValidation } from '@/lib/cad-demo';
import {
  cadTemplates,
  type CadTemplate,
} from '@/lib/cad-templates';
import {
  createProject,
  getActiveProjectId,
  loadProjects,
  saveProjects,
  setActiveProjectId,
  touchProject,
  upsertProject,
  type CadProject,
  type CadProjectSource,
} from '@/lib/cad-project';
import type { PcbGeometry, ValidateKiCadResponse, ValidationIssue } from '@/lib/cad-types';
import { isProxyFailure } from '@/lib/proxy-client';

type SelectionState = {
  footprintRef: string | null;
};

function pickRefFromComponent(component: string, geometry: PcbGeometry | null): string | null {
  if (!geometry) return null;

  const match = (component || '').toUpperCase().match(/\b[A-Z]{1,3}\d{1,4}\b/);
  if (!match) return null;

  const ref = match[0];
  return geometry.footprints.some((footprint) => footprint.ref.toUpperCase() === ref) ? ref : null;
}

function sourceLabel(project: CadProject | null) {
  if (!project) return 'No source';
  if (project.source.type === 'kicad') return `KiCad import • ${project.source.filename}`;
  if (project.source.type === 'demo') return 'Reference demo board';
  if (project.source.type === 'template') return `Template • ${project.source.templateId}`;
  return 'Blank workspace';
}

function projectNameFromFile(filename: string) {
  return filename.replace(/\.[^.]+$/, '') || filename;
}

function formatMillimeters(value: number) {
  return `${value.toFixed(1)} mm`;
}

function issueSummary(issues: ValidationIssue[]) {
  return issues.reduce(
    (summary, issue) => {
      const severity = String(issue.severity).toLowerCase();

      if (severity === 'critical') summary.critical += 1;
      else if (severity === 'error') summary.error += 1;
      else if (severity === 'warning') summary.warning += 1;
      else summary.info += 1;

      return summary;
    },
    { critical: 0, error: 0, warning: 0, info: 0 },
  );
}

async function loadPublicFile(path: string, filename: string) {
  const response = await fetch(path);
  if (!response.ok) throw new Error(`Failed to load ${path}`);

  const blob = await response.blob();
  return new File([blob], filename, { type: 'text/plain' });
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
  const [pcbFile, setPcbFile] = useState<File | null>(null);
  const [netFile, setNetFile] = useState<File | null>(null);
  const [activeFileKind, setActiveFileKind] = useState<'pcb' | 'net'>('pcb');
  const [geometry, setGeometry] = useState<PcbGeometry | null>(null);
  const [issues, setIssues] = useState<ValidationIssue[]>([]);
  const [nextSteps, setNextSteps] = useState<string[]>([]);
  const [status, setStatus] = useState('idle');
  const [manufacturingReady, setManufacturingReady] = useState(false);
  const [busy, setBusy] = useState(false);
  const [backendOk, setBackendOk] = useState<boolean | null>(null);
  const [projects, setProjects] = useState<CadProject[]>([]);
  const [activeProject, setActiveProject] = useState<CadProject | null>(null);
  const [showStart, setShowStart] = useState(true);
  const [starterChecklist, setStarterChecklist] = useState<string[]>([]);
  const [defaultHints, setDefaultHints] = useState<Record<string, unknown> | null>(null);
  const [activeTemplateId, setActiveTemplateId] = useState<string | null>(null);
  const [exportStatus, setExportStatus] = useState('');
  const [lastGerberFilename, setLastGerberFilename] = useState<string | null>(null);
  const [activeView, setActiveView] = useState<'design' | 'fab'>('design');
  const [fabMode, setFabMode] = useState<'robot' | 'manual'>('manual');
  const [selectedRef, setSelectedRef] = useState<string | null>(null);
  const [activeTray, setActiveTray] = useState<'issues' | 'projects' | 'fabrication'>('issues');

  const activeFile = useMemo(
    () => (activeFileKind === 'pcb' ? pcbFile : netFile),
    [activeFileKind, netFile, pcbFile],
  );

  const selectedFootprint = useMemo(
    () => geometry?.footprints.find((footprint) => footprint.ref === selectedRef) || null,
    [geometry, selectedRef],
  );

  const selectedIssues = useMemo(
    () => (selectedRef ? issues.filter((issue) => issue.component === selectedRef) : []),
    [issues, selectedRef],
  );

  const primaryIssue = selectedIssues[0] || issues[0] || null;
  const visibleNets = useMemo(
    () => geometry?.nets.filter((net) => net.name.trim()).slice(0, 4) || [],
    [geometry],
  );

  const summary = useMemo(() => issueSummary(issues), [issues]);
  const recentProjects = useMemo(
    () => [...projects].sort((a, b) => b.lastOpenedAt.localeCompare(a.lastOpenedAt)).slice(0, 8),
    [projects],
  );

  const headerStatus = useMemo(() => {
    if (busy) return 'Validating';
    if (status === 'idle') return 'Ready';
    return status.toUpperCase();
  }, [busy, status]);

  const hydrateTemplateContext = useCallback((source: CadProjectSource) => {
    if (source.type === 'template') {
      const template = cadTemplates.find((item) => item.id === source.templateId);
      setStarterChecklist(template?.starterChecklist || []);
      setDefaultHints(template?.defaultHints ?? null);
      setActiveTemplateId(template?.id || null);
      return;
    }

    if (source.type === 'demo') {
      setStarterChecklist([
        'Click issues to focus the board',
        'Switch between design review and fabrication review',
        'Export manufacturing artifacts after validating a real KiCad board',
      ]);
      setDefaultHints(null);
      setActiveTemplateId(null);
      return;
    }

    setStarterChecklist([]);
    setDefaultHints(null);
    setActiveTemplateId(null);
  }, []);

  const resetWorkspace = useCallback(() => {
    setPcbFile(null);
    setNetFile(null);
    setActiveFileKind('pcb');
    setGeometry(null);
    setIssues([]);
    setNextSteps([]);
    setSelectedRef(null);
    setStatus('idle');
    setManufacturingReady(false);
    setExportStatus('');
    setLastGerberFilename(null);
    setActiveView('design');
    setFabMode('manual');
    setActiveTray('issues');
  }, []);

  const activateProject = useCallback((project: CadProject, nextProjects?: CadProject[]) => {
    const openedProject = touchProject(project);

    setProjects((currentProjects) => {
      const persisted = upsertProject(nextProjects ?? currentProjects, openedProject);
      saveProjects(persisted);
      return persisted;
    });

    setActiveProject(openedProject);
    setActiveProjectId(openedProject.id);
    setShowStart(false);
    hydrateTemplateContext(openedProject.source);

    if (openedProject.source.type === 'demo') {
      setPcbFile(null);
      setNetFile(null);
      setActiveFileKind('pcb');
      setGeometry(demoValidation.pcb_geometry ?? null);
      setIssues(demoValidation.validation.issues);
      setNextSteps(demoValidation.next_steps || []);
      setSelectedRef(demoValidation.pcb_geometry?.footprints?.[0]?.ref || null);
      setStatus(demoValidation.status || 'ready');
      setManufacturingReady(Boolean(demoValidation.manufacturing_ready));
      setExportStatus('');
      setLastGerberFilename(null);
      return openedProject;
    }

    if (openedProject.source.type !== 'kicad') {
      resetWorkspace();
    } else {
      setExportStatus('');
      setLastGerberFilename(null);
    }

    return openedProject;
  }, [hydrateTemplateContext, resetWorkspace]);

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
    setArtifactName(activeFile?.name || null);
  }, [activeFile, setArtifactName]);

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

  useEffect(() => {
    if (activeView === 'fab') setActiveTray('fabrication');
  }, [activeView]);

  const createAndActivateProject = (name: string, source: CadProjectSource) => {
    const project = createProject(name.trim(), source);
    const nextProjects = upsertProject(projects, project);
    saveProjects(nextProjects);
    setProjects(nextProjects);
    activateProject(project, nextProjects);
  };

  const startNewProject = (source: CadProjectSource) => {
    const defaultName =
      source.type === 'demo'
        ? 'Demo Board'
        : source.type === 'template'
          ? 'Template Project'
          : 'New Project';

    const name = window.prompt('Project name?', defaultName);
    if (!name) return;

    createAndActivateProject(name, source);
  };

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const nextFile = event.target.files?.[0] || null;
    if (!nextFile) return;

    const isPcb = nextFile.name.toLowerCase().endsWith('.kicad_pcb');
    const project =
      activeProject ||
      createProject(projectNameFromFile(nextFile.name), isPcb ? { type: 'kicad', filename: nextFile.name } : { type: 'blank' });

    const nextProject = isPcb
      ? {
          ...project,
          name: projectNameFromFile(nextFile.name),
          source: { type: 'kicad', filename: nextFile.name } as const,
        }
      : project;

    activateProject(nextProject, upsertProject(projects, nextProject));

    if (isPcb) {
      setPcbFile(nextFile);
      setActiveFileKind('pcb');
      setGeometry(null);
      setIssues([]);
      setNextSteps([]);
      setSelectedRef(null);
      setStatus('staged');
      setExportStatus('');
      setLastGerberFilename(null);
    } else {
      setNetFile(nextFile);
      setActiveFileKind('net');
      setExportStatus('Netlist loaded. BOM export is available once you want manufacturing outputs.');
    }

    event.target.value = '';
  };

  const validate = useCallback(async (fileOverride?: File) => {
    const file = fileOverride ?? pcbFile;
    if (!file) return null;

    setBusy(true);
    setStatus('running');

    try {
      if (backendOk === null) {
        try {
          const health = await fetch('/api/proxy/health', { method: 'GET' });
          setBackendOk(health.ok);
        } catch {
          setBackendOk(false);
        }
      }

      const formData = new FormData();
      formData.set('kicad_file', file, file.name);
      if (defaultHints) formData.set('hints', JSON.stringify(defaultHints));

      const response = await fetch('/api/proxy/validate-kicad', { method: 'POST', body: formData });
      const payload = (await response.json()) as ValidateKiCadResponse | { error?: string; ok?: boolean };

      if (isProxyFailure(payload)) {
        throw new Error(payload.error || 'Validation failed.');
      }

      const result = payload as ValidateKiCadResponse;
      setGeometry(result.pcb_geometry ?? null);
      setIssues(result.validation.issues || []);
      setNextSteps(result.next_steps || []);
      setManufacturingReady(Boolean(result.manufacturing_ready));
      setStatus(result.status || (result.manufacturing_ready ? 'ready' : 'review'));
      setSelectedRef(result.pcb_geometry?.footprints?.[0]?.ref || null);
      setExportStatus(
        result.validation.issues?.length
          ? 'Validation loaded the board and issue set. Review the board, then export manufacturing artifacts when ready.'
          : 'Validation completed with no active issues.',
      );

      if (activeProject) {
        const updatedProject: CadProject = {
          ...activeProject,
          lastOpenedAt: new Date().toISOString(),
          source: { type: 'kicad', filename: file.name },
        };
        const nextProjects = upsertProject(projects, updatedProject);
        saveProjects(nextProjects);
        setProjects(nextProjects);
        setActiveProject(updatedProject);
        setActiveProjectId(updatedProject.id);
      }

      return result;
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
      setNextSteps([]);
      setManufacturingReady(false);
      setStatus('error');
      setExportStatus(message);
      return null;
    } finally {
      setBusy(false);
    }
  }, [activeProject, backendOk, defaultHints, pcbFile, projects]);

  const loadDemo = () => {
    const existingDemo = projects.find((project) => project.source.type === 'demo');
    const demoProject = existingDemo
      ? { ...existingDemo, name: 'Reference Demo Board', source: { type: 'demo' } as const }
      : createProject('Reference Demo Board', { type: 'demo' });

    activateProject(demoProject, upsertProject(projects, demoProject));
  };

  const loadTemplateSample = async (template: CadTemplate, mode: 'load' | 'guided') => {
    if (!template.sampleFiles) return;

    createAndActivateProject(template.productName ?? template.name, template.source);
    hydrateTemplateContext(template.source);

    try {
      const [pcb, net] = await Promise.all([
        loadPublicFile(template.sampleFiles.pcbPath, template.sampleFiles.pcbFilename),
        loadPublicFile(template.sampleFiles.netPath, template.sampleFiles.netFilename),
      ]);

      setPcbFile(pcb);
      setNetFile(net);
      setActiveFileKind('pcb');
      setStatus('staged');
      setExportStatus(mode === 'guided' ? 'Sample loaded. Running validate…' : 'Sample loaded. Review it or validate when ready.');

      if (mode === 'guided') {
        const result = await validate(pcb);
        const firstIssue = result?.validation.issues?.[0];
        const firstRef = firstIssue ? pickRefFromComponent(firstIssue.component, result?.pcb_geometry ?? null) : null;
        if (firstRef) setSelectedRef(firstRef);
      }
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : 'Failed to load sample.';
      setExportStatus(message);
    }
  };

  const exportGerbers = async () => {
    if (!pcbFile) return;

    setExportStatus('Generating Gerbers…');
    setLastGerberFilename(null);

    try {
      const formData = new FormData();
      formData.set('pcb_file', pcbFile, pcbFile.name);
      formData.set('quantity', '5');

      const response = await fetch('/api/proxy/manufacture/gerber', { method: 'POST', body: formData });
      const payload = await response.json();

      if (!response.ok) {
        setExportStatus(payload?.error ? `Gerber export failed: ${payload.error}` : 'Gerber export failed.');
        return;
      }

      const zipFile: string | undefined = payload?.zip_file;
      const filename = zipFile ? String(zipFile).split('/').pop() : null;

      if (filename) {
        setLastGerberFilename(filename);
        setExportStatus(`Gerbers ready: ${filename}`);
      } else {
        setExportStatus('Gerbers generated.');
      }
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : 'Gerber export failed.';
      setExportStatus(`Gerber export error: ${message}`);
    }
  };

  const exportBom = async (format: 'json' | 'csv') => {
    if (!netFile) return;

    setExportStatus(`Generating BOM (${format.toUpperCase()})…`);

    try {
      const formData = new FormData();
      formData.set('netlist_file', netFile, netFile.name);
      formData.set('include_pricing', 'false');
      formData.set('format', format);

      const response = await fetch('/api/proxy/manufacture/bom', { method: 'POST', body: formData });
      if (!response.ok) {
        const text = await response.text();
        setExportStatus(`BOM export failed: ${text.slice(0, 200)}`);
        return;
      }

      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = format === 'csv' ? 'bom.csv' : 'bom.json';
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
      setExportStatus(`BOM downloaded (${format.toUpperCase()}).`);
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : 'BOM export failed.';
      setExportStatus(`BOM export error: ${message}`);
    }
  };

  const focusComponent = (component: string) => {
    const ref = pickRefFromComponent(component, geometry);
    if (ref) setSelectedRef(ref);
  };

  const heroTemplate = cadTemplates.find((template) => template.id === 'hero-drone-fc-power') || null;
  const activeTemplate = cadTemplates.find((template) => template.id === activeTemplateId) || null;

  return (
    <div className="min-h-screen bg-[#070b14] text-white">
      <div className="border-b border-white/10 bg-[#0b1220]">
        <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-3">
          <div className="flex min-w-0 flex-wrap items-center gap-2">
            <Link href="/" className="text-sm font-semibold tracking-[0.12em] text-white/90">
              Circuit.AI / CAD
            </Link>
            {activeProject ? (
              <div className="rounded border border-white/10 bg-white/5 px-2 py-1 text-xs text-white/70">
                {activeProject.name}
              </div>
            ) : null}
            <div className="rounded border border-white/10 bg-white/5 px-2 py-1 text-xs text-white/70">
              {headerStatus}
            </div>
            {backendOk !== null ? (
              <div
                className={`rounded border px-2 py-1 text-xs ${
                  backendOk
                    ? 'border-emerald-400/20 bg-emerald-500/10 text-emerald-200'
                    : 'border-red-400/20 bg-red-500/10 text-red-200'
                }`}
              >
                API {backendOk ? 'Connected' : 'Offline'}
              </div>
            ) : null}
            {manufacturingReady ? (
              <div className="rounded border border-emerald-400/20 bg-emerald-500/10 px-2 py-1 text-xs text-emerald-200">
                Manufacturing Ready
              </div>
            ) : null}
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <input
              ref={fileInputRef}
              type="file"
              className="hidden"
              accept=".kicad_pcb,.net"
              onChange={handleFileSelect}
            />
            <Button variant="outline" onClick={() => setShowStart(true)}>
              Projects
            </Button>
            <Button asChild variant="outline">
              <Link href="/projects">Project board</Link>
            </Button>
            <Button variant="outline" onClick={() => fileInputRef.current?.click()}>
              <FileUp className="mr-2 h-4 w-4" />
              Import KiCad
            </Button>
            <Button disabled={!pcbFile || busy} onClick={() => void validate()}>
              {busy ? <LoaderCircle className="mr-2 h-4 w-4 animate-spin" /> : <Wrench className="mr-2 h-4 w-4" />}
              Validate
            </Button>
            <Button variant="outline" onClick={loadDemo}>
              <Zap className="mr-2 h-4 w-4" />
              Demo board
            </Button>
            {heroTemplate ? (
              <Button variant="outline" onClick={() => void loadTemplateSample(heroTemplate, 'guided')}>
                Guided Drone
              </Button>
            ) : null}
          </div>
        </div>
      </div>

      <div className="grid gap-3 p-3 xl:h-[calc(100vh-73px)] xl:grid-cols-[280px_minmax(0,1fr)_360px] xl:grid-rows-[minmax(480px,1fr)_230px]">
        <section className="order-1 flex min-h-[420px] min-w-0 flex-col overflow-hidden rounded-xl border border-white/10 bg-[#0b1220] xl:col-start-2 xl:row-start-1 xl:min-h-0">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/10 px-4 py-3">
            <div>
              <div className="text-sm font-semibold text-white/90">Board stage</div>
              <div className="mt-1 text-xs text-white/50">
                {activeProject ? `${activeProject.name} • ${sourceLabel(activeProject)}` : 'Create a project or load the demo board.'}
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <button
                type="button"
                onClick={() => setActiveView('design')}
                className={`rounded border px-3 py-1.5 text-xs ${activeView === 'design' ? 'border-blue-400/30 bg-blue-500/10 text-blue-200' : 'border-white/10 bg-white/5 text-white/65 hover:bg-white/10'}`}
              >
                Design review
              </button>
              <button
                type="button"
                onClick={() => setActiveView('fab')}
                className={`rounded border px-3 py-1.5 text-xs ${activeView === 'fab' ? 'border-amber-400/30 bg-amber-500/10 text-amber-200' : 'border-white/10 bg-white/5 text-white/65 hover:bg-white/10'}`}
              >
                Fabrication review
              </button>
            </div>
          </div>

          <div className="min-h-0 flex-1 p-3">
            <PcbViewport
              geometry={geometry}
              issues={issues}
              selection={{ footprintRef: selectedRef }}
              onSelectionChange={({ footprintRef }: SelectionState) => setSelectedRef(footprintRef)}
            />
          </div>
        </section>

        <aside className="order-2 flex min-h-0 flex-col gap-3 xl:col-start-3 xl:row-span-2">
          <div className="rounded-xl border border-white/10 bg-[#0b1220] p-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="text-xs font-semibold uppercase tracking-[0.18em] text-white/45">Selection inspector</div>
                <div className="mt-2 text-2xl font-semibold text-white">
                  {selectedFootprint?.ref || selectedRef || 'None'}
                </div>
              </div>
              <div className="rounded border border-white/10 bg-white/5 px-2 py-1 text-xs text-white/60">
                {selectedIssues.length ? `${selectedIssues.length} issue` : geometry ? 'Geometry live' : 'Idle'}
              </div>
            </div>

            <div className="mt-4 grid gap-3">
              <div className="rounded-lg border border-white/10 bg-white/5 p-3">
                <div className="text-[11px] uppercase tracking-[0.18em] text-white/45">Footprint</div>
                <div className="mt-2 text-sm font-semibold text-white/90">
                  {selectedFootprint ? `${selectedFootprint.value || 'Unnamed'} • ${selectedFootprint.footprint}` : 'Select a footprint from the board or project tree.'}
                </div>
                {selectedFootprint ? (
                  <div className="mt-3 grid gap-2 sm:grid-cols-2">
                    <div className="rounded border border-white/10 bg-black/20 p-2 text-xs text-white/70">
                      Layer
                      <div className="mt-1 text-sm font-semibold text-white">{selectedFootprint.layer}</div>
                    </div>
                    <div className="rounded border border-white/10 bg-black/20 p-2 text-xs text-white/70">
                      Rotation
                      <div className="mt-1 text-sm font-semibold text-white">{selectedFootprint.at.rot_deg}°</div>
                    </div>
                    <div className="rounded border border-white/10 bg-black/20 p-2 text-xs text-white/70 sm:col-span-2">
                      Position
                      <div className="mt-1 text-sm font-semibold text-white">
                        {formatMillimeters(selectedFootprint.at.x)} × {formatMillimeters(selectedFootprint.at.y)}
                      </div>
                    </div>
                  </div>
                ) : null}
              </div>

              <div className="rounded-lg border border-white/10 bg-white/5 p-3">
                <div className="text-[11px] uppercase tracking-[0.18em] text-white/45">Constraint context</div>
                <div className="mt-2 text-sm text-white/80">
                  {selectedIssues[0]?.issue || primaryIssue?.issue || 'No active constraint tied to the current selection.'}
                </div>
                <div className="mt-2 text-sm text-cyan-200/90">
                  {selectedIssues[0]?.solution || primaryIssue?.solution || 'Validate a board to populate review context.'}
                </div>
              </div>

              <div className="rounded-lg border border-white/10 bg-white/5 p-3 text-sm text-white/70">
                <div className="text-[11px] uppercase tracking-[0.18em] text-white/45">Review mode</div>
                <div className="mt-2">
                  {activeView === 'fab'
                    ? `${fabMode === 'manual' ? 'Manual rework' : 'Robot execution'} active`
                    : 'Design review active'}
                </div>
              </div>
            </div>
          </div>

          <div className="min-h-[320px] flex-1">
            <IssuesPanel issues={issues} onFocusComponent={focusComponent} />
          </div>
        </aside>

        <section className="order-3 overflow-hidden rounded-xl border border-white/10 bg-[#0b1220] xl:col-start-2 xl:row-start-2">
          <div className="flex items-center gap-2 border-b border-white/10 px-4 py-3">
            {[
              ['issues', 'Issues'],
              ['projects', 'Projects'],
              ['fabrication', 'Fabrication'],
            ].map(([value, label]) => (
              <button
                key={value}
                type="button"
                onClick={() => setActiveTray(value as 'issues' | 'projects' | 'fabrication')}
                className={`rounded border px-3 py-1.5 text-xs ${activeTray === value ? 'border-blue-400/30 bg-blue-500/10 text-blue-200' : 'border-white/10 bg-white/5 text-white/60 hover:bg-white/10'}`}
              >
                {label}
              </button>
            ))}
          </div>

          <div className="grid gap-3 p-4 md:grid-cols-[minmax(0,1.15fr)_300px]">
            {activeTray === 'issues' ? (
              <>
                <div className="rounded-lg border border-white/10 bg-white/5 p-3">
                  <div className="flex items-center justify-between">
                    <div className="text-sm font-semibold text-white/90">Next steps</div>
                    <div className="text-xs text-white/45">
                      {activeFile ? `Active file: ${activeFile.name}` : activeProject ? 'Project active' : 'No project'}
                    </div>
                  </div>
                  <div className="mt-3 grid gap-3 md:grid-cols-2">
                    <div className="rounded border border-white/10 bg-black/20 p-3 text-sm text-white/70">
                      {starterChecklist.length === 0 && nextSteps.length === 0 ? (
                        <div className="text-white/50">Start a project or validate a board to get a review checklist.</div>
                      ) : (
                        <ol className="list-decimal space-y-1 pl-4">
                          {starterChecklist.map((item, index) => (
                            <li key={`starter-${index}`}>{item}</li>
                          ))}
                          {nextSteps.map((item, index) => (
                            <li key={`next-${index}`}>{item}</li>
                          ))}
                        </ol>
                      )}
                    </div>
                    <div className="rounded border border-white/10 bg-black/20 p-3 text-sm text-white/70">
                      <div className="text-[11px] uppercase tracking-[0.18em] text-white/45">Validation summary</div>
                      <div className="mt-2">{exportStatus || 'Validate a board to populate guidance and manufacturing readiness.'}</div>
                    </div>
                  </div>
                </div>

                <div className="grid gap-3">
                  <div className="rounded-lg border border-white/10 bg-white/5 p-3">
                    <div className="text-sm font-semibold text-white/90">DRC summary</div>
                    <div className="mt-3 grid grid-cols-2 gap-2">
                      {[
                        ['Critical', summary.critical],
                        ['Error', summary.error],
                        ['Warning', summary.warning],
                        ['Info', summary.info],
                      ].map(([label, value]) => (
                        <div key={label} className="rounded border border-white/10 bg-black/20 p-2">
                          <div className="text-[11px] uppercase tracking-[0.18em] text-white/45">{label}</div>
                          <div className="mt-1 text-lg font-semibold text-white">{value}</div>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="rounded-lg border border-white/10 bg-white/5 p-3">
                    <div className="text-sm font-semibold text-white/90">Visible nets</div>
                    <div className="mt-3 flex flex-wrap gap-2">
                      {visibleNets.length ? visibleNets.map((net) => (
                        <div key={net.id} className="rounded border border-white/10 bg-black/20 px-2 py-1 text-xs text-white/70">
                          {net.name}
                        </div>
                      )) : (
                        <div className="text-sm text-white/50">No named nets loaded.</div>
                      )}
                    </div>
                  </div>
                </div>
              </>
            ) : null}

            {activeTray === 'projects' ? (
              <>
                <div className="rounded-lg border border-white/10 bg-white/5 p-3">
                  <div className="text-sm font-semibold text-white/90">Recent projects</div>
                  <div className="mt-3 grid gap-2">
                    {recentProjects.length ? recentProjects.map((project) => (
                      <button
                        key={project.id}
                        type="button"
                        onClick={() => activateProject(project, projects)}
                        className={`rounded border px-3 py-2 text-left ${
                          project.id === activeProject?.id
                            ? 'border-blue-400/30 bg-blue-500/10 text-blue-100'
                            : 'border-white/10 bg-black/20 text-white/75 hover:bg-white/10'
                        }`}
                      >
                        <div className="text-sm font-semibold">{project.name}</div>
                        <div className="mt-1 text-xs text-white/45">{sourceLabel(project)}</div>
                      </button>
                    )) : (
                      <div className="rounded border border-white/10 bg-black/20 p-3 text-sm text-white/50">
                        No projects yet.
                      </div>
                    )}
                  </div>
                </div>

                <div className="grid gap-3">
                  <div className="rounded-lg border border-white/10 bg-white/5 p-3">
                    <div className="text-sm font-semibold text-white/90">Active workspace</div>
                    <div className="mt-2 text-lg font-semibold text-white">{activeProject?.name || 'None'}</div>
                    <div className="mt-2 text-sm text-white/60">{sourceLabel(activeProject)}</div>
                  </div>

                  {activeTemplate ? (
                    <div className="rounded-lg border border-white/10 bg-white/5 p-3">
                      <div className="text-sm font-semibold text-white/90">{activeTemplate.productName ?? activeTemplate.name}</div>
                      <div className="mt-2 text-sm text-white/60">{activeTemplate.productPitch ?? activeTemplate.description}</div>
                    </div>
                  ) : null}
                </div>
              </>
            ) : null}

            {activeTray === 'fabrication' ? (
              <>
                <div className="rounded-lg border border-white/10 bg-white/5 p-3">
                  <div className="text-sm font-semibold text-white/90">Fabrication actions</div>
                  <div className="mt-3 grid gap-2 md:grid-cols-2">
                    {(activeView === 'fab'
                      ? fabMode === 'manual'
                        ? ['Heat target pad', 'Apply flux', 'Lift component carefully', 'Document rework result']
                        : ['Prepare robot path', 'Verify nozzle clearance', 'Stage execution packet', 'Dry-run robot sequence']
                      : ['Validate board geometry', 'Review highest-risk issue', 'Switch to fabrication review', 'Generate outputs']
                    ).map((step) => (
                      <div key={step} className="rounded border border-white/10 bg-black/20 p-3 text-sm text-white/75">
                        {step}
                      </div>
                    ))}
                  </div>
                </div>

                <div className="grid gap-3">
                  <div className="rounded-lg border border-white/10 bg-white/5 p-3">
                    <div className="text-sm font-semibold text-white/90">Outputs</div>
                    <div className="mt-3 grid gap-2">
                      <Button variant="outline" disabled={!pcbFile || busy} onClick={() => void exportGerbers()}>
                        Export Gerbers
                      </Button>
                      <Button variant="outline" disabled={!netFile || busy} onClick={() => void exportBom('json')}>
                        Export BOM (JSON)
                      </Button>
                      <Button variant="outline" disabled={!netFile || busy} onClick={() => void exportBom('csv')}>
                        Export BOM (CSV)
                      </Button>
                      {lastGerberFilename ? (
                        <Button
                          variant="outline"
                          onClick={() => {
                            window.location.href = `/api/proxy/manufacture/download-gerber/${encodeURIComponent(lastGerberFilename)}`;
                          }}
                        >
                          Download ZIP
                        </Button>
                      ) : null}
                    </div>
                  </div>

                  <div className="rounded-lg border border-white/10 bg-white/5 p-3 text-sm text-white/70">
                    <div className="text-[11px] uppercase tracking-[0.18em] text-white/45">Gating issue</div>
                    <div className="mt-2">
                      {primaryIssue
                        ? `${primaryIssue.issue}. ${primaryIssue.solution}`
                        : 'No active issue is blocking fabrication in the current session.'}
                    </div>
                  </div>
                </div>
              </>
            ) : null}
          </div>
        </section>

        <aside className="order-4 flex min-h-0 flex-col gap-3 xl:col-start-1 xl:row-span-2">
          <div className="rounded-xl border border-white/10 bg-[#0b1220] p-4">
            <div className="text-xs font-semibold uppercase tracking-[0.18em] text-white/45">Workspace</div>
            <div className="mt-2 text-xl font-semibold text-white">
              {activeProject?.name || 'No project'}
            </div>
            <div className="mt-2 text-sm text-white/60">{sourceLabel(activeProject)}</div>

            <div className="mt-4 grid gap-2 sm:grid-cols-2 xl:grid-cols-1">
              <div className="rounded border border-white/10 bg-white/5 p-3">
                <div className="text-[11px] uppercase tracking-[0.18em] text-white/45">Files</div>
                <div className="mt-2 text-sm text-white/80">{pcbFile ? pcbFile.name : 'No PCB loaded'}</div>
                <div className="mt-1 text-xs text-white/50">{netFile ? netFile.name : 'No netlist loaded'}</div>
              </div>
              <div className="rounded border border-white/10 bg-white/5 p-3">
                <div className="text-[11px] uppercase tracking-[0.18em] text-white/45">Selection</div>
                <div className="mt-2 text-sm text-white/80">{selectedRef || 'None'}</div>
                <div className="mt-1 text-xs text-white/50">
                  {geometry ? `${geometry.footprints.length} footprints • ${geometry.nets.length} nets` : 'No geometry loaded'}
                </div>
              </div>
            </div>
          </div>

          <div className="rounded-xl border border-white/10 bg-[#0b1220] p-4">
            <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-white/90">
              <Layers className="h-4 w-4 text-cyan-300" />
              Stage modes
            </div>
            <div className="grid gap-2">
              <button
                type="button"
                onClick={() => setActiveView('design')}
                className={`rounded border px-3 py-2 text-left text-sm ${activeView === 'design' ? 'border-blue-400/30 bg-blue-500/10 text-blue-200' : 'border-white/10 bg-white/5 text-white/70 hover:bg-white/10'}`}
              >
                Design review
              </button>
              <button
                type="button"
                onClick={() => setActiveView('fab')}
                className={`rounded border px-3 py-2 text-left text-sm ${activeView === 'fab' ? 'border-amber-400/30 bg-amber-500/10 text-amber-200' : 'border-white/10 bg-white/5 text-white/70 hover:bg-white/10'}`}
              >
                Fabrication review
              </button>
            </div>

            {activeView === 'fab' ? (
              <div className="mt-3 grid gap-2 sm:grid-cols-2 xl:grid-cols-1">
                <button
                  type="button"
                  onClick={() => setFabMode('manual')}
                  className={`rounded border px-3 py-2 text-left text-sm ${fabMode === 'manual' ? 'border-white/20 bg-white text-slate-950' : 'border-white/10 bg-white/5 text-white/70 hover:bg-white/10'}`}
                >
                  Manual
                </button>
                <button
                  type="button"
                  onClick={() => setFabMode('robot')}
                  className={`rounded border px-3 py-2 text-left text-sm ${fabMode === 'robot' ? 'border-amber-400/30 bg-amber-500/10 text-amber-200' : 'border-white/10 bg-white/5 text-white/70 hover:bg-white/10'}`}
                >
                  Robot
                </button>
              </div>
            ) : null}
          </div>

          {activeTemplate ? (
            <div className="rounded-xl border border-white/10 bg-[#0b1220] p-4">
              <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-white/90">
                <PackageCheck className="h-4 w-4 text-cyan-300" />
                Product context
              </div>
              <div className="text-sm font-semibold text-white">{activeTemplate.productName ?? activeTemplate.name}</div>
              <div className="mt-2 text-sm text-white/60">{activeTemplate.productPitch ?? activeTemplate.description}</div>
            </div>
          ) : null}

          <div className="min-h-[320px] flex-1">
            <TreePanel
              geometry={geometry}
              selectedRef={selectedRef ?? undefined}
              onSelectRef={(ref) => setSelectedRef(ref)}
            />
          </div>
        </aside>
      </div>

      {showStart ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
          <div className="max-h-[90vh] w-full max-w-4xl overflow-auto rounded-xl border border-white/10 bg-[#0b1220] p-5">
            <div className="flex items-start justify-between gap-4">
              <div>
                <div className="text-lg font-semibold text-white">Start a project</div>
                <div className="mt-1 text-sm text-white/60">
                  This workspace is project-first. Start from a product, a demo board, or a direct KiCad import.
                </div>
              </div>
              <button
                type="button"
                className="rounded border border-white/10 bg-white/5 px-3 py-1 text-xs text-white/70 hover:bg-white/10"
                onClick={() => setShowStart(false)}
              >
                Close
              </button>
            </div>

            <div className="mt-5 grid gap-3 md:grid-cols-3">
              <button
                type="button"
                className="rounded-lg border border-white/10 bg-white/5 p-4 text-left hover:bg-white/10"
                onClick={() => startNewProject({ type: 'blank' })}
              >
                <div className="text-sm font-semibold text-white">New Project</div>
                <div className="mt-1 text-xs text-white/60">Start with an empty CAD workspace.</div>
              </button>
              <button
                type="button"
                className="rounded-lg border border-white/10 bg-white/5 p-4 text-left hover:bg-white/10"
                onClick={() => fileInputRef.current?.click()}
              >
                <div className="text-sm font-semibold text-white">Import KiCad</div>
                <div className="mt-1 text-xs text-white/60">Bring in a `.kicad_pcb` or `.net` file directly.</div>
              </button>
              <button
                type="button"
                className="rounded-lg border border-white/10 bg-white/5 p-4 text-left hover:bg-white/10"
                onClick={loadDemo}
              >
                <div className="text-sm font-semibold text-white">Demo Project</div>
                <div className="mt-1 text-xs text-white/60">Instant board + issues for direct review.</div>
              </button>
            </div>

            <div className="mt-6">
              <div className="text-xs font-semibold uppercase tracking-[0.18em] text-white/45">Templates</div>
              <div className="mt-3 grid gap-3 md:grid-cols-2">
                {cadTemplates.map((template) => (
                  <button
                    key={template.id}
                    type="button"
                    className="rounded-lg border border-white/10 bg-white/5 p-4 text-left hover:bg-white/10"
                    onClick={() => {
                      createAndActivateProject(template.productName ?? template.name, template.source);
                      hydrateTemplateContext(template.source);
                    }}
                  >
                    <div className="text-sm font-semibold text-white">{template.name}</div>
                    <div className="mt-2 text-xs text-white/60">{template.description}</div>
                  </button>
                ))}
              </div>
            </div>

            <div className="mt-6">
              <div className="text-xs font-semibold uppercase tracking-[0.18em] text-white/45">One-click products</div>
              <div className="mt-3 space-y-2">
                {cadTemplates
                  .filter((template) => Boolean(template.sampleFiles))
                  .slice()
                  .sort((a, b) => {
                    const rank = (template: CadTemplate) => (template.id === 'hero-drone-fc-power' ? 0 : template.id.startsWith('hero-') ? 1 : 2);
                    return rank(a) - rank(b);
                  })
                  .map((template) => (
                    <div key={template.id} className="rounded-lg border border-white/10 bg-white/5 p-4">
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div className="min-w-0">
                          <div className="text-sm font-semibold text-white">{template.productName ?? template.name}</div>
                          <div className="mt-1 text-xs text-white/60">{template.description}</div>
                        </div>
                        <div className="flex gap-2">
                          <Button variant="outline" size="sm" onClick={() => void loadTemplateSample(template, 'load')}>
                            Load
                          </Button>
                          <Button size="sm" onClick={() => void loadTemplateSample(template, 'guided')}>
                            Guided
                          </Button>
                        </div>
                      </div>
                    </div>
                  ))}
              </div>
            </div>

            <div className="mt-6">
              <div className="text-xs font-semibold uppercase tracking-[0.18em] text-white/45">Recent projects</div>
              <div className="mt-3 max-h-48 overflow-auto rounded-lg border border-white/10">
                {recentProjects.length ? recentProjects.map((project) => (
                  <button
                    key={project.id}
                    type="button"
                    className="flex w-full items-center justify-between border-b border-white/10 bg-transparent px-4 py-3 text-left hover:bg-white/5 last:border-b-0"
                    onClick={() => activateProject(project, projects)}
                  >
                    <div className="min-w-0">
                      <div className="truncate text-sm font-semibold text-white/90">{project.name}</div>
                      <div className="truncate text-xs text-white/45">{sourceLabel(project)}</div>
                    </div>
                    <div className="text-xs text-white/35">{new Date(project.lastOpenedAt).toLocaleString()}</div>
                  </button>
                )) : (
                  <div className="p-4 text-sm text-white/50">No projects yet.</div>
                )}
              </div>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}

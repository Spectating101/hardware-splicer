'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import {
  AlertTriangle,
  ArrowLeft,
  Box,
  BrainCircuit,
  CheckCircle2,
  CircuitBoard,
  Eye,
  FileArchive,
  FileSearch,
  Gauge,
  GitBranch,
  Layers3,
  LoaderCircle,
  PackageCheck,
  RefreshCw,
  Search,
  ShieldAlert,
  ShieldCheck,
  Waypoints,
  Wrench,
  XCircle,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { usePageTitle } from '@/components/use-page-title';
import {
  CanonicalSystemCanvas,
  deriveCanonicalSystemGraph,
  type CanonicalVisualObject,
} from '@/components/engineering/canonical-system-canvas';
import {
  BringUpModePanel,
  DecisionModePanel,
  VerifyModePanel,
  workbenchModes,
  type WorkbenchMode,
} from '@/components/engineering/workbench-mode-panels';
import {
  engineeringVisualAdapters,
  type EngineeringVisualView,
  visualAdapter,
} from '@/lib/engineering-visual-adapters';
import {
  getProxyErrorMessage,
  isProxyFailure,
  readJsonPayload,
  type ProxyErrorPayload,
} from '@/lib/proxy-client';

type JsonRecord = Record<string, unknown>;
type ProjectSummary = {
  project_id?: string;
  name?: string;
  project_name?: string;
  revision?: number;
  archived?: boolean;
};
type ProjectsResponse = { ok?: boolean; projects?: ProjectSummary[] };
type ProjectEnvelope = { project_id?: string; revision?: number; snapshot?: JsonRecord };
type ProjectResponse = { ok?: boolean; project?: ProjectEnvelope };

const workbenchModeIds = new Set<WorkbenchMode>(['explore', 'decide', 'verify', 'bringup']);
const engineeringViewIds = new Set<EngineeringVisualView>(['system', 'kicad', 'proposal', 'mechanical', 'gerber', 'assembly']);

function record(value: unknown): JsonRecord {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value)
    ? value as JsonRecord
    : {};
}

function rows(value: unknown): JsonRecord[] {
  return Array.isArray(value)
    ? value.filter((row): row is JsonRecord => Boolean(row) && typeof row === 'object' && !Array.isArray(row))
    : [];
}

function text(value: unknown, fallback = '—') {
  return value === undefined || value === null || value === '' ? fallback : String(value);
}

function projectLabel(project: ProjectSummary) {
  return text(project.name || project.project_name, text(project.project_id));
}

function artifactType(source: JsonRecord) {
  const type = text(source.source_type, '').toLowerCase();
  const name = text(source.filename || source.name || source.storage_filename, '').toLowerCase();
  if (type.includes('schematic') || name.endsWith('.kicad_sch')) return 'kicad_schematic';
  if (type === 'pcb' || name.endsWith('.kicad_pcb')) return 'kicad_pcb';
  if (type.includes('cad') || name.endsWith('.step') || name.endsWith('.stp') || name.endsWith('.glb') || name.endsWith('.gltf')) return 'mechanical';
  if (type.includes('gerber') || name.endsWith('.gbr') || name.endsWith('.drl')) return 'gerber';
  if (type.includes('bom') || name.includes('ibom')) return 'assembly';
  if (type.includes('circuit_json') || name.endsWith('.circuit.json')) return 'circuit_json';
  return type || 'source';
}

function iconForView(view: EngineeringVisualView) {
  if (view === 'system') return Waypoints;
  if (view === 'kicad') return CircuitBoard;
  if (view === 'proposal') return GitBranch;
  if (view === 'mechanical') return Box;
  if (view === 'gerber') return Layers3;
  return PackageCheck;
}

function adapterTone(status: 'active' | 'adapter-ready' | 'planned') {
  if (status === 'active') return 'border-emerald-300/25 bg-emerald-300/10 text-emerald-100';
  if (status === 'adapter-ready') return 'border-cyan-300/25 bg-cyan-300/10 text-cyan-100';
  return 'border-white/10 bg-white/[0.03] text-slate-400';
}

function objectStatusIcon(object: CanonicalVisualObject) {
  if (object.status === 'blocked') return <ShieldAlert className="h-3.5 w-3.5 text-rose-300" />;
  if (object.status === 'supported') return <CheckCircle2 className="h-3.5 w-3.5 text-emerald-300" />;
  return <Eye className="h-3.5 w-3.5 text-violet-300" />;
}

export default function VisualEngineeringWorkbenchPage() {
  usePageTitle('Visual Workbench | Hardware Splicer');
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [projectId, setProjectId] = useState('');
  const [revision, setRevision] = useState<number | null>(null);
  const [snapshot, setSnapshot] = useState<JsonRecord | null>(null);
  const [session, setSession] = useState<JsonRecord | null>(null);
  const [mode, setMode] = useState<WorkbenchMode>('explore');
  const [activeView, setActiveView] = useState<EngineeringVisualView>('system');
  const [selectedObject, setSelectedObject] = useState<CanonicalVisualObject | null>(null);
  const [objectQuery, setObjectQuery] = useState('');
  const [busy, setBusy] = useState<'projects' | 'project' | null>(null);
  const [error, setError] = useState<string | null>(null);

  const sources = rows(snapshot?.engineeringSources);
  const sessions = rows(snapshot?.engineeringAiSessions);
  const actions = rows(session?.actions);
  const turns = rows(session?.conversationTurns);
  const graph = useMemo(() => deriveCanonicalSystemGraph(snapshot, session), [snapshot, session]);
  const activeAdapter = visualAdapter(activeView);
  const matchingSources = useMemo(() => sources.filter((source) => {
    const type = artifactType(source);
    if (activeView === 'kicad') return type === 'kicad_schematic' || type === 'kicad_pcb';
    if (activeView === 'proposal') return type === 'circuit_json';
    if (activeView === 'mechanical') return type === 'mechanical';
    if (activeView === 'gerber') return type === 'gerber';
    if (activeView === 'assembly') return type === 'assembly';
    return false;
  }), [activeView, sources]);
  const failedActions = actions.filter((action) => text(action.status, '').toLowerCase() === 'failed');
  const sessionId = text(session?.session_id || session?.id, '');
  const physicalGates: Array<[string, unknown]> = [
    ['Fabrication', snapshot?.fabrication_authorized],
    ['Flashing', snapshot?.firmware_flash_authorized],
    ['Power-on', snapshot?.power_on_authorized],
    ['Motion', snapshot?.motion_authorized],
    ['Operation', snapshot?.operational_authorized],
    ['Release', snapshot?.release_authorized],
  ];

  const selectedInCurrentGraph = selectedObject
    ? graph.objects.find((object) => object.id === selectedObject.id) || selectedObject
    : null;

  const filteredObjects = useMemo(() => {
    const query = objectQuery.trim().toLowerCase();
    if (!query) return graph.objects;
    return graph.objects.filter((object) => [
      object.label,
      object.id,
      object.kind,
      object.domain,
      object.description,
      ...object.blockers,
      ...object.evidenceIds,
    ].some((value) => value.toLowerCase().includes(query)));
  }, [graph.objects, objectQuery]);

  async function loadProject(selectedProjectId: string, preferredObjectId = '') {
    if (!selectedProjectId) return;
    setBusy('project');
    setError(null);
    try {
      const response = await fetch(`/api/proxy/engineering/projects/${encodeURIComponent(selectedProjectId)}`, { cache: 'no-store' });
      const payload = await readJsonPayload<ProjectResponse | ProxyErrorPayload>(response);
      if (!response.ok || isProxyFailure(payload)) {
        throw new Error(getProxyErrorMessage(payload, 'Hardware Splicer could not load the visual project.'));
      }
      const envelope = (payload as ProjectResponse).project || {};
      const nextSnapshot = record(envelope.snapshot);
      const nextSessions = rows(nextSnapshot.engineeringAiSessions);
      const nextSession = nextSessions.at(-1) || null;
      const nextGraph = deriveCanonicalSystemGraph(nextSnapshot, nextSession);
      const preferred = nextGraph.objects.find((object) => object.id === preferredObjectId);
      setProjectId(selectedProjectId);
      setRevision(Number(envelope.revision));
      setSnapshot(nextSnapshot);
      setSession(nextSession);
      setSelectedObject(preferred || nextGraph.objects[0] || null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Visual project load failed.');
    } finally {
      setBusy(null);
    }
  }

  async function loadProjects() {
    setBusy('projects');
    setError(null);
    try {
      const response = await fetch('/api/proxy/engineering/projects', { cache: 'no-store' });
      const payload = await readJsonPayload<ProjectsResponse | ProxyErrorPayload>(response);
      if (!response.ok || isProxyFailure(payload)) {
        throw new Error(getProxyErrorMessage(payload, 'Hardware Splicer could not list projects.'));
      }
      const listed = (payload as ProjectsResponse).projects || [];
      setProjects(listed);

      const params = typeof window === 'undefined' ? null : new URLSearchParams(window.location.search);
      const requestedMode = params?.get('mode') as WorkbenchMode | null;
      const requestedView = params?.get('view') as EngineeringVisualView | null;
      const requestedObject = params?.get('object') || '';
      const requestedProject = params?.get('project') || '';
      if (requestedMode && workbenchModeIds.has(requestedMode)) setMode(requestedMode);
      if (requestedView && engineeringViewIds.has(requestedView)) setActiveView(requestedView);

      const first = requestedProject || projectId || text(listed[0]?.project_id, '');
      if (first) await loadProject(first, requestedObject);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Project list failed.');
    } finally {
      setBusy(null);
    }
  }

  useEffect(() => {
    void loadProjects();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!selectedObject && graph.objects.length) setSelectedObject(graph.objects[0]);
  }, [graph.objects, selectedObject]);

  useEffect(() => {
    if (!projectId || typeof window === 'undefined') return;
    const url = new URL(window.location.href);
    url.searchParams.set('project', projectId);
    url.searchParams.set('mode', mode);
    url.searchParams.set('view', activeView);
    if (selectedInCurrentGraph?.id) url.searchParams.set('object', selectedInCurrentGraph.id);
    else url.searchParams.delete('object');
    window.history.replaceState(null, '', `${url.pathname}?${url.searchParams.toString()}`);
  }, [activeView, mode, projectId, selectedInCurrentGraph?.id]);

  function chooseMode(nextMode: WorkbenchMode) {
    setMode(nextMode);
    if (nextMode === 'explore') return;
    if (nextMode === 'decide') setActiveView('proposal');
    else setActiveView('system');
  }

  return (
    <main className="min-h-screen bg-[#020711] px-3 py-3 text-slate-100 sm:px-4 lg:px-5">
      <div className="mx-auto max-w-[2200px]">
        <header className="rounded-[1.6rem] border border-white/10 bg-[linear-gradient(135deg,#06111f,#09172a)] px-5 py-4 shadow-[0_24px_80px_rgba(2,6,23,0.42)]">
          <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
            <div className="flex items-center gap-4">
              <Link href="/engineering/studio" className="rounded-xl border border-white/10 bg-white/[0.03] p-2 text-slate-400 hover:text-white"><ArrowLeft className="h-4 w-4" /></Link>
              <div className="rounded-2xl border border-cyan-300/20 bg-cyan-300/10 p-3 text-cyan-100"><Waypoints className="h-6 w-6" /></div>
              <div>
                <div className="text-[10px] font-semibold uppercase tracking-[0.24em] text-cyan-300">Hardware Splicer moat layer</div>
                <h1 className="mt-1 text-2xl font-semibold text-white">Visual Engineering Workbench</h1>
                <p className="mt-1 max-w-4xl text-sm leading-6 text-slate-400">Public renderers draw artifacts. Hardware Splicer keeps object identity, evidence, failures, proposals, revisions, JARVIS context, and authority coherent across the complete engineering lifecycle.</p>
              </div>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <span className="rounded-full border border-white/10 bg-[#020711] px-3 py-1.5 text-xs text-slate-300">Revision {revision ?? '—'}</span>
              <span className="rounded-full border border-emerald-300/20 bg-emerald-300/10 px-3 py-1.5 text-xs text-emerald-100">Viewers grant no authority</span>
              <Button size="sm" variant="outline" onClick={loadProjects} disabled={busy !== null}>{busy ? <LoaderCircle className="mr-2 h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="mr-2 h-3.5 w-3.5" />}Refresh</Button>
            </div>
          </div>

          <div className="mt-4 grid gap-2 lg:grid-cols-4">
            {workbenchModes.map((option) => {
              const active = mode === option.id;
              return (
                <button key={option.id} type="button" onClick={() => chooseMode(option.id)} className={`rounded-xl border px-3 py-2.5 text-left transition ${active ? 'border-cyan-300/30 bg-cyan-300/10 text-white' : 'border-white/8 bg-[#020711]/70 text-slate-400 hover:border-white/16 hover:text-white'}`}>
                  <div className="text-xs font-semibold uppercase tracking-[0.12em]">{option.label}</div>
                  <div className="mt-1 text-[10px] leading-4 opacity-70">{option.description}</div>
                </button>
              );
            })}
          </div>
        </header>

        {error ? <div className="mt-3 flex items-start gap-3 rounded-2xl border border-rose-300/20 bg-rose-300/10 p-4 text-sm text-rose-100"><XCircle className="mt-0.5 h-4 w-4" />{error}</div> : null}

        <section className="mt-3 overflow-hidden rounded-[1.6rem] border border-white/10 bg-white/5">
          <div className="flex min-h-14 items-center gap-2 overflow-x-auto border-b border-white/10 bg-[#06101d] px-3 py-2">
            {mode === 'explore' ? engineeringVisualAdapters.map((adapter) => {
              const Icon = iconForView(adapter.view);
              const active = activeView === adapter.view;
              return (
                <button
                  key={adapter.id}
                  type="button"
                  onClick={() => setActiveView(adapter.view)}
                  className={`inline-flex shrink-0 items-center gap-2 rounded-xl border px-3 py-2 text-xs font-semibold transition ${active ? 'border-cyan-300/30 bg-cyan-300/12 text-white' : 'border-white/8 bg-white/[0.025] text-slate-400 hover:border-white/16 hover:text-white'}`}
                >
                  <Icon className="h-3.5 w-3.5" />
                  {adapter.label}
                  <span className={`rounded-full border px-1.5 py-0.5 text-[8px] uppercase tracking-[0.12em] ${adapterTone(adapter.status)}`}>{adapter.status}</span>
                </button>
              );
            }) : (
              <div className="flex items-center gap-2 text-xs text-slate-400"><GitBranch className="h-3.5 w-3.5 text-cyan-300" />{workbenchModes.find((option) => option.id === mode)?.description}</div>
            )}
          </div>

          <div className="grid min-h-[calc(100vh-15rem)] gap-px bg-white/10 xl:grid-cols-[280px_minmax(0,1fr)_370px]">
            <aside className="bg-[#06101d] p-4">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <div className="text-[10px] font-semibold uppercase tracking-[0.2em] text-slate-500">Project model</div>
                  <div className="mt-1 text-sm font-semibold text-white">Objects and interfaces</div>
                </div>
                <FileSearch className="h-4 w-4 text-cyan-300" />
              </div>

              <select
                value={projectId}
                onChange={(event) => void loadProject(event.target.value)}
                className="mt-4 w-full rounded-xl border border-white/10 bg-[#020711] px-3 py-2.5 text-xs text-white outline-none"
              >
                {projects.map((project) => <option key={text(project.project_id)} value={text(project.project_id)}>{projectLabel(project)}</option>)}
              </select>

              <label className="mt-3 flex items-center gap-2 rounded-xl border border-white/10 bg-[#020711] px-3 py-2">
                <Search className="h-3.5 w-3.5 text-slate-500" />
                <input
                  value={objectQuery}
                  onChange={(event) => setObjectQuery(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter' && filteredObjects[0]) setSelectedObject(filteredObjects[0]);
                  }}
                  placeholder="Search objects, evidence, blockers"
                  className="min-w-0 flex-1 bg-transparent text-xs text-white outline-none placeholder:text-slate-600"
                />
              </label>

              <div className="mt-4 space-y-2">
                {filteredObjects.map((object) => {
                  const active = selectedInCurrentGraph?.id === object.id;
                  return (
                    <button
                      key={object.id}
                      type="button"
                      onClick={() => setSelectedObject(object)}
                      className={`w-full rounded-2xl border p-3 text-left transition ${active ? 'border-cyan-300/30 bg-cyan-300/10' : 'border-white/8 bg-[#020711] hover:border-white/16'}`}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <div className="truncate text-xs font-semibold text-white">{object.label}</div>
                        {objectStatusIcon(object)}
                      </div>
                      <div className="mt-1 text-[10px] uppercase tracking-[0.12em] text-slate-500">{object.domain} · {object.kind}</div>
                    </button>
                  );
                })}
                {!filteredObjects.length ? <div className="rounded-xl border border-white/8 p-3 text-xs text-slate-500">No canonical object matches this search.</div> : null}
              </div>

              <div className="mt-5 rounded-2xl border border-white/8 bg-[#020711] p-3">
                <div className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">Project layers</div>
                <div className="mt-3 space-y-2 text-xs text-slate-400">
                  <div className="flex justify-between"><span>Sources</span><span>{sources.length}</span></div>
                  <div className="flex justify-between"><span>AI sessions</span><span>{sessions.length}</span></div>
                  <div className="flex justify-between"><span>Failed previews</span><span>{failedActions.length}</span></div>
                  <div className="flex justify-between"><span>JARVIS turns</span><span>{turns.length}</span></div>
                </div>
              </div>
            </aside>

            <section className="min-w-0 bg-[#020711] p-3">
              {mode === 'explore' ? (
                activeView === 'system' ? (
                  <CanonicalSystemCanvas
                    snapshot={snapshot}
                    session={session}
                    revision={revision}
                    selectedObjectId={selectedInCurrentGraph?.id}
                    onSelectObject={setSelectedObject}
                  />
                ) : (
                  <AdapterBoundary
                    activeView={activeView}
                    activeAdapter={activeAdapter}
                    matchingSources={matchingSources}
                    selectedObject={selectedInCurrentGraph}
                  />
                )
              ) : mode === 'decide' ? (
                <DecisionModePanel projectId={projectId} selectedObject={selectedInCurrentGraph} revision={revision} />
              ) : mode === 'verify' ? (
                <VerifyModePanel projectId={projectId} sessionId={sessionId} selectedObject={selectedInCurrentGraph} actions={actions} />
              ) : (
                <BringUpModePanel projectId={projectId} selectedObject={selectedInCurrentGraph} sourcesCount={sources.length} actions={actions} physicalGates={physicalGates} />
              )}
            </section>

            <aside className="bg-[#06101d] p-4">
              <div className="flex items-center gap-3">
                <div className="rounded-xl border border-fuchsia-300/20 bg-fuchsia-300/10 p-2 text-fuchsia-100"><BrainCircuit className="h-4 w-4" /></div>
                <div>
                  <div className="text-[10px] font-semibold uppercase tracking-[0.2em] text-fuchsia-300">Contextual JARVIS inspector</div>
                  <div className="mt-1 text-sm font-semibold text-white">{selectedInCurrentGraph?.label || 'Select an object'}</div>
                </div>
              </div>

              <div className="mt-4 rounded-xl border border-cyan-300/15 bg-cyan-300/5 p-3 text-xs text-cyan-50">
                Current mode: <span className="font-semibold uppercase">{mode}</span>. Selection and canonical identity persist across every mode and renderer.
              </div>

              {selectedInCurrentGraph ? (
                <div className="mt-4 space-y-4">
                  <section className="rounded-2xl border border-white/10 bg-[#020711] p-4">
                    <div className="flex flex-wrap gap-2 text-[10px] font-semibold uppercase tracking-[0.13em]">
                      <span className="rounded-full border border-white/10 px-2 py-1 text-slate-300">{selectedInCurrentGraph.kind}</span>
                      <span className="rounded-full border border-white/10 px-2 py-1 text-slate-300">{selectedInCurrentGraph.domain}</span>
                      <span className="rounded-full border border-violet-300/20 bg-violet-300/10 px-2 py-1 text-violet-100">{selectedInCurrentGraph.status}</span>
                    </div>
                    <p className="mt-3 text-xs leading-5 text-slate-300">{selectedInCurrentGraph.description}</p>
                  </section>

                  <section className="rounded-2xl border border-white/10 bg-[#020711] p-4">
                    <div className="flex items-center gap-2 text-xs font-semibold text-white"><FileSearch className="h-3.5 w-3.5 text-cyan-300" />Evidence and provenance</div>
                    <div className="mt-3 space-y-2">
                      {selectedInCurrentGraph.evidenceIds.length ? selectedInCurrentGraph.evidenceIds.map((id) => <div key={id} className="rounded-xl border border-white/8 bg-white/[0.025] px-3 py-2 text-[10px] text-slate-300">{id}</div>) : <div className="text-xs text-slate-500">No evidence identity is attached.</div>}
                    </div>
                  </section>

                  <section className={`rounded-2xl border p-4 ${selectedInCurrentGraph.blockers.length ? 'border-rose-300/20 bg-rose-300/5' : 'border-emerald-300/20 bg-emerald-300/5'}`}>
                    <div className="flex items-center gap-2 text-xs font-semibold text-white">{selectedInCurrentGraph.blockers.length ? <ShieldAlert className="h-3.5 w-3.5 text-rose-300" /> : <ShieldCheck className="h-3.5 w-3.5 text-emerald-300" />}Blockers</div>
                    <div className="mt-3 space-y-2 text-xs leading-5 text-slate-300">
                      {selectedInCurrentGraph.blockers.length ? selectedInCurrentGraph.blockers.map((blocker) => <div key={blocker}>• {blocker}</div>) : <div>No blocker is attached to this object.</div>}
                    </div>
                  </section>

                  {selectedInCurrentGraph.proposalIds.length ? (
                    <section className="rounded-2xl border border-violet-300/20 bg-violet-300/5 p-4">
                      <div className="text-xs font-semibold text-violet-100">Proposal lineage</div>
                      <div className="mt-3 space-y-2">{selectedInCurrentGraph.proposalIds.map((id) => <div key={id} className="break-all rounded-xl border border-violet-300/15 px-3 py-2 font-mono text-[10px] text-violet-100">{id}</div>)}</div>
                    </section>
                  ) : null}

                  <section className="rounded-2xl border border-white/10 bg-[#020711] p-4">
                    <div className="flex items-center gap-2 text-xs font-semibold text-white"><Gauge className="h-3.5 w-3.5 text-amber-300" />Physical gates</div>
                    <div className="mt-3 space-y-2">
                      {physicalGates.map(([label, value]) => <div key={label} className="flex items-center justify-between rounded-xl border border-white/8 px-3 py-2 text-[10px]"><span className="text-slate-400">{label}</span><span className={value === true ? 'text-rose-200' : 'text-emerald-200'}>{value === true ? 'authorized' : 'closed'}</span></div>)}
                    </div>
                  </section>

                  <div className="rounded-2xl border border-cyan-300/15 bg-cyan-300/5 p-4 text-xs leading-5 text-cyan-50">
                    JARVIS explanations and changes must remain attached to this canonical object identity. A renderer selection never becomes a project mutation by itself.
                  </div>
                </div>
              ) : null}
            </aside>
          </div>

          <div className="border-t border-white/10 bg-[#050d18] px-4 py-3">
            <div className="flex flex-col gap-3 xl:flex-row xl:items-center">
              <div className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-500"><Wrench className="h-3.5 w-3.5" />Revision and tool timeline</div>
              <div className="flex min-w-0 flex-1 gap-2 overflow-x-auto">
                {actions.length ? actions.map((action, index) => <div key={text(action.action_id, `action-${index}`)} className="shrink-0 rounded-xl border border-white/8 bg-[#020711] px-3 py-2 text-[10px]"><span className="font-semibold text-slate-200">{text(action.action_type)}</span><span className="ml-2 text-slate-500">{text(action.status)}</span></div>) : <div className="text-xs text-slate-500">No action history in the active session.</div>}
              </div>
              <div className="text-[10px] text-slate-500">Selected canonical ID: <span className="font-mono text-slate-300">{selectedInCurrentGraph?.id || 'none'}</span></div>
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}

function AdapterBoundary({
  activeView,
  activeAdapter,
  matchingSources,
  selectedObject,
}: {
  activeView: EngineeringVisualView;
  activeAdapter: ReturnType<typeof visualAdapter>;
  matchingSources: JsonRecord[];
  selectedObject: CanonicalVisualObject | null;
}) {
  return (
    <div className="flex h-full min-h-[650px] items-center justify-center rounded-3xl border border-white/10 bg-[#050b14] p-8">
      <div className="w-full max-w-3xl">
        <div className="flex items-start gap-4">
          <div className="rounded-2xl border border-cyan-300/20 bg-cyan-300/10 p-3 text-cyan-100">{activeView === 'kicad' ? <CircuitBoard className="h-6 w-6" /> : activeView === 'mechanical' ? <Box className="h-6 w-6" /> : activeView === 'gerber' ? <Layers3 className="h-6 w-6" /> : activeView === 'assembly' ? <FileArchive className="h-6 w-6" /> : <GitBranch className="h-6 w-6" />}</div>
          <div>
            <div className="text-[10px] font-semibold uppercase tracking-[0.2em] text-cyan-300">Public adapter boundary</div>
            <h2 className="mt-2 text-xl font-semibold text-white">{activeAdapter?.project}</h2>
            <p className="mt-2 text-sm leading-6 text-slate-400">{activeAdapter?.purpose}</p>
          </div>
        </div>

        <div className="mt-6 grid gap-4 md:grid-cols-2">
          <div className="rounded-2xl border border-white/10 bg-[#020711] p-4">
            <div className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">Adapter contract</div>
            <div className="mt-3 space-y-2 text-xs text-slate-300">
              <div className="flex justify-between gap-3"><span className="text-slate-500">Status</span><span>{activeAdapter?.status}</span></div>
              <div className="flex justify-between gap-3"><span className="text-slate-500">License</span><span>{activeAdapter?.license}</span></div>
              <div className="flex justify-between gap-3"><span className="text-slate-500">Project truth</span><span>Never owned</span></div>
              <div className="flex justify-between gap-3"><span className="text-slate-500">Authority effect</span><span>None</span></div>
              <div className="flex justify-between gap-3"><span className="text-slate-500">Selected object</span><span className="max-w-[12rem] truncate">{selectedObject?.label || 'none'}</span></div>
            </div>
          </div>
          <div className="rounded-2xl border border-white/10 bg-[#020711] p-4">
            <div className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">Required artifact</div>
            <div className="mt-3 flex flex-wrap gap-2">
              {activeAdapter?.requiredArtifactTypes.map((type) => <span key={type} className="rounded-full border border-white/10 px-2.5 py-1 text-[10px] text-slate-300">{type}</span>)}
            </div>
            <div className="mt-4 text-xs text-slate-500">{matchingSources.length ? `${matchingSources.length} matching registered source descriptor${matchingSources.length === 1 ? '' : 's'} found.` : 'No matching renderable artifact is registered in this project revision.'}</div>
          </div>
        </div>

        <div className="mt-4 rounded-2xl border border-amber-300/15 bg-amber-300/5 p-4">
          <div className="flex items-center gap-2 text-xs font-semibold text-amber-100"><AlertTriangle className="h-3.5 w-3.5" />Honest integration state</div>
          <div className="mt-3 space-y-2 text-xs leading-5 text-slate-400">
            {activeAdapter?.limitations.map((limitation) => <div key={limitation}>• {limitation}</div>)}
          </div>
        </div>

        {matchingSources.length ? (
          <div className="mt-4 space-y-2">
            {matchingSources.map((source, index) => (
              <div key={text(source.source_id, `source-${index}`)} className="rounded-xl border border-white/10 bg-[#020711] px-3 py-2.5 text-xs">
                <div className="font-semibold text-white">{text(source.filename || source.name || source.source_id)}</div>
                <div className="mt-1 text-slate-500">{artifactType(source)} · {text(source.sha256 || source.content_sha256, 'hash unavailable')}</div>
              </div>
            ))}
          </div>
        ) : null}
      </div>
    </div>
  );
}

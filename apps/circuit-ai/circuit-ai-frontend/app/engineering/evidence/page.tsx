'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import Link from 'next/link';
import {
  AlertTriangle,
  ArrowRight,
  Check,
  ChevronRight,
  CircuitBoard,
  FileCheck2,
  FileText,
  GitBranch,
  History,
  LoaderCircle,
  PanelRight,
  RefreshCw,
  Search,
  ShieldAlert,
  ShieldCheck,
  XCircle,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { usePageTitle } from '@/components/use-page-title';
import {
  deriveCanonicalSystemGraph,
  type CanonicalVisualObject,
} from '@/components/engineering/canonical-system-canvas';
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
};
type ProjectsResponse = { ok?: boolean; projects?: ProjectSummary[] };
type ProjectEnvelope = { project_id?: string; revision?: number; snapshot?: JsonRecord };
type ProjectResponse = { ok?: boolean; project?: ProjectEnvelope };
type BuildFile = { name?: string; relative?: string; kind?: string };
type BuildFilesResponse = { ok?: boolean; files?: BuildFile[] };
type BuildContentResponse = { ok?: boolean; content?: string };
type RailTab = 'project' | 'findings' | 'history';
type InspectorTab = 'object' | 'findings' | 'evidence';

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

function actionStatus(action: JsonRecord) {
  return text(action.status, 'unknown').toLowerCase();
}

function firstString(...values: unknown[]) {
  for (const value of values) {
    if (typeof value === 'string' && value.trim()) return value;
  }
  return '';
}

function deriveBuildDir(snapshot: JsonRecord | null, session: JsonRecord | null) {
  if (!snapshot) return '';
  const projectPackage = record(snapshot.projectPackage || snapshot.project_package);
  const compose = record(snapshot.composeResult || snapshot.compose_result);
  const sessionPackage = record(session?.projectPackage || session?.project_package);
  const direct = firstString(
    snapshot.buildDir,
    snapshot.build_dir,
    projectPackage.build_dir,
    compose.out_dir,
    compose.build_dir,
    session?.buildDir,
    session?.build_dir,
    sessionPackage.build_dir,
  );
  if (direct) return direct;

  const actions = rows(session?.actions).slice().reverse();
  for (const action of actions) {
    const result = record(action.tool_result || action.result || action.payload);
    const nested = record(result.result || result.payload || result.project_package);
    const candidate = firstString(
      action.build_dir,
      action.out_dir,
      result.build_dir,
      result.out_dir,
      nested.build_dir,
      nested.out_dir,
    );
    if (candidate) return candidate;
  }
  return '';
}

function statusChip(label: string, state: 'verified' | 'blocked' | 'pending') {
  const styles = state === 'verified'
    ? 'border-emerald-200 bg-emerald-50 text-emerald-800'
    : state === 'blocked'
      ? 'border-red-200 bg-red-50 text-red-800'
      : 'border-stone-200 bg-stone-100 text-stone-600';
  const Icon = state === 'verified' ? Check : state === 'blocked' ? XCircle : AlertTriangle;
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1.5 text-xs font-medium ${styles}`}>
      <span className="text-stone-500">{label}</span>
      <Icon className="h-3.5 w-3.5" />
      {state === 'verified' ? 'Verified' : state === 'blocked' ? 'Blocked' : 'Pending'}
    </span>
  );
}

function useKiCanvasScript() {
  const [ready, setReady] = useState(() => (
    typeof customElements !== 'undefined' && Boolean(customElements.get('kicanvas-embed'))
  ));
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    if (ready) return;
    const existing = document.querySelector('script[data-kicanvas-vnext="1"]');
    if (existing) {
      const onLoad = () => setReady(true);
      const onError = () => setFailed(true);
      existing.addEventListener('load', onLoad, { once: true });
      existing.addEventListener('error', onError, { once: true });
      return () => {
        existing.removeEventListener('load', onLoad);
        existing.removeEventListener('error', onError);
      };
    }
    const script = document.createElement('script');
    script.type = 'module';
    script.src = '/kicanvas/kicanvas.js';
    script.dataset.kicanvasVnext = '1';
    script.onload = () => setReady(true);
    script.onerror = () => setFailed(true);
    document.head.appendChild(script);
  }, [ready]);

  return { ready, failed };
}

function ArtifactViewport({ buildDir, overlayFinding }: { buildDir: string; overlayFinding: string }) {
  const hostRef = useRef<HTMLDivElement>(null);
  const { ready, failed: viewerFailed } = useKiCanvasScript();
  const [files, setFiles] = useState<BuildFile[]>([]);
  const [activeRelative, setActiveRelative] = useState('');
  const [content, setContent] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!buildDir) {
      setFiles([]);
      setActiveRelative('');
      setContent('');
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError('');
    fetch('/api/proxy/hardware-splicer/build-files/list', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ build_dir: buildDir }),
      cache: 'no-store',
    })
      .then(async (response) => {
        const payload = await response.json() as BuildFilesResponse & { detail?: unknown };
        if (!response.ok) throw new Error('Build artifact list is unavailable.');
        return payload;
      })
      .then((payload) => {
        if (cancelled) return;
        const nextFiles = payload.files || [];
        setFiles(nextFiles);
        const preferred = nextFiles.find((file) => file.kind === 'schematic')
          || nextFiles.find((file) => file.kind === 'pcb')
          || nextFiles[0];
        setActiveRelative(preferred?.relative || '');
      })
      .catch((caught) => {
        if (!cancelled) setError(caught instanceof Error ? caught.message : 'Build artifact list is unavailable.');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, [buildDir]);

  useEffect(() => {
    if (!buildDir || !activeRelative) {
      setContent('');
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError('');
    fetch('/api/proxy/hardware-splicer/build-files/content', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ build_dir: buildDir, relative: activeRelative }),
      cache: 'no-store',
    })
      .then(async (response) => {
        const payload = await response.json() as BuildContentResponse;
        if (!response.ok) throw new Error('Artifact content is unavailable.');
        return payload;
      })
      .then((payload) => {
        if (!cancelled) setContent(payload.content || '');
      })
      .catch((caught) => {
        if (!cancelled) setError(caught instanceof Error ? caught.message : 'Artifact content is unavailable.');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, [activeRelative, buildDir]);

  useEffect(() => {
    const host = hostRef.current;
    if (!host || !ready || !content) return;
    host.replaceChildren();
    const embed = document.createElement('kicanvas-embed');
    embed.setAttribute('controls', 'basic');
    embed.setAttribute('controlslist', 'nodownload nooverlay');
    const source = document.createElement('kicanvas-source');
    source.textContent = content;
    embed.appendChild(source);
    host.appendChild(embed);
  }, [content, ready]);

  const visibleFiles = files.filter((file) => file.kind === 'schematic' || file.kind === 'pcb');

  return (
    <div className="flex h-full min-h-[650px] flex-col bg-white">
      <div className="flex min-h-12 items-center justify-between gap-3 border-b border-stone-200 px-3">
        <div className="flex items-center gap-1">
          {visibleFiles.map((file) => {
            const active = file.relative === activeRelative;
            return (
              <button
                key={file.relative || file.name}
                type="button"
                onClick={() => setActiveRelative(file.relative || '')}
                className={`border-b-2 px-3 py-3 text-xs font-medium ${active ? 'border-stone-900 text-stone-950' : 'border-transparent text-stone-500 hover:text-stone-900'}`}
              >
                {file.kind === 'schematic' ? 'Schematic' : file.kind === 'pcb' ? 'PCB' : file.name}
              </button>
            );
          })}
          {!visibleFiles.length ? <span className="px-3 text-xs text-stone-500">Artifact</span> : null}
        </div>
        <span className="max-w-[38%] truncate font-mono text-[10px] text-stone-400">{activeRelative || 'no KiCad artifact attached'}</span>
      </div>

      <div className="relative min-h-0 flex-1 overflow-hidden bg-[#fbfbfa]">
        {loading ? (
          <div className="absolute inset-0 z-20 flex items-center justify-center bg-white/70"><LoaderCircle className="h-5 w-5 animate-spin text-stone-500" /></div>
        ) : null}

        {!buildDir || error || viewerFailed || (!content && !loading) ? (
          <div className="flex h-full min-h-[600px] items-center justify-center p-8">
            <div className="max-w-sm text-center">
              <CircuitBoard className="mx-auto h-9 w-9 text-stone-300" />
              <div className="mt-3 text-sm font-medium text-stone-800">{buildDir ? 'KiCad preview unavailable' : 'No build artifact attached'}</div>
              <div className="mt-1 text-xs leading-5 text-stone-500">{error || (viewerFailed ? 'The bundled KiCanvas viewer failed to load.' : 'The current project snapshot does not expose a build directory yet.')}</div>
            </div>
          </div>
        ) : (
          <div ref={hostRef} className="h-full min-h-[600px] w-full [&>kicanvas-embed]:block [&>kicanvas-embed]:h-full [&>kicanvas-embed]:min-h-[600px] [&>kicanvas-embed]:w-full" />
        )}

        {overlayFinding ? (
          <div className="absolute left-5 top-5 z-10 max-w-xs rounded-md border border-red-200 bg-white/95 px-3 py-2 shadow-sm backdrop-blur">
            <div className="flex gap-2">
              <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-red-600 text-white"><AlertTriangle className="h-3 w-3" /></span>
              <div>
                <div className="text-xs font-semibold text-red-800">Review required</div>
                <div className="mt-0.5 line-clamp-2 text-xs leading-5 text-stone-700">{overlayFinding}</div>
              </div>
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
}

export default function EvidenceOverviewPage() {
  usePageTitle('Project Review | Hardware Splicer');
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [projectId, setProjectId] = useState('');
  const [revision, setRevision] = useState<number | null>(null);
  const [snapshot, setSnapshot] = useState<JsonRecord | null>(null);
  const [session, setSession] = useState<JsonRecord | null>(null);
  const [selectedObject, setSelectedObject] = useState<CanonicalVisualObject | null>(null);
  const [railTab, setRailTab] = useState<RailTab>('project');
  const [inspectorTab, setInspectorTab] = useState<InspectorTab>('object');
  const [query, setQuery] = useState('');
  const [busy, setBusy] = useState<'projects' | 'project' | null>(null);
  const [error, setError] = useState<string | null>(null);

  const sources = rows(snapshot?.engineeringSources);
  const sessions = rows(snapshot?.engineeringAiSessions);
  const actions = rows(session?.actions);
  const graph = useMemo(() => deriveCanonicalSystemGraph(snapshot, session), [snapshot, session]);
  const failedActions = actions.filter((action) => actionStatus(action) === 'failed');
  const completedActions = actions.filter((action) => ['completed', 'passed', 'succeeded'].includes(actionStatus(action)));
  const blockedObjects = graph.objects.filter((object) => object.blockers.length > 0 || object.status === 'blocked');
  const fabricationAuthorized = snapshot?.fabrication_authorized === true;
  const powerOnAuthorized = snapshot?.power_on_authorized === true;
  const releaseAuthorized = snapshot?.release_authorized === true;
  const buildDir = deriveBuildDir(snapshot, session);

  const projectName = useMemo(() => {
    const match = projects.find((project) => text(project.project_id) === projectId);
    return match ? projectLabel(match) : text(snapshot?.name || snapshot?.project_name, projectId || 'Hardware project');
  }, [projectId, projects, snapshot]);

  const selected = selectedObject
    ? graph.objects.find((object) => object.id === selectedObject.id) || selectedObject
    : graph.objects[0] || null;

  const filteredObjects = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) return graph.objects;
    return graph.objects.filter((object) => [object.label, object.id, object.kind, object.domain, ...object.evidenceIds, ...object.blockers]
      .some((value) => value.toLowerCase().includes(normalized)));
  }, [graph.objects, query]);

  const overlayFinding = selected?.blockers[0]
    || blockedObjects[0]?.blockers[0]
    || (failedActions.length ? text(failedActions[0]?.title || failedActions[0]?.action_type, 'Deterministic check failed') : '');

  async function loadProject(selectedProjectId: string, preferredObjectId = '') {
    if (!selectedProjectId) return;
    setBusy('project');
    setError(null);
    try {
      const response = await fetch(`/api/proxy/engineering/projects/${encodeURIComponent(selectedProjectId)}`, { cache: 'no-store' });
      const payload = await readJsonPayload<ProjectResponse | ProxyErrorPayload>(response);
      if (!response.ok || isProxyFailure(payload)) {
        throw new Error(getProxyErrorMessage(payload, 'Hardware Splicer could not load this project.'));
      }
      const envelope = (payload as ProjectResponse).project || {};
      const nextSnapshot = record(envelope.snapshot);
      const nextSessions = rows(nextSnapshot.engineeringAiSessions);
      const nextSession = nextSessions.at(-1) || null;
      const nextGraph = deriveCanonicalSystemGraph(nextSnapshot, nextSession);
      setProjectId(selectedProjectId);
      setRevision(Number(envelope.revision));
      setSnapshot(nextSnapshot);
      setSession(nextSession);
      setSelectedObject(nextGraph.objects.find((object) => object.id === preferredObjectId) || nextGraph.objects[0] || null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Project load failed.');
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
      const requested = params?.get('project') || projectId || text(listed[0]?.project_id, '');
      const objectId = params?.get('object') || '';
      if (requested) await loadProject(requested, objectId);
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
    if (!projectId || typeof window === 'undefined') return;
    const url = new URL(window.location.href);
    url.searchParams.set('project', projectId);
    if (selected?.id) url.searchParams.set('object', selected.id);
    else url.searchParams.delete('object');
    window.history.replaceState(null, '', `${url.pathname}?${url.searchParams.toString()}`);
  }, [projectId, selected?.id]);

  useEffect(() => {
    if (!selectedObject && graph.objects.length) setSelectedObject(graph.objects[0]);
  }, [graph.objects, selectedObject]);

  const railTabs: Array<[RailTab, string, number | null]> = [
    ['project', 'Project', null],
    ['findings', 'Findings', blockedObjects.length + failedActions.length],
    ['history', 'History', actions.length],
  ];

  return (
    <main className="min-h-screen bg-stone-100 text-stone-950">
      <div className="flex min-h-screen flex-col">
        <header className="border-b border-stone-200 bg-white">
          <div className="flex min-h-14 flex-wrap items-center gap-3 px-4 lg:px-5">
            <Link href="/engineering/studio" className="text-sm font-semibold tracking-tight text-stone-950">Hardware Splicer</Link>
            <ChevronRight className="h-3.5 w-3.5 text-stone-300" />
            <select
              value={projectId}
              onChange={(event) => void loadProject(event.target.value)}
              className="max-w-64 bg-transparent text-sm font-medium text-stone-900 outline-none"
              aria-label="Project"
            >
              {projects.map((project) => <option key={text(project.project_id)} value={text(project.project_id)}>{projectLabel(project)}</option>)}
            </select>
            <span className="rounded-md bg-stone-100 px-2 py-1 font-mono text-[11px] text-stone-500">Rev {revision ?? '—'}</span>

            <div className="ml-auto flex flex-wrap items-center gap-2">
              {statusChip('Design', failedActions.length || blockedObjects.length ? 'blocked' : completedActions.length ? 'verified' : 'pending')}
              {statusChip('Fabrication', fabricationAuthorized ? 'verified' : 'blocked')}
              {statusChip('Power-on', powerOnAuthorized ? 'verified' : 'blocked')}
              <Button size="sm" variant="outline" onClick={loadProjects} disabled={busy !== null} className="h-8 border-stone-300 bg-white text-stone-700">
                {busy ? <LoaderCircle className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
              </Button>
              <Link href={`/engineering/visual?project=${encodeURIComponent(projectId)}&mode=decide`} className="inline-flex h-8 items-center gap-1.5 rounded-md bg-stone-900 px-3 text-xs font-medium text-white hover:bg-stone-800">
                Compare <ArrowRight className="h-3.5 w-3.5" />
              </Link>
            </div>
          </div>
        </header>

        {error ? (
          <div className="flex items-start gap-2 border-b border-red-200 bg-red-50 px-4 py-2 text-xs text-red-800"><XCircle className="mt-0.5 h-3.5 w-3.5" />{error}</div>
        ) : null}

        <section className="grid min-h-0 flex-1 grid-cols-1 gap-px bg-stone-200 xl:grid-cols-[260px_minmax(0,1fr)_340px]">
          <aside className="flex min-h-[720px] flex-col bg-white">
            <div className="grid grid-cols-3 border-b border-stone-200 p-2">
              {railTabs.map(([id, label, count]) => (
                <button key={id} type="button" onClick={() => setRailTab(id)} className={`rounded-md px-2 py-2 text-xs font-medium ${railTab === id ? 'bg-stone-100 text-stone-950' : 'text-stone-500 hover:text-stone-900'}`}>
                  {label}{count ? <span className="ml-1 text-stone-400">{count}</span> : null}
                </button>
              ))}
            </div>

            {railTab === 'project' ? (
              <>
                <label className="m-3 flex items-center gap-2 rounded-md border border-stone-200 bg-stone-50 px-2.5 py-2">
                  <Search className="h-3.5 w-3.5 text-stone-400" />
                  <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search" className="min-w-0 flex-1 bg-transparent text-xs outline-none placeholder:text-stone-400" />
                </label>
                <div className="min-h-0 flex-1 overflow-y-auto px-2 pb-3">
                  <div className="px-2 pb-2 text-[10px] font-semibold uppercase tracking-[0.12em] text-stone-400">Objects</div>
                  {filteredObjects.map((object) => {
                    const active = selected?.id === object.id;
                    return (
                      <button key={object.id} type="button" onClick={() => { setSelectedObject(object); setInspectorTab('object'); }} className={`mb-0.5 flex w-full items-center gap-2 rounded-md px-2.5 py-2 text-left ${active ? 'bg-stone-100' : 'hover:bg-stone-50'}`}>
                        <span className={`h-2 w-2 shrink-0 rounded-full ${object.blockers.length || object.status === 'blocked' ? 'bg-red-500' : object.status === 'supported' ? 'bg-emerald-500' : 'bg-stone-300'}`} />
                        <div className="min-w-0 flex-1">
                          <div className="truncate text-xs font-medium text-stone-800">{object.label}</div>
                          <div className="truncate text-[10px] text-stone-400">{object.kind} · {object.domain}</div>
                        </div>
                      </button>
                    );
                  })}
                </div>
                <div className="border-t border-stone-200 p-3 text-[10px] text-stone-400">{sources.length} sources · {graph.objects.length} objects · {sessions.length} AI sessions</div>
              </>
            ) : railTab === 'findings' ? (
              <div className="min-h-0 flex-1 overflow-y-auto p-3">
                {!blockedObjects.length && !failedActions.length ? <div className="text-xs text-stone-500">No recorded blocker or failed check.</div> : null}
                {blockedObjects.map((object) => (
                  <button key={object.id} type="button" onClick={() => { setSelectedObject(object); setInspectorTab('findings'); }} className="mb-2 w-full rounded-md border border-red-100 bg-red-50 p-3 text-left">
                    <div className="text-xs font-semibold text-red-800">{object.label}</div>
                    <div className="mt-1 line-clamp-2 text-[11px] leading-4 text-red-700/80">{object.blockers[0] || 'Blocked object'}</div>
                  </button>
                ))}
                {failedActions.map((action, index) => (
                  <div key={text(action.action_id, `failed-${index}`)} className="mb-2 rounded-md border border-red-100 bg-red-50 p-3">
                    <div className="text-xs font-semibold text-red-800">{text(action.title || action.action_type, 'Failed check')}</div>
                    <div className="mt-1 font-mono text-[10px] text-red-600/70">{text(action.action_id, '')}</div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="min-h-0 flex-1 overflow-y-auto p-3">
                {actions.slice().reverse().map((action, index) => (
                  <div key={text(action.action_id, `action-${index}`)} className="flex gap-2 border-b border-stone-100 py-2.5">
                    <span className={`mt-1 h-2 w-2 shrink-0 rounded-full ${actionStatus(action) === 'failed' ? 'bg-red-500' : ['completed', 'passed', 'succeeded'].includes(actionStatus(action)) ? 'bg-emerald-500' : 'bg-stone-300'}`} />
                    <div className="min-w-0">
                      <div className="truncate text-xs font-medium text-stone-700">{text(action.title || action.action_type, 'Engineering action')}</div>
                      <div className="mt-0.5 text-[10px] uppercase tracking-[0.08em] text-stone-400">{actionStatus(action)}</div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </aside>

          <section className="min-w-0 bg-white">
            <ArtifactViewport buildDir={buildDir} overlayFinding={overlayFinding} />
          </section>

          <aside className="flex min-h-[720px] flex-col bg-white">
            <div className="grid grid-cols-3 border-b border-stone-200 p-2">
              {([['object', 'Object'], ['findings', `Findings${selected?.blockers.length ? ` ${selected.blockers.length}` : ''}`], ['evidence', `Evidence${selected?.evidenceIds.length ? ` ${selected.evidenceIds.length}` : ''}`]] as Array<[InspectorTab, string]>).map(([id, label]) => (
                <button key={id} type="button" onClick={() => setInspectorTab(id)} className={`rounded-md px-2 py-2 text-xs font-medium ${inspectorTab === id ? 'bg-stone-100 text-stone-950' : 'text-stone-500 hover:text-stone-900'}`}>{label}</button>
              ))}
            </div>

            <div className="min-h-0 flex-1 overflow-y-auto p-4">
              {!selected ? <div className="text-sm text-stone-500">Select an engineering object.</div> : inspectorTab === 'object' ? (
                <div>
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <h2 className="text-lg font-semibold tracking-tight text-stone-950">{selected.label}</h2>
                      <div className="mt-1 text-xs text-stone-500">{selected.domain} · {selected.kind}</div>
                    </div>
                    <span className={`rounded-full px-2 py-1 text-[10px] font-semibold ${selected.blockers.length || selected.status === 'blocked' ? 'bg-red-50 text-red-700' : selected.status === 'supported' ? 'bg-emerald-50 text-emerald-700' : 'bg-stone-100 text-stone-600'}`}>{selected.status}</span>
                  </div>
                  {selected.description ? <p className="mt-4 text-sm leading-6 text-stone-600">{selected.description}</p> : null}
                  <dl className="mt-5 divide-y divide-stone-100 border-y border-stone-100 text-xs">
                    <div className="flex justify-between gap-4 py-3"><dt className="text-stone-500">Evidence</dt><dd className="font-medium text-stone-900">{selected.evidenceIds.length}</dd></div>
                    <div className="flex justify-between gap-4 py-3"><dt className="text-stone-500">Blockers</dt><dd className={selected.blockers.length ? 'font-medium text-red-700' : 'font-medium text-stone-900'}>{selected.blockers.length}</dd></div>
                    <div className="flex justify-between gap-4 py-3"><dt className="text-stone-500">Proposals</dt><dd className="font-medium text-stone-900">{selected.proposalIds.length}</dd></div>
                    <div className="flex justify-between gap-4 py-3"><dt className="text-stone-500">Revision</dt><dd className="font-mono text-stone-900">{revision ?? '—'}</dd></div>
                  </dl>
                  <div className="mt-5 grid gap-2">
                    <Link href={`/engineering/visual?project=${encodeURIComponent(projectId)}&mode=verify&object=${encodeURIComponent(selected.id)}`} className="flex items-center justify-between rounded-md border border-stone-200 px-3 py-2.5 text-xs font-medium text-stone-700 hover:bg-stone-50">Inspect verification <FileCheck2 className="h-3.5 w-3.5" /></Link>
                    <Link href={`/engineering/visual?project=${encodeURIComponent(projectId)}&mode=decide&object=${encodeURIComponent(selected.id)}`} className="flex items-center justify-between rounded-md border border-stone-200 px-3 py-2.5 text-xs font-medium text-stone-700 hover:bg-stone-50">Compare proposal <GitBranch className="h-3.5 w-3.5" /></Link>
                  </div>
                </div>
              ) : inspectorTab === 'findings' ? (
                <div>
                  <h2 className="text-sm font-semibold text-stone-900">Related findings</h2>
                  <div className="mt-3 space-y-2">
                    {selected.blockers.map((blocker) => (
                      <div key={blocker} className="rounded-md border border-red-200 bg-red-50 p-3">
                        <div className="flex gap-2"><ShieldAlert className="mt-0.5 h-4 w-4 shrink-0 text-red-700" /><div className="text-xs leading-5 text-red-800">{blocker}</div></div>
                      </div>
                    ))}
                    {!selected.blockers.length ? <div className="flex gap-2 rounded-md border border-stone-200 p-3 text-xs text-stone-500"><ShieldCheck className="h-4 w-4 text-emerald-600" />No blocker is attached to this object.</div> : null}
                  </div>
                </div>
              ) : (
                <div>
                  <h2 className="text-sm font-semibold text-stone-900">Evidence identities</h2>
                  <div className="mt-3 space-y-2">
                    {selected.evidenceIds.map((id) => <div key={id} className="flex items-center gap-2 rounded-md border border-stone-200 px-3 py-2.5"><FileText className="h-3.5 w-3.5 text-stone-400" /><span className="break-all font-mono text-[10px] text-stone-600">{id}</span></div>)}
                    {!selected.evidenceIds.length ? <div className="text-xs text-stone-500">No evidence identity is attached.</div> : null}
                  </div>
                </div>
              )}
            </div>

            <div className="border-t border-stone-200 p-4">
              <div className="mb-2 flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.1em] text-stone-400"><PanelRight className="h-3.5 w-3.5" />Authority</div>
              <div className="grid grid-cols-3 gap-1.5 text-center text-[10px] font-medium">
                <div className={`rounded-md px-2 py-2 ${fabricationAuthorized ? 'bg-emerald-50 text-emerald-700' : 'bg-stone-100 text-stone-500'}`}>FAB<br />{fabricationAuthorized ? 'OPEN' : 'CLOSED'}</div>
                <div className={`rounded-md px-2 py-2 ${powerOnAuthorized ? 'bg-emerald-50 text-emerald-700' : 'bg-stone-100 text-stone-500'}`}>POWER<br />{powerOnAuthorized ? 'OPEN' : 'CLOSED'}</div>
                <div className={`rounded-md px-2 py-2 ${releaseAuthorized ? 'bg-emerald-50 text-emerald-700' : 'bg-stone-100 text-stone-500'}`}>RELEASE<br />{releaseAuthorized ? 'OPEN' : 'CLOSED'}</div>
              </div>
            </div>
          </aside>
        </section>

        <footer className="border-t border-stone-200 bg-white px-4 py-3">
          <div className="flex items-center gap-4 overflow-x-auto">
            <div className="flex shrink-0 items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.1em] text-stone-400"><History className="h-3.5 w-3.5" />Timeline</div>
            <div className="flex min-w-0 flex-1 items-center gap-2">
              {actions.slice(-6).map((action, index) => (
                <div key={text(action.action_id, `timeline-${index}`)} className="flex shrink-0 items-center gap-2 rounded-md bg-stone-50 px-2.5 py-1.5 text-[10px] text-stone-600">
                  <span className={`h-1.5 w-1.5 rounded-full ${actionStatus(action) === 'failed' ? 'bg-red-500' : ['completed', 'passed', 'succeeded'].includes(actionStatus(action)) ? 'bg-emerald-500' : 'bg-stone-300'}`} />
                  <span className="max-w-40 truncate">{text(action.title || action.action_type, 'action')}</span>
                </div>
              ))}
              {!actions.length ? <span className="text-[10px] text-stone-400">No persisted engineering action yet.</span> : null}
            </div>
            <Link href={`/engineering/visual?project=${encodeURIComponent(projectId)}&mode=bringup`} className="inline-flex shrink-0 items-center gap-1.5 rounded-md border border-stone-300 px-3 py-1.5 text-xs font-medium text-stone-700 hover:bg-stone-50">Bring-up <ArrowRight className="h-3.5 w-3.5" /></Link>
          </div>
        </footer>
      </div>
    </main>
  );
}

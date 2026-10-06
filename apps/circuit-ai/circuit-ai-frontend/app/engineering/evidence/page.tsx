'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import Link from 'next/link';
import {
  AlertTriangle,
  ArrowRight,
  Check,
  ChevronRight,
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
import { ProvenanceChip, findProvenance, type FindingProvenance } from '@/components/engineering/provenance-chip';
import { ReviewThreadsPanel } from '@/components/engineering/review-threads-panel';
import { useProjectFindings } from '@/lib/project-findings';
import { setPresenceFocus } from '@/lib/project-live';
import { useProjectParts } from '@/lib/project-parts';
import { PartsPanel } from '@/components/engineering/parts-panel';
import { EvidenceArtifactViewport, type ActiveArtifact, type FocusPart, type PlacedPin, type ProposalPreview, type ViewerPin } from '@/components/engineering/evidence-artifact-viewport';
import { ProposalsPanel } from '@/components/engineering/proposals-panel';
import { fetchCandidateFile, useCandidates, type Candidate } from '@/lib/project-candidates';
import { changesToHighlights } from '@/lib/artifact-diff';
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
type RailTab = 'project' | 'findings' | 'parts' | 'proposals' | 'history';
type InspectorTab = 'object' | 'findings' | 'evidence' | 'threads';

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
  const { findings } = useProjectFindings(projectId);
  const parts = useProjectParts(projectId, revision, railTab === 'parts');
  const [activeArtifact, setActiveArtifact] = useState<ActiveArtifact | null>(null);
  const candidates = useCandidates(projectId);
  const [preview, setPreview] = useState<ProposalPreview | null>(null);
  const [previewError, setPreviewError] = useState('');
  const [focusChange, setFocusChange] = useState<string | null>(null);
  const [focusPart, setFocusPart] = useState<FocusPart | null>(null);

  async function previewCandidate(candidate: Candidate | null) {
    setPreviewError('');
    if (!candidate) { setPreview(null); setFocusChange(null); return; }
    try {
      const text = await fetchCandidateFile(projectId, candidate.candidate_id, candidate.kind);
      setPreview({ candidateId: candidate.candidate_id, kind: candidate.kind, text, relative: candidate.files?.[candidate.kind]?.relative });
    } catch (caught) {
      setPreview(null);
      setPreviewError(caught instanceof Error ? caught.message : 'The proposed file could not be loaded.');
    }
  }

  // A preview belongs to one project; leaving it must not leave another project's file on screen.
  useEffect(() => { setPreview(null); setPreviewError(''); setFocusChange(null); }, [projectId]);

  // The previewed proposal's changes, boxed on the file they belong to. Shown only while that file is the one on screen.
  const previewedCandidate = preview ? candidates.candidates.find((item) => item.candidate_id === preview.candidateId) || null : null;
  const previewHighlights = previewedCandidate && activeArtifact && activeArtifact.kind === previewedCandidate.kind
    ? changesToHighlights({
        available: true,
        kind: previewedCandidate.kind,
        summary: previewedCandidate.diff?.summary || { added: 0, removed: 0, changed: 0, unchanged: 0 },
        changes: previewedCandidate.diff?.changes || [],
      }, activeArtifact.relative)
    : [];
  const [placing, setPlacing] = useState(false);
  const [pendingPin, setPendingPin] = useState<PlacedPin | null>(null);
  const [threadPins, setThreadPins] = useState<ViewerPin[]>([]);
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

  /** What a registered source is and which recorded requirements cite it. Nothing here is inferred. */
  function evidenceDetail(id: string) {
    const source = sources.find((item) => text(item.source_id || item.id, '') === id) || null;
    const supports = sessions.flatMap((item) => rows(item.requirements)
      .filter((requirement) => (Array.isArray(requirement.source_ids) ? requirement.source_ids : []).map(String).includes(id))
      .map((requirement) => text(requirement.statement, '')))
      .filter(Boolean);
    return { source, supports: Array.from(new Set(supports)) };
  }

  const failedCheckProvenance = (actionId: string): FindingProvenance | null => findings
    .find((item) => item.category === 'failed_check' && item.provenance.source_ref === actionId)?.provenance || null;

  // Findings the backend recorded that this page did not already derive itself (for example release blockers).
  const recordedFindings = useMemo(() => {
    const shownTexts = new Set([...blockedObjects.flatMap((object) => object.blockers), ...failedActions.map((action) => text(action.title || action.action_type, ''))]);
    const shownRefs = new Set(failedActions.map((action) => text(action.action_id, '')));
    return findings.filter((item) => !shownTexts.has(item.text) && !(item.category === 'failed_check' && item.provenance.source_ref && shownRefs.has(item.provenance.source_ref)));
  }, [findings, blockedObjects, failedActions]);

  const firstBlocked = blockedObjects[0] || null;
  const searchRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    setPresenceFocus(selected?.id || '');
  }, [selected?.id]);

  useEffect(() => {
    // A pin placed for one object must not leak into a thread started on another.
    setPendingPin(null);
    setPlacing(false);
  }, [selected?.id]);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.metaKey || event.ctrlKey || event.altKey) return;
      const target = event.target;
      if (target instanceof HTMLElement && (target.isContentEditable || ['INPUT', 'SELECT', 'TEXTAREA'].includes(target.tagName))) return;
      if (event.key === '/') {
        event.preventDefault();
        setRailTab('project');
        window.setTimeout(() => searchRef.current?.focus(), 0);
      } else if ((event.key === 'j' || event.key === 'k') && filteredObjects.length) {
        event.preventDefault();
        const index = filteredObjects.findIndex((object) => object.id === selected?.id);
        const next = event.key === 'j' ? Math.min(index + 1, filteredObjects.length - 1) : Math.max(index - 1, 0);
        setSelectedObject(filteredObjects[next]);
        setInspectorTab('object');
      }
    }
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [filteredObjects, selected?.id]);

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
    ['parts', 'Parts', null],
    ['proposals', 'Proposals', candidates.candidates.length],
    ['history', 'History', null],
  ];

  return (
    <main className="h-full bg-stone-100 text-stone-950">
      <div className="flex h-full min-h-[760px] flex-col">
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

        {projectId ? (
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1 border-b border-stone-200 bg-white px-4 py-2 text-xs text-stone-600" data-testid="next-step">
            {firstBlocked || failedActions.length ? (
              <>
                <span className="h-2 w-2 shrink-0 rounded-full bg-red-500" aria-hidden="true" />
                <span>
                  <span className="font-medium text-stone-900">Design is blocked.</span>{' '}
                  {blockedObjects.length ? `${blockedObjects.length} of ${graph.objects.length} objects carry a blocker` : ''}
                  {blockedObjects.length && failedActions.length ? ' and ' : ''}
                  {failedActions.length ? `${failedActions.length} check${failedActions.length === 1 ? '' : 's'} failed` : ''}.
                </span>
                {firstBlocked ? (
                  <button
                    type="button"
                    onClick={() => { setSelectedObject(firstBlocked); setRailTab('findings'); setInspectorTab('findings'); }}
                    className="inline-flex items-center gap-1 rounded-md border border-stone-300 px-2 py-1 font-medium text-stone-800 hover:bg-stone-50"
                  >
                    Review {firstBlocked.label} first <ArrowRight className="h-3 w-3" />
                  </button>
                ) : null}
              </>
            ) : (
              <>
                <span className="h-2 w-2 shrink-0 rounded-full bg-emerald-500" aria-hidden="true" />
                <span>
                  <span className="font-medium text-stone-900">No recorded blockers.</span>
                  {powerOnAuthorized ? '' : ' Power-on stays closed until real measurements are attached.'}
                </span>
              </>
            )}
          </div>
        ) : null}

        {error ? (
          <div className="flex items-start gap-2 border-b border-red-200 bg-red-50 px-4 py-2 text-xs text-red-800"><XCircle className="mt-0.5 h-3.5 w-3.5" />{error}</div>
        ) : null}

        <section className="grid min-h-0 flex-1 grid-cols-1 gap-px bg-stone-200 xl:grid-cols-[320px_minmax(0,1fr)_340px] xl:grid-rows-[minmax(0,1fr)]">
          <aside className="flex min-h-[720px] xl:min-h-0 flex-col bg-white">
            <div className="flex overflow-x-auto border-b border-stone-200 p-2">
              {railTabs.map(([id, label, count]) => (
                <button key={id} type="button" onClick={() => setRailTab(id)} className={`shrink-0 rounded-md px-1 py-2 text-[11.5px] font-medium ${railTab === id ? 'bg-stone-100 text-stone-950' : 'text-stone-500 hover:text-stone-900'}`}>
                  {label}{count ? <span className="ml-0.5 text-stone-400">{count}</span> : null}
                </button>
              ))}
            </div>

            {railTab === 'project' ? (
              <>
                <label className="m-3 flex items-center gap-2 rounded-md border border-stone-200 bg-stone-50 px-2.5 py-2">
                  <Search className="h-3.5 w-3.5 text-stone-400" />
                  <input ref={searchRef} value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search" className="min-w-0 flex-1 bg-transparent text-xs outline-none placeholder:text-stone-400" />
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
            ) : railTab === 'proposals' ? (
              <>
                {previewError ? <div role="alert" className="m-3 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-800">{previewError}</div> : null}
                <ProposalsPanel candidates={candidates.candidates} loading={candidates.loading} projectId={projectId} nextRevision={revision ? revision + 1 : null} previewId={preview?.candidateId || null} onPreview={(candidate) => void previewCandidate(candidate)} onFocusChange={setFocusChange} decide={candidates.decide} />
              </>
            ) : railTab === 'parts' ? (
              <PartsPanel result={parts.result} loading={parts.loading} error={parts.error} onCheckAvailability={() => void parts.checkAvailability()} onLocate={(ref) => setFocusPart({ ref, kind: 'schematic', nonce: Date.now() })} />
            ) : railTab === 'findings' ? (
              <div className="min-h-0 flex-1 overflow-y-auto p-3">
                {!blockedObjects.length && !failedActions.length && !recordedFindings.length ? <div className="text-xs text-stone-500">No recorded blocker or failed check.</div> : null}
                {blockedObjects.length ? <div className="px-0.5 pb-2 text-[10px] font-semibold uppercase tracking-[0.12em] text-stone-400">Blocked objects · {blockedObjects.length}</div> : null}
                {blockedObjects.map((object) => (
                  <button key={object.id} type="button" onClick={() => { setSelectedObject(object); setInspectorTab('findings'); }} className="mb-2 w-full rounded-md border border-red-100 bg-red-50 p-3 text-left">
                    <div className="text-xs font-semibold text-red-800">{object.label}</div>
                    <div className="mt-1 line-clamp-2 text-[11px] leading-4 text-red-700/80">{object.blockers[0] || 'Blocked object'}</div>
                    {object.blockers[0] ? <div className="mt-2"><ProvenanceChip provenance={findProvenance(findings, object.blockers[0], object.id)} /></div> : null}
                  </button>
                ))}
                {failedActions.length ? <div className="px-0.5 pb-2 pt-2 text-[10px] font-semibold uppercase tracking-[0.12em] text-stone-400">Failed checks · {failedActions.length}</div> : null}
                {failedActions.map((action, index) => (
                  <div key={text(action.action_id, `failed-${index}`)} className="mb-2 rounded-md border border-red-100 bg-red-50 p-3">
                    <div className="text-xs font-semibold text-red-800">{text(action.title || action.action_type, 'Failed check')}</div>
                    <div className="mt-1 font-mono text-[10px] text-red-600/70">{text(action.action_id, '')}</div>
                    <div className="mt-2"><ProvenanceChip provenance={failedCheckProvenance(text(action.action_id, ''))} /></div>
                  </div>
                ))}
                {recordedFindings.length ? <div className="px-0.5 pb-2 pt-2 text-[10px] font-semibold uppercase tracking-[0.12em] text-stone-400">Recorded by checks · {recordedFindings.length}</div> : null}
                {recordedFindings.map((item) => (
                  <div key={item.finding_id} className="mb-2 rounded-md border border-red-100 bg-red-50 p-3">
                    <div className="text-[10px] font-medium text-red-700/80">{item.category === 'release_blocker' ? 'Release blocker' : item.category === 'traceability_issue' ? 'Traceability' : item.category === 'failed_check' ? 'Check' : 'Finding'}</div>
                    <div className="mt-1 text-[11px] leading-4 text-red-800">{item.text}</div>
                    <div className="mt-2"><ProvenanceChip provenance={item.provenance} /></div>
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

          <section className="order-first min-w-0 bg-white xl:order-none">
            <EvidenceArtifactViewport
              buildDir={buildDir}
              overlayFinding={overlayFinding}
              pins={threadPins}
              placing={placing}
              onPlace={(pin) => { setPendingPin(pin); setPlacing(false); }}
              onCancelPlace={() => setPlacing(false)}
              onActiveArtifact={setActiveArtifact}
              model3d={{ projectId, revision }}
              preview={preview}
              focusPart={focusPart}
              highlights={previewHighlights}
              focusHighlightId={focusChange}
              proposing={revision ? {
                projectId,
                baseRevision: revision,
                onPropose: (kind, input, note) => candidates.propose({ baseRevision: revision, kind, note, ...input }),
                onProposed: () => setRailTab('proposals'),
              } : undefined}
            />
          </section>

          <aside className="flex min-h-[720px] xl:min-h-0 flex-col bg-white">
            <div className="grid grid-cols-4 border-b border-stone-200 p-2">
              {([['object', 'Object'], ['findings', `Findings${selected?.blockers.length ? ` ${selected.blockers.length}` : ''}`], ['evidence', `Evidence${selected?.evidenceIds.length ? ` ${selected.evidenceIds.length}` : ''}`], ['threads', 'Threads']] as Array<[InspectorTab, string]>).map(([id, label]) => (
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
                        <div className="mt-2"><ProvenanceChip provenance={findProvenance(findings, blocker, selected.id)} /></div>
                      </div>
                    ))}
                    {!selected.blockers.length ? <div className="flex gap-2 rounded-md border border-stone-200 p-3 text-xs text-stone-500"><ShieldCheck className="h-4 w-4 text-emerald-600" />No blocker is attached to this object.</div> : null}
                  </div>
                </div>
              ) : inspectorTab === 'threads' ? (
                <ReviewThreadsPanel
                  projectId={projectId}
                  revision={revision}
                  objectId={selected.id}
                  objectLabel={selected.label}
                  activeArtifact={activeArtifact}
                  pendingPin={pendingPin}
                  onRequestPin={() => setPlacing(true)}
                  onClearPin={() => { setPendingPin(null); setPlacing(false); }}
                  onPinsChange={setThreadPins}
                />
              ) : (
                <div>
                  <h2 className="text-sm font-semibold text-stone-900">Evidence identities</h2>
                  <div className="mt-3 space-y-2">
                    {selected.evidenceIds.map((id) => {
                      const detail = evidenceDetail(id);
                      return (
                        <div key={id} className="rounded-md border border-stone-200 px-3 py-2.5">
                          <div className="flex items-center gap-2">
                            <FileText className="h-3.5 w-3.5 shrink-0 text-stone-400" />
                            <span className="min-w-0 flex-1 break-all font-mono text-[10px] text-stone-700">{id}</span>
                            <span className={`shrink-0 rounded px-1.5 py-0.5 text-[10px] font-medium ${detail.source ? 'bg-stone-100 text-stone-600' : 'bg-amber-50 text-amber-700'}`}>
                              {detail.source ? text(detail.source.source_type, 'source') : 'not registered'}
                            </span>
                          </div>
                          <div className="mt-2 text-[10px] font-medium text-stone-400">Cited by</div>
                          {detail.supports.length ? (
                            <ul className="mt-1 space-y-1">
                              {detail.supports.map((statement) => <li key={statement} className="text-[11px] leading-4 text-stone-600">{statement}</li>)}
                            </ul>
                          ) : <div className="mt-1 text-[11px] text-stone-500">No recorded requirement cites this source.</div>}
                        </div>
                      );
                    })}
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

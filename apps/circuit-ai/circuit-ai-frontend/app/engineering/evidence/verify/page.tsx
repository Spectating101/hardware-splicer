'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  ChevronRight,
  Circle,
  FileCheck2,
  FileText,
  LoaderCircle,
  RefreshCw,
  ShieldAlert,
  ShieldCheck,
  XCircle,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { usePageTitle } from '@/components/use-page-title';
import {
  EvidenceArtifactViewport,
  deriveEvidenceBuildDir,
} from '@/components/engineering/evidence-artifact-viewport';
import { deriveCanonicalSystemGraph } from '@/components/engineering/canonical-system-canvas';
import {
  getProxyErrorMessage,
  isProxyFailure,
  readJsonPayload,
  type ProxyErrorPayload,
} from '@/lib/proxy-client';

type JsonRecord = Record<string, unknown>;
type ProjectSummary = { project_id?: string; name?: string; project_name?: string; revision?: number };
type ProjectsResponse = { ok?: boolean; projects?: ProjectSummary[] };
type ProjectEnvelope = { project_id?: string; revision?: number; snapshot?: JsonRecord };
type ProjectResponse = { ok?: boolean; project?: ProjectEnvelope };
type CheckState = 'passed' | 'failed' | 'pending';
type VerificationCheck = {
  id: string;
  label: string;
  detail: string;
  state: CheckState;
  kind: 'artifact' | 'source' | 'deterministic' | 'blocker' | 'physical';
  evidenceIds: string[];
  raw?: JsonRecord;
};

function record(value: unknown): JsonRecord {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value) ? value as JsonRecord : {};
}

function rows(value: unknown): JsonRecord[] {
  return Array.isArray(value)
    ? value.filter((row): row is JsonRecord => Boolean(row) && typeof row === 'object' && !Array.isArray(row))
    : [];
}

function text(value: unknown, fallback = '—') {
  return value === undefined || value === null || value === '' ? fallback : String(value);
}

function uniqueStrings(values: string[]) {
  return Array.from(new Set(values.filter(Boolean)));
}

function projectLabel(project: ProjectSummary) {
  return text(project.name || project.project_name, text(project.project_id));
}

function actionStatus(action: JsonRecord) {
  return text(action.status, 'unknown').toLowerCase();
}

function stateIcon(state: CheckState) {
  if (state === 'passed') return <CheckCircle2 className="h-4 w-4 text-emerald-600" />;
  if (state === 'failed') return <XCircle className="h-4 w-4 text-red-600" />;
  return <Circle className="h-4 w-4 text-stone-300" />;
}

function stateTone(state: CheckState) {
  if (state === 'passed') return 'border-emerald-200 bg-emerald-50/60';
  if (state === 'failed') return 'border-red-200 bg-red-50/60';
  return 'border-stone-200 bg-white';
}

export default function EvidenceVerifyPage() {
  usePageTitle('Verification | Hardware Splicer');
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [projectId, setProjectId] = useState('');
  const [revision, setRevision] = useState<number | null>(null);
  const [snapshot, setSnapshot] = useState<JsonRecord | null>(null);
  const [session, setSession] = useState<JsonRecord | null>(null);
  const [selectedCheckId, setSelectedCheckId] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const sources = rows(snapshot?.engineeringSources);
  const sessions = rows(snapshot?.engineeringAiSessions);
  const actions = rows(session?.actions);
  const graph = useMemo(() => deriveCanonicalSystemGraph(snapshot, session), [snapshot, session]);
  const buildDir = deriveEvidenceBuildDir(snapshot, session);
  const blockedObjects = graph.objects.filter((object) => object.blockers.length > 0 || object.status === 'blocked');
  const fabricationAuthorized = snapshot?.fabrication_authorized === true;
  const powerOnAuthorized = snapshot?.power_on_authorized === true;
  const releaseAuthorized = snapshot?.release_authorized === true;

  const projectName = useMemo(() => {
    const match = projects.find((project) => text(project.project_id) === projectId);
    return match ? projectLabel(match) : text(snapshot?.name || snapshot?.project_name, projectId || 'Hardware project');
  }, [projectId, projects, snapshot]);

  const checks = useMemo<VerificationCheck[]>(() => {
    const structuralEvidence = uniqueStrings(graph.objects.flatMap((object) => object.evidenceIds));
    const actionChecks = actions.map((action, index) => {
      const status = actionStatus(action);
      const state: CheckState = status === 'failed'
        ? 'failed'
        : ['completed', 'passed', 'succeeded'].includes(status)
          ? 'passed'
          : 'pending';
      return {
        id: text(action.action_id, `action-${index}`),
        label: text(action.title || action.action_type, 'Engineering check'),
        detail: status,
        state,
        kind: 'deterministic' as const,
        evidenceIds: [],
        raw: action,
      };
    });

    return [
      {
        id: 'artifact',
        label: 'Revision-bound design artifact',
        detail: buildDir ? 'KiCad artifact is attached to the active project state.' : 'No build artifact is attached to the active snapshot.',
        state: buildDir ? 'passed' : 'pending',
        kind: 'artifact',
        evidenceIds: [],
      },
      {
        id: 'sources',
        label: 'Engineering sources',
        detail: sources.length ? `${sources.length} registered source descriptor${sources.length === 1 ? '' : 's'}.` : 'No engineering source descriptor is registered.',
        state: sources.length ? 'passed' : 'pending',
        kind: 'source',
        evidenceIds: structuralEvidence,
      },
      ...actionChecks,
      {
        id: 'blockers',
        label: 'Unresolved engineering blockers',
        detail: blockedObjects.length ? `${blockedObjects.length} object${blockedObjects.length === 1 ? '' : 's'} remain blocked.` : 'No canonical object currently carries a blocker.',
        state: blockedObjects.length ? 'failed' : 'passed',
        kind: 'blocker',
        evidenceIds: uniqueStrings(blockedObjects.flatMap((object) => object.evidenceIds)),
      },
      {
        id: 'physical-proof',
        label: 'Physical correctness',
        detail: 'Software verification does not establish physical correctness. Physical evidence is reviewed in Bring-up.',
        state: 'pending',
        kind: 'physical',
        evidenceIds: [],
      },
    ];
  }, [actions, blockedObjects, buildDir, graph.objects, sources.length]);

  const selected = checks.find((check) => check.id === selectedCheckId) || checks.find((check) => check.state === 'failed') || checks[0];
  const failedCount = checks.filter((check) => check.state === 'failed').length;
  const passedCount = checks.filter((check) => check.state === 'passed').length;
  const pendingCount = checks.filter((check) => check.state === 'pending').length;
  const overlay = selected?.state === 'failed' ? selected.label : '';

  async function loadProject(nextProjectId: string) {
    if (!nextProjectId) return;
    setBusy(true);
    setError('');
    try {
      const response = await fetch(`/api/proxy/engineering/projects/${encodeURIComponent(nextProjectId)}`, { cache: 'no-store' });
      const payload = await readJsonPayload<ProjectResponse | ProxyErrorPayload>(response);
      if (!response.ok || isProxyFailure(payload)) throw new Error(getProxyErrorMessage(payload, 'Hardware Splicer could not load this project.'));
      const envelope = (payload as ProjectResponse).project || {};
      const nextSnapshot = record(envelope.snapshot);
      const nextSessions = rows(nextSnapshot.engineeringAiSessions);
      setProjectId(nextProjectId);
      setRevision(Number(envelope.revision));
      setSnapshot(nextSnapshot);
      setSession(nextSessions.at(-1) || null);
      setSelectedCheckId('');
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Project load failed.');
    } finally {
      setBusy(false);
    }
  }

  async function loadProjects() {
    setBusy(true);
    setError('');
    try {
      const response = await fetch('/api/proxy/engineering/projects', { cache: 'no-store' });
      const payload = await readJsonPayload<ProjectsResponse | ProxyErrorPayload>(response);
      if (!response.ok || isProxyFailure(payload)) throw new Error(getProxyErrorMessage(payload, 'Hardware Splicer could not list projects.'));
      const listed = (payload as ProjectsResponse).projects || [];
      setProjects(listed);
      const params = typeof window === 'undefined' ? null : new URLSearchParams(window.location.search);
      const requested = params?.get('project') || text(listed[0]?.project_id, '');
      if (requested) await loadProject(requested);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Project list failed.');
      setBusy(false);
    }
  }

  useEffect(() => { void loadProjects(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <main className="min-h-screen bg-stone-100 text-stone-950">
      <div className="flex min-h-screen flex-col">
        <header className="border-b border-stone-200 bg-white">
          <div className="flex min-h-14 flex-wrap items-center gap-3 px-4 lg:px-5">
            <Link href={`/engineering/evidence?project=${encodeURIComponent(projectId)}`} className="inline-flex items-center gap-2 text-sm font-semibold text-stone-950"><ArrowLeft className="h-4 w-4" />Hardware Splicer</Link>
            <ChevronRight className="h-3.5 w-3.5 text-stone-300" />
            <span className="text-sm font-medium text-stone-700">Verification</span>
            <select value={projectId} onChange={(event) => void loadProject(event.target.value)} className="ml-2 max-w-64 bg-transparent text-sm font-medium outline-none" aria-label="Project">
              {projects.map((project) => <option key={text(project.project_id)} value={text(project.project_id)}>{projectLabel(project)}</option>)}
            </select>
            <span className="rounded-md bg-stone-100 px-2 py-1 font-mono text-[11px] text-stone-500">Rev {revision ?? '—'}</span>
            <div className="ml-auto flex items-center gap-2">
              <span className="rounded-md border border-emerald-200 bg-emerald-50 px-2.5 py-1.5 text-xs font-medium text-emerald-800">{passedCount} passed</span>
              <span className={`rounded-md border px-2.5 py-1.5 text-xs font-medium ${failedCount ? 'border-red-200 bg-red-50 text-red-800' : 'border-stone-200 bg-stone-50 text-stone-600'}`}>{failedCount} failed</span>
              <span className="rounded-md border border-stone-200 bg-stone-50 px-2.5 py-1.5 text-xs font-medium text-stone-600">{pendingCount} pending</span>
              <Button size="sm" variant="outline" onClick={loadProjects} disabled={busy} className="h-8 border-stone-300 bg-white text-stone-700">{busy ? <LoaderCircle className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}</Button>
            </div>
          </div>
        </header>

        {error ? <div className="border-b border-red-200 bg-red-50 px-4 py-2 text-xs text-red-800">{error}</div> : null}

        <section className="grid min-h-0 flex-1 grid-cols-1 gap-px bg-stone-200 xl:grid-cols-[290px_minmax(0,1fr)_340px]">
          <aside className="min-h-[720px] overflow-y-auto bg-white p-3">
            <div className="flex items-center gap-2 px-2 pb-3 text-[10px] font-semibold uppercase tracking-[0.12em] text-stone-400"><FileCheck2 className="h-3.5 w-3.5" />Verification ladder</div>
            <div className="space-y-1">
              {checks.map((check) => (
                <button key={check.id} type="button" onClick={() => setSelectedCheckId(check.id)} className={`flex w-full items-start gap-3 rounded-md border px-3 py-3 text-left ${selected?.id === check.id ? stateTone(check.state) : 'border-transparent hover:bg-stone-50'}`}>
                  <div className="mt-0.5">{stateIcon(check.state)}</div>
                  <div className="min-w-0 flex-1">
                    <div className="text-xs font-semibold text-stone-900">{check.label}</div>
                    <div className="mt-1 truncate text-[10px] text-stone-400">{check.detail}</div>
                  </div>
                </button>
              ))}
            </div>
          </aside>

          <section className="min-w-0 bg-white">
            <EvidenceArtifactViewport buildDir={buildDir} overlayFinding={overlay} preferredKind="schematic" />
          </section>

          <aside className="flex min-h-[720px] flex-col bg-white">
            <div className="border-b border-stone-200 px-4 py-3">
              <div className="text-[10px] font-semibold uppercase tracking-[0.1em] text-stone-400">Selected check</div>
              <div className="mt-1 text-xs text-stone-500">{projectName} · Rev {revision ?? '—'}</div>
            </div>
            <div className="min-h-0 flex-1 overflow-y-auto p-4">
              {selected ? (
                <div>
                  <div className="flex items-start gap-3">
                    <div className="mt-0.5">{stateIcon(selected.state)}</div>
                    <div>
                      <div className="text-[10px] font-semibold uppercase tracking-[0.1em] text-stone-400">{selected.kind}</div>
                      <h1 className="mt-1 text-base font-semibold leading-6 text-stone-950">{selected.label}</h1>
                    </div>
                  </div>
                  <p className="mt-4 text-xs leading-5 text-stone-600">{selected.detail}</p>

                  <dl className="mt-5 divide-y divide-stone-100 border-y border-stone-100 text-xs">
                    <div className="flex justify-between gap-4 py-3"><dt className="text-stone-500">State</dt><dd className={`font-medium ${selected.state === 'failed' ? 'text-red-700' : selected.state === 'passed' ? 'text-emerald-700' : 'text-stone-600'}`}>{selected.state}</dd></div>
                    <div className="flex justify-between gap-4 py-3"><dt className="text-stone-500">Evidence refs</dt><dd className="font-medium text-stone-900">{selected.evidenceIds.length}</dd></div>
                    <div className="flex justify-between gap-4 py-3"><dt className="text-stone-500">Project revision</dt><dd className="font-mono text-stone-900">{revision ?? '—'}</dd></div>
                  </dl>

                  {selected.evidenceIds.length ? (
                    <section className="mt-5">
                      <div className="text-[10px] font-semibold uppercase tracking-[0.1em] text-stone-400">Evidence identities</div>
                      <div className="mt-2 space-y-1.5">{selected.evidenceIds.slice(0, 10).map((id) => <div key={id} className="flex items-center gap-2 rounded-md border border-stone-200 px-2.5 py-2"><FileText className="h-3.5 w-3.5 text-stone-400" /><span className="break-all font-mono text-[10px] text-stone-600">{id}</span></div>)}</div>
                    </section>
                  ) : null}

                  {selected.state === 'failed' ? (
                    <div className="mt-5 flex gap-2 rounded-md border border-red-200 bg-red-50 p-3 text-xs leading-5 text-red-800"><ShieldAlert className="mt-0.5 h-4 w-4 shrink-0" />This result blocks downstream confidence. A repair must create a successor state and relevant checks must run again.</div>
                  ) : selected.state === 'passed' ? (
                    <div className="mt-5 flex gap-2 rounded-md border border-emerald-200 bg-emerald-50 p-3 text-xs leading-5 text-emerald-800"><ShieldCheck className="mt-0.5 h-4 w-4 shrink-0" />This check supports the digital artifact at this revision. It does not establish physical correctness.</div>
                  ) : (
                    <div className="mt-5 flex gap-2 rounded-md border border-stone-200 bg-stone-50 p-3 text-xs leading-5 text-stone-600"><AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />This evidence class has not been established by the current record.</div>
                  )}
                </div>
              ) : null}
            </div>

            <div className="border-t border-stone-200 p-4">
              <div className="mb-2 text-[10px] font-semibold uppercase tracking-[0.1em] text-stone-400">Authority remains separate</div>
              <div className="grid grid-cols-3 gap-1.5 text-center text-[10px] font-medium">
                <div className={`rounded-md px-2 py-2 ${fabricationAuthorized ? 'bg-emerald-50 text-emerald-700' : 'bg-stone-100 text-stone-500'}`}>FAB<br />{fabricationAuthorized ? 'OPEN' : 'CLOSED'}</div>
                <div className={`rounded-md px-2 py-2 ${powerOnAuthorized ? 'bg-emerald-50 text-emerald-700' : 'bg-stone-100 text-stone-500'}`}>POWER<br />{powerOnAuthorized ? 'OPEN' : 'CLOSED'}</div>
                <div className={`rounded-md px-2 py-2 ${releaseAuthorized ? 'bg-emerald-50 text-emerald-700' : 'bg-stone-100 text-stone-500'}`}>RELEASE<br />{releaseAuthorized ? 'OPEN' : 'CLOSED'}</div>
              </div>
              <Link href={`/engineering/evidence/bringup?project=${encodeURIComponent(projectId)}`} className="mt-3 flex items-center justify-between rounded-md border border-stone-300 px-3 py-2.5 text-xs font-medium text-stone-700 hover:bg-stone-50">Open physical bring-up <ChevronRight className="h-3.5 w-3.5" /></Link>
            </div>
          </aside>
        </section>
      </div>
    </main>
  );
}
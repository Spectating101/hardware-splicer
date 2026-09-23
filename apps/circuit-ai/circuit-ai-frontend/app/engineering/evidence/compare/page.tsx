'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import {
  AlertTriangle,
  ArrowLeft,
  Check,
  ChevronRight,
  CircleDot,
  FileDiff,
  FileText,
  GitCompareArrows,
  LoaderCircle,
  Minus,
  Plus,
  RefreshCw,
  ShieldAlert,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { usePageTitle } from '@/components/use-page-title';
import {
  EvidenceArtifactViewport,
  deriveEvidenceBuildDir,
} from '@/components/engineering/evidence-artifact-viewport';
import {
  summarizeRevisionDiff,
  type ProjectRevision,
  type RevisionDiffResponse,
  type StatusBlocker,
} from '@/lib/engineering-status';
import {
  getProxyErrorMessage,
  isProxyFailure,
  readJsonPayload,
  type ProxyErrorPayload,
} from '@/lib/proxy-client';

type JsonRecord = Record<string, unknown>;
type ProjectSummary = { project_id?: string; name?: string; project_name?: string; revision?: number; latest_revision?: number };
type ProjectsResponse = { ok?: boolean; projects?: ProjectSummary[] };
type ProjectEnvelope = { project_id?: string; revision?: number; snapshot?: JsonRecord };
type ProjectResponse = { ok?: boolean; project?: ProjectEnvelope };
type DeltaKind = 'opened' | 'resolved' | 'persistent' | 'identity' | 'artifact' | 'execution' | 'authority';
type DeltaItem = {
  id: string;
  kind: DeltaKind;
  title: string;
  detail: string;
  targetIds: string[];
  evidenceIds: string[];
  raw: unknown;
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

function projectLabel(project: ProjectSummary) {
  return text(project.name || project.project_name, text(project.project_id));
}

function blockerItem(blocker: StatusBlocker, kind: 'opened' | 'resolved' | 'persistent'): DeltaItem {
  return {
    id: `${kind}:${blocker.blocker_id}`,
    kind,
    title: blocker.message || blocker.blocker_id,
    detail: blocker.blocker_id,
    targetIds: blocker.target_ids || [],
    evidenceIds: blocker.required_evidence || blocker.source_ids || [],
    raw: blocker,
  };
}

function genericItem(kind: DeltaKind, row: JsonRecord, index: number): DeltaItem {
  const title = text(
    row.summary
    || row.message
    || row.change
    || row.category
    || row.artifact_id
    || row.action_id,
    `${kind} change ${index + 1}`,
  );
  const id = text(row.artifact_id || row.action_id || row.category || row.id, `${kind}-${index}`);
  const targetIds = Array.isArray(row.target_ids) ? row.target_ids.map(String) : [];
  const evidenceIds = Array.isArray(row.required_evidence) ? row.required_evidence.map(String) : [];
  return { id: `${kind}:${id}`, kind, title, detail: id, targetIds, evidenceIds, raw: row };
}

function deltaTone(kind: DeltaKind) {
  if (kind === 'opened' || kind === 'authority') return 'bg-red-500';
  if (kind === 'resolved') return 'bg-emerald-500';
  if (kind === 'persistent') return 'bg-amber-500';
  return 'bg-stone-400';
}

function deltaIcon(kind: DeltaKind) {
  if (kind === 'opened') return Plus;
  if (kind === 'resolved') return Minus;
  if (kind === 'persistent') return AlertTriangle;
  if (kind === 'authority') return ShieldAlert;
  return CircleDot;
}

function deltaLabel(kind: DeltaKind) {
  if (kind === 'opened') return 'Opened blocker';
  if (kind === 'resolved') return 'Resolved blocker';
  if (kind === 'persistent') return 'Persistent blocker';
  if (kind === 'identity') return 'Identity change';
  if (kind === 'artifact') return 'Artifact change';
  if (kind === 'execution') return 'Verification change';
  return 'Authority regression';
}

export default function EvidenceComparePage() {
  usePageTitle('Compare Revisions | Hardware Splicer');
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [projectId, setProjectId] = useState('');
  const [snapshot, setSnapshot] = useState<JsonRecord | null>(null);
  const [session, setSession] = useState<JsonRecord | null>(null);
  const [revisions, setRevisions] = useState<ProjectRevision[]>([]);
  const [baseRevision, setBaseRevision] = useState<number | null>(null);
  const [candidateRevision, setCandidateRevision] = useState<number | null>(null);
  const [diff, setDiff] = useState<RevisionDiffResponse | null>(null);
  const [selectedDeltaId, setSelectedDeltaId] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const projectName = useMemo(() => {
    const match = projects.find((project) => project.project_id === projectId);
    return match ? projectLabel(match) : projectId || 'Hardware project';
  }, [projectId, projects]);

  const buildDir = deriveEvidenceBuildDir(snapshot, session);
  const semantic = diff?.engineering_revision_diff;
  const summary = useMemo(() => summarizeRevisionDiff(diff), [diff]);

  const deltaItems = useMemo<DeltaItem[]>(() => {
    if (!semantic) return [];
    return [
      ...(semantic.opened_blockers || []).map((row) => blockerItem(row, 'opened')),
      ...(semantic.resolved_blockers || []).map((row) => blockerItem(row, 'resolved')),
      ...(semantic.persistent_blockers || []).map((row) => blockerItem(row, 'persistent')),
      ...rows(semantic.identity_changes).map((row, index) => genericItem('identity', row, index)),
      ...rows(semantic.artifact_changes).map((row, index) => genericItem('artifact', row, index)),
      ...rows(semantic.execution_changes).map((row, index) => genericItem('execution', row, index)),
      ...(semantic.authority_regressions || []).map((message, index) => ({
        id: `authority:${index}`,
        kind: 'authority' as const,
        title: message,
        detail: `authority-regression-${index + 1}`,
        targetIds: [],
        evidenceIds: [],
        raw: message,
      })),
    ];
  }, [semantic]);

  const selected = deltaItems.find((item) => item.id === selectedDeltaId) || deltaItems[0] || null;
  const overlay = selected && ['opened', 'persistent', 'authority'].includes(selected.kind) ? selected.title : '';

  async function loadDiff(nextProjectId: string, nextBase: number, nextCandidate: number) {
    setBusy(true);
    setError('');
    try {
      const response = await fetch('/api/proxy/engineering/revisions/diff', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ project_id: nextProjectId, base_revision: nextBase, candidate_revision: nextCandidate }),
        cache: 'no-store',
      });
      const payload = await readJsonPayload<RevisionDiffResponse | ProxyErrorPayload>(response);
      if (!response.ok || isProxyFailure(payload)) throw new Error(getProxyErrorMessage(payload, 'Revision comparison is unavailable.'));
      setDiff(payload as RevisionDiffResponse);
      setSelectedDeltaId('');
    } catch (caught) {
      setDiff(null);
      setError(caught instanceof Error ? caught.message : 'Revision comparison failed.');
    } finally {
      setBusy(false);
    }
  }

  async function loadProject(nextProjectId: string) {
    if (!nextProjectId) return;
    setBusy(true);
    setError('');
    try {
      const [projectResponse, revisionsResponse] = await Promise.all([
        fetch(`/api/proxy/engineering/projects/${encodeURIComponent(nextProjectId)}`, { cache: 'no-store' }),
        fetch(`/api/proxy/engineering/projects/${encodeURIComponent(nextProjectId)}/revisions`, { cache: 'no-store' }),
      ]);
      const projectPayload = await readJsonPayload<ProjectResponse | ProxyErrorPayload>(projectResponse);
      const revisionsPayload = await readJsonPayload<{ ok?: boolean; revisions?: ProjectRevision[] } | ProxyErrorPayload>(revisionsResponse);
      if (!projectResponse.ok || isProxyFailure(projectPayload)) throw new Error(getProxyErrorMessage(projectPayload, 'Project comparison source is unavailable.'));
      if (!revisionsResponse.ok || isProxyFailure(revisionsPayload)) throw new Error(getProxyErrorMessage(revisionsPayload, 'Project revisions are unavailable.'));

      const envelope = (projectPayload as ProjectResponse).project || {};
      const nextSnapshot = record(envelope.snapshot);
      const nextSessions = rows(nextSnapshot.engineeringAiSessions);
      const revisionRows = (revisionsPayload as { revisions?: ProjectRevision[] }).revisions || [];
      const candidate = revisionRows[0]?.revision || Number(envelope.revision) || 0;
      const base = revisionRows[1]?.revision || candidate - 1;

      setProjectId(nextProjectId);
      setSnapshot(nextSnapshot);
      setSession(nextSessions.at(-1) || null);
      setRevisions(revisionRows);
      setCandidateRevision(candidate || null);
      setBaseRevision(base > 0 ? base : null);
      if (base > 0 && candidate > 0) await loadDiff(nextProjectId, base, candidate);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Comparison workspace failed to load.');
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
      if (!response.ok || isProxyFailure(payload)) throw new Error(getProxyErrorMessage(payload, 'Projects are unavailable.'));
      const listed = (payload as ProjectsResponse).projects || [];
      setProjects(listed);
      const params = typeof window === 'undefined' ? null : new URLSearchParams(window.location.search);
      const requested = params?.get('project') || text(listed[0]?.project_id, '');
      if (requested) await loadProject(requested);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Projects are unavailable.');
    } finally {
      setBusy(false);
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
    if (baseRevision) url.searchParams.set('base', String(baseRevision));
    if (candidateRevision) url.searchParams.set('candidate', String(candidateRevision));
    window.history.replaceState(null, '', `${url.pathname}?${url.searchParams.toString()}`);
  }, [baseRevision, candidateRevision, projectId]);

  async function applyRevisionPair(nextBase: number | null, nextCandidate: number | null) {
    setBaseRevision(nextBase);
    setCandidateRevision(nextCandidate);
    if (projectId && nextBase && nextCandidate && nextBase !== nextCandidate) await loadDiff(projectId, nextBase, nextCandidate);
  }

  const grouped = {
    risk: deltaItems.filter((item) => item.kind === 'opened' || item.kind === 'persistent' || item.kind === 'authority'),
    resolved: deltaItems.filter((item) => item.kind === 'resolved'),
    changed: deltaItems.filter((item) => ['identity', 'artifact', 'execution'].includes(item.kind)),
  };

  return (
    <main className="min-h-screen bg-stone-100 text-stone-950">
      <div className="flex min-h-screen flex-col">
        <header className="border-b border-stone-200 bg-white">
          <div className="flex min-h-14 flex-wrap items-center gap-3 px-4 lg:px-5">
            <Link href={`/engineering/evidence?project=${encodeURIComponent(projectId)}`} className="inline-flex items-center gap-2 text-sm font-semibold tracking-tight text-stone-950">
              <ArrowLeft className="h-3.5 w-3.5" /> Hardware Splicer
            </Link>
            <ChevronRight className="h-3.5 w-3.5 text-stone-300" />
            <select value={projectId} onChange={(event) => void loadProject(event.target.value)} className="max-w-64 bg-transparent text-sm font-medium text-stone-900 outline-none" aria-label="Project">
              {projects.map((project) => <option key={text(project.project_id)} value={text(project.project_id)}>{projectLabel(project)}</option>)}
            </select>
            <span className="rounded-md bg-stone-100 px-2 py-1 text-[11px] font-medium text-stone-500">Compare</span>

            <div className="ml-auto flex flex-wrap items-center gap-2">
              <select
                value={baseRevision || ''}
                onChange={(event) => void applyRevisionPair(Number(event.target.value) || null, candidateRevision)}
                className="h-8 rounded-md border border-stone-300 bg-white px-2 text-xs text-stone-700 outline-none"
                aria-label="Base revision"
              >
                {revisions.map((revision) => <option key={`base-${revision.revision}`} value={revision.revision}>Rev {revision.revision}</option>)}
              </select>
              <span className="text-xs text-stone-400">→</span>
              <select
                value={candidateRevision || ''}
                onChange={(event) => void applyRevisionPair(baseRevision, Number(event.target.value) || null)}
                className="h-8 rounded-md border border-stone-300 bg-white px-2 text-xs font-semibold text-stone-900 outline-none"
                aria-label="Candidate revision"
              >
                {revisions.map((revision) => <option key={`candidate-${revision.revision}`} value={revision.revision}>Rev {revision.revision}</option>)}
              </select>
              <span className="rounded-md border border-stone-200 bg-stone-50 px-2.5 py-1.5 text-[11px] text-stone-600">No automatic merge</span>
              <Button size="sm" variant="outline" onClick={() => baseRevision && candidateRevision && void loadDiff(projectId, baseRevision, candidateRevision)} disabled={busy} className="h-8 border-stone-300 bg-white text-stone-700">
                {busy ? <LoaderCircle className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
              </Button>
            </div>
          </div>
        </header>

        {error ? <div className="border-b border-red-200 bg-red-50 px-4 py-2 text-xs text-red-800">{error}</div> : null}

        <div className="grid min-h-0 flex-1 grid-cols-1 gap-px bg-stone-200 xl:grid-cols-[260px_minmax(0,1fr)_340px]">
          <aside className="min-h-[720px] overflow-y-auto bg-white p-3">
            <div className="flex items-center gap-2 px-1 pb-3 text-[10px] font-semibold uppercase tracking-[0.12em] text-stone-400"><GitCompareArrows className="h-3.5 w-3.5" />Semantic delta</div>
            {([
              ['risk', 'Needs review'],
              ['resolved', 'Resolved'],
              ['changed', 'Changed'],
            ] as const).map(([groupId, label]) => (
              <section key={groupId} className="mb-5">
                <div className="mb-2 flex items-center justify-between px-1 text-[10px] font-semibold uppercase tracking-[0.1em] text-stone-400">
                  <span>{label}</span><span>{grouped[groupId].length}</span>
                </div>
                <div className="space-y-1">
                  {grouped[groupId].map((item) => {
                    const Icon = deltaIcon(item.kind);
                    const active = selected?.id === item.id;
                    return (
                      <button key={item.id} type="button" onClick={() => setSelectedDeltaId(item.id)} className={`w-full rounded-md border px-2.5 py-2.5 text-left ${active ? 'border-stone-300 bg-stone-100' : 'border-transparent hover:bg-stone-50'}`}>
                        <div className="flex gap-2">
                          <span className={`mt-1 flex h-4 w-4 shrink-0 items-center justify-center rounded-full text-white ${deltaTone(item.kind)}`}><Icon className="h-2.5 w-2.5" /></span>
                          <div className="min-w-0 flex-1">
                            <div className="line-clamp-2 text-xs font-medium leading-4 text-stone-800">{item.title}</div>
                            <div className="mt-1 text-[10px] text-stone-400">{deltaLabel(item.kind)}</div>
                          </div>
                        </div>
                      </button>
                    );
                  })}
                  {!grouped[groupId].length ? <div className="px-2 py-2 text-[11px] text-stone-400">None</div> : null}
                </div>
              </section>
            ))}
          </aside>

          <section className="min-w-0 bg-white">
            <div className="flex min-h-11 items-center justify-between border-b border-stone-200 px-4">
              <div>
                <span className="text-xs font-medium text-stone-500">Candidate artifact</span>
                <span className="ml-2 font-mono text-[10px] text-stone-400">Rev {candidateRevision ?? '—'}</span>
              </div>
              <div className="flex items-center gap-3 text-[10px] text-stone-500">
                <span className="inline-flex items-center gap-1"><Plus className="h-3 w-3 text-red-600" />{summary.opened} opened</span>
                <span className="inline-flex items-center gap-1"><Minus className="h-3 w-3 text-emerald-600" />{summary.resolved} resolved</span>
                <span>{summary.artifacts} artifact change</span>
              </div>
            </div>
            <EvidenceArtifactViewport buildDir={buildDir} overlayFinding={overlay} compact />
          </section>

          <aside className="flex min-h-[720px] flex-col bg-white">
            <div className="border-b border-stone-200 px-4 py-3">
              <div className="text-[10px] font-semibold uppercase tracking-[0.1em] text-stone-400">Selected delta</div>
              <div className="mt-1 text-xs text-stone-500">Rev {baseRevision ?? '—'} → Rev {candidateRevision ?? '—'}</div>
            </div>
            <div className="min-h-0 flex-1 overflow-y-auto p-4">
              {selected ? (
                <div>
                  <div className="flex items-start gap-3">
                    <span className={`mt-1 h-2.5 w-2.5 shrink-0 rounded-full ${deltaTone(selected.kind)}`} />
                    <div>
                      <div className="text-[10px] font-semibold uppercase tracking-[0.1em] text-stone-400">{deltaLabel(selected.kind)}</div>
                      <h2 className="mt-1 text-base font-semibold leading-6 text-stone-950">{selected.title}</h2>
                    </div>
                  </div>

                  <dl className="mt-5 divide-y divide-stone-100 border-y border-stone-100 text-xs">
                    <div className="flex justify-between gap-4 py-3"><dt className="text-stone-500">Delta ID</dt><dd className="max-w-[12rem] break-all text-right font-mono text-[10px] text-stone-700">{selected.detail}</dd></div>
                    <div className="flex justify-between gap-4 py-3"><dt className="text-stone-500">Targets</dt><dd className="text-right font-medium text-stone-800">{selected.targetIds.length || '—'}</dd></div>
                    <div className="flex justify-between gap-4 py-3"><dt className="text-stone-500">Evidence refs</dt><dd className="text-right font-medium text-stone-800">{selected.evidenceIds.length || '—'}</dd></div>
                  </dl>

                  {selected.targetIds.length ? (
                    <section className="mt-5">
                      <div className="text-[10px] font-semibold uppercase tracking-[0.1em] text-stone-400">Affected objects</div>
                      <div className="mt-2 flex flex-wrap gap-1.5">{selected.targetIds.map((id) => <span key={id} className="rounded-md bg-stone-100 px-2 py-1 font-mono text-[10px] text-stone-600">{id}</span>)}</div>
                    </section>
                  ) : null}

                  {selected.evidenceIds.length ? (
                    <section className="mt-5">
                      <div className="text-[10px] font-semibold uppercase tracking-[0.1em] text-stone-400">Evidence</div>
                      <div className="mt-2 space-y-1.5">{selected.evidenceIds.map((id) => <div key={id} className="flex items-center gap-2 rounded-md border border-stone-200 px-2.5 py-2"><FileText className="h-3.5 w-3.5 text-stone-400" /><span className="break-all font-mono text-[10px] text-stone-600">{id}</span></div>)}</div>
                    </section>
                  ) : null}

                  <section className="mt-5 rounded-md border border-stone-200 bg-stone-50 p-3">
                    <div className="flex items-center gap-2 text-xs font-medium text-stone-800"><FileDiff className="h-3.5 w-3.5" />Review consequence</div>
                    <div className="mt-2 text-xs leading-5 text-stone-600">
                      {selected.kind === 'resolved'
                        ? 'This blocker is resolved in the candidate revision. Downstream evidence still remains scoped to its own validity boundary.'
                        : selected.kind === 'opened' || selected.kind === 'persistent'
                          ? 'The candidate remains blocked on this issue. Review and fresh verification are required before downstream authority can change.'
                          : selected.kind === 'authority'
                            ? 'Authority regressed across the revision boundary. No downstream physical action should inherit prior permission.'
                            : 'This change belongs to the candidate revision and requires the relevant deterministic or evidence checks to be refreshed.'}
                    </div>
                  </section>
                </div>
              ) : <div className="text-xs text-stone-500">No semantic delta is available.</div>}
            </div>
            <div className="border-t border-stone-200 p-4">
              <div className="grid grid-cols-3 gap-1.5 text-center text-[10px] font-medium">
                <div className="rounded-md bg-stone-100 px-2 py-2 text-stone-600">OPENED<br /><span className="text-red-700">{summary.opened}</span></div>
                <div className="rounded-md bg-stone-100 px-2 py-2 text-stone-600">RESOLVED<br /><span className="text-emerald-700">{summary.resolved}</span></div>
                <div className="rounded-md bg-stone-100 px-2 py-2 text-stone-600">AUTH REGRESS<br /><span className={summary.authorityRegressions ? 'text-red-700' : 'text-stone-500'}>{summary.authorityRegressions}</span></div>
              </div>
              <div className="mt-3 rounded-md border border-stone-200 px-3 py-2 text-[11px] leading-4 text-stone-500">
                A semantic diff is review evidence, not merge authority. Candidate state remains separate from project truth until the existing decision boundary is used.
              </div>
            </div>
          </aside>
        </div>

        <footer className="border-t border-stone-200 bg-white px-4 py-2.5">
          <div className="flex items-center justify-between gap-4 text-[10px] text-stone-500">
            <div className="flex items-center gap-4">
              <span className="font-medium text-stone-700">{projectName}</span>
              <span>{summary.identities} identity category changed</span>
              <span>{summary.execution} verification change</span>
              <span>{summary.persistent} persistent blocker</span>
            </div>
            <Link href={`/engineering/evidence?project=${encodeURIComponent(projectId)}`} className="inline-flex items-center gap-1.5 rounded-md border border-stone-300 px-3 py-1.5 text-xs font-medium text-stone-700 hover:bg-stone-50">Back to project review <ArrowLeft className="h-3.5 w-3.5" /></Link>
          </div>
        </footer>
      </div>
    </main>
  );
}

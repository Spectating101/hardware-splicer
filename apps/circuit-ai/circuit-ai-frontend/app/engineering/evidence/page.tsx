'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import {
  AlertTriangle,
  ArrowRight,
  Check,
  ChevronRight,
  Circle,
  CircuitBoard,
  FileCheck2,
  GitBranch,
  LoaderCircle,
  RefreshCw,
  Search,
  ShieldCheck,
  XCircle,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { usePageTitle } from '@/components/use-page-title';
import { deriveCanonicalSystemGraph } from '@/components/engineering/canonical-system-canvas';
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

type StateTone = 'complete' | 'blocked' | 'pending' | 'neutral';

type LadderRow = {
  label: string;
  detail: string;
  tone: StateTone;
};

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

function StatusMark({ tone }: { tone: StateTone }) {
  if (tone === 'complete') {
    return <span className="flex h-6 w-6 items-center justify-center rounded-full bg-emerald-50 text-emerald-700"><Check className="h-3.5 w-3.5" /></span>;
  }
  if (tone === 'blocked') {
    return <span className="flex h-6 w-6 items-center justify-center rounded-full bg-red-50 text-red-700"><XCircle className="h-3.5 w-3.5" /></span>;
  }
  if (tone === 'pending') {
    return <span className="flex h-6 w-6 items-center justify-center rounded-full bg-amber-50 text-amber-700"><AlertTriangle className="h-3.5 w-3.5" /></span>;
  }
  return <span className="flex h-6 w-6 items-center justify-center rounded-full bg-stone-100 text-stone-500"><Circle className="h-3.5 w-3.5" /></span>;
}

function StatusText({ tone }: { tone: StateTone }) {
  const labels: Record<StateTone, string> = {
    complete: 'Established',
    blocked: 'Blocked',
    pending: 'Needs review',
    neutral: 'Not established',
  };
  const classes: Record<StateTone, string> = {
    complete: 'text-emerald-700',
    blocked: 'text-red-700',
    pending: 'text-amber-700',
    neutral: 'text-stone-500',
  };
  return <span className={`text-xs font-medium ${classes[tone]}`}>{labels[tone]}</span>;
}

export default function EvidenceOverviewPage() {
  usePageTitle('Project Evidence | Hardware Splicer');

  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [projectId, setProjectId] = useState('');
  const [revision, setRevision] = useState<number | null>(null);
  const [snapshot, setSnapshot] = useState<JsonRecord | null>(null);
  const [session, setSession] = useState<JsonRecord | null>(null);
  const [busy, setBusy] = useState<'projects' | 'project' | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState('');

  const sources = rows(snapshot?.engineeringSources);
  const sessions = rows(snapshot?.engineeringAiSessions);
  const actions = rows(session?.actions);
  const graph = useMemo(() => deriveCanonicalSystemGraph(snapshot, session), [snapshot, session]);
  const failedActions = actions.filter((action) => actionStatus(action) === 'failed');
  const completedActions = actions.filter((action) => ['completed', 'passed', 'succeeded'].includes(actionStatus(action)));
  const blockedObjects = graph.objects.filter((object) => object.blockers.length > 0 || object.status === 'blocked');
  const supportedObjects = graph.objects.filter((object) => object.status === 'supported');

  const fabricationAuthorized = snapshot?.fabrication_authorized === true;
  const powerOnAuthorized = snapshot?.power_on_authorized === true;
  const releaseAuthorized = snapshot?.release_authorized === true;

  const projectName = useMemo(() => {
    const match = projects.find((project) => text(project.project_id) === projectId);
    return match ? projectLabel(match) : text(snapshot?.name || snapshot?.project_name, projectId || 'Hardware project');
  }, [projectId, projects, snapshot]);

  const ladder: LadderRow[] = [
    {
      label: 'Engineering sources registered',
      detail: sources.length ? `${sources.length} source descriptor${sources.length === 1 ? '' : 's'} attached to this project.` : 'No engineering source descriptor is registered.',
      tone: sources.length ? 'complete' : 'neutral',
    },
    {
      label: 'Project objects mapped',
      detail: graph.objects.length ? `${graph.objects.length} canonical object${graph.objects.length === 1 ? '' : 's'} represented; ${supportedObjects.length} currently supported.` : 'No project object is available in the current graph.',
      tone: graph.objects.length ? 'complete' : 'neutral',
    },
    {
      label: 'Deterministic software checks',
      detail: failedActions.length
        ? `${failedActions.length} failed check${failedActions.length === 1 ? '' : 's'} remain in the active session.`
        : completedActions.length
          ? `${completedActions.length} completed check${completedActions.length === 1 ? '' : 's'} with no persisted failure in the active session.`
          : 'No completed deterministic check is visible in the active session.',
      tone: failedActions.length ? 'blocked' : completedActions.length ? 'complete' : 'neutral',
    },
    {
      label: 'Fabrication authority',
      detail: fabricationAuthorized ? 'Explicitly authorized for the current stored state.' : 'No fabrication authorization is asserted by the current project state.',
      tone: fabricationAuthorized ? 'complete' : blockedObjects.length || failedActions.length ? 'blocked' : 'neutral',
    },
    {
      label: 'Power-on authority',
      detail: powerOnAuthorized ? 'Explicitly authorized for the current stored state.' : 'No power-on authorization is asserted by the current project state.',
      tone: powerOnAuthorized ? 'complete' : 'neutral',
    },
    {
      label: 'Release authority',
      detail: releaseAuthorized ? 'Explicitly authorized for the current stored state.' : 'No release authorization is asserted by the current project state.',
      tone: releaseAuthorized ? 'complete' : 'neutral',
    },
  ];

  const reviewFocus = failedActions.length
    ? `Review ${failedActions.length} failed deterministic check${failedActions.length === 1 ? '' : 's'} before relying on downstream state.`
    : blockedObjects.length
      ? `Resolve the first recorded blocker: ${blockedObjects[0]?.blockers[0] || blockedObjects[0]?.label}.`
      : !fabricationAuthorized
        ? 'Review the evidence package and decide whether fabrication authority is justified.'
        : !powerOnAuthorized
          ? 'Complete the required physical evidence before considering power-on authorization.'
          : 'Inspect the next unresolved physical or release condition in the project record.';

  const visibleObjects = useMemo(() => {
    const query = filter.trim().toLowerCase();
    if (!query) return graph.objects.slice(0, 12);
    return graph.objects.filter((object) => [
      object.label,
      object.id,
      object.kind,
      object.domain,
      object.description,
      ...object.blockers,
      ...object.evidenceIds,
    ].some((value) => value.toLowerCase().includes(query))).slice(0, 20);
  }, [filter, graph.objects]);

  async function loadProject(selectedProjectId: string) {
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
      setProjectId(selectedProjectId);
      setRevision(Number(envelope.revision));
      setSnapshot(nextSnapshot);
      setSession(nextSessions.at(-1) || null);
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
      if (requested) await loadProject(requested);
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
    window.history.replaceState(null, '', `${url.pathname}?${url.searchParams.toString()}`);
  }, [projectId]);

  return (
    <main className="min-h-screen bg-stone-50 text-stone-950">
      <div className="mx-auto max-w-[1680px] px-4 py-5 sm:px-6 lg:px-8">
        <header className="border-b border-stone-200 pb-5">
          <div className="flex flex-col gap-5 xl:flex-row xl:items-end xl:justify-between">
            <div>
              <div className="flex items-center gap-2 text-xs text-stone-500">
                <Link href="/engineering/studio" className="hover:text-stone-900">Hardware Splicer</Link>
                <ChevronRight className="h-3.5 w-3.5" />
                <span>Project evidence</span>
              </div>
              <div className="mt-3 flex flex-wrap items-baseline gap-x-4 gap-y-2">
                <h1 className="text-3xl font-semibold tracking-tight text-stone-950">{projectName}</h1>
                <span className="font-mono text-xs text-stone-500">revision {revision ?? '—'}</span>
              </div>
              <p className="mt-2 max-w-3xl text-sm leading-6 text-stone-600">
                What is established, what is unresolved, and what the current evidence permits you to do next.
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <select
                value={projectId}
                onChange={(event) => void loadProject(event.target.value)}
                className="min-w-56 rounded-md border border-stone-300 bg-white px-3 py-2 text-sm text-stone-900 outline-none focus:border-stone-500"
              >
                {projects.map((project) => (
                  <option key={text(project.project_id)} value={text(project.project_id)}>{projectLabel(project)}</option>
                ))}
              </select>
              <Button size="sm" variant="outline" onClick={loadProjects} disabled={busy !== null} className="border-stone-300 bg-white text-stone-700 hover:bg-stone-100">
                {busy ? <LoaderCircle className="mr-2 h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="mr-2 h-3.5 w-3.5" />}
                Refresh
              </Button>
              <Link
                href={`/engineering/visual?project=${encodeURIComponent(projectId)}`}
                className="inline-flex items-center gap-2 rounded-md bg-stone-900 px-3 py-2 text-sm font-medium text-white hover:bg-stone-800"
              >
                Open workbench <ArrowRight className="h-3.5 w-3.5" />
              </Link>
            </div>
          </div>
        </header>

        {error ? (
          <div className="mt-5 flex items-start gap-3 rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-800">
            <XCircle className="mt-0.5 h-4 w-4 shrink-0" />{error}
          </div>
        ) : null}

        <section className="mt-6 grid gap-5 xl:grid-cols-[minmax(0,1fr)_360px]">
          <div className="space-y-5">
            <section className="rounded-lg border border-stone-200 bg-white">
              <div className="border-b border-stone-200 px-5 py-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <h2 className="text-base font-semibold text-stone-950">Current evidence state</h2>
                    <p className="mt-1 text-sm text-stone-500">Evidence stops where the record stops. Software success does not imply physical correctness.</p>
                  </div>
                  <div className="flex items-center gap-2 text-xs text-stone-500">
                    <ShieldCheck className="h-4 w-4" />
                    No viewer action changes authority
                  </div>
                </div>
              </div>

              <div className="divide-y divide-stone-100">
                {ladder.map((row) => (
                  <div key={row.label} className="grid gap-3 px-5 py-4 md:grid-cols-[28px_220px_minmax(0,1fr)_110px] md:items-center">
                    <StatusMark tone={row.tone} />
                    <div className="text-sm font-medium text-stone-900">{row.label}</div>
                    <div className="text-sm leading-5 text-stone-600">{row.detail}</div>
                    <div className="md:text-right"><StatusText tone={row.tone} /></div>
                  </div>
                ))}
              </div>
            </section>

            <section className="grid gap-5 lg:grid-cols-2">
              <div className="rounded-lg border border-stone-200 bg-white p-5">
                <div className="flex items-center justify-between gap-3">
                  <h2 className="text-base font-semibold text-stone-950">Needs attention</h2>
                  <span className="text-xs text-stone-500">{blockedObjects.length + failedActions.length} recorded</span>
                </div>
                <div className="mt-4 space-y-3">
                  {failedActions.slice(0, 3).map((action, index) => (
                    <div key={text(action.action_id, `failed-${index}`)} className="rounded-md border border-red-200 bg-red-50 p-3">
                      <div className="flex items-start gap-2">
                        <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-red-700" />
                        <div>
                          <div className="text-sm font-medium text-red-900">{text(action.title || action.action_type, 'Deterministic check failed')}</div>
                          <div className="mt-1 font-mono text-[11px] text-red-700/70">{text(action.action_id, 'action id unavailable')}</div>
                        </div>
                      </div>
                    </div>
                  ))}
                  {blockedObjects.slice(0, 4).map((object) => (
                    <div key={object.id} className="rounded-md border border-amber-200 bg-amber-50 p-3">
                      <div className="flex items-start gap-2">
                        <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-700" />
                        <div>
                          <div className="text-sm font-medium text-amber-950">{object.label}</div>
                          <div className="mt-1 text-xs leading-5 text-amber-900/75">{object.blockers[0] || 'This object is recorded as blocked.'}</div>
                        </div>
                      </div>
                    </div>
                  ))}
                  {!failedActions.length && !blockedObjects.length ? (
                    <div className="flex items-start gap-2 rounded-md border border-stone-200 bg-stone-50 p-3 text-sm text-stone-600">
                      <Check className="mt-0.5 h-4 w-4 shrink-0 text-emerald-700" />
                      No failed action or object blocker is visible in the current project state.
                    </div>
                  ) : null}
                </div>
              </div>

              <div className="rounded-lg border border-stone-200 bg-white p-5">
                <h2 className="text-base font-semibold text-stone-950">Suggested review focus</h2>
                <p className="mt-3 text-lg leading-7 text-stone-800">{reviewFocus}</p>
                <p className="mt-3 text-xs leading-5 text-stone-500">
                  This is a presentation-layer suggestion derived from existing state. It does not grant authority or replace the project review boundary.
                </p>
                <div className="mt-5 flex flex-wrap gap-2">
                  <Link href={`/engineering/visual?project=${encodeURIComponent(projectId)}&mode=verify`} className="inline-flex items-center gap-2 rounded-md border border-stone-300 bg-white px-3 py-2 text-sm font-medium text-stone-700 hover:bg-stone-50">
                    Review verification <FileCheck2 className="h-3.5 w-3.5" />
                  </Link>
                  <Link href={`/engineering/visual?project=${encodeURIComponent(projectId)}&mode=decide`} className="inline-flex items-center gap-2 rounded-md border border-stone-300 bg-white px-3 py-2 text-sm font-medium text-stone-700 hover:bg-stone-50">
                    Compare proposal <GitBranch className="h-3.5 w-3.5" />
                  </Link>
                </div>
              </div>
            </section>

            <section className="rounded-lg border border-stone-200 bg-white">
              <div className="flex flex-col gap-3 border-b border-stone-200 px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <h2 className="text-base font-semibold text-stone-950">Project objects</h2>
                  <p className="mt-1 text-sm text-stone-500">Engineering objects with their evidence and blocker state.</p>
                </div>
                <label className="flex min-w-64 items-center gap-2 rounded-md border border-stone-300 bg-white px-3 py-2">
                  <Search className="h-3.5 w-3.5 text-stone-400" />
                  <input
                    value={filter}
                    onChange={(event) => setFilter(event.target.value)}
                    placeholder="Search objects or evidence"
                    className="min-w-0 flex-1 bg-transparent text-sm text-stone-900 outline-none placeholder:text-stone-400"
                  />
                </label>
              </div>

              <div className="divide-y divide-stone-100">
                {visibleObjects.map((object) => (
                  <Link
                    key={object.id}
                    href={`/engineering/visual?project=${encodeURIComponent(projectId)}&mode=explore&object=${encodeURIComponent(object.id)}`}
                    className="grid gap-3 px-5 py-4 hover:bg-stone-50 md:grid-cols-[minmax(0,1fr)_150px_120px_24px] md:items-center"
                  >
                    <div>
                      <div className="text-sm font-medium text-stone-900">{object.label}</div>
                      <div className="mt-1 line-clamp-1 text-xs text-stone-500">{object.description || object.id}</div>
                    </div>
                    <div className="text-xs text-stone-500">{object.domain} · {object.kind}</div>
                    <div className="text-xs">
                      {object.blockers.length ? <span className="text-red-700">{object.blockers.length} blocker{object.blockers.length === 1 ? '' : 's'}</span> : object.evidenceIds.length ? <span className="text-emerald-700">{object.evidenceIds.length} evidence</span> : <span className="text-stone-400">No evidence</span>}
                    </div>
                    <ChevronRight className="h-4 w-4 text-stone-300" />
                  </Link>
                ))}
                {!visibleObjects.length ? <div className="px-5 py-8 text-center text-sm text-stone-500">No project object matches this search.</div> : null}
              </div>
            </section>
          </div>

          <aside className="space-y-5">
            <section className="rounded-lg border border-stone-200 bg-white p-5">
              <div className="flex items-center gap-2">
                <CircuitBoard className="h-4 w-4 text-stone-500" />
                <h2 className="text-sm font-semibold text-stone-950">Project summary</h2>
              </div>
              <dl className="mt-4 divide-y divide-stone-100 text-sm">
                <div className="flex justify-between gap-4 py-2.5"><dt className="text-stone-500">Objects</dt><dd className="font-medium text-stone-900">{graph.objects.length}</dd></div>
                <div className="flex justify-between gap-4 py-2.5"><dt className="text-stone-500">Sources</dt><dd className="font-medium text-stone-900">{sources.length}</dd></div>
                <div className="flex justify-between gap-4 py-2.5"><dt className="text-stone-500">AI sessions</dt><dd className="font-medium text-stone-900">{sessions.length}</dd></div>
                <div className="flex justify-between gap-4 py-2.5"><dt className="text-stone-500">Completed checks</dt><dd className="font-medium text-stone-900">{completedActions.length}</dd></div>
                <div className="flex justify-between gap-4 py-2.5"><dt className="text-stone-500">Failed checks</dt><dd className={failedActions.length ? 'font-medium text-red-700' : 'font-medium text-stone-900'}>{failedActions.length}</dd></div>
              </dl>
            </section>

            <section className="rounded-lg border border-stone-200 bg-white p-5">
              <h2 className="text-sm font-semibold text-stone-950">Physical authority</h2>
              <div className="mt-4 space-y-3">
                {[
                  ['Fabrication', fabricationAuthorized],
                  ['Power-on', powerOnAuthorized],
                  ['Release', releaseAuthorized],
                ].map(([label, authorized]) => (
                  <div key={String(label)} className="flex items-center justify-between gap-4">
                    <span className="text-sm text-stone-600">{String(label)}</span>
                    <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${authorized ? 'bg-emerald-50 text-emerald-700' : 'bg-stone-100 text-stone-600'}`}>
                      {authorized ? 'Authorized' : 'Closed'}
                    </span>
                  </div>
                ))}
              </div>
              <p className="mt-4 border-t border-stone-100 pt-4 text-xs leading-5 text-stone-500">
                Closed means the stored project state does not assert authorization. It is not inferred from model confidence or viewer state.
              </p>
            </section>

            <section className="rounded-lg border border-stone-300 bg-stone-900 p-5 text-white">
              <div className="text-xs font-medium text-stone-300">Evidence boundary</div>
              <p className="mt-2 text-sm leading-6 text-stone-100">
                Passing software checks can establish properties of the digital artifact. They do not establish that a manufactured board is physically correct.
              </p>
              <Link href={`/engineering/visual?project=${encodeURIComponent(projectId)}&mode=bringup`} className="mt-4 inline-flex items-center gap-2 text-sm font-medium text-white underline decoration-stone-500 underline-offset-4 hover:decoration-white">
                Inspect physical validation <ArrowRight className="h-3.5 w-3.5" />
              </Link>
            </section>
          </aside>
        </section>
      </div>
    </main>
  );
}

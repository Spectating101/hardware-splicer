'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  Binary,
  Boxes,
  CheckCircle2,
  ChevronRight,
  CircleOff,
  ClipboardCheck,
  Code2,
  Diff,
  FileJson2,
  GitCompareArrows,
  LoaderCircle,
  PlayCircle,
  RefreshCw,
  Route,
  Save,
  ShieldCheck,
  TriangleAlert,
  Wrench,
  XCircle,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { StudioCommandBar } from '@/components/studio-command-bar';
import { StudioShell } from '@/components/studio-shell';
import { usePageTitle } from '@/components/use-page-title';
import {
  blockerTone,
  extractEngineeringPlan,
  formatSavedAt,
  safeParseEngineeringPlan,
  sortNextActions,
  statusTone,
  summarizeRevisionDiff,
  type EngineeringPlan,
  type EngineeringStatus,
  type EngineeringStatusResponse,
  type NextAction,
  type ProjectEnvelope,
  type ProjectRevision,
  type ProjectSummary,
  type RevisionDiffResponse,
  type StatusBlocker,
} from '@/lib/engineering-status';
import {
  getProxyErrorMessage,
  isProxyFailure,
  readJsonPayload,
  type ProxyErrorPayload,
} from '@/lib/proxy-client';

const navItems = [
  { href: '/', label: 'Overview' },
  { href: '/analyze', label: 'Analyze' },
  { href: '/components', label: 'Components' },
  { href: '/projects', label: 'Projects' },
  { href: '/engineering', label: 'Engineering' },
  { href: '/cad', label: 'CAD' },
];

const localStarterPlan: EngineeringPlan = {
  machine_project: {
    project_id: 'local-engineering-draft',
    name: 'Local engineering draft',
    purpose: 'Paste or load a guided Hardware Splicer plan.',
    requirements: [],
    components: [],
    interfaces: [],
    artifacts: [],
    evidence: [],
    verifications: [],
    discipline_payloads: {},
  },
  engineering_source_graph: { unresolved_source_ids: [], conflicts: [] },
  robot_topology: { topology_id: 'unresolved-topology', unresolved: [] },
  engineering_analysis: { findings: [] },
  manufacturing_closure: { checks: [] },
  engineering_execution_plan: { checks: [], unresolved: [] },
  change_impact: { impacts: [], unresolved: [] },
  missing_info: ['Load a persisted project or replace this local starter with a guided engineering plan.'],
  engineering_readiness: {
    status: 'blocked',
    fabrication_authorized: false,
    flash_authorized: false,
    power_on_authorized: false,
    motion_authorized: false,
    release_authorized: false,
  },
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
}

function asRecord(value: unknown): Record<string, unknown> {
  return isRecord(value) ? value : {};
}

function asRows<T>(value: unknown): T[] {
  return Array.isArray(value) ? value as T[] : [];
}

function metric(value: unknown, fallback = '0') {
  if (typeof value === 'number' || typeof value === 'string') return String(value);
  return fallback;
}

function categoryLabel(value: string) {
  return value.replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function phaseIcon(category: string) {
  if (category === 'source') return FileJson2;
  if (category === 'topology') return Route;
  if (category === 'analysis') return Activity;
  if (category === 'manufacturing') return Boxes;
  if (category === 'execution') return Code2;
  if (category === 'verification') return ClipboardCheck;
  if (category === 'release') return ShieldCheck;
  return Wrench;
}

function panelHeading(eyebrow: string, title: string) {
  return (
    <div className="mb-4">
      <div className="text-[11px] font-semibold uppercase tracking-[0.24em] text-slate-500">{eyebrow}</div>
      <div className="mt-2 text-sm font-semibold text-white">{title}</div>
    </div>
  );
}

function AuthorityGate({ label, allowed }: { label: string; allowed: boolean }) {
  return (
    <div className={`flex items-center justify-between rounded-[0.9rem] border px-3 py-2.5 ${allowed ? 'border-emerald-300/20 bg-emerald-300/8' : 'border-white/8 bg-[#081423]'}`}>
      <span className="text-xs font-medium text-slate-300">{label}</span>
      <span className={`inline-flex items-center gap-1 text-[10px] font-semibold uppercase tracking-[0.16em] ${allowed ? 'text-emerald-200' : 'text-slate-500'}`}>
        {allowed ? <CheckCircle2 className="h-3.5 w-3.5" /> : <CircleOff className="h-3.5 w-3.5" />}
        {allowed ? 'Allowed' : 'Not authorized'}
      </span>
    </div>
  );
}

function BlockerCard({ blocker }: { blocker: StatusBlocker }) {
  const Icon = blocker.severity === 'error' ? XCircle : blocker.severity === 'warning' ? AlertTriangle : Activity;
  return (
    <div className={`rounded-[1.2rem] border p-4 ${blockerTone(blocker.severity)}`}>
      <div className="flex items-start gap-3">
        <div className="mt-0.5 rounded-xl border border-white/8 bg-black/15 p-2">
          <Icon className="h-4 w-4 text-white/80" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-[10px] font-semibold uppercase tracking-[0.2em] text-white/55">{categoryLabel(blocker.category)}</span>
            <span className="rounded-full border border-white/8 bg-black/15 px-2 py-0.5 text-[10px] text-slate-400">{blocker.blocker_id}</span>
          </div>
          <div className="mt-2 text-sm font-semibold leading-6 text-white">{blocker.message}</div>
          {blocker.target_ids?.length ? (
            <div className="mt-3 flex flex-wrap gap-1.5">
              {blocker.target_ids.slice(0, 5).map((target) => (
                <span key={target} className="rounded-full border border-white/8 bg-[#081423]/70 px-2 py-1 text-[10px] text-slate-300">{target}</span>
              ))}
            </div>
          ) : null}
          {blocker.required_inputs?.length ? (
            <div className="mt-3 text-xs leading-5 text-slate-300">
              <span className="font-semibold text-white/80">Needs:</span> {blocker.required_inputs.join(' • ')}
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}

function ActionCard({ action, active = false }: { action: NextAction; active?: boolean }) {
  const Icon = phaseIcon(action.category);
  return (
    <div className={`rounded-[1.15rem] border p-4 ${active ? 'border-cyan-300/25 bg-cyan-300/10' : 'border-white/8 bg-[#081423]'}`}>
      <div className="flex items-start gap-3">
        <div className={`rounded-xl border p-2 ${active ? 'border-cyan-300/20 bg-cyan-300/12 text-cyan-200' : 'border-white/8 bg-white/[0.03] text-slate-300'}`}>
          <Icon className="h-4 w-4" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center justify-between gap-2">
            <div className="text-[10px] font-semibold uppercase tracking-[0.2em] text-slate-500">Priority {action.priority} • {categoryLabel(action.category)}</div>
            <span className="rounded-full border border-white/8 px-2 py-0.5 text-[10px] text-slate-400">{action.method || 'POST'}</span>
          </div>
          <div className="mt-2 text-sm font-semibold text-white">{action.title}</div>
          <div className="mt-2 text-xs leading-5 text-slate-400">{action.instruction}</div>
          <div className="mt-3 truncate rounded-lg border border-white/8 bg-black/15 px-2.5 py-2 font-mono text-[10px] text-cyan-200">{action.route}</div>
        </div>
      </div>
    </div>
  );
}

export default function EngineeringPage() {
  usePageTitle('Engineering Closure | Circuit.AI');

  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [projectsLoading, setProjectsLoading] = useState(true);
  const [selectedProjectId, setSelectedProjectId] = useState<string>('');
  const [projectSource, setProjectSource] = useState<'persisted' | 'local'>('local');
  const [plan, setPlan] = useState<EngineeringPlan>(localStarterPlan);
  const [planText, setPlanText] = useState(JSON.stringify(localStarterPlan, null, 2));
  const [planLoading, setPlanLoading] = useState(false);
  const [statusResponse, setStatusResponse] = useState<EngineeringStatusResponse | null>(null);
  const [statusLoading, setStatusLoading] = useState(false);
  const [statusError, setStatusError] = useState<string | null>(null);
  const [editorError, setEditorError] = useState<string | null>(null);
  const [revisions, setRevisions] = useState<ProjectRevision[]>([]);
  const [baseRevision, setBaseRevision] = useState<number | null>(null);
  const [candidateRevision, setCandidateRevision] = useState<number | null>(null);
  const [diffResponse, setDiffResponse] = useState<RevisionDiffResponse | null>(null);
  const [diffLoading, setDiffLoading] = useState(false);
  const [diffError, setDiffError] = useState<string | null>(null);

  const engineeringStatus = statusResponse?.engineering_status || null;
  const readiness = asRecord(statusResponse?.engineering_readiness);
  const blockers = engineeringStatus?.blockers || [];
  const advisories = engineeringStatus?.advisories || [];
  const actions = useMemo(() => sortNextActions(engineeringStatus?.next_actions), [engineeringStatus]);
  const nextAction = actions[0] || statusResponse?.next_action || null;
  const tone = statusTone(engineeringStatus?.overall_status || statusResponse?.overall_status);
  const manufacturing = asRecord(plan.manufacturing_closure);
  const manufacturingChecks = asRows<Record<string, unknown>>(manufacturing.checks);
  const manufacturingBlocking = manufacturingChecks.filter((row) => row.status !== 'pass' && row.severity === 'error').length;
  const executionPlan = asRecord(plan.engineering_execution_plan);
  const executionChecks = asRows<Record<string, unknown>>(executionPlan.checks);
  const executionUnresolved = asRows<Record<string, unknown>>(executionPlan.unresolved);
  const diffSummary = useMemo(() => summarizeRevisionDiff(diffResponse), [diffResponse]);

  const runStatus = useCallback(async (candidatePlan: EngineeringPlan) => {
    setStatusLoading(true);
    setStatusError(null);
    try {
      const response = await fetch('/api/proxy/engineering/status', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ plan: candidatePlan }),
        cache: 'no-store',
      });
      const payload = await readJsonPayload<EngineeringStatusResponse | ProxyErrorPayload>(response);
      if (!response.ok || isProxyFailure(payload)) {
        throw new Error(getProxyErrorMessage(payload, 'Hardware Splicer could not compile engineering status.'));
      }
      setStatusResponse(payload as EngineeringStatusResponse);
    } catch (error: unknown) {
      setStatusResponse(null);
      setStatusError(error instanceof Error ? error.message : 'Hardware Splicer status is unavailable.');
    } finally {
      setStatusLoading(false);
    }
  }, []);

  useEffect(() => {
    let active = true;
    async function loadProjects() {
      setProjectsLoading(true);
      try {
        const response = await fetch('/api/proxy/engineering/projects', { cache: 'no-store' });
        const payload = await readJsonPayload<{ ok?: boolean; projects?: ProjectSummary[] } | ProxyErrorPayload>(response);
        if (!active) return;
        if (!response.ok || isProxyFailure(payload)) {
          setProjects([]);
          return;
        }
        const rows = (payload as { projects?: ProjectSummary[] } | null)?.projects || [];
        setProjects(rows);
        if (rows[0]?.project_id) setSelectedProjectId(rows[0].project_id);
      } catch {
        if (active) setProjects([]);
      } finally {
        if (active) setProjectsLoading(false);
      }
    }
    loadProjects();
    return () => { active = false; };
  }, []);

  useEffect(() => {
    if (!selectedProjectId) return;
    let active = true;
    async function loadProject() {
      setPlanLoading(true);
      setStatusError(null);
      setDiffError(null);
      setDiffResponse(null);
      try {
        const [projectResponse, revisionsResponse] = await Promise.all([
          fetch(`/api/proxy/engineering/projects/${encodeURIComponent(selectedProjectId)}`, { cache: 'no-store' }),
          fetch(`/api/proxy/engineering/projects/${encodeURIComponent(selectedProjectId)}/revisions`, { cache: 'no-store' }),
        ]);
        const projectPayload = await readJsonPayload<{ ok?: boolean; project?: ProjectEnvelope } | ProxyErrorPayload>(projectResponse);
        const revisionsPayload = await readJsonPayload<{ ok?: boolean; revisions?: ProjectRevision[] } | ProxyErrorPayload>(revisionsResponse);
        if (!active) return;
        if (!projectResponse.ok || isProxyFailure(projectPayload)) {
          throw new Error(getProxyErrorMessage(projectPayload, `Could not load ${selectedProjectId}.`));
        }
        const loadedPlan = extractEngineeringPlan((projectPayload as { project?: ProjectEnvelope } | null)?.project);
        if (!loadedPlan) throw new Error('The selected project revision does not contain a guided engineering plan.');
        const revisionRows = !revisionsResponse.ok || isProxyFailure(revisionsPayload)
          ? []
          : ((revisionsPayload as { revisions?: ProjectRevision[] } | null)?.revisions || []);
        setPlan(loadedPlan);
        setPlanText(JSON.stringify(loadedPlan, null, 2));
        setProjectSource('persisted');
        setEditorError(null);
        setRevisions(revisionRows);
        setCandidateRevision(revisionRows[0]?.revision || null);
        setBaseRevision(revisionRows[1]?.revision || null);
        await runStatus(loadedPlan);
      } catch (error: unknown) {
        if (!active) return;
        setStatusError(error instanceof Error ? error.message : 'Project load failed.');
      } finally {
        if (active) setPlanLoading(false);
      }
    }
    loadProject();
    return () => { active = false; };
  }, [runStatus, selectedProjectId]);

  function applyEditor() {
    const parsed = safeParseEngineeringPlan(planText);
    if (!parsed.plan) {
      setEditorError(parsed.error);
      return;
    }
    setEditorError(null);
    setPlan(parsed.plan);
    setProjectSource('local');
    void runStatus(parsed.plan);
  }

  async function compareRevisions() {
    if (!selectedProjectId || !baseRevision || !candidateRevision) return;
    setDiffLoading(true);
    setDiffError(null);
    try {
      const response = await fetch('/api/proxy/engineering/revisions/diff', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({
          project_id: selectedProjectId,
          base_revision: baseRevision,
          candidate_revision: candidateRevision,
        }),
        cache: 'no-store',
      });
      const payload = await readJsonPayload<RevisionDiffResponse | ProxyErrorPayload>(response);
      if (!response.ok || isProxyFailure(payload)) {
        throw new Error(getProxyErrorMessage(payload, 'Revision comparison is unavailable.'));
      }
      setDiffResponse(payload as RevisionDiffResponse);
    } catch (error: unknown) {
      setDiffResponse(null);
      setDiffError(error instanceof Error ? error.message : 'Revision comparison failed.');
    } finally {
      setDiffLoading(false);
    }
  }

  const statusLabel = statusLoading
    ? 'Compiling status'
    : engineeringStatus
      ? `${engineeringStatus.overall_status} • ${engineeringStatus.current_phase}`
      : 'No live status';

  return (
    <StudioShell
      eyebrow="Engineering"
      title="Close the machine, not just the circuit."
      description="One workspace for source boundaries, robot topology, quantitative margins, manufacturing identity, bounded execution, revision impact, and the exact next action."
      status={statusLabel}
      commandBar={(
        <StudioCommandBar
          modeLabel="Engineering closure"
          objective="Resolve the highest-risk blocker before spending fabrication, firmware, or bench time."
          context={engineeringStatus
            ? `${engineeringStatus.project_id} • ${blockers.length} blockers • next ${engineeringStatus.next_action_id || 'release review'}`
            : 'Load a persisted guided plan or compile the local JSON draft.'}
          status={statusLoading ? 'compiling' : engineeringStatus?.overall_status || 'local draft'}
          badges={['evidence-governed', 'revision-aware', 'no auto motion']}
        />
      )}
      activeHref="/engineering"
      navItems={navItems}
      actions={(
        <>
          <Button
            type="button"
            onClick={() => void runStatus(plan)}
            disabled={statusLoading}
            className="rounded-full bg-white text-slate-950 hover:bg-slate-100"
          >
            {statusLoading ? <LoaderCircle className="mr-2 h-4 w-4 animate-spin" /> : <RefreshCw className="mr-2 h-4 w-4" />}
            Recompile status
          </Button>
          <Button asChild variant="outline" className="rounded-full border-white/15 bg-white/5 text-white hover:bg-white/10">
            <Link href="/cad">
              <Boxes className="mr-2 h-4 w-4" />
              CAD workspace
            </Link>
          </Button>
        </>
      )}
      defaultBottomOpen
      left={(
        <div className="space-y-5">
          <div className="rounded-[1.5rem] border border-white/10 bg-[linear-gradient(180deg,#0c1730,#091323)] p-4">
            {panelHeading('Projects', 'Persistent engineering revisions')}
            {projectsLoading ? (
              <div className="flex items-center gap-2 text-sm text-slate-400"><LoaderCircle className="h-4 w-4 animate-spin" /> Loading Hardware Splicer projects</div>
            ) : projects.length ? (
              <div className="space-y-2">
                {projects.slice(0, 10).map((project) => (
                  <button
                    key={project.project_id}
                    type="button"
                    onClick={() => setSelectedProjectId(project.project_id)}
                    className={`w-full rounded-[1rem] border px-3 py-3 text-left transition-colors ${selectedProjectId === project.project_id ? 'border-cyan-300/25 bg-cyan-300/10' : 'border-white/8 bg-[#081423] hover:border-white/15'}`}
                  >
                    <div className="truncate text-sm font-semibold text-white">{project.name || project.project_id}</div>
                    <div className="mt-1 flex items-center justify-between gap-2 text-[10px] uppercase tracking-[0.16em] text-slate-500">
                      <span>rev {project.latest_revision}</span>
                      <span>{project.current_stage || project.mode || 'engineering'}</span>
                    </div>
                    <div className="mt-2 truncate text-xs text-slate-400">{formatSavedAt(project.saved_at)}</div>
                  </button>
                ))}
              </div>
            ) : (
              <div className="rounded-[1rem] border border-amber-300/15 bg-amber-300/8 p-3 text-xs leading-5 text-amber-100">
                Hardware Splicer project storage is unavailable or empty. The local starter remains clearly labeled and no live status is fabricated.
              </div>
            )}
          </div>

          <div className="rounded-[1.5rem] border border-white/10 bg-[linear-gradient(180deg,#0c1730,#091323)] p-4">
            <div className="mb-3 flex items-center justify-between gap-2">
              <div>
                <div className="text-[11px] font-semibold uppercase tracking-[0.24em] text-slate-500">Plan JSON</div>
                <div className="mt-2 text-sm font-semibold text-white">{projectSource === 'persisted' ? 'Persisted revision' : 'Local editor'}</div>
              </div>
              <span className={`rounded-full border px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.16em] ${projectSource === 'persisted' ? 'border-emerald-300/20 bg-emerald-300/8 text-emerald-200' : 'border-amber-300/20 bg-amber-300/8 text-amber-200'}`}>
                {projectSource}
              </span>
            </div>
            <textarea
              value={planText}
              onChange={(event) => setPlanText(event.target.value)}
              spellCheck={false}
              className="h-52 w-full resize-y rounded-[1rem] border border-white/10 bg-[#050c16] p-3 font-mono text-[11px] leading-5 text-slate-300 outline-none transition-colors focus:border-cyan-300/30"
              aria-label="Guided engineering plan JSON"
            />
            {editorError ? <div className="mt-2 text-xs leading-5 text-rose-300">{editorError}</div> : null}
            <Button type="button" onClick={applyEditor} className="mt-3 w-full rounded-xl bg-cyan-300 text-slate-950 hover:bg-cyan-200">
              <Binary className="mr-2 h-4 w-4" />
              Compile local plan
            </Button>
          </div>
        </div>
      )}
      main={(
        <div className="h-full overflow-y-auto p-4 sm:p-6">
          <div className="mx-auto max-w-6xl space-y-5">
            <div className="rounded-[1.6rem] border border-white/10 bg-[radial-gradient(circle_at_15%_0%,rgba(34,211,238,0.12),transparent_36%),linear-gradient(180deg,#0b172a,#07111f)] p-6">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <div className="text-[11px] font-semibold uppercase tracking-[0.24em] text-cyan-300/80">Unified project status</div>
                  <h1 className="mt-2 text-3xl font-semibold tracking-tight text-white">{engineeringStatus?.project_id || 'No compiled engineering status'}</h1>
                  <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-300">
                    {engineeringStatus
                      ? `Hardware Splicer is currently in the ${categoryLabel(engineeringStatus.current_phase)} phase. The queue is ranked by engineering dependency, not by visual severity alone.`
                      : 'Load or compile a guided plan to derive blockers, closure state, bounded checks, revision impact, and a deterministic next action.'}
                  </p>
                </div>
                <div className={`inline-flex items-center gap-2 rounded-full border px-3 py-2 text-xs font-semibold uppercase tracking-[0.16em] ${tone.border} ${tone.background} ${tone.text}`}>
                  <span className={`h-2 w-2 rounded-full ${tone.dot}`} />
                  {statusLoading ? 'Compiling' : engineeringStatus?.overall_status || 'Local draft'}
                </div>
              </div>

              <div className="mt-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
                {[
                  ['Phase', engineeringStatus ? categoryLabel(engineeringStatus.current_phase) : 'Uncompiled'],
                  ['Blockers', String(blockers.length)],
                  ['Advisories', String(advisories.length)],
                  ['Manufacturing', manufacturingBlocking ? `${manufacturingBlocking} blocked` : manufacturingChecks.length ? 'Candidate' : 'Unresolved'],
                  ['Bounded checks', `${executionChecks.length} planned`],
                ].map(([label, value]) => (
                  <div key={label} className="rounded-[1rem] border border-white/8 bg-[#081423]/85 p-3">
                    <div className="text-[10px] uppercase tracking-[0.18em] text-slate-500">{label}</div>
                    <div className="mt-2 text-sm font-semibold text-white">{value}</div>
                  </div>
                ))}
              </div>
            </div>

            {statusError ? (
              <div className="rounded-[1.3rem] border border-rose-400/20 bg-rose-500/10 p-4 text-sm leading-6 text-rose-100">
                <TriangleAlert className="mr-2 inline h-4 w-4" />{statusError}
              </div>
            ) : null}

            <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_17rem]">
              <div className="rounded-[1.5rem] border border-white/10 bg-[linear-gradient(180deg,#0a1526,#07111f)] p-5">
                <div className="flex items-center justify-between gap-3">
                  {panelHeading('Blockers', 'Ranked engineering closure queue')}
                  <div className="text-xs text-slate-500">{blockers.length + advisories.length} visible</div>
                </div>
                {statusLoading || planLoading ? (
                  <div className="flex min-h-52 items-center justify-center gap-3 text-sm text-slate-400">
                    <LoaderCircle className="h-5 w-5 animate-spin" /> Compiling canonical status
                  </div>
                ) : blockers.length || advisories.length ? (
                  <div className="space-y-3">
                    {[...blockers, ...advisories].slice(0, 12).map((blocker) => <BlockerCard key={blocker.blocker_id} blocker={blocker} />)}
                  </div>
                ) : engineeringStatus ? (
                  <div className="rounded-[1.2rem] border border-emerald-300/20 bg-emerald-300/8 p-5 text-sm leading-6 text-emerald-100">
                    <CheckCircle2 className="mr-2 inline h-5 w-5" /> No modeled engineering blockers remain. The project advances to scoped human release review; this does not self-authorize fabrication, flashing, power, or motion.
                  </div>
                ) : (
                  <div className="rounded-[1.2rem] border border-white/8 bg-[#081423] p-5 text-sm leading-6 text-slate-400">No live blocker model is available yet.</div>
                )}
              </div>

              <div className="space-y-5">
                <div className="rounded-[1.5rem] border border-white/10 bg-[linear-gradient(180deg,#0a1526,#07111f)] p-4">
                  {panelHeading('Groups', 'Blockers by domain')}
                  <div className="space-y-2">
                    {Object.entries(engineeringStatus?.blocker_groups || {}).length ? Object.entries(engineeringStatus?.blocker_groups || {}).map(([category, ids]) => (
                      <div key={category} className="flex items-center justify-between rounded-[0.9rem] border border-white/8 bg-[#081423] px-3 py-2.5">
                        <span className="text-xs font-medium text-slate-300">{categoryLabel(category)}</span>
                        <span className="rounded-full border border-white/8 px-2 py-0.5 text-[10px] font-semibold text-white">{ids.length}</span>
                      </div>
                    )) : <div className="text-xs leading-5 text-slate-500">No grouped status yet.</div>}
                  </div>
                </div>

                <div className="rounded-[1.5rem] border border-white/10 bg-[linear-gradient(180deg,#0a1526,#07111f)] p-4">
                  {panelHeading('Closure', 'Manufacturing and execution')}
                  <div className="space-y-2 text-xs">
                    <div className="flex items-center justify-between rounded-[0.9rem] border border-white/8 bg-[#081423] px-3 py-2.5"><span className="text-slate-400">Closure checks</span><span className="font-semibold text-white">{manufacturingChecks.length}</span></div>
                    <div className="flex items-center justify-between rounded-[0.9rem] border border-white/8 bg-[#081423] px-3 py-2.5"><span className="text-slate-400">Blocking checks</span><span className="font-semibold text-rose-200">{manufacturingBlocking}</span></div>
                    <div className="flex items-center justify-between rounded-[0.9rem] border border-white/8 bg-[#081423] px-3 py-2.5"><span className="text-slate-400">Preview checks</span><span className="font-semibold text-cyan-200">{executionChecks.length}</span></div>
                    <div className="flex items-center justify-between rounded-[0.9rem] border border-white/8 bg-[#081423] px-3 py-2.5"><span className="text-slate-400">Missing local inputs</span><span className="font-semibold text-amber-200">{executionUnresolved.length}</span></div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
      right={(
        <div className="space-y-5">
          <div className="rounded-[1.5rem] border border-cyan-300/18 bg-[linear-gradient(180deg,rgba(34,211,238,0.10),rgba(8,20,35,0.96))] p-4">
            {panelHeading('Next action', nextAction?.title || 'Compile project status')}
            {nextAction ? (
              <>
                <div className="text-sm leading-6 text-slate-200">{nextAction.instruction}</div>
                <div className="mt-4 rounded-xl border border-cyan-300/15 bg-black/15 p-3 font-mono text-[10px] leading-5 text-cyan-200">{nextAction.method || 'POST'} {nextAction.route}</div>
                {nextAction.required_inputs?.length ? (
                  <div className="mt-4">
                    <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-500">Required inputs</div>
                    <div className="mt-2 space-y-1.5">
                      {nextAction.required_inputs.slice(0, 5).map((item) => <div key={item} className="flex gap-2 text-xs leading-5 text-slate-300"><ChevronRight className="mt-0.5 h-3.5 w-3.5 shrink-0 text-cyan-300" />{item}</div>)}
                    </div>
                  </div>
                ) : null}
              </>
            ) : (
              <div className="text-sm leading-6 text-slate-400">Load a persisted plan or compile the local editor to receive a deterministic, API-backed next action.</div>
            )}
          </div>

          <div className="rounded-[1.5rem] border border-white/10 bg-[linear-gradient(180deg,#0c1730,#091323)] p-4">
            {panelHeading('Authority', 'Physical gates remain closed')}
            <div className="space-y-2">
              <AuthorityGate label="Fabrication" allowed={readiness.fabrication_authorized === true} />
              <AuthorityGate label="Firmware flash" allowed={readiness.flash_authorized === true} />
              <AuthorityGate label="Power-on" allowed={readiness.power_on_authorized === true} />
              <AuthorityGate label="Motion" allowed={readiness.motion_authorized === true} />
              <AuthorityGate label="Release" allowed={readiness.release_authorized === true} />
            </div>
          </div>

          <div className="rounded-[1.5rem] border border-white/10 bg-[linear-gradient(180deg,#0c1730,#091323)] p-4">
            {panelHeading('Revision diff', selectedProjectId ? `${selectedProjectId} history` : 'Select a persisted project')}
            <div className="grid grid-cols-2 gap-2">
              <label className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                Base
                <select
                  value={baseRevision || ''}
                  onChange={(event) => setBaseRevision(event.target.value ? Number(event.target.value) : null)}
                  className="mt-2 w-full rounded-xl border border-white/10 bg-[#081423] px-2 py-2 text-xs text-white outline-none"
                >
                  <option value="">Select</option>
                  {revisions.map((revision) => <option key={`base-${revision.revision}`} value={revision.revision}>rev {revision.revision}</option>)}
                </select>
              </label>
              <label className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                Candidate
                <select
                  value={candidateRevision || ''}
                  onChange={(event) => setCandidateRevision(event.target.value ? Number(event.target.value) : null)}
                  className="mt-2 w-full rounded-xl border border-white/10 bg-[#081423] px-2 py-2 text-xs text-white outline-none"
                >
                  <option value="">Select</option>
                  {revisions.map((revision) => <option key={`candidate-${revision.revision}`} value={revision.revision}>rev {revision.revision}</option>)}
                </select>
              </label>
            </div>
            <Button
              type="button"
              onClick={() => void compareRevisions()}
              disabled={!selectedProjectId || !baseRevision || !candidateRevision || diffLoading}
              variant="outline"
              className="mt-3 w-full rounded-xl border-white/15 bg-white/5 text-white hover:bg-white/10"
            >
              {diffLoading ? <LoaderCircle className="mr-2 h-4 w-4 animate-spin" /> : <GitCompareArrows className="mr-2 h-4 w-4" />}
              Compare revisions
            </Button>
            {diffError ? <div className="mt-3 text-xs leading-5 text-rose-300">{diffError}</div> : null}
            {diffResponse ? (
              <div className="mt-4 grid grid-cols-2 gap-2 text-xs">
                {[
                  ['Opened', diffSummary.opened, 'text-rose-200'],
                  ['Resolved', diffSummary.resolved, 'text-emerald-200'],
                  ['Persistent', diffSummary.persistent, 'text-amber-200'],
                  ['Artifacts', diffSummary.artifacts, 'text-cyan-200'],
                  ['Execution', diffSummary.execution, 'text-violet-200'],
                  ['Authority flags', diffSummary.authorityRegressions, 'text-rose-200'],
                ].map(([label, value, color]) => (
                  <div key={String(label)} className="rounded-[0.9rem] border border-white/8 bg-[#081423] p-2.5">
                    <div className="text-[10px] uppercase tracking-[0.14em] text-slate-500">{label}</div>
                    <div className={`mt-1 text-lg font-semibold ${color}`}>{value}</div>
                  </div>
                ))}
              </div>
            ) : null}
          </div>
        </div>
      )}
      bottom={(
        <div className="grid h-full grid-rows-[40px_minmax(0,1fr)]">
          <div className="flex items-center gap-2 border-b border-white/8 bg-[#08111d] px-4">
            <div className="inline-flex items-center gap-2 rounded-lg bg-cyan-300/12 px-3 py-1.5 text-xs font-medium text-cyan-100"><PlayCircle className="h-3.5 w-3.5" /> Action queue</div>
            <div className="text-xs text-slate-500">{actions.length} ranked actions • no automatic physical execution</div>
          </div>
          <div className="overflow-x-auto p-3 pr-24">
            <div className="flex min-w-max gap-3">
              {actions.length ? actions.map((action, index) => (
                <div key={action.action_id} className="w-80"><ActionCard action={action} active={index === 0} /></div>
              )) : (
                <div className="flex w-full min-w-[42rem] items-center justify-between rounded-[1rem] border border-white/8 bg-[#081423] p-4">
                  <div>
                    <div className="text-sm font-semibold text-white">No compiled action queue</div>
                    <div className="mt-1 text-xs text-slate-400">Compile the current plan to rank source, topology, analysis, manufacturing, execution, regression, and release work.</div>
                  </div>
                  <ArrowRight className="h-5 w-5 text-slate-500" />
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    />
  );
}

'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  ChevronRight,
  Circle,
  FileText,
  Gauge,
  LoaderCircle,
  LockKeyhole,
  RefreshCw,
  ShieldCheck,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { usePageTitle } from '@/components/use-page-title';
import {
  EvidenceArtifactViewport,
  deriveEvidenceBuildDir,
} from '@/components/engineering/evidence-artifact-viewport';
import { getProxyErrorMessage, isProxyFailure, readJsonPayload, type ProxyErrorPayload } from '@/lib/proxy-client';

type JsonRecord = Record<string, unknown>;
type ProjectSummary = { project_id?: string; name?: string; project_name?: string; revision?: number };
type ProjectsResponse = { ok?: boolean; projects?: ProjectSummary[] };
type ProjectEnvelope = { project_id?: string; revision?: number; snapshot?: JsonRecord };
type ProjectResponse = { ok?: boolean; project?: ProjectEnvelope };
type GateState = 'complete' | 'active' | 'blocked' | 'pending';
type BringupGate = { id: string; label: string; detail: string; state: GateState; evidence: string };

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

function isRealEvidence(item: JsonRecord) {
  return item.simulated === false || item.is_simulated === false;
}

function gateIcon(state: GateState) {
  if (state === 'complete') return <CheckCircle2 className="h-4 w-4 text-emerald-600" />;
  if (state === 'blocked') return <LockKeyhole className="h-4 w-4 text-red-600" />;
  if (state === 'active') return <Gauge className="h-4 w-4 text-amber-600" />;
  return <Circle className="h-4 w-4 text-stone-300" />;
}

function gateStyle(state: GateState) {
  if (state === 'complete') return 'border-emerald-200 bg-emerald-50/60';
  if (state === 'blocked') return 'border-red-200 bg-red-50/60';
  if (state === 'active') return 'border-amber-200 bg-amber-50/60';
  return 'border-stone-200 bg-white';
}

export default function EvidenceBringupPage() {
  usePageTitle('Physical Bring-up | Hardware Splicer');
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [projectId, setProjectId] = useState('');
  const [revision, setRevision] = useState<number | null>(null);
  const [snapshot, setSnapshot] = useState<JsonRecord | null>(null);
  const [session, setSession] = useState<JsonRecord | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedGate, setSelectedGate] = useState('identity');

  const sources = rows(snapshot?.engineeringSources);
  const fabricationAuthorized = snapshot?.fabrication_authorized === true;
  const powerOnAuthorized = snapshot?.power_on_authorized === true;
  const releaseAuthorized = snapshot?.release_authorized === true;
  const physicalEvidence = rows(snapshot?.physicalEvidence || snapshot?.physical_evidence || snapshot?.benchEvidence || snapshot?.bench_evidence);
  const realPhysicalEvidence = physicalEvidence.filter(isRealEvidence);
  const buildDir = deriveEvidenceBuildDir(snapshot, session);

  const projectName = useMemo(() => {
    const match = projects.find((project) => text(project.project_id) === projectId);
    return match ? projectLabel(match) : text(snapshot?.name || snapshot?.project_name, projectId || 'Hardware project');
  }, [projectId, projects, snapshot]);

  const gates = useMemo<BringupGate[]>(() => [
    {
      id: 'identity',
      label: 'Identity & assembly',
      detail: 'Exact board revision, component identity, DNP state, orientation and assembly condition.',
      state: sources.length ? 'complete' : 'active',
      evidence: sources.length ? `${sources.length} engineering source${sources.length === 1 ? '' : 's'} registered` : 'source identity incomplete',
    },
    {
      id: 'cold',
      label: 'Cold checks',
      detail: 'Unpowered resistance, continuity, isolation and polarity before energizing the board.',
      state: realPhysicalEvidence.length ? 'complete' : 'active',
      evidence: realPhysicalEvidence.length ? `${realPhysicalEvidence.length} explicitly real record${realPhysicalEvidence.length === 1 ? '' : 's'}` : 'no real measurement captured',
    },
    {
      id: 'power',
      label: 'Controlled power',
      detail: 'Power-on is a separate authority transition after valid cold evidence and human review.',
      state: powerOnAuthorized ? 'complete' : 'blocked',
      evidence: powerOnAuthorized ? 'power-on authority open' : 'power-on authority closed',
    },
    {
      id: 'functional',
      label: 'Functional test',
      detail: 'Run the bounded transaction only after rail and power-on evidence are valid.',
      state: powerOnAuthorized && realPhysicalEvidence.length ? 'active' : 'blocked',
      evidence: powerOnAuthorized ? 'awaiting bounded functional evidence' : 'blocked by power-on authority',
    },
    {
      id: 'release',
      label: 'Release decision',
      detail: 'Release remains an explicit human-scoped decision after the relevant physical evidence exists.',
      state: releaseAuthorized ? 'complete' : 'pending',
      evidence: releaseAuthorized ? 'release authority open' : 'release authority not granted',
    },
  ], [powerOnAuthorized, realPhysicalEvidence.length, releaseAuthorized, sources.length]);

  const selected = gates.find((gate) => gate.id === selectedGate) || gates[0];
  const overlay = selected.state === 'blocked' ? selected.evidence : '';

  async function loadProject(nextProjectId: string) {
    if (!nextProjectId) return;
    setBusy(true);
    setError(null);
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
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Project load failed.');
    } finally {
      setBusy(false);
    }
  }

  async function loadProjects() {
    setBusy(true);
    setError(null);
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
            <span className="text-sm font-medium text-stone-700">Physical bring-up</span>
            <select value={projectId} onChange={(event) => void loadProject(event.target.value)} className="ml-2 max-w-64 bg-transparent text-sm font-medium outline-none" aria-label="Project">
              {projects.map((project) => <option key={text(project.project_id)} value={text(project.project_id)}>{projectLabel(project)}</option>)}
            </select>
            <span className="rounded-md bg-stone-100 px-2 py-1 font-mono text-[11px] text-stone-500">Rev {revision ?? '—'}</span>
            <div className="ml-auto flex items-center gap-2">
              <span className={`rounded-md border px-2.5 py-1.5 text-xs font-medium ${fabricationAuthorized ? 'border-emerald-200 bg-emerald-50 text-emerald-800' : 'border-stone-200 bg-stone-100 text-stone-600'}`}>Fabrication {fabricationAuthorized ? 'open' : 'closed'}</span>
              <span className={`rounded-md border px-2.5 py-1.5 text-xs font-medium ${powerOnAuthorized ? 'border-emerald-200 bg-emerald-50 text-emerald-800' : 'border-red-200 bg-red-50 text-red-800'}`}>Power-on {powerOnAuthorized ? 'open' : 'blocked'}</span>
              <Button size="sm" variant="outline" onClick={loadProjects} disabled={busy} className="h-8 border-stone-300 bg-white text-stone-700">{busy ? <LoaderCircle className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}</Button>
            </div>
          </div>
        </header>

        {error ? <div className="border-b border-red-200 bg-red-50 px-4 py-2 text-xs text-red-800">{error}</div> : null}

        <section className="grid min-h-0 flex-1 grid-cols-1 gap-px bg-stone-200 xl:grid-cols-[285px_minmax(0,1fr)_340px]">
          <aside className="min-h-[720px] overflow-y-auto bg-white p-3">
            <div className="px-2 pb-3 text-[10px] font-semibold uppercase tracking-[0.12em] text-stone-400">Validation sequence</div>
            <div className="space-y-1">
              {gates.map((gate, index) => (
                <button key={gate.id} type="button" onClick={() => setSelectedGate(gate.id)} className={`flex w-full items-start gap-3 rounded-md border px-3 py-3 text-left ${selectedGate === gate.id ? gateStyle(gate.state) : 'border-transparent hover:bg-stone-50'}`}>
                  <div className="mt-0.5">{gateIcon(gate.state)}</div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center justify-between gap-2"><span className="text-xs font-semibold text-stone-900">{index + 1}. {gate.label}</span><span className="text-[9px] uppercase tracking-[0.08em] text-stone-400">{gate.state}</span></div>
                    <div className="mt-1 line-clamp-2 text-[10px] leading-4 text-stone-500">{gate.evidence}</div>
                  </div>
                </button>
              ))}
            </div>
            <div className="mt-4 border-t border-stone-200 px-2 pt-4 text-[10px] leading-4 text-stone-400">Unlike generic HIL dashboards, test execution does not automatically change physical authority.</div>
          </aside>

          <section className="min-w-0 bg-white">
            <div className="flex min-h-11 items-center justify-between border-b border-stone-200 px-4">
              <div>
                <span className="text-xs font-medium text-stone-700">{selected.label}</span>
                <span className="ml-2 text-[10px] text-stone-400">{selected.detail}</span>
              </div>
              <span className={`rounded-md border px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.08em] ${selected.state === 'complete' ? 'border-emerald-200 bg-emerald-50 text-emerald-700' : selected.state === 'blocked' ? 'border-red-200 bg-red-50 text-red-700' : selected.state === 'active' ? 'border-amber-200 bg-amber-50 text-amber-700' : 'border-stone-200 bg-stone-50 text-stone-500'}`}>{selected.state}</span>
            </div>
            <EvidenceArtifactViewport buildDir={buildDir} overlayFinding={overlay} preferredKind="pcb" compact />
          </section>

          <aside className="flex min-h-[720px] flex-col bg-white">
            <div className="border-b border-stone-200 px-4 py-3">
              <div className="text-[10px] font-semibold uppercase tracking-[0.1em] text-stone-400">Physical evidence</div>
              <div className="mt-1 text-xs text-stone-500">{projectName} · Rev {revision ?? '—'}</div>
            </div>
            <div className="min-h-0 flex-1 overflow-y-auto p-4">
              <div className="mb-5 rounded-md border border-stone-200 bg-stone-50 p-3">
                <div className="text-[10px] font-semibold uppercase tracking-[0.1em] text-stone-400">Selected gate</div>
                <div className="mt-1 text-sm font-semibold text-stone-900">{selected.label}</div>
                <div className="mt-2 text-xs leading-5 text-stone-600">{selected.evidence}</div>
              </div>

              <div className="space-y-2">
                {physicalEvidence.slice(-10).map((item, index) => (
                  <div key={text(item.id || item.evidence_id, `physical-${index}`)} className={`rounded-md border p-3 ${isRealEvidence(item) ? 'border-emerald-200 bg-emerald-50/40' : 'border-stone-200'}`}>
                    <div className="flex items-center gap-2"><FileText className="h-3.5 w-3.5 text-stone-400" /><span className="truncate text-xs font-medium text-stone-800">{text(item.label || item.kind || item.measurement_type, 'Physical record')}</span></div>
                    <div className="mt-1 text-[10px] text-stone-400">{isRealEvidence(item) ? 'real evidence' : 'simulation status unresolved'}</div>
                    <div className="mt-1 font-mono text-[9px] text-stone-400">Rev {text(item.revision || item.project_revision, revision ?? '—')}</div>
                  </div>
                ))}
                {!physicalEvidence.length ? <div className="rounded-md border border-dashed border-stone-300 p-4 text-xs leading-5 text-stone-500">No physical measurement record is attached to this project snapshot yet.</div> : null}
              </div>
            </div>

            <div className="border-t border-stone-200 p-4">
              <div className="mb-2 flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.1em] text-stone-400"><ShieldCheck className="h-3.5 w-3.5" />Authority</div>
              <div className="grid grid-cols-3 gap-1.5 text-center text-[10px] font-medium">
                <div className={`rounded-md px-2 py-2 ${fabricationAuthorized ? 'bg-emerald-50 text-emerald-700' : 'bg-stone-100 text-stone-500'}`}>FAB<br />{fabricationAuthorized ? 'OPEN' : 'CLOSED'}</div>
                <div className={`rounded-md px-2 py-2 ${powerOnAuthorized ? 'bg-emerald-50 text-emerald-700' : 'bg-red-50 text-red-700'}`}>POWER<br />{powerOnAuthorized ? 'OPEN' : 'BLOCKED'}</div>
                <div className={`rounded-md px-2 py-2 ${releaseAuthorized ? 'bg-emerald-50 text-emerald-700' : 'bg-stone-100 text-stone-500'}`}>RELEASE<br />{releaseAuthorized ? 'OPEN' : 'CLOSED'}</div>
              </div>
              <Link href={`/engineering/evidence/verify?project=${encodeURIComponent(projectId)}`} className="mt-3 flex items-center justify-between rounded-md border border-stone-300 px-3 py-2.5 text-xs font-medium text-stone-700 hover:bg-stone-50">Back to verification <ChevronRight className="h-3.5 w-3.5" /></Link>
            </div>
          </aside>
        </section>
      </div>
    </main>
  );
}
'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import {
  AlertTriangle,
  ArrowLeft,
  Check,
  CheckCircle2,
  ChevronRight,
  Circle,
  FileText,
  FlaskConical,
  Gauge,
  LoaderCircle,
  LockKeyhole,
  RefreshCw,
  ShieldCheck,
  TestTube2,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { usePageTitle } from '@/components/use-page-title';
import { getProxyErrorMessage, isProxyFailure, readJsonPayload, type ProxyErrorPayload } from '@/lib/proxy-client';

type JsonRecord = Record<string, unknown>;
type ProjectSummary = { project_id?: string; name?: string; project_name?: string; revision?: number };
type ProjectsResponse = { ok?: boolean; projects?: ProjectSummary[] };
type ProjectEnvelope = { project_id?: string; revision?: number; snapshot?: JsonRecord };
type ProjectResponse = { ok?: boolean; project?: ProjectEnvelope };

type GateState = 'complete' | 'active' | 'blocked' | 'pending';

type BringupGate = {
  id: string;
  label: string;
  detail: string;
  state: GateState;
  evidence?: string;
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

function gateIcon(state: GateState) {
  if (state === 'complete') return <CheckCircle2 className="h-4 w-4 text-emerald-600" />;
  if (state === 'blocked') return <LockKeyhole className="h-4 w-4 text-red-600" />;
  if (state === 'active') return <Gauge className="h-4 w-4 text-amber-600" />;
  return <Circle className="h-4 w-4 text-stone-300" />;
}

function gateStyle(state: GateState) {
  if (state === 'complete') return 'border-emerald-200 bg-emerald-50/50';
  if (state === 'blocked') return 'border-red-200 bg-red-50/50';
  if (state === 'active') return 'border-amber-200 bg-amber-50/50';
  return 'border-stone-200 bg-white';
}

export default function EvidenceBringupPage() {
  usePageTitle('Physical Bring-up | Hardware Splicer');
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [projectId, setProjectId] = useState('');
  const [revision, setRevision] = useState<number | null>(null);
  const [snapshot, setSnapshot] = useState<JsonRecord | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedGate, setSelectedGate] = useState('identity');

  const sources = rows(snapshot?.engineeringSources);
  const fabricationAuthorized = snapshot?.fabrication_authorized === true;
  const powerOnAuthorized = snapshot?.power_on_authorized === true;
  const releaseAuthorized = snapshot?.release_authorized === true;
  const physicalEvidence = rows(snapshot?.physicalEvidence || snapshot?.physical_evidence || snapshot?.benchEvidence || snapshot?.bench_evidence);
  const physicalCount = physicalEvidence.length;

  const projectName = useMemo(() => {
    const match = projects.find((project) => text(project.project_id) === projectId);
    return match ? projectLabel(match) : text(snapshot?.name || snapshot?.project_name, projectId || 'Hardware project');
  }, [projectId, projects, snapshot]);

  const gates = useMemo<BringupGate[]>(() => {
    const sourceReady = sources.length > 0;
    const realEvidence = physicalEvidence.filter((item) => item.simulated === false || item.is_simulated === false);
    return [
      {
        id: 'identity',
        label: 'Identity & assembly',
        detail: 'Confirm exact board revision, component identities, DNP state, orientation, and assembly condition.',
        state: sourceReady ? 'complete' : 'active',
        evidence: sourceReady ? `${sources.length} registered engineering source${sources.length === 1 ? '' : 's'}` : 'No engineering source is registered.',
      },
      {
        id: 'cold',
        label: 'Cold checks',
        detail: 'Record unpowered resistance, continuity, isolation, and polarity checks before energizing the board.',
        state: realEvidence.length ? 'complete' : 'active',
        evidence: realEvidence.length ? `${realEvidence.length} explicitly real physical evidence record${realEvidence.length === 1 ? '' : 's'}` : 'No explicitly real measurement has been recorded.',
      },
      {
        id: 'power',
        label: 'Controlled power',
        detail: 'Power-on remains a separate authority transition after valid cold evidence and human review.',
        state: powerOnAuthorized ? 'complete' : 'blocked',
        evidence: powerOnAuthorized ? 'Power-on authority is open for this snapshot.' : 'Power-on authority is closed.',
      },
      {
        id: 'functional',
        label: 'Functional test',
        detail: 'Run the bounded functional transaction only after rail and power-on evidence are valid.',
        state: powerOnAuthorized && physicalCount ? 'active' : 'blocked',
        evidence: powerOnAuthorized ? 'Awaiting bounded functional evidence.' : 'Blocked by power-on authority.',
      },
      {
        id: 'release',
        label: 'Release decision',
        detail: 'Release is an explicit human-scoped decision; previous software or physical success does not grant it automatically.',
        state: releaseAuthorized ? 'complete' : 'pending',
        evidence: releaseAuthorized ? 'Release authority is open.' : 'Release authority has not been granted.',
      },
    ];
  }, [physicalCount, physicalEvidence, powerOnAuthorized, releaseAuthorized, sources.length]);

  const selected = gates.find((gate) => gate.id === selectedGate) || gates[0];

  async function loadProject(nextProjectId: string) {
    if (!nextProjectId) return;
    setBusy(true);
    setError(null);
    try {
      const response = await fetch(`/api/proxy/engineering/projects/${encodeURIComponent(nextProjectId)}`, { cache: 'no-store' });
      const payload = await readJsonPayload<ProjectResponse | ProxyErrorPayload>(response);
      if (!response.ok || isProxyFailure(payload)) throw new Error(getProxyErrorMessage(payload, 'Hardware Splicer could not load this project.'));
      const envelope = (payload as ProjectResponse).project || {};
      setProjectId(nextProjectId);
      setRevision(Number(envelope.revision));
      setSnapshot(record(envelope.snapshot));
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
          <div className="flex min-h-14 items-center gap-3 px-4 lg:px-5">
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

        <section className="grid min-h-0 flex-1 grid-cols-1 gap-px bg-stone-200 xl:grid-cols-[300px_minmax(0,1fr)_340px]">
          <aside className="bg-white p-3">
            <div className="px-2 py-2">
              <div className="text-[10px] font-semibold uppercase tracking-[0.12em] text-stone-400">Validation sequence</div>
              <div className="mt-1 text-xs text-stone-500">Evidence advances the sequence. A later gate never retroactively upgrades an earlier one.</div>
            </div>
            <div className="mt-3 space-y-1">
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
          </aside>

          <section className="min-w-0 bg-[#fbfbfa] p-4 lg:p-6">
            <div className="mx-auto flex h-full max-w-5xl flex-col">
              <div className="flex items-center justify-between border-b border-stone-200 pb-4">
                <div>
                  <div className="text-[10px] font-semibold uppercase tracking-[0.12em] text-stone-400">{projectName}</div>
                  <h1 className="mt-1 text-2xl font-semibold tracking-tight">{selected.label}</h1>
                </div>
                <span className={`rounded-md border px-2.5 py-1.5 text-xs font-medium ${selected.state === 'complete' ? 'border-emerald-200 bg-emerald-50 text-emerald-800' : selected.state === 'blocked' ? 'border-red-200 bg-red-50 text-red-800' : selected.state === 'active' ? 'border-amber-200 bg-amber-50 text-amber-800' : 'border-stone-200 bg-white text-stone-600'}`}>{selected.state}</span>
              </div>

              <div className="grid flex-1 place-items-center py-8">
                <div className="w-full max-w-3xl rounded-lg border border-stone-200 bg-white p-5 shadow-sm">
                  <div className="flex items-start gap-4">
                    <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg bg-stone-950 text-white">{selected.id === 'cold' ? <TestTube2 className="h-5 w-5" /> : selected.id === 'power' ? <Gauge className="h-5 w-5" /> : selected.id === 'functional' ? <FlaskConical className="h-5 w-5" /> : <ShieldCheck className="h-5 w-5" />}</div>
                    <div className="min-w-0 flex-1">
                      <div className="text-sm font-semibold text-stone-950">{selected.detail}</div>
                      <div className="mt-2 text-xs leading-5 text-stone-500">{selected.evidence}</div>
                    </div>
                  </div>

                  <div className="mt-6 grid gap-2 sm:grid-cols-2">
                    <div className="rounded-md border border-stone-200 p-3">
                      <div className="text-[10px] font-semibold uppercase tracking-[0.1em] text-stone-400">Evidence attached</div>
                      <div className="mt-2 text-2xl font-semibold tracking-tight">{selected.id === 'identity' ? sources.length : physicalCount}</div>
                    </div>
                    <div className="rounded-md border border-stone-200 p-3">
                      <div className="text-[10px] font-semibold uppercase tracking-[0.1em] text-stone-400">Authority effect</div>
                      <div className="mt-2 text-sm font-semibold text-stone-800">{selected.id === 'power' && powerOnAuthorized ? 'Power-on permitted' : selected.id === 'release' && releaseAuthorized ? 'Release permitted' : 'No automatic authority'}</div>
                    </div>
                  </div>

                  {selected.state === 'blocked' ? (
                    <div className="mt-5 flex gap-3 rounded-md border border-red-200 bg-red-50 p-3 text-xs leading-5 text-red-800"><AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />This gate is blocked by current project state. The interface does not infer permission from successful software checks.</div>
                  ) : selected.state === 'complete' ? (
                    <div className="mt-5 flex gap-3 rounded-md border border-emerald-200 bg-emerald-50 p-3 text-xs leading-5 text-emerald-800"><Check className="mt-0.5 h-4 w-4 shrink-0" />This stage has supporting project evidence. Later stages remain independently scoped.</div>
                  ) : null}
                </div>
              </div>
            </div>
          </section>

          <aside className="bg-white p-4">
            <div className="text-[10px] font-semibold uppercase tracking-[0.12em] text-stone-400">Physical evidence</div>
            <div className="mt-3 space-y-2">
              {physicalEvidence.slice(-8).map((item, index) => (
                <div key={text(item.id || item.evidence_id, `physical-${index}`)} className="rounded-md border border-stone-200 p-3">
                  <div className="flex items-center gap-2"><FileText className="h-3.5 w-3.5 text-stone-400" /><span className="truncate text-xs font-medium text-stone-800">{text(item.label || item.kind || item.measurement_type, 'Physical record')}</span></div>
                  <div className="mt-1 text-[10px] text-stone-400">{item.simulated === false || item.is_simulated === false ? 'real evidence' : 'simulation status unresolved'}</div>
                </div>
              ))}
              {!physicalEvidence.length ? <div className="rounded-md border border-dashed border-stone-300 p-4 text-xs leading-5 text-stone-500">No physical measurement record is attached to this project snapshot yet.</div> : null}
            </div>

            <div className="mt-6 border-t border-stone-200 pt-4">
              <div className="text-[10px] font-semibold uppercase tracking-[0.12em] text-stone-400">Current boundary</div>
              <div className="mt-3 space-y-2 text-xs">
                <div className="flex justify-between"><span className="text-stone-500">Fabrication</span><span className={fabricationAuthorized ? 'font-medium text-emerald-700' : 'font-medium text-stone-600'}>{fabricationAuthorized ? 'open' : 'closed'}</span></div>
                <div className="flex justify-between"><span className="text-stone-500">Power-on</span><span className={powerOnAuthorized ? 'font-medium text-emerald-700' : 'font-medium text-red-700'}>{powerOnAuthorized ? 'open' : 'blocked'}</span></div>
                <div className="flex justify-between"><span className="text-stone-500">Release</span><span className={releaseAuthorized ? 'font-medium text-emerald-700' : 'font-medium text-stone-600'}>{releaseAuthorized ? 'open' : 'closed'}</span></div>
              </div>
            </div>
          </aside>
        </section>
      </div>
    </main>
  );
}

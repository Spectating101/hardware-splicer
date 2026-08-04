'use client';

import { useState } from 'react';
import Link from 'next/link';
import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  CircleOff,
  Download,
  FolderOpen,
  LoaderCircle,
  Play,
  ShieldCheck,
  UploadCloud,
  XCircle,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { usePageTitle } from '@/components/use-page-title';
import {
  getProxyErrorMessage,
  isProxyFailure,
  readJsonPayload,
  type ProxyErrorPayload,
} from '@/lib/proxy-client';

type JsonRecord = Record<string, unknown>;
type ProjectEnvelope = { revision?: number; snapshot?: JsonRecord };
type ProjectResponse = { ok?: boolean; project?: ProjectEnvelope };
type ProjectPlanResponse = {
  ok?: boolean;
  project_id?: string;
  revision?: number;
  persisted_source_count?: number;
  combined_source_count?: number;
  plan?: JsonRecord;
  engineering_readiness?: JsonRecord;
  engineering_status?: JsonRecord;
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
  if (value === null || value === undefined || value === '') return fallback;
  return String(value);
}

function downloadJson(filename: string, value: unknown) {
  const blob = new Blob([JSON.stringify(value, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

function Gate({ label, allowed }: { label: string; allowed: boolean }) {
  return (
    <div className="rounded-xl border border-white/10 bg-black/10 p-3">
      <div className="text-[10px] uppercase tracking-[0.16em] text-slate-500">{label}</div>
      <div className={`mt-2 inline-flex items-center gap-1.5 text-xs font-semibold ${allowed ? 'text-emerald-200' : 'text-slate-400'}`}>
        {allowed ? <CheckCircle2 className="h-3.5 w-3.5" /> : <CircleOff className="h-3.5 w-3.5" />}
        {allowed ? 'Authorized' : 'Not authorized'}
      </div>
    </div>
  );
}

export default function ProjectPreflightPage() {
  usePageTitle('Project Preflight | Hardware Splicer');
  const [projectId, setProjectId] = useState('');
  const [projectName, setProjectName] = useState('');
  const [revision, setRevision] = useState<number | null>(null);
  const [sourceCount, setSourceCount] = useState(0);
  const [goal, setGoal] = useState('');
  const [mode, setMode] = useState('greenfield');
  const [partsText, setPartsText] = useState('[]');
  const [constraintsText, setConstraintsText] = useState('{}');
  const [loading, setLoading] = useState(false);
  const [planning, setPlanning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [plan, setPlan] = useState<JsonRecord | null>(null);

  const readiness = record(plan?.engineering_readiness);
  const status = record(plan?.engineering_status);
  const blockers = rows(status.blockers);
  const advisories = rows(status.advisories);
  const nextActions = rows(status.next_actions);
  const machineProject = record(plan?.machine_project);

  async function loadProject() {
    setLoading(true);
    setError(null);
    setPlan(null);
    try {
      if (!projectId.trim()) throw new Error('Project ID is required.');
      const response = await fetch(`/api/proxy/engineering/projects/${encodeURIComponent(projectId.trim())}`, { cache: 'no-store' });
      const payload = await readJsonPayload<ProjectResponse | ProxyErrorPayload>(response);
      if (!response.ok || isProxyFailure(payload)) {
        throw new Error(getProxyErrorMessage(payload, 'Hardware Splicer could not load the project.'));
      }
      const envelope = (payload as ProjectResponse).project || {};
      const snapshot = record(envelope.snapshot);
      setRevision(Number(envelope.revision || 0));
      setProjectName(String(snapshot.projectName || snapshot.projectId || projectId.trim()));
      setSourceCount(rows(snapshot.engineeringSources).length);
      const priorPlan = record(snapshot.engineeringPlan);
      if (Object.keys(priorPlan).length) {
        setPlan(priorPlan);
        const context = record(priorPlan.engineering_context);
        const normalized = record(context.normalized_intake);
        setGoal(String(normalized.goal || normalized.mission || goal));
        setMode(String(context.normalized_mode || mode));
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Project loading failed.');
    } finally {
      setLoading(false);
    }
  }

  async function generatePlan() {
    setPlanning(true);
    setError(null);
    try {
      if (!projectId.trim()) throw new Error('Project ID is required.');
      if (revision === null || revision < 1) throw new Error('Load a revisioned project first.');
      if (!goal.trim()) throw new Error('Describe what the system must do.');
      const availableParts = JSON.parse(partsText || '[]');
      const constraints = JSON.parse(constraintsText || '{}');
      if (!Array.isArray(availableParts)) throw new Error('Available parts JSON must be an array.');
      if (!constraints || typeof constraints !== 'object' || Array.isArray(constraints)) throw new Error('Constraints JSON must be an object.');

      const response = await fetch(`/api/proxy/engineering/projects/${encodeURIComponent(projectId.trim())}/plan`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({
          expected_revision: revision,
          intake: {
            project_name: projectId.trim(),
            name: projectName || projectId.trim(),
            goal: goal.trim(),
            mode,
            available_parts: availableParts,
            constraints,
          },
          declared_conflicts: [],
          additional_engineering_sources: [],
          skip_vision: true,
        }),
        cache: 'no-store',
      });
      const payload = await readJsonPayload<ProjectPlanResponse | ProxyErrorPayload>(response);
      if (!response.ok || isProxyFailure(payload)) {
        throw new Error(getProxyErrorMessage(payload, 'Hardware Splicer could not generate and save the project plan.'));
      }
      const candidate = record((payload as ProjectPlanResponse).plan);
      if (!Object.keys(candidate).length) throw new Error('Hardware Splicer returned no plan.');
      setRevision(Number((payload as ProjectPlanResponse).revision || revision));
      setSourceCount(Number((payload as ProjectPlanResponse).combined_source_count || sourceCount));
      setPlan(candidate);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Project planning failed.');
    } finally {
      setPlanning(false);
    }
  }

  return (
    <main className="min-h-screen bg-[#040b14] text-slate-100">
      <div className="mx-auto max-w-[1450px] px-4 py-6 sm:px-6 lg:px-8">
        <div className="flex flex-col gap-5 border-b border-white/10 pb-6 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <Link href="/engineering/sources" className="inline-flex items-center gap-2 text-xs font-medium text-slate-400 hover:text-white">
              <ArrowLeft className="h-3.5 w-3.5" /> Engineering Sources
            </Link>
            <div className="mt-4 flex items-center gap-3">
              <div className="rounded-2xl border border-cyan-300/20 bg-cyan-300/10 p-3 text-cyan-200"><ShieldCheck className="h-6 w-6" /></div>
              <div>
                <h1 className="text-2xl font-semibold text-white">Project Preflight</h1>
                <p className="mt-1 max-w-3xl text-sm leading-6 text-slate-400">Generate and persist a governed plan from the exact source boundary registered in one project revision.</p>
              </div>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" onClick={() => downloadJson(`${projectId || 'hardware-splicer'}-guided-plan.json`, plan)} disabled={!plan}>
              <Download className="mr-2 h-4 w-4" />Download plan
            </Button>
            <Button onClick={generatePlan} disabled={planning || revision === null}>
              {planning ? <LoaderCircle className="mr-2 h-4 w-4 animate-spin" /> : <Play className="mr-2 h-4 w-4" />}
              Generate and save
            </Button>
          </div>
        </div>

        {error ? (
          <div className="mt-5 flex items-start gap-3 rounded-2xl border border-rose-300/20 bg-rose-300/10 p-4 text-sm text-rose-100">
            <XCircle className="mt-0.5 h-4 w-4 shrink-0" /><div>{error}</div>
          </div>
        ) : null}

        <div className="mt-6 grid gap-6 xl:grid-cols-[410px_minmax(0,1fr)]">
          <section className="space-y-5 rounded-3xl border border-white/10 bg-[#07111f] p-5">
            <div>
              <div className="text-xs font-semibold uppercase tracking-[0.2em] text-cyan-200">Persisted project</div>
              <label className="mt-4 block text-xs font-medium text-slate-300">Project ID</label>
              <input value={projectId} onChange={(event) => { setProjectId(event.target.value); setRevision(null); setPlan(null); }} placeholder="inspection-rover-r1" className="mt-2 w-full rounded-xl border border-white/10 bg-[#040b14] px-3 py-2.5 text-sm text-white outline-none focus:border-cyan-300/40" />
              <Button variant="outline" onClick={loadProject} disabled={loading} className="mt-3 w-full">
                {loading ? <LoaderCircle className="mr-2 h-4 w-4 animate-spin" /> : <FolderOpen className="mr-2 h-4 w-4" />}
                Load project
              </Button>
              <div className="mt-4 grid grid-cols-2 gap-2">
                <div className="rounded-xl border border-white/10 bg-black/10 p-3"><div className="text-[10px] uppercase tracking-[0.16em] text-slate-500">Revision</div><div className="mt-2 text-xl font-semibold text-white">{revision ?? '—'}</div></div>
                <div className="rounded-xl border border-white/10 bg-black/10 p-3"><div className="text-[10px] uppercase tracking-[0.16em] text-slate-500">Registered sources</div><div className="mt-2 text-xl font-semibold text-white">{sourceCount}</div></div>
              </div>
            </div>

            <div className="border-t border-white/10 pt-5">
              <div className="text-xs font-semibold uppercase tracking-[0.2em] text-cyan-200">Mission</div>
              <label className="mt-4 block text-xs font-medium text-slate-300">What must this system do?</label>
              <textarea value={goal} onChange={(event) => setGoal(event.target.value)} rows={6} placeholder="Describe mission, environment, payload, runtime, safety and acceptance criteria." className="mt-2 w-full resize-y rounded-xl border border-white/10 bg-[#040b14] px-3 py-2.5 text-sm leading-6 text-white outline-none focus:border-cyan-300/40" />
              <label className="mt-4 block text-xs font-medium text-slate-300">Work mode</label>
              <select value={mode} onChange={(event) => setMode(event.target.value)} className="mt-2 w-full rounded-xl border border-white/10 bg-[#040b14] px-3 py-2.5 text-sm text-white outline-none focus:border-cyan-300/40">
                <option value="greenfield">New build</option>
                <option value="modify">Modification</option>
                <option value="repair">Repair / reconstruction</option>
                <option value="evolve">Field evolution</option>
              </select>
            </div>

            <div className="border-t border-white/10 pt-5">
              <div className="text-xs font-semibold uppercase tracking-[0.2em] text-cyan-200">Parts and constraints</div>
              <label className="mt-4 block text-xs font-medium text-slate-300">Available parts JSON</label>
              <textarea value={partsText} onChange={(event) => setPartsText(event.target.value)} rows={7} spellCheck={false} className="mt-2 w-full rounded-xl border border-white/10 bg-[#040b14] px-3 py-2.5 font-mono text-xs leading-5 text-slate-200 outline-none focus:border-cyan-300/40" />
              <label className="mt-4 block text-xs font-medium text-slate-300">Constraints JSON</label>
              <textarea value={constraintsText} onChange={(event) => setConstraintsText(event.target.value)} rows={9} spellCheck={false} className="mt-2 w-full rounded-xl border border-white/10 bg-[#040b14] px-3 py-2.5 font-mono text-xs leading-5 text-slate-200 outline-none focus:border-cyan-300/40" />
            </div>

            <div className="border-t border-white/10 pt-5">
              <Link href="/engineering/sources" className="inline-flex items-center gap-2 text-xs text-cyan-200 hover:text-white"><UploadCloud className="h-3.5 w-3.5" />Add or inspect project sources</Link>
            </div>
          </section>

          <section className="min-w-0 rounded-3xl border border-white/10 bg-[#07111f]">
            {!plan ? (
              <div className="flex min-h-[760px] flex-col items-center justify-center px-6 text-center">
                <ShieldCheck className="h-10 w-10 text-cyan-200" />
                <h2 className="mt-5 text-xl font-semibold text-white">No saved project plan loaded</h2>
                <p className="mt-3 max-w-xl text-sm leading-6 text-slate-400">Load a project with registered sources, complete the mission intake, and generate the next governed revision.</p>
              </div>
            ) : (
              <div>
                <div className="border-b border-white/10 p-5">
                  <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                    <div>
                      <div className="flex flex-wrap items-center gap-2">
                        <span className={`rounded-full border px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] ${text(status.overall_status || readiness.status) === 'blocked' ? 'border-rose-300/20 bg-rose-300/10 text-rose-200' : 'border-amber-300/20 bg-amber-300/10 text-amber-200'}`}>{text(status.overall_status || readiness.status)}</span>
                        <span className="text-xs text-slate-500">Saved revision {revision}</span>
                      </div>
                      <h2 className="mt-3 text-xl font-semibold text-white">{text(machineProject.name, projectName || projectId)}</h2>
                      <p className="mt-2 text-sm text-slate-400">Phase: {text(status.current_phase || readiness.current_phase)}</p>
                    </div>
                    <Link href="/engineering"><Button variant="outline">Open Project inspector</Button></Link>
                  </div>
                  <div className="mt-5 grid gap-3 sm:grid-cols-4">
                    <div className="rounded-xl border border-white/10 bg-black/10 p-4"><div className="text-[10px] uppercase tracking-[0.16em] text-slate-500">Sources</div><div className="mt-2 text-2xl font-semibold text-white">{sourceCount}</div></div>
                    <div className="rounded-xl border border-white/10 bg-black/10 p-4"><div className="text-[10px] uppercase tracking-[0.16em] text-slate-500">Blockers</div><div className="mt-2 text-2xl font-semibold text-white">{blockers.length}</div></div>
                    <div className="rounded-xl border border-white/10 bg-black/10 p-4"><div className="text-[10px] uppercase tracking-[0.16em] text-slate-500">Advisories</div><div className="mt-2 text-2xl font-semibold text-white">{advisories.length}</div></div>
                    <div className="rounded-xl border border-white/10 bg-black/10 p-4"><div className="text-[10px] uppercase tracking-[0.16em] text-slate-500">Next actions</div><div className="mt-2 text-2xl font-semibold text-white">{nextActions.length}</div></div>
                  </div>
                </div>

                <div className="space-y-6 p-5">
                  {nextActions[0] ? (
                    <div className="rounded-2xl border border-cyan-300/20 bg-cyan-300/[0.07] p-5">
                      <div className="text-[10px] font-semibold uppercase tracking-[0.2em] text-cyan-200">Recommended next action</div>
                      <div className="mt-2 text-lg font-semibold text-white">{text(nextActions[0].title)}</div>
                      <div className="mt-2 text-sm leading-6 text-slate-300">{text(nextActions[0].instruction)}</div>
                    </div>
                  ) : null}

                  <div>
                    <h3 className="text-sm font-semibold text-white">Blocking issues</h3>
                    <div className="mt-3 space-y-2">
                      {blockers.length ? blockers.slice(0, 12).map((blocker, index) => (
                        <div key={text(blocker.blocker_id, String(index))} className="flex items-start gap-3 rounded-xl border border-rose-300/15 bg-rose-300/[0.05] p-3">
                          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-rose-200" />
                          <div><div className="text-sm text-white">{text(blocker.message)}</div><div className="mt-1 text-[11px] uppercase tracking-[0.16em] text-slate-500">{text(blocker.category)}</div></div>
                        </div>
                      )) : <div className="rounded-xl border border-emerald-300/15 bg-emerald-300/[0.05] p-4 text-sm text-emerald-100">No canonical blockers reported. Human release review is still required.</div>}
                    </div>
                  </div>

                  <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
                    <Gate label="Fabrication" allowed={readiness.fabrication_authorized === true} />
                    <Gate label="Firmware flash" allowed={readiness.flash_authorized === true} />
                    <Gate label="Power-on" allowed={readiness.power_on_authorized === true} />
                    <Gate label="Motion" allowed={readiness.motion_authorized === true} />
                    <Gate label="Release" allowed={readiness.release_authorized === true} />
                  </div>
                </div>
              </div>
            )}
          </section>
        </div>
      </div>
    </main>
  );
}

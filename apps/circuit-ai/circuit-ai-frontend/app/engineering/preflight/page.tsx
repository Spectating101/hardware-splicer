'use client';

import { useMemo, useRef, useState } from 'react';
import type { ChangeEvent } from 'react';
import Link from 'next/link';
import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  ChevronRight,
  ClipboardList,
  Download,
  LoaderCircle,
  Play,
  Plus,
  Route,
  ShieldCheck,
  Sparkles,
  Trash2,
  Upload,
  Wrench,
  XCircle,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { usePageTitle } from '@/components/use-page-title';
import { getProxyErrorMessage, isProxyFailure, readJsonPayload, type ProxyErrorPayload } from '@/lib/proxy-client';

type JsonRecord = Record<string, unknown>;
type PartRow = { name: string; type: string; quantity: number };
type SourceRow = JsonRecord & { source_id?: string; source_type?: string; uri?: string };
type PlanResponse = { ok?: boolean; plan?: JsonRecord; engineering_readiness?: JsonRecord; machine_project?: JsonRecord; operator_guide?: JsonRecord };

const demoParts: PartRow[] = [
  { name: 'Raspberry Pi 5', type: 'computer', quantity: 1 },
  { name: 'ESP32-S3 controller', type: 'microcontroller', quantity: 1 },
  { name: '12 V geared motor with encoder', type: 'dc_motor', quantity: 2 },
  { name: 'Dual-channel motor driver', type: 'motor_driver', quantity: 1 },
  { name: 'RPLIDAR A1', type: 'lidar', quantity: 1 },
  { name: 'BNO085 IMU', type: 'imu', quantity: 1 },
  { name: '12 V 8 Ah battery with BMS', type: 'power_source', quantity: 1 },
  { name: 'Emergency motor-power switch', type: 'safety_switch', quantity: 1 },
];

const demoConstraints = {
  drive_type: 'differential_drive',
  maximum_width_mm: 500,
  target_runtime_min: 90,
  maximum_speed_mps: 0.4,
  payload_mass_kg: 0.5,
  threshold_height_mm: 15,
  battery_voltage_v: 12,
  battery_capacity_ah: 8,
  battery_usable_fraction: 0.8,
  continuous_power_w: 42,
  supply_current_limit_a: 20,
  peak_current_a: 12,
  emergency_stop_required: true,
  first_motion_current_limited: true,
};

const demoSources: SourceRow[] = [
  {
    source_id: 'linorobot2-repository',
    source_type: 'repository',
    uri: 'https://github.com/linorobot/linorobot2',
    revision: 'retrieval-required',
    authority_ceiling: 'declared',
    claims: [
      { subject_id: 'reference-rover', predicate: 'reference_architecture', value: 'ROS 2 differential-drive navigation stack' },
    ],
  },
  {
    source_id: 'turtlebot3-hardware-reference',
    source_type: 'manual',
    uri: 'https://emanual.robotis.com/docs/en/platform/turtlebot3/overview/',
    revision: 'retrieval-required',
    authority_ceiling: 'declared',
    claims: [
      { subject_id: 'reference-rover', predicate: 'assembly_reference', value: 'modular indoor mobile robot architecture' },
    ],
  },
  {
    source_id: 'assembly-video-observation',
    source_type: 'video',
    uri: 'https://www.youtube.com/results?search_query=linorobot2+assembly',
    revision: 'unresolved-video-selection',
    authority_ceiling: 'observed',
    claims: [
      { subject_id: 'reference-rover', predicate: 'observed_assembly_pattern', value: 'video requires exact selection and timestamps' },
    ],
  },
];

const tabs = ['Summary', 'Sources', 'Topology', 'Closure', 'Guide', 'Raw'] as const;
type Tab = typeof tabs[number];

function rows(value: unknown): JsonRecord[] {
  return Array.isArray(value) ? value.filter((row): row is JsonRecord => Boolean(row) && typeof row === 'object' && !Array.isArray(row)) : [];
}

function record(value: unknown): JsonRecord {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value) ? value as JsonRecord : {};
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

function Metric({ label, value, note }: { label: string; value: string | number; note?: string }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-white/[0.035] p-4">
      <div className="text-[10px] font-semibold uppercase tracking-[0.2em] text-slate-500">{label}</div>
      <div className="mt-2 text-2xl font-semibold text-white">{value}</div>
      {note ? <div className="mt-1 text-xs text-slate-400">{note}</div> : null}
    </div>
  );
}

export default function EngineeringPreflightPage() {
  usePageTitle('HS Preflight | Hardware Splicer');
  const sourceFileRef = useRef<HTMLInputElement>(null);
  const [projectName, setProjectName] = useState('');
  const [goal, setGoal] = useState('');
  const [mode, setMode] = useState('greenfield');
  const [parts, setParts] = useState<PartRow[]>([{ name: '', type: '', quantity: 1 }]);
  const [constraintsText, setConstraintsText] = useState('{}');
  const [sources, setSources] = useState<SourceRow[]>([]);
  const [sourcesText, setSourcesText] = useState('[]');
  const [activeTab, setActiveTab] = useState<Tab>('Summary');
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [plan, setPlan] = useState<JsonRecord | null>(null);

  const readiness = record(plan?.engineering_readiness);
  const status = record(plan?.engineering_status);
  const blockers = rows(status.blockers);
  const advisories = rows(status.advisories);
  const nextActions = rows(status.next_actions);
  const sourceGraph = record(plan?.engineering_source_graph);
  const topology = record(plan?.robot_topology);
  const closure = record(plan?.manufacturing_closure);
  const guide = record(plan?.operator_guide);
  const sourceRows = rows(sourceGraph.sources);
  const jointRows = rows(topology.joints);
  const actuatorRows = rows(topology.actuators);
  const closureChecks = rows(closure.checks);
  const guideSteps = rows(guide.steps);
  const closureFailures = closureChecks.filter((row) => row.status !== 'pass');

  const sourceSummary = useMemo(() => {
    const counts = new Map<string, number>();
    sourceRows.forEach((row) => {
      const key = text(row.source_type, 'other');
      counts.set(key, (counts.get(key) || 0) + 1);
    });
    return [...counts.entries()].sort((a, b) => b[1] - a[1]);
  }, [sourceRows]);

  function loadDemo() {
    setProjectName('reference-rich-indoor-inspection-rover');
    setGoal('Prepare a repairable indoor differential-drive inspection rover that fits through 70 cm doors, crosses a 15 mm threshold, carries a 500 g sensor payload, runs for at least 90 minutes, maps with 2D lidar, and supports ROS 2 autonomous navigation.');
    setMode('greenfield');
    setParts(demoParts);
    setConstraintsText(JSON.stringify(demoConstraints, null, 2));
    setSources(demoSources);
    setSourcesText(JSON.stringify(demoSources, null, 2));
    setPlan(null);
    setError(null);
    setActiveTab('Summary');
  }

  function updatePart(index: number, field: keyof PartRow, value: string) {
    setParts((current) => current.map((row, rowIndex) => rowIndex === index
      ? { ...row, [field]: field === 'quantity' ? Math.max(1, Number(value) || 1) : value }
      : row));
  }

  function parseSourcesFromEditor() {
    try {
      const parsed = JSON.parse(sourcesText);
      if (!Array.isArray(parsed)) throw new Error('Sources JSON must be an array.');
      setSources(parsed as SourceRow[]);
      setError(null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Sources JSON is invalid.');
    }
  }

  async function importSourceFiles(event: ChangeEvent<HTMLInputElement>) {
    const files = Array.from(event.target.files || []);
    if (!files.length) return;
    const imported: SourceRow[] = [];
    for (const file of files) {
      try {
        const content = await file.text();
        const parsed = JSON.parse(content);
        if (Array.isArray(parsed)) imported.push(...parsed as SourceRow[]);
        else if (parsed && typeof parsed === 'object') imported.push(parsed as SourceRow);
      } catch {
        imported.push({
          source_id: file.name.replace(/[^a-zA-Z0-9_.-]+/g, '-').toLowerCase(),
          source_type: 'other',
          revision: 'local-file-unhashed',
          authority_ceiling: 'declared',
          metadata: { filename: file.name, import_error: 'File was not valid JSON; content was not transmitted.' },
        });
      }
    }
    const merged = [...sources, ...imported];
    setSources(merged);
    setSourcesText(JSON.stringify(merged, null, 2));
    event.target.value = '';
  }

  async function runPreflight() {
    setRunning(true);
    setError(null);
    try {
      if (!projectName.trim()) throw new Error('Project name is required.');
      if (!goal.trim()) throw new Error('Describe what the machine must do.');
      const constraints = JSON.parse(constraintsText || '{}');
      const sourcePayload = JSON.parse(sourcesText || '[]');
      if (!Array.isArray(sourcePayload)) throw new Error('Sources JSON must be an array.');
      const availableParts = parts.filter((row) => row.name.trim()).map((row) => ({
        name: row.name.trim(),
        type: row.type.trim() || 'component',
        quantity: row.quantity,
      }));
      const response = await fetch('/api/proxy/engineering/plan', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({
          intake: {
            project_name: projectName.trim(),
            goal: goal.trim(),
            mode,
            available_parts: availableParts,
            constraints,
          },
          engineering_sources: sourcePayload,
          declared_conflicts: [],
          skip_vision: true,
        }),
        cache: 'no-store',
      });
      const payload = await readJsonPayload<PlanResponse | ProxyErrorPayload>(response);
      if (!response.ok || isProxyFailure(payload)) {
        throw new Error(getProxyErrorMessage(payload, 'Hardware Splicer could not build the preflight plan.'));
      }
      const candidate = record((payload as PlanResponse).plan);
      if (!Object.keys(candidate).length) throw new Error('Hardware Splicer returned no plan.');
      setPlan(candidate);
      setActiveTab('Summary');
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Preflight failed.');
    } finally {
      setRunning(false);
    }
  }

  return (
    <main className="min-h-screen bg-[#040b14] text-slate-100">
      <div className="mx-auto max-w-[1500px] px-4 py-6 sm:px-6 lg:px-8">
        <div className="flex flex-col gap-5 border-b border-white/10 pb-6 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <Link href="/engineering" className="inline-flex items-center gap-2 text-xs font-medium text-slate-400 hover:text-white">
              <ArrowLeft className="h-3.5 w-3.5" /> Engineering workspace
            </Link>
            <div className="mt-4 flex items-center gap-3">
              <div className="rounded-2xl border border-cyan-300/20 bg-cyan-300/10 p-3 text-cyan-200"><ShieldCheck className="h-6 w-6" /></div>
              <div>
                <h1 className="text-2xl font-semibold text-white">HS Preflight</h1>
                <p className="mt-1 max-w-3xl text-sm leading-6 text-slate-400">Describe one physical system, attach its engineering sources, and receive a fail-closed readiness plan without editing internal schemas.</p>
              </div>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" onClick={loadDemo}><Sparkles className="mr-2 h-4 w-4" />Load rover demo</Button>
            <Button onClick={runPreflight} disabled={running}>
              {running ? <LoaderCircle className="mr-2 h-4 w-4 animate-spin" /> : <Play className="mr-2 h-4 w-4" />}
              Run preflight
            </Button>
          </div>
        </div>

        {error ? (
          <div className="mt-5 flex items-start gap-3 rounded-2xl border border-rose-300/20 bg-rose-300/10 p-4 text-sm text-rose-100">
            <XCircle className="mt-0.5 h-4 w-4 shrink-0" />
            <div>{error}</div>
          </div>
        ) : null}

        <div className="mt-6 grid gap-6 xl:grid-cols-[430px_minmax(0,1fr)]">
          <section className="space-y-5 rounded-3xl border border-white/10 bg-[#07111f] p-5">
            <div>
              <div className="text-xs font-semibold uppercase tracking-[0.2em] text-cyan-200">1 · Project brief</div>
              <label className="mt-4 block text-xs font-medium text-slate-300">Project name</label>
              <input value={projectName} onChange={(event) => setProjectName(event.target.value)} placeholder="inspection-rover-r1" className="mt-2 w-full rounded-xl border border-white/10 bg-[#040b14] px-3 py-2.5 text-sm text-white outline-none focus:border-cyan-300/40" />
              <label className="mt-4 block text-xs font-medium text-slate-300">What must this system do?</label>
              <textarea value={goal} onChange={(event) => setGoal(event.target.value)} rows={5} placeholder="Describe the mission, environment, payload, runtime, safety and success criteria." className="mt-2 w-full resize-y rounded-xl border border-white/10 bg-[#040b14] px-3 py-2.5 text-sm leading-6 text-white outline-none focus:border-cyan-300/40" />
              <label className="mt-4 block text-xs font-medium text-slate-300">Work mode</label>
              <select value={mode} onChange={(event) => setMode(event.target.value)} className="mt-2 w-full rounded-xl border border-white/10 bg-[#040b14] px-3 py-2.5 text-sm text-white outline-none focus:border-cyan-300/40">
                <option value="greenfield">New build</option>
                <option value="modify">Modification</option>
                <option value="repair">Repair / reconstruction</option>
                <option value="evolve">Field evolution</option>
              </select>
            </div>

            <div className="border-t border-white/10 pt-5">
              <div className="flex items-center justify-between">
                <div className="text-xs font-semibold uppercase tracking-[0.2em] text-cyan-200">2 · Available parts</div>
                <button type="button" onClick={() => setParts((current) => [...current, { name: '', type: '', quantity: 1 }])} className="inline-flex items-center gap-1 text-xs text-cyan-200 hover:text-white"><Plus className="h-3.5 w-3.5" />Add part</button>
              </div>
              <div className="mt-3 space-y-2">
                {parts.map((part, index) => (
                  <div key={index} className="grid grid-cols-[1fr_0.8fr_64px_32px] gap-2">
                    <input aria-label={`Part ${index + 1} name`} value={part.name} onChange={(event) => updatePart(index, 'name', event.target.value)} placeholder="Motor" className="min-w-0 rounded-lg border border-white/10 bg-[#040b14] px-2.5 py-2 text-xs text-white" />
                    <input aria-label={`Part ${index + 1} type`} value={part.type} onChange={(event) => updatePart(index, 'type', event.target.value)} placeholder="dc_motor" className="min-w-0 rounded-lg border border-white/10 bg-[#040b14] px-2.5 py-2 text-xs text-white" />
                    <input aria-label={`Part ${index + 1} quantity`} type="number" min="1" value={part.quantity} onChange={(event) => updatePart(index, 'quantity', event.target.value)} className="min-w-0 rounded-lg border border-white/10 bg-[#040b14] px-2 py-2 text-xs text-white" />
                    <button type="button" aria-label={`Remove part ${index + 1}`} onClick={() => setParts((current) => current.filter((_, rowIndex) => rowIndex !== index))} className="rounded-lg border border-white/10 text-slate-500 hover:border-rose-300/30 hover:text-rose-200"><Trash2 className="mx-auto h-3.5 w-3.5" /></button>
                  </div>
                ))}
              </div>
            </div>

            <div className="border-t border-white/10 pt-5">
              <div className="text-xs font-semibold uppercase tracking-[0.2em] text-cyan-200">3 · Constraints</div>
              <p className="mt-2 text-xs leading-5 text-slate-500">Use JSON for dimensions, voltage, runtime, payload, current limits and safety requirements. Unknown values may be omitted.</p>
              <textarea value={constraintsText} onChange={(event) => setConstraintsText(event.target.value)} rows={10} spellCheck={false} className="mt-3 w-full rounded-xl border border-white/10 bg-[#040b14] px-3 py-2.5 font-mono text-xs leading-5 text-slate-200 outline-none focus:border-cyan-300/40" />
            </div>

            <div className="border-t border-white/10 pt-5">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <div className="text-xs font-semibold uppercase tracking-[0.2em] text-cyan-200">4 · Sources</div>
                  <div className="mt-1 text-xs text-slate-500">{sources.length} parsed source records</div>
                </div>
                <div className="flex gap-2">
                  <input ref={sourceFileRef} type="file" multiple accept=".json,application/json" onChange={importSourceFiles} className="hidden" />
                  <button type="button" onClick={() => sourceFileRef.current?.click()} className="inline-flex items-center gap-1 rounded-lg border border-white/10 px-2.5 py-2 text-xs text-slate-300 hover:text-white"><Upload className="h-3.5 w-3.5" />Import JSON</button>
                  <button type="button" onClick={parseSourcesFromEditor} className="rounded-lg border border-white/10 px-2.5 py-2 text-xs text-slate-300 hover:text-white">Apply</button>
                </div>
              </div>
              <textarea value={sourcesText} onChange={(event) => setSourcesText(event.target.value)} rows={12} spellCheck={false} className="mt-3 w-full rounded-xl border border-white/10 bg-[#040b14] px-3 py-2.5 font-mono text-xs leading-5 text-slate-200 outline-none focus:border-cyan-300/40" />
              <p className="mt-2 text-[11px] leading-5 text-slate-500">Current UI imports structured JSON source descriptors. Binary CAD, PCB and media upload requires the next file-ingestion tranche; the interface does not pretend those bytes were processed.</p>
            </div>
          </section>

          <section className="min-w-0 rounded-3xl border border-white/10 bg-[#07111f]">
            {!plan ? (
              <div className="flex min-h-[720px] flex-col items-center justify-center px-6 text-center">
                <div className="rounded-3xl border border-cyan-300/20 bg-cyan-300/8 p-5 text-cyan-200"><ClipboardList className="h-10 w-10" /></div>
                <h2 className="mt-6 text-xl font-semibold text-white">No preflight result yet</h2>
                <p className="mt-3 max-w-xl text-sm leading-6 text-slate-400">Load the rover demo or enter a real project. Hardware Splicer will preserve uncertainty, generate a machine model, identify blockers and tell the operator what to do next.</p>
                <Button className="mt-6" onClick={loadDemo}><Sparkles className="mr-2 h-4 w-4" />Start with the rover demo</Button>
              </div>
            ) : (
              <div>
                <div className="border-b border-white/10 p-5">
                  <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                    <div>
                      <div className="flex flex-wrap items-center gap-2">
                        <span className={`rounded-full border px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] ${text(status.overall_status || readiness.status) === 'blocked' ? 'border-rose-300/20 bg-rose-300/10 text-rose-200' : 'border-amber-300/20 bg-amber-300/10 text-amber-200'}`}>{text(status.overall_status || readiness.status)}</span>
                        <span className="text-xs text-slate-500">Phase: {text(status.current_phase || readiness.current_phase)}</span>
                      </div>
                      <h2 className="mt-3 text-xl font-semibold text-white">{text(record(plan.machine_project).name, projectName)}</h2>
                    </div>
                    <Button variant="outline" onClick={() => downloadJson(`${projectName || 'hardware-splicer'}-preflight.json`, plan)}><Download className="mr-2 h-4 w-4" />Download report</Button>
                  </div>
                  <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                    <Metric label="Blocking issues" value={blockers.length} note={`${advisories.length} advisories`} />
                    <Metric label="Sources retained" value={sourceRows.length} note={`${rows(sourceGraph.conflicts).length} conflicts`} />
                    <Metric label="Robot topology" value={`${jointRows.length} joints`} note={`${actuatorRows.length} actuators`} />
                    <Metric label="Closure gaps" value={closureFailures.length} note={`${closureChecks.length} checks`} />
                  </div>
                </div>

                <div className="flex flex-wrap gap-1 border-b border-white/10 px-5 pt-3">
                  {tabs.map((tab) => (
                    <button key={tab} type="button" onClick={() => setActiveTab(tab)} className={`rounded-t-xl px-3 py-2.5 text-xs font-medium ${activeTab === tab ? 'bg-white/10 text-white' : 'text-slate-500 hover:text-slate-200'}`}>{tab}</button>
                  ))}
                </div>

                <div className="p-5">
                  {activeTab === 'Summary' ? (
                    <div className="space-y-5">
                      {nextActions[0] ? (
                        <div className="rounded-2xl border border-cyan-300/20 bg-cyan-300/8 p-5">
                          <div className="text-[10px] font-semibold uppercase tracking-[0.2em] text-cyan-200">Recommended next action</div>
                          <div className="mt-2 text-lg font-semibold text-white">{text(nextActions[0].title)}</div>
                          <div className="mt-2 text-sm leading-6 text-slate-300">{text(nextActions[0].instruction)}</div>
                          <div className="mt-3 inline-flex items-center gap-2 text-xs text-cyan-200">Priority {text(nextActions[0].priority)} <ChevronRight className="h-3.5 w-3.5" /></div>
                        </div>
                      ) : null}
                      <div>
                        <h3 className="text-sm font-semibold text-white">Blocking issues</h3>
                        <div className="mt-3 space-y-2">
                          {blockers.length ? blockers.slice(0, 12).map((blocker, index) => (
                            <div key={text(blocker.blocker_id, String(index))} className="flex items-start gap-3 rounded-xl border border-rose-300/15 bg-rose-300/[0.06] p-3">
                              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-rose-200" />
                              <div><div className="text-sm text-white">{text(blocker.message)}</div><div className="mt-1 text-[11px] uppercase tracking-[0.16em] text-slate-500">{text(blocker.category)}</div></div>
                            </div>
                          )) : <div className="flex items-center gap-2 rounded-xl border border-emerald-300/15 bg-emerald-300/[0.06] p-4 text-sm text-emerald-100"><CheckCircle2 className="h-4 w-4" />No canonical blockers reported. Human release review is still required.</div>}
                        </div>
                      </div>
                      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
                        {['fabrication_authorized', 'flash_authorized', 'power_on_authorized', 'motion_authorized', 'release_authorized'].map((key) => (
                          <div key={key} className="rounded-xl border border-white/10 bg-black/10 p-3"><div className="text-[10px] uppercase tracking-[0.16em] text-slate-500">{key.replaceAll('_', ' ')}</div><div className="mt-2 text-xs font-semibold text-slate-300">{readiness[key] === true ? 'Authorized' : 'Not authorized'}</div></div>
                        ))}
                      </div>
                    </div>
                  ) : null}

                  {activeTab === 'Sources' ? (
                    <div>
                      <div className="flex flex-wrap gap-2">{sourceSummary.map(([kind, count]) => <span key={kind} className="rounded-full border border-white/10 bg-white/[0.03] px-3 py-1 text-xs text-slate-300">{kind} · {count}</span>)}</div>
                      <div className="mt-4 space-y-2">{sourceRows.map((source, index) => <div key={text(source.source_id, String(index))} className="rounded-xl border border-white/10 p-4"><div className="flex flex-wrap items-center justify-between gap-2"><div className="font-mono text-xs text-cyan-200">{text(source.source_id)}</div><div className="text-[10px] uppercase tracking-[0.16em] text-slate-500">{text(source.authority_ceiling)} · {text(source.source_type)}</div></div><div className="mt-2 break-all text-xs text-slate-400">{text(source.uri)}</div><div className="mt-2 text-xs text-slate-500">Revision: {text(source.revision || source.content_hash || source.retrieved_at, 'unresolved')}</div></div>)}</div>
                    </div>
                  ) : null}

                  {activeTab === 'Topology' ? (
                    <div className="grid gap-5 lg:grid-cols-2">
                      <div><h3 className="flex items-center gap-2 text-sm font-semibold text-white"><Route className="h-4 w-4 text-cyan-200" />Joints</h3><div className="mt-3 space-y-2">{jointRows.map((joint, index) => <div key={text(joint.joint_id, String(index))} className="rounded-xl border border-white/10 p-3"><div className="text-sm font-medium text-white">{text(joint.name || joint.joint_id)}</div><div className="mt-1 text-xs text-slate-500">{text(joint.parent_link_id)} → {text(joint.child_link_id)} · {text(joint.joint_type)}</div></div>)}</div></div>
                      <div><h3 className="flex items-center gap-2 text-sm font-semibold text-white"><Wrench className="h-4 w-4 text-cyan-200" />Actuators</h3><div className="mt-3 space-y-2">{actuatorRows.map((actuator, index) => <div key={text(actuator.actuator_id, String(index))} className="rounded-xl border border-white/10 p-3"><div className="text-sm font-medium text-white">{text(actuator.name || actuator.actuator_id)}</div><div className="mt-1 text-xs text-slate-500">Channel: {text(actuator.firmware_channel_id)} · {text(actuator.actuator_type)}</div></div>)}</div></div>
                    </div>
                  ) : null}

                  {activeTab === 'Closure' ? (
                    <div className="space-y-2">{closureChecks.map((check, index) => { const passed = check.status === 'pass'; return <div key={text(check.check_id, String(index))} className={`flex items-start gap-3 rounded-xl border p-3 ${passed ? 'border-emerald-300/15 bg-emerald-300/[0.04]' : 'border-rose-300/15 bg-rose-300/[0.05]'}`}>{passed ? <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-200" /> : <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-rose-200" />}<div><div className="text-sm text-white">{text(check.message || check.check_id)}</div><div className="mt-1 text-xs text-slate-500">{text(check.check_id)} · {text(check.status)}</div></div></div>; })}</div>
                  ) : null}

                  {activeTab === 'Guide' ? (
                    <div className="space-y-3">{guideSteps.map((step, index) => <div key={text(step.step_id, String(index))} className="grid grid-cols-[36px_1fr] gap-3 rounded-xl border border-white/10 p-4"><div className="flex h-9 w-9 items-center justify-center rounded-full border border-cyan-300/20 bg-cyan-300/10 text-xs font-semibold text-cyan-100">{index + 1}</div><div><div className="text-sm font-semibold text-white">{text(step.title || step.name)}</div><div className="mt-2 text-xs leading-5 text-slate-400">{text(step.instruction || step.description)}</div>{Array.isArray(step.stop_conditions) && step.stop_conditions.length ? <div className="mt-2 text-xs text-rose-200">Stop: {step.stop_conditions.map(String).join(' • ')}</div> : null}</div></div>)}</div>
                  ) : null}

                  {activeTab === 'Raw' ? <pre className="max-h-[900px] overflow-auto whitespace-pre-wrap rounded-2xl border border-white/10 bg-[#040b14] p-4 text-xs leading-5 text-slate-300">{JSON.stringify(plan, null, 2)}</pre> : null}
                </div>
              </div>
            )}
          </section>
        </div>
      </div>
    </main>
  );
}

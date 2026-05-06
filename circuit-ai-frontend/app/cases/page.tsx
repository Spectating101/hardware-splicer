'use client';

import Link from 'next/link';
import { useCallback, useEffect, useMemo, useState, type FormEvent } from 'react';
import {
  AlertTriangle,
  BatteryCharging,
  CheckCircle2,
  CircleDollarSign,
  ClipboardList,
  FileCheck2,
  Gamepad2,
  Gauge,
  LoaderCircle,
  PlayCircle,
  RefreshCw,
  ShieldCheck,
  Target,
  Wrench,
  Zap,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { SiteFooter } from '@/components/site-footer';
import { SiteHeader } from '@/components/site-header';
import { usePageTitle } from '@/components/use-page-title';
import { getProxyErrorMessage, isProxyFailure, readJsonPayload, type ProxyErrorPayload } from '@/lib/proxy-client';

type LanePackPreview = {
  lane_id: string;
  label: string;
  status: string;
  positioning: string;
  best_for: string[];
  not_for: string[];
  case_templates: string[];
  evidence_prompt_count: number;
  measurement_count: number;
  launch_target?: {
    case_count?: number;
    review_completion?: number;
    successful_fix_rate?: number;
  };
};

type LanePacksResponse = {
  lane_packs?: {
    packs?: LanePackPreview[];
    recommended_launch_order?: string[];
  };
};

type CaseEvalCase = {
  case_id: string;
  title: string;
  verdict: 'solvable_now' | 'assistive_only' | 'not_ready' | string;
  workflow_score: number;
  blockers: string[];
  coverage?: {
    top_label?: string;
    coverage_level?: string;
    coverage?: number;
  };
  repair_guide?: {
    family?: string;
    family_label?: string;
    confidence?: number;
    safety_risk?: string;
    top_fault?: string;
    top_fault_name?: string;
    top_fault_likelihood?: number;
    diagnostic_step_count?: number;
  };
  playbook?: {
    pattern_label?: string;
    can_follow_score?: number;
    quality_gate_count?: number;
  };
  board_session?: {
    session_id?: string;
    route?: string;
    task_count?: number;
    capture_burden?: number;
    measurement_count_required?: number;
    first_tasks?: Array<{ type?: string; prompt?: string }>;
  };
  recommended_next_builds?: string[];
};

type CaseEvalResponse = {
  case_eval?: {
    summary?: {
      case_count?: number;
      solvable_now?: number;
      assistive_only?: number;
      not_ready?: number;
      average_workflow_score?: number;
    };
    cases?: CaseEvalCase[];
    next_builds?: string[];
  };
};

type CaseEvalSummary = NonNullable<CaseEvalResponse['case_eval']>['summary'];

type ValueTrial = {
  trial_id?: string;
  session_id?: string;
  verdict: 'value_proven' | 'value_likely' | 'not_valuable_yet' | 'plumbing_only' | string;
  value_score: number;
  evidence_gates?: Array<{ gate: string; passed: boolean; why: string }>;
  honesty_notes?: string[];
  assisted?: {
    capture_count?: number;
    measurement_count?: number;
    review_count?: number;
    outcome_count?: number;
    training_export_count?: number;
    time_saved_minutes?: number;
    value_recovered_usd?: number;
  };
  scorecard?: Array<{ dimension: string; score: number; weight: number }>;
};

type ValueTrialResponse = {
  value_trial?: ValueTrial;
};

type ValueBenchmarkResponse = {
  benchmark?: {
    summary?: {
      trial_count?: number;
      average_value_score?: number;
      value_proven?: number;
      value_likely?: number;
      plumbing_only?: number;
      measured_outcome_count?: number;
      value_readiness_score?: number;
    };
    next_actions?: string[];
  };
};

type SessionsResponse = {
  sessions?: Array<{
    session_id?: string;
    title?: string;
    route?: string;
    open_task_count?: number;
    metrics?: {
      open_task_count?: number;
      task_count?: number;
      capture_burden?: number;
    };
  }>;
};

const laneIcons: Record<string, LucideIcon> = {
  controller_input: Gamepad2,
  battery_charging: BatteryCharging,
  small_motor_usb: Zap,
};

const examples = {
  controller_input: {
    title: 'Xbox controller stick drift repair',
    device: 'Xbox controller',
    symptoms: 'stick drift\nthumbstick axis is unreliable\ncontroller input is intermittent',
    source: 'https://www.ifixit.com/Troubleshooting/Xbox_One_Controller/Xbox%2BOne%2BWireless%2BController%2BHas%2BMalfunctioning%2BThumbstick/444889',
  },
  battery_charging: {
    title: 'Electric toothbrush not charging',
    device: 'electric toothbrush charging dock',
    symptoms: 'not charging\nbattery does not hold charge\ncharging dock suspected',
    source: 'https://www.ifixit.com/Troubleshooting/Electric_Toothbrush/Not%2BCharging/564390',
  },
  small_motor_usb: {
    title: 'USB fan warms but motor will not spin',
    device: 'USB fan controller board',
    symptoms: 'warm board\nmotor will not spin\nno spin unless wire is wiggled',
    source: 'local board-in-hand case',
  },
};

function percent(value: number | undefined) {
  if (typeof value !== 'number' || Number.isNaN(value)) return 'N/A';
  return `${Math.round(value * 100)}%`;
}

function splitLines(value: string) {
  return value
    .split(/\n|;|,/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function verdictVariant(verdict: string) {
  if (verdict === 'solvable_now') return 'success';
  if (verdict === 'assistive_only') return 'warning';
  return 'error';
}

function valueVariant(verdict: string) {
  if (verdict === 'value_proven') return 'success';
  if (verdict === 'value_likely') return 'info';
  if (verdict === 'plumbing_only') return 'warning';
  return 'error';
}

async function readUiJson<T>(response: Response, fallback: string): Promise<T> {
  const payload = await readJsonPayload<T | ProxyErrorPayload>(response);
  if (!response.ok || isProxyFailure(payload)) {
    throw new Error(getProxyErrorMessage(payload as ProxyErrorPayload | null, fallback));
  }
  return payload as T;
}

export default function CasesPage() {
  usePageTitle('Cases | Circuit.AI');

  const [lanes, setLanes] = useState<LanePackPreview[]>([]);
  const [sessions, setSessions] = useState<SessionsResponse['sessions']>([]);
  const [selectedLane, setSelectedLane] = useState('controller_input');
  const [title, setTitle] = useState(examples.controller_input.title);
  const [deviceHint, setDeviceHint] = useState(examples.controller_input.device);
  const [symptoms, setSymptoms] = useState(examples.controller_input.symptoms);
  const [sourceUrl, setSourceUrl] = useState(examples.controller_input.source);
  const [caseResult, setCaseResult] = useState<CaseEvalCase | null>(null);
  const [summary, setSummary] = useState<CaseEvalSummary | null>(null);
  const [valueProof, setValueProof] = useState<ValueTrial | null>(null);
  const [valueBenchmark, setValueBenchmark] = useState<ValueBenchmarkResponse['benchmark'] | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [valueChecking, setValueChecking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const selectedPack = useMemo(
    () => lanes.find((lane) => lane.lane_id === selectedLane) ?? lanes[0],
    [lanes, selectedLane],
  );

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [laneResponse, sessionResponse, valueResponse] = await Promise.all([
        fetch('/api/proxy/repair/lane-packs', { cache: 'no-store' }),
        fetch('/api/proxy/board-sessions?limit=8', { cache: 'no-store' }),
        fetch('/api/proxy/repair/value-trials/benchmark', { cache: 'no-store' }),
      ]);
      const lanePayload = await readUiJson<LanePacksResponse>(laneResponse, 'Could not load repair lane packs.');
      const sessionPayload = await readUiJson<SessionsResponse>(sessionResponse, 'Could not load case sessions.');
      const valuePayload = await readUiJson<ValueBenchmarkResponse>(valueResponse, 'Could not load value benchmark.');
      setLanes(lanePayload.lane_packs?.packs ?? []);
      setSessions(sessionPayload.sessions ?? []);
      setValueBenchmark(valuePayload.benchmark ?? null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Could not load cases workbench.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const chooseLane = useCallback((laneId: string) => {
    setSelectedLane(laneId);
    const example = examples[laneId as keyof typeof examples];
    if (example) {
      setTitle(example.title);
      setDeviceHint(example.device);
      setSymptoms(example.symptoms);
      setSourceUrl(example.source);
    }
  }, []);

  const submitCase = useCallback(async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    setCaseResult(null);
    setValueProof(null);
    try {
      const caseId = `workbench_${Date.now().toString(36)}`;
      const response = await fetch('/api/proxy/repair/case-eval', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({
          commit_sessions: true,
          cases: [
            {
              case_id: caseId,
              title,
              device_hint: deviceHint,
              symptoms: splitLines(symptoms),
              source_url: sourceUrl,
              expected_lane: selectedLane,
              notes: `${selectedPack?.label ?? selectedLane} workbench case`,
            },
          ],
        }),
      });
      const payload = await readUiJson<CaseEvalResponse>(response, 'Could not evaluate and create case.');
      setSummary(payload.case_eval?.summary ?? null);
      setCaseResult(payload.case_eval?.cases?.[0] ?? null);
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Case creation failed.');
    } finally {
      setSubmitting(false);
    }
  }, [deviceHint, load, selectedLane, selectedPack?.label, sourceUrl, symptoms, title]);

  const checkValueProof = useCallback(async () => {
    if (!caseResult) return;
    setValueChecking(true);
    setError(null);
    try {
      const response = await fetch('/api/proxy/repair/value-trials', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({
          session_id: caseResult.board_session?.session_id ?? `eval_${caseResult.case_id}`,
          case_id: caseResult.case_id,
          title: caseResult.title,
          lane_id: selectedLane,
          source_url: sourceUrl,
          symptoms: splitLines(symptoms),
          workflow_score: caseResult.workflow_score,
          case_verdict: caseResult.verdict,
          baseline: {
            method: 'manual search or ad-hoc repair',
            estimated_time_minutes: 60,
            confidence: 0.25,
            expected_value_usd: 25,
          },
        }),
      });
      const payload = await readUiJson<ValueTrialResponse>(response, 'Could not score value proof.');
      setValueProof(payload.value_trial ?? null);
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Value scoring failed.');
    } finally {
      setValueChecking(false);
    }
  }, [caseResult, load, selectedLane, sourceUrl, symptoms]);

  const metrics = [
    { label: 'Pilot lanes', value: lanes.length || 'N/A', icon: Target },
    { label: 'Recent sessions', value: sessions?.length ?? 0, icon: ClipboardList },
    { label: 'Last score', value: percent(caseResult?.workflow_score), icon: Gauge },
    { label: 'Last verdict', value: caseResult?.verdict?.replace(/_/g, ' ') ?? 'N/A', icon: ShieldCheck },
    { label: 'Value ready', value: percent(valueBenchmark?.summary?.value_readiness_score), icon: CircleDollarSign },
  ];

  return (
    <div className="min-h-screen bg-[#090f18] text-slate-100">
      <SiteHeader />
      <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        <section className="mb-6 rounded-lg border border-white/10 bg-white/[0.02] p-5">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <div className="mb-3 flex flex-wrap gap-2">
                <Badge variant="info">case workbench</Badge>
                <Badge variant="default">pilot lanes</Badge>
                <Badge variant="default">board session</Badge>
              </div>
              <h1 className="text-3xl font-semibold text-white">Repair case workbench</h1>
              <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-400">
                Start with the repair lanes that are strongest today, create a persistent case, then work the evidence queue.
              </p>
            </div>
            <Button
              onClick={() => void load()}
              disabled={loading}
              className="rounded-lg border border-white/10 bg-white/[0.04] text-white hover:bg-white/[0.08]"
            >
              {loading ? <LoaderCircle className="mr-2 h-4 w-4 animate-spin" /> : <RefreshCw className="mr-2 h-4 w-4" />}
              Refresh
            </Button>
          </div>
        </section>

        {error ? (
          <section className="mb-6 rounded-lg border border-rose-400/40 bg-rose-500/10 p-4 text-sm text-rose-100">
            {error}
          </section>
        ) : null}

        <section className="mb-6 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          {metrics.map(({ label, value, icon: MetricIcon }) => (
            <div key={label} className="rounded-lg border border-white/10 bg-white/[0.02] p-4">
              <div className="flex items-center justify-between gap-3">
                <div className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">{label}</div>
                <MetricIcon className="h-4 w-4 text-cyan-200" />
              </div>
              <div className="mt-3 text-2xl font-semibold text-white">{String(value)}</div>
            </div>
          ))}
        </section>

        <div className="grid gap-6 lg:grid-cols-[340px_minmax(0,1fr)_360px]">
          <section className="space-y-3">
            {lanes.map((lane) => {
              const LaneIcon = laneIcons[lane.lane_id] ?? Wrench;
              const active = selectedLane === lane.lane_id;
              return (
                <button
                  key={lane.lane_id}
                  type="button"
                  onClick={() => chooseLane(lane.lane_id)}
                  className={`w-full rounded-lg border p-4 text-left transition-colors ${
                    active ? 'border-cyan-300/60 bg-cyan-300/10' : 'border-white/10 bg-white/[0.02] hover:bg-white/[0.05]'
                  }`}
                >
                  <div className="flex items-start gap-3">
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-white/10 text-cyan-100">
                      <LaneIcon className="h-5 w-5" />
                    </div>
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <div className="font-semibold text-white">{lane.label}</div>
                        <Badge variant="success">{lane.status.replace(/_/g, ' ')}</Badge>
                      </div>
                      <p className="mt-2 text-sm leading-6 text-slate-400">{lane.positioning}</p>
                      <div className="mt-3 flex flex-wrap gap-2 text-xs text-slate-500">
                        <span>{lane.evidence_prompt_count} evidence</span>
                        <span>{lane.measurement_count} measurements</span>
                      </div>
                    </div>
                  </div>
                </button>
              );
            })}
          </section>

          <section className="rounded-lg border border-white/10 bg-white/[0.02] p-5">
            <form onSubmit={submitCase} className="space-y-4">
              <div>
                <label className="mb-2 block text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Case title</label>
                <input
                  value={title}
                  onChange={(event) => setTitle(event.target.value)}
                  className="h-11 w-full rounded-md border border-white/10 bg-black/30 px-3 text-sm text-white outline-none placeholder:text-slate-600 focus:border-cyan-300/60"
                  required
                />
              </div>
              <div className="grid gap-4 md:grid-cols-2">
                <div>
                  <label className="mb-2 block text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Device</label>
                  <input
                    value={deviceHint}
                    onChange={(event) => setDeviceHint(event.target.value)}
                    className="h-11 w-full rounded-md border border-white/10 bg-black/30 px-3 text-sm text-white outline-none placeholder:text-slate-600 focus:border-cyan-300/60"
                    required
                  />
                </div>
                <div>
                  <label className="mb-2 block text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Source</label>
                  <input
                    value={sourceUrl}
                    onChange={(event) => setSourceUrl(event.target.value)}
                    className="h-11 w-full rounded-md border border-white/10 bg-black/30 px-3 text-sm text-white outline-none placeholder:text-slate-600 focus:border-cyan-300/60"
                  />
                </div>
              </div>
              <div>
                <label className="mb-2 block text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Symptoms</label>
                <textarea
                  value={symptoms}
                  onChange={(event) => setSymptoms(event.target.value)}
                  rows={6}
                  className="w-full resize-none rounded-md border border-white/10 bg-black/30 px-3 py-2 text-sm leading-6 text-white outline-none placeholder:text-slate-600 focus:border-cyan-300/60"
                  required
                />
              </div>
              <Button
                type="submit"
                disabled={submitting || !title.trim() || !deviceHint.trim() || !symptoms.trim()}
                className="w-full rounded-lg bg-cyan-300 text-slate-950 hover:bg-cyan-200"
              >
                {submitting ? <LoaderCircle className="mr-2 h-4 w-4 animate-spin" /> : <PlayCircle className="mr-2 h-4 w-4" />}
                Create case
              </Button>
            </form>

            {caseResult ? (
              <div className="mt-6 rounded-lg border border-white/10 bg-black/20 p-4">
                <div className="mb-3 flex flex-wrap items-center gap-2">
                  <Badge variant={verdictVariant(caseResult.verdict)}>{caseResult.verdict.replace(/_/g, ' ')}</Badge>
                  <Badge variant="default">{percent(caseResult.workflow_score)}</Badge>
                  <Badge variant={caseResult.repair_guide?.safety_risk === 'high' ? 'warning' : 'success'}>
                    {caseResult.repair_guide?.safety_risk ?? 'risk unknown'}
                  </Badge>
                </div>
                <h2 className="text-xl font-semibold text-white">{caseResult.repair_guide?.top_fault_name ?? caseResult.title}</h2>
                <p className="mt-2 text-sm leading-6 text-slate-400">
                  {caseResult.repair_guide?.family_label ?? caseResult.coverage?.top_label ?? 'Repair case'}
                </p>
                {caseResult.blockers?.length ? (
                  <div className="mt-4 rounded-md border border-amber-300/30 bg-amber-300/10 p-3">
                    <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-amber-100">
                      <AlertTriangle className="h-4 w-4" />
                      Blockers
                    </div>
                    <div className="space-y-1">
                      {caseResult.blockers.map((blocker) => (
                        <p key={blocker} className="text-sm leading-6 text-amber-50/80">{blocker.replace(/^hard:\s*/, '')}</p>
                      ))}
                    </div>
                  </div>
                ) : null}
                <div className="mt-4 grid gap-3 md:grid-cols-3">
                  <div className="rounded-md border border-white/10 bg-white/[0.02] p-3">
                    <div className="text-xs text-slate-500">Tasks</div>
                    <div className="mt-1 text-lg font-semibold text-white">{caseResult.board_session?.task_count ?? 0}</div>
                  </div>
                  <div className="rounded-md border border-white/10 bg-white/[0.02] p-3">
                    <div className="text-xs text-slate-500">Captures</div>
                    <div className="mt-1 text-lg font-semibold text-white">{caseResult.board_session?.capture_burden ?? 0}</div>
                  </div>
                  <div className="rounded-md border border-white/10 bg-white/[0.02] p-3">
                    <div className="text-xs text-slate-500">Measurements</div>
                    <div className="mt-1 text-lg font-semibold text-white">{caseResult.board_session?.measurement_count_required ?? 0}</div>
                  </div>
                </div>
                <div className="mt-4 space-y-2">
                  {(caseResult.board_session?.first_tasks ?? []).slice(0, 5).map((task) => (
                    <div key={`${task.type}-${task.prompt}`} className="rounded-md border border-white/10 bg-black/20 p-3">
                      <Badge variant={task.type === 'measurement' ? 'warning' : task.type === 'capture' ? 'info' : 'default'}>
                        {task.type ?? 'task'}
                      </Badge>
                      <p className="mt-2 text-sm leading-6 text-slate-200">{task.prompt}</p>
                    </div>
                  ))}
                </div>
                <div className="mt-4 flex flex-wrap gap-2">
                  <Button asChild className="rounded-lg bg-emerald-300 text-slate-950 hover:bg-emerald-200">
                    <Link href="/review">
                      <ClipboardList className="mr-2 h-4 w-4" />
                      Review queue
                    </Link>
                  </Button>
                  <Button asChild className="rounded-lg border border-white/10 bg-white/[0.04] text-white hover:bg-white/[0.08]">
                    <Link href="/repair">
                      <Wrench className="mr-2 h-4 w-4" />
                      Repair guide
                    </Link>
                  </Button>
                  <Button
                    type="button"
                    onClick={() => void checkValueProof()}
                    disabled={valueChecking}
                    className="rounded-lg border border-white/10 bg-white/[0.04] text-white hover:bg-white/[0.08]"
                  >
                    {valueChecking ? <LoaderCircle className="mr-2 h-4 w-4 animate-spin" /> : <FileCheck2 className="mr-2 h-4 w-4" />}
                    Value proof
                  </Button>
                </div>
                {valueProof ? (
                  <div className="mt-4 rounded-lg border border-white/10 bg-black/20 p-4">
                    <div className="mb-3 flex flex-wrap items-center gap-2">
                      <Badge variant={valueVariant(valueProof.verdict)}>{valueProof.verdict.replace(/_/g, ' ')}</Badge>
                      <Badge variant="default">{percent(valueProof.value_score)}</Badge>
                      <Badge variant="default">{valueProof.assisted?.measurement_count ?? 0} measurements</Badge>
                      <Badge variant="default">{valueProof.assisted?.outcome_count ?? 0} outcomes</Badge>
                    </div>
                    <div className="grid gap-2 md:grid-cols-3">
                      <div className="rounded-md border border-white/10 bg-white/[0.02] p-3">
                        <div className="text-xs text-slate-500">Saved time</div>
                        <div className="mt-1 text-lg font-semibold text-white">{valueProof.assisted?.time_saved_minutes ?? 0}m</div>
                      </div>
                      <div className="rounded-md border border-white/10 bg-white/[0.02] p-3">
                        <div className="text-xs text-slate-500">Recovered</div>
                        <div className="mt-1 text-lg font-semibold text-white">${valueProof.assisted?.value_recovered_usd ?? 0}</div>
                      </div>
                      <div className="rounded-md border border-white/10 bg-white/[0.02] p-3">
                        <div className="text-xs text-slate-500">Exports</div>
                        <div className="mt-1 text-lg font-semibold text-white">{valueProof.assisted?.training_export_count ?? 0}</div>
                      </div>
                    </div>
                    <div className="mt-3 space-y-2">
                      {(valueProof.evidence_gates ?? []).filter((gate) => !gate.passed).slice(0, 4).map((gate) => (
                        <div key={gate.gate} className="rounded-md border border-amber-300/30 bg-amber-300/10 p-3 text-sm text-amber-50/90">
                          {gate.why}
                        </div>
                      ))}
                      {!(valueProof.evidence_gates ?? []).some((gate) => !gate.passed) ? (
                        <div className="rounded-md border border-emerald-300/30 bg-emerald-300/10 p-3 text-sm text-emerald-50/90">
                          All value gates passed.
                        </div>
                      ) : null}
                    </div>
                    {valueProof.honesty_notes?.length ? (
                      <div className="mt-3 space-y-2">
                        {valueProof.honesty_notes.slice(0, 3).map((note) => (
                          <p key={note} className="text-sm leading-6 text-slate-400">{note}</p>
                        ))}
                      </div>
                    ) : null}
                  </div>
                ) : null}
              </div>
            ) : null}
          </section>

          <aside className="space-y-4">
            <section className="rounded-lg border border-white/10 bg-white/[0.02] p-4">
              <div className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                <CheckCircle2 className="h-4 w-4" />
                Lane scope
              </div>
              <div className="space-y-3">
                {(selectedPack?.best_for ?? []).map((item) => (
                  <p key={item} className="text-sm leading-6 text-slate-300">{item}</p>
                ))}
              </div>
              <div className="mt-4 border-t border-white/10 pt-4">
                <div className="mb-2 text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Hold back</div>
                <div className="space-y-2">
                  {(selectedPack?.not_for ?? []).slice(0, 4).map((item) => (
                    <p key={item} className="text-sm leading-6 text-slate-400">{item}</p>
                  ))}
                </div>
              </div>
            </section>

            <section className="rounded-lg border border-white/10 bg-white/[0.02] p-4">
              <div className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                <Target className="h-4 w-4" />
                Pilot target
              </div>
              <div className="grid grid-cols-3 gap-2">
                <div className="rounded-md border border-white/10 bg-black/20 p-3">
                  <div className="text-xs text-slate-500">Cases</div>
                  <div className="mt-1 text-lg font-semibold text-white">{selectedPack?.launch_target?.case_count ?? 0}</div>
                </div>
                <div className="rounded-md border border-white/10 bg-black/20 p-3">
                  <div className="text-xs text-slate-500">Review</div>
                  <div className="mt-1 text-lg font-semibold text-white">{percent(selectedPack?.launch_target?.review_completion)}</div>
                </div>
                <div className="rounded-md border border-white/10 bg-black/20 p-3">
                  <div className="text-xs text-slate-500">Fix</div>
                  <div className="mt-1 text-lg font-semibold text-white">{percent(selectedPack?.launch_target?.successful_fix_rate)}</div>
                </div>
              </div>
            </section>

            <section className="rounded-lg border border-white/10 bg-white/[0.02] p-4">
              <div className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                <ClipboardList className="h-4 w-4" />
                Recent cases
              </div>
              <div className="space-y-2">
                {(sessions ?? []).slice(0, 6).map((session) => (
                  <div key={session.session_id} className="rounded-md border border-white/10 bg-black/20 p-3">
                    <div className="truncate text-sm font-semibold text-white">{session.title || session.session_id}</div>
                    <div className="mt-1 text-xs text-slate-500">
                      {session.route ?? 'repair'} · {session.open_task_count ?? session.metrics?.open_task_count ?? 0} open
                    </div>
                  </div>
                ))}
                {!sessions?.length && !loading ? <p className="text-sm text-slate-500">No saved cases yet.</p> : null}
              </div>
            </section>

            {summary ? (
              <section className="rounded-lg border border-white/10 bg-white/[0.02] p-4">
                <div className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                  <Gauge className="h-4 w-4" />
                  Last run
                </div>
                <div className="space-y-2 text-sm text-slate-300">
                  <p>{summary.solvable_now ?? 0} solvable now</p>
                  <p>{summary.assistive_only ?? 0} assistive only</p>
                  <p>{summary.not_ready ?? 0} not ready</p>
                </div>
              </section>
            ) : null}

            <section className="rounded-lg border border-white/10 bg-white/[0.02] p-4">
              <div className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                <CircleDollarSign className="h-4 w-4" />
                Value proof
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div className="rounded-md border border-white/10 bg-black/20 p-3">
                  <div className="text-xs text-slate-500">Trials</div>
                  <div className="mt-1 text-lg font-semibold text-white">{valueBenchmark?.summary?.trial_count ?? 0}</div>
                </div>
                <div className="rounded-md border border-white/10 bg-black/20 p-3">
                  <div className="text-xs text-slate-500">Measured</div>
                  <div className="mt-1 text-lg font-semibold text-white">{valueBenchmark?.summary?.measured_outcome_count ?? 0}</div>
                </div>
                <div className="rounded-md border border-white/10 bg-black/20 p-3">
                  <div className="text-xs text-slate-500">Proven</div>
                  <div className="mt-1 text-lg font-semibold text-white">{valueBenchmark?.summary?.value_proven ?? 0}</div>
                </div>
                <div className="rounded-md border border-white/10 bg-black/20 p-3">
                  <div className="text-xs text-slate-500">Plumbing</div>
                  <div className="mt-1 text-lg font-semibold text-white">{valueBenchmark?.summary?.plumbing_only ?? 0}</div>
                </div>
              </div>
            </section>
          </aside>
        </div>
      </main>
      <SiteFooter />
    </div>
  );
}

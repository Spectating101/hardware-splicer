'use client';

import { useCallback, useEffect, useMemo, useState, type FormEvent } from 'react';
import {
  AlertTriangle,
  Camera,
  CheckCircle2,
  ClipboardList,
  Database,
  Download,
  LoaderCircle,
  RefreshCw,
  Ruler,
  Save,
  ShieldCheck,
  Target,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { SiteFooter } from '@/components/site-footer';
import { SiteHeader } from '@/components/site-header';
import { usePageTitle } from '@/components/use-page-title';
import { getProxyErrorMessage, isProxyFailure, readJsonPayload, type ProxyErrorPayload } from '@/lib/proxy-client';

type SessionPreview = {
  session_id?: string;
  title?: string;
  route?: string;
  status?: string;
  device_hint?: string;
  updated_at?: string;
  open_task_count?: number;
  review_count?: number;
  training_export_count?: number;
  certainty?: {
    overall?: {
      level?: string;
      score?: number;
    };
  };
  metrics?: {
    task_count?: number;
    open_task_count?: number;
    capture_burden?: number;
    measurement_count_required?: number;
    certainty_level?: string;
    certainty_score?: number;
  };
};

type ReviewTask = {
  task_id: string;
  type: string;
  prompt: string;
  priority?: number;
  status?: string;
  source?: string;
  session_id?: string;
  session_title?: string;
  route?: string;
  usable_for?: string[];
  certainty?: {
    level?: string;
    score?: number;
  };
};

type BenchmarkReport = {
  summary?: {
    session_count?: number;
    open_task_count?: number;
    resolved_task_count?: number;
    review_completion?: number;
    avg_evidence_tasks_per_session?: number;
    avg_capture_burden_per_session?: number;
    training_export_count?: number;
    launch_readiness_score?: number;
  };
  next_actions?: string[];
  competitive_scorecard?: Array<{
    dimension?: string;
    metric?: string;
    current?: unknown;
    target?: string;
  }>;
};

type SessionsResponse = { sessions?: SessionPreview[] };
type QueueResponse = { tasks?: ReviewTask[] };
type BenchmarkResponse = { benchmark?: BenchmarkReport };

function percent(value: number | undefined) {
  if (typeof value !== 'number' || Number.isNaN(value)) return 'N/A';
  return `${Math.round(value * 100)}%`;
}

function taskVariant(type: string) {
  if (type === 'measurement') return 'warning';
  if (type === 'capture') return 'info';
  if (type === 'review') return 'success';
  if (type === 'reference') return 'processing';
  return 'default';
}

async function readUiJson<T>(response: Response, fallback: string): Promise<T> {
  const payload = await readJsonPayload<T | ProxyErrorPayload>(response);
  if (!response.ok || isProxyFailure(payload)) {
    throw new Error(getProxyErrorMessage(payload as ProxyErrorPayload | null, fallback));
  }
  return payload as T;
}

export default function ReviewPage() {
  usePageTitle('Review Queue | Circuit.AI');

  const [sessions, setSessions] = useState<SessionPreview[]>([]);
  const [tasks, setTasks] = useState<ReviewTask[]>([]);
  const [benchmark, setBenchmark] = useState<BenchmarkReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [actioning, setActioning] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selectedSessionId, setSelectedSessionId] = useState('');
  const [captureFile, setCaptureFile] = useState<File | null>(null);
  const [captureKind, setCaptureKind] = useState('marking_closeup');
  const [captureNotes, setCaptureNotes] = useState('');
  const [measurementTarget, setMeasurementTarget] = useState('');
  const [measurementValue, setMeasurementValue] = useState('');
  const [measurementUnit, setMeasurementUnit] = useState('');
  const [outcomeDecision, setOutcomeDecision] = useState('repaired');
  const [outcomeValue, setOutcomeValue] = useState('');
  const [outcomeMinutes, setOutcomeMinutes] = useState('');
  const [closeOutcome, setCloseOutcome] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [sessionResponse, queueResponse, benchmarkResponse] = await Promise.all([
        fetch('/api/proxy/board-sessions?limit=30', { cache: 'no-store' }),
        fetch('/api/proxy/board-sessions/review-queue?limit=80', { cache: 'no-store' }),
        fetch('/api/proxy/board-sessions/benchmark', { cache: 'no-store' }),
      ]);
      const sessionPayload = await readUiJson<SessionsResponse>(sessionResponse, 'Could not load board sessions.');
      const queuePayload = await readUiJson<QueueResponse>(queueResponse, 'Could not load review queue.');
      const benchmarkPayload = await readUiJson<BenchmarkResponse>(benchmarkResponse, 'Could not load benchmark.');
      setSessions(sessionPayload.sessions ?? []);
      setTasks(queuePayload.tasks ?? []);
      setBenchmark(benchmarkPayload.benchmark ?? null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Review queue failed.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (!selectedSessionId && sessions[0]?.session_id) {
      setSelectedSessionId(sessions[0].session_id);
    }
  }, [selectedSessionId, sessions]);

  const grouped = useMemo(() => {
    const bySession = new Map<string, ReviewTask[]>();
    for (const task of tasks) {
      const key = task.session_id || 'unknown';
      bySession.set(key, [...(bySession.get(key) ?? []), task]);
    }
    return [...bySession.entries()];
  }, [tasks]);

  const markTask = useCallback(async (task: ReviewTask, action: string) => {
    if (!task.session_id) return;
    setActioning(`${task.session_id}:${task.task_id}:${action}`);
    setError(null);
    try {
      const response = await fetch(`/api/proxy/board-sessions/${encodeURIComponent(task.session_id)}/review`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({
          task_id: task.task_id,
          action,
          notes: action === 'accepted' ? 'Reviewed from launch queue.' : 'Deferred from launch queue.',
        }),
      });
      await readUiJson(response, 'Could not update review task.');
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Task update failed.');
    } finally {
      setActioning(null);
    }
  }, [load]);

  const exportTraining = useCallback(async (sessionId: string) => {
    setActioning(`export:${sessionId}`);
    setError(null);
    try {
      const response = await fetch(`/api/proxy/board-sessions/${encodeURIComponent(sessionId)}/training-export`, {
        method: 'POST',
      });
      await readUiJson(response, 'Could not export training package.');
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Training export failed.');
    } finally {
      setActioning(null);
    }
  }, [load]);

  const addCapture = useCallback(async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selectedSessionId) return;
    setActioning(`capture:${selectedSessionId}`);
    setError(null);
    try {
      const formData = new FormData();
      formData.set('kind', captureKind);
      formData.set('notes', captureNotes);
      if (captureFile) formData.set('file', captureFile);
      const response = await fetch(`/api/proxy/board-sessions/${encodeURIComponent(selectedSessionId)}/captures`, {
        method: 'POST',
        body: formData,
      });
      await readUiJson(response, 'Could not add capture evidence.');
      event.currentTarget.reset();
      setCaptureFile(null);
      setCaptureKind('marking_closeup');
      setCaptureNotes('');
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Capture evidence failed.');
    } finally {
      setActioning(null);
    }
  }, [captureFile, captureKind, captureNotes, load, selectedSessionId]);

  const addMeasurement = useCallback(async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selectedSessionId || !measurementTarget.trim()) return;
    setActioning(`measurement:${selectedSessionId}`);
    setError(null);
    try {
      const response = await fetch(`/api/proxy/board-sessions/${encodeURIComponent(selectedSessionId)}/measurement`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({
          type: 'operator_measurement',
          target: measurementTarget,
          value: measurementValue,
          unit: measurementUnit,
        }),
      });
      await readUiJson(response, 'Could not add measurement.');
      event.currentTarget.reset();
      setMeasurementTarget('');
      setMeasurementValue('');
      setMeasurementUnit('');
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Measurement failed.');
    } finally {
      setActioning(null);
    }
  }, [load, measurementTarget, measurementUnit, measurementValue, selectedSessionId]);

  const recordOutcome = useCallback(async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selectedSessionId) return;
    setActioning(`outcome:${selectedSessionId}`);
    setError(null);
    try {
      const response = await fetch(`/api/proxy/board-sessions/${encodeURIComponent(selectedSessionId)}/outcome`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({
          decision: outcomeDecision,
          value_recovered_usd: Number(outcomeValue || 0),
          time_saved_minutes: Number(outcomeMinutes || 0),
          close: closeOutcome,
        }),
      });
      await readUiJson(response, 'Could not record outcome.');
      event.currentTarget.reset();
      setOutcomeDecision('repaired');
      setOutcomeValue('');
      setOutcomeMinutes('');
      setCloseOutcome(false);
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Outcome failed.');
    } finally {
      setActioning(null);
    }
  }, [closeOutcome, load, outcomeDecision, outcomeMinutes, outcomeValue, selectedSessionId]);

  const summary = benchmark?.summary ?? {};
  const metrics: Array<{ label: string; value: string | number; icon: LucideIcon }> = [
    { label: 'Sessions', value: summary.session_count ?? sessions.length, icon: Database },
    { label: 'Open tasks', value: summary.open_task_count ?? tasks.length, icon: ClipboardList },
    { label: 'Reviewed', value: percent(summary.review_completion), icon: CheckCircle2 },
    { label: 'Captures', value: summary.avg_capture_burden_per_session ?? 'N/A', icon: Target },
    { label: 'Launch score', value: percent(summary.launch_readiness_score), icon: ShieldCheck },
  ];
  const selectedSession = useMemo(
    () => sessions.find((session) => session.session_id === selectedSessionId),
    [selectedSessionId, sessions],
  );

  return (
    <div className="min-h-screen bg-[#090f18] text-slate-100">
      <SiteHeader />
      <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        <section className="mb-6 rounded-lg border border-white/10 bg-white/[0.02] p-5">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <div className="mb-3 flex flex-wrap gap-2">
                <Badge variant="info">learning loop</Badge>
                <Badge variant="default">review</Badge>
                <Badge variant="default">training export</Badge>
                <Badge variant="default">launch benchmark</Badge>
              </div>
              <h1 className="text-3xl font-semibold text-white">Board session review</h1>
              <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-400">
                Review uncertain claims, keep capture burden under control, and export reviewed sessions into training data.
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

        {error && (
          <section className="mb-6 rounded-lg border border-rose-400/40 bg-rose-500/10 p-4 text-sm text-rose-100">
            {error}
          </section>
        )}

        <section className="mb-6 grid gap-3 md:grid-cols-2 xl:grid-cols-5">
          {metrics.map(({ label, value, icon: MetricIcon }) => {
            return (
              <div key={label} className="rounded-lg border border-white/10 bg-white/[0.02] p-4">
                <div className="flex items-center justify-between gap-3">
                  <div className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">{label}</div>
                  <MetricIcon className="h-4 w-4 text-cyan-200" />
                </div>
                <div className="mt-3 text-2xl font-semibold text-white">{String(value)}</div>
              </div>
            );
          })}
        </section>

        <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_360px]">
          <section className="space-y-4">
            {loading ? (
              <div className="rounded-lg border border-white/10 bg-white/[0.02] p-8 text-center text-sm text-slate-400">
                <LoaderCircle className="mx-auto mb-3 h-5 w-5 animate-spin text-cyan-200" />
                Loading review queue...
              </div>
            ) : grouped.length ? (
              grouped.map(([sessionId, sessionTasks]) => (
                <div key={sessionId} className="rounded-lg border border-white/10 bg-white/[0.02] p-4">
                  <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <div className="text-sm font-semibold text-white">{sessionTasks[0]?.session_title || sessionId}</div>
                      <div className="mt-1 text-xs text-slate-500">{sessionTasks.length} open task(s) · {sessionTasks[0]?.route ?? 'intake'}</div>
                    </div>
                    <Button
                      size="sm"
                      onClick={() => void exportTraining(sessionId)}
                      disabled={actioning === `export:${sessionId}`}
                      className="rounded-lg border border-white/10 bg-white/[0.04] text-white hover:bg-white/[0.08]"
                    >
                      {actioning === `export:${sessionId}` ? <LoaderCircle className="mr-2 h-4 w-4 animate-spin" /> : <Download className="mr-2 h-4 w-4" />}
                      Export
                    </Button>
                  </div>
                  <div className="space-y-2">
                    {sessionTasks.map((task) => (
                      <div key={`${task.session_id}-${task.task_id}`} className="rounded-lg border border-white/10 bg-black/20 p-3">
                        <div className="flex flex-wrap items-start justify-between gap-3">
                          <div className="min-w-0">
                            <div className="mb-2 flex flex-wrap gap-2">
                              <Badge variant={taskVariant(task.type)}>{task.type}</Badge>
                              <Badge variant="default">P{task.priority ?? 3}</Badge>
                              {task.source ? <Badge variant="default">{task.source}</Badge> : null}
                            </div>
                            <p className="text-sm leading-6 text-slate-200">{task.prompt}</p>
                            {task.usable_for?.length ? (
                              <div className="mt-2 text-xs text-slate-500">Useful for {task.usable_for.slice(0, 4).join(', ')}</div>
                            ) : null}
                          </div>
                          <div className="flex shrink-0 gap-2">
                            <Button
                              size="sm"
                              onClick={() => void markTask(task, 'accepted')}
                              disabled={Boolean(actioning)}
                              className="rounded-lg bg-emerald-300 text-slate-950 hover:bg-emerald-200"
                            >
                              Accept
                            </Button>
                            <Button
                              size="sm"
                              onClick={() => void markTask(task, 'deferred')}
                              disabled={Boolean(actioning)}
                              className="rounded-lg border border-white/10 bg-white/[0.04] text-white hover:bg-white/[0.08]"
                            >
                              Defer
                            </Button>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ))
            ) : (
              <div className="rounded-lg border border-dashed border-white/10 bg-white/[0.01] p-8 text-center">
                <CheckCircle2 className="mx-auto h-7 w-7 text-emerald-300" />
                <h2 className="mt-3 text-lg font-semibold text-white">No open review tasks</h2>
                <p className="mt-2 text-sm text-slate-400">Create board sessions from the Start page or scan endpoint to fill this queue.</p>
              </div>
            )}
          </section>

          <aside className="space-y-4">
            <section className="rounded-lg border border-white/10 bg-white/[0.02] p-4">
              <div className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                <Camera className="h-4 w-4" />
                Evidence intake
              </div>
              <div className="mb-3">
                <select
                  value={selectedSessionId}
                  onChange={(event) => setSelectedSessionId(event.target.value)}
                  className="h-10 w-full rounded-md border border-white/10 bg-black/30 px-3 text-sm text-white outline-none focus:border-cyan-300/60"
                >
                  <option value="">Select session</option>
                  {sessions.slice(0, 20).map((session) => (
                    <option key={session.session_id} value={session.session_id}>
                      {session.title || session.session_id}
                    </option>
                  ))}
                </select>
                {selectedSession ? (
                  <div className="mt-2 text-xs text-slate-500">
                    {selectedSession.route ?? 'intake'} · {selectedSession.open_task_count ?? selectedSession.metrics?.open_task_count ?? 0} open tasks
                  </div>
                ) : null}
              </div>

              <form onSubmit={addCapture} className="space-y-2">
                <div className="grid grid-cols-[1fr_auto] gap-2">
                  <select
                    value={captureKind}
                    onChange={(event) => setCaptureKind(event.target.value)}
                    className="h-10 rounded-md border border-white/10 bg-black/30 px-3 text-sm text-white outline-none focus:border-cyan-300/60"
                  >
                    <option value="marking_closeup">Marking close-up</option>
                    <option value="connector_closeup">Connector close-up</option>
                    <option value="reverse_side">Reverse side</option>
                    <option value="golden_reference">Golden reference</option>
                    <option value="netlist_reference">Netlist/reference</option>
                  </select>
                  <Button
                    type="submit"
                    size="sm"
                    disabled={!selectedSessionId || (!captureFile && !captureNotes.trim()) || Boolean(actioning)}
                    className="rounded-lg bg-cyan-300 text-slate-950 hover:bg-cyan-200"
                  >
                    {actioning === `capture:${selectedSessionId}` ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
                  </Button>
                </div>
                <input
                  type="file"
                  accept="image/*,.json,.net,.kicad_pcb,.csv,.txt"
                  onChange={(event) => setCaptureFile(event.target.files?.[0] ?? null)}
                  className="block w-full rounded-md border border-white/10 bg-black/30 px-3 py-2 text-xs text-slate-300 file:mr-3 file:rounded-md file:border-0 file:bg-white/10 file:px-2 file:py-1 file:text-xs file:text-white"
                />
                <textarea
                  value={captureNotes}
                  onChange={(event) => setCaptureNotes(event.target.value)}
                  placeholder="Evidence note"
                  rows={2}
                  className="w-full resize-none rounded-md border border-white/10 bg-black/30 px-3 py-2 text-sm text-white outline-none placeholder:text-slate-600 focus:border-cyan-300/60"
                />
              </form>
            </section>

            <section className="rounded-lg border border-white/10 bg-white/[0.02] p-4">
              <div className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                <Ruler className="h-4 w-4" />
                Measurement
              </div>
              <form onSubmit={addMeasurement} className="space-y-2">
                <input
                  value={measurementTarget}
                  onChange={(event) => setMeasurementTarget(event.target.value)}
                  placeholder="Target"
                  className="h-10 w-full rounded-md border border-white/10 bg-black/30 px-3 text-sm text-white outline-none placeholder:text-slate-600 focus:border-cyan-300/60"
                />
                <div className="grid grid-cols-[1fr_88px_auto] gap-2">
                  <input
                    value={measurementValue}
                    onChange={(event) => setMeasurementValue(event.target.value)}
                    placeholder="Value"
                    className="h-10 min-w-0 rounded-md border border-white/10 bg-black/30 px-3 text-sm text-white outline-none placeholder:text-slate-600 focus:border-cyan-300/60"
                  />
                  <input
                    value={measurementUnit}
                    onChange={(event) => setMeasurementUnit(event.target.value)}
                    placeholder="Unit"
                    className="h-10 min-w-0 rounded-md border border-white/10 bg-black/30 px-3 text-sm text-white outline-none placeholder:text-slate-600 focus:border-cyan-300/60"
                  />
                  <Button
                    type="submit"
                    size="sm"
                    disabled={!selectedSessionId || !measurementTarget.trim() || Boolean(actioning)}
                    className="rounded-lg bg-emerald-300 text-slate-950 hover:bg-emerald-200"
                  >
                    {actioning === `measurement:${selectedSessionId}` ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
                  </Button>
                </div>
              </form>
            </section>

            <section className="rounded-lg border border-white/10 bg-white/[0.02] p-4">
              <div className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                <ShieldCheck className="h-4 w-4" />
                Outcome
              </div>
              <form onSubmit={recordOutcome} className="space-y-2">
                <select
                  value={outcomeDecision}
                  onChange={(event) => setOutcomeDecision(event.target.value)}
                  className="h-10 w-full rounded-md border border-white/10 bg-black/30 px-3 text-sm text-white outline-none focus:border-cyan-300/60"
                >
                  <option value="repaired">Repaired</option>
                  <option value="salvaged">Salvaged</option>
                  <option value="parts_only">Parts only</option>
                  <option value="not_economic">Not economic</option>
                  <option value="unsafe">Unsafe</option>
                </select>
                <div className="grid grid-cols-[1fr_1fr_auto] gap-2">
                  <input
                    value={outcomeValue}
                    onChange={(event) => setOutcomeValue(event.target.value)}
                    inputMode="decimal"
                    placeholder="USD"
                    className="h-10 min-w-0 rounded-md border border-white/10 bg-black/30 px-3 text-sm text-white outline-none placeholder:text-slate-600 focus:border-cyan-300/60"
                  />
                  <input
                    value={outcomeMinutes}
                    onChange={(event) => setOutcomeMinutes(event.target.value)}
                    inputMode="decimal"
                    placeholder="Minutes"
                    className="h-10 min-w-0 rounded-md border border-white/10 bg-black/30 px-3 text-sm text-white outline-none placeholder:text-slate-600 focus:border-cyan-300/60"
                  />
                  <Button
                    type="submit"
                    size="sm"
                    disabled={!selectedSessionId || Boolean(actioning)}
                    className="rounded-lg border border-white/10 bg-white/[0.04] text-white hover:bg-white/[0.08]"
                  >
                    {actioning === `outcome:${selectedSessionId}` ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
                  </Button>
                </div>
                <label className="flex items-center gap-2 text-xs text-slate-400">
                  <input
                    type="checkbox"
                    checked={closeOutcome}
                    onChange={(event) => setCloseOutcome(event.target.checked)}
                    className="h-4 w-4 rounded border-white/10 bg-black/30"
                  />
                  Close session
                </label>
              </form>
            </section>

            <section className="rounded-lg border border-white/10 bg-white/[0.02] p-4">
              <div className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                <AlertTriangle className="h-4 w-4" />
                Next launch gates
              </div>
              <div className="space-y-2">
                {(benchmark?.next_actions ?? []).slice(0, 6).map((item) => (
                  <p key={item} className="text-sm leading-6 text-slate-300">{item}</p>
                ))}
                {!benchmark?.next_actions?.length && <p className="text-sm text-slate-500">Benchmark data appears after sessions exist.</p>}
              </div>
            </section>

            <section className="rounded-lg border border-white/10 bg-white/[0.02] p-4">
              <div className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                <Target className="h-4 w-4" />
                Competitive scorecard
              </div>
              <div className="space-y-3">
                {(benchmark?.competitive_scorecard ?? []).slice(0, 4).map((row) => (
                  <div key={row.dimension} className="rounded-md border border-white/10 bg-black/20 p-3">
                    <div className="text-sm font-semibold text-white">{row.dimension?.replace(/_/g, ' ')}</div>
                    <div className="mt-1 text-xs leading-5 text-slate-500">{row.metric}</div>
                    <div className="mt-2 text-xs leading-5 text-slate-300">Target: {row.target}</div>
                  </div>
                ))}
              </div>
            </section>

            <section className="rounded-lg border border-white/10 bg-white/[0.02] p-4">
              <div className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                <Database className="h-4 w-4" />
                Recent sessions
              </div>
              <div className="space-y-2">
                {sessions.slice(0, 6).map((session) => (
                  <div key={session.session_id} className="rounded-md border border-white/10 bg-black/20 p-3">
                    <div className="truncate text-sm font-semibold text-white">{session.title || session.session_id}</div>
                    <div className="mt-1 text-xs text-slate-500">
                      {session.route ?? 'intake'} · {session.open_task_count ?? session.metrics?.open_task_count ?? 0} open · {session.training_export_count ?? 0} exports
                    </div>
                  </div>
                ))}
              </div>
            </section>
          </aside>
        </div>
      </main>
      <SiteFooter />
    </div>
  );
}

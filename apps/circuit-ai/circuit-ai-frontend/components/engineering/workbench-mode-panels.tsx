'use client';

import Link from 'next/link';
import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  Circle,
  FileCheck2,
  FlaskConical,
  GitCompareArrows,
  History,
  ShieldAlert,
  ShieldCheck,
  Wrench,
  XCircle,
} from 'lucide-react';
import type { CanonicalVisualObject } from './canonical-system-canvas';

type JsonRecord = Record<string, unknown>;

export type WorkbenchMode = 'explore' | 'decide' | 'verify' | 'bringup';

export const workbenchModes: Array<{
  id: WorkbenchMode;
  label: string;
  description: string;
}> = [
  { id: 'explore', label: 'Explore', description: 'Understand objects, evidence, and relationships.' },
  { id: 'decide', label: 'Decide', description: 'Compare current state with a proposed successor.' },
  { id: 'verify', label: 'Verify', description: 'Inspect deterministic checks, failures, and repair eligibility.' },
  { id: 'bringup', label: 'Bring-up', description: 'Prepare physical procedures and identify missing evidence.' },
];

function text(value: unknown, fallback = '—') {
  return value === undefined || value === null || value === '' ? fallback : String(value);
}

function statusTone(status: string) {
  if (status === 'failed' || status === 'blocked') return 'border-rose-300/20 bg-rose-300/8 text-rose-100';
  if (status === 'completed' || status === 'passed' || status === 'supported') return 'border-emerald-300/20 bg-emerald-300/8 text-emerald-100';
  if (status === 'proposed' || status === 'accepted') return 'border-violet-300/20 bg-violet-300/8 text-violet-100';
  return 'border-white/10 bg-white/[0.03] text-slate-300';
}

export function DecisionModePanel({
  projectId,
  selectedObject,
  revision,
}: {
  projectId: string;
  selectedObject: CanonicalVisualObject | null;
  revision: number | null;
}) {
  const hasProposal = Boolean(selectedObject?.proposalIds.length || selectedObject?.status === 'proposed');
  const blockers = selectedObject?.blockers || [];

  return (
    <div className="h-full min-h-[650px] rounded-3xl border border-white/10 bg-[#050b14] p-5 lg:p-7">
      <div className="flex flex-col gap-3 border-b border-white/10 pb-5 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <div className="text-[10px] font-semibold uppercase tracking-[0.2em] text-violet-300">Human decision workspace</div>
          <h2 className="mt-2 text-xl font-semibold text-white">Current state versus proposed successor</h2>
          <p className="mt-2 text-sm leading-6 text-slate-400">A proposal remains separate from project truth until a named reviewer decides and a later deterministic check completes.</p>
        </div>
        <span className="rounded-full border border-white/10 bg-[#020711] px-3 py-1.5 text-xs text-slate-300">Source revision {revision ?? '—'}</span>
      </div>

      <div className="mt-5 grid gap-4 xl:grid-cols-2">
        <section className="rounded-2xl border border-rose-300/15 bg-rose-300/[0.04] p-5">
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.14em] text-rose-200"><History className="h-4 w-4" />Current</div>
          <div className="mt-4 text-lg font-semibold text-white">{selectedObject?.label || 'Select an engineering object'}</div>
          <div className="mt-1 text-xs text-slate-500">{selectedObject?.id || 'No canonical object selected'}</div>
          <p className="mt-4 text-sm leading-6 text-slate-300">{selectedObject?.description || 'Choose an object from the project model to compare its state.'}</p>
          <div className="mt-5 space-y-2">
            {blockers.length ? blockers.map((blocker) => (
              <div key={blocker} className="flex gap-2 rounded-xl border border-rose-300/15 bg-[#020711] p-3 text-xs leading-5 text-rose-100">
                <ShieldAlert className="mt-0.5 h-3.5 w-3.5 shrink-0" />{blocker}
              </div>
            )) : <div className="rounded-xl border border-white/8 bg-[#020711] p-3 text-xs text-slate-400">No current blocker is attached to this object.</div>}
          </div>
        </section>

        <section className="rounded-2xl border border-violet-300/20 bg-violet-300/[0.05] p-5">
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.14em] text-violet-200"><GitCompareArrows className="h-4 w-4" />Proposed</div>
          <div className="mt-4 text-lg font-semibold text-white">{hasProposal ? `${selectedObject?.label} successor` : 'No successor attached yet'}</div>
          <p className="mt-4 text-sm leading-6 text-slate-300">{hasProposal
            ? 'The successor preserves this canonical identity while changing its implementation. It still requires explicit review and fresh deterministic verification.'
            : 'JARVIS may explain the problem, but no project-changing proposal is attached to this object in the active revision.'}</p>
          <div className="mt-5 space-y-2 text-xs">
            <div className="flex gap-2 rounded-xl border border-violet-300/15 bg-[#020711] p-3 text-violet-100"><CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0" />Carry source and evidence identities into the successor.</div>
            <div className="flex gap-2 rounded-xl border border-violet-300/15 bg-[#020711] p-3 text-violet-100"><CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0" />Preserve the failed or blocked parent revision.</div>
            <div className="flex gap-2 rounded-xl border border-amber-300/15 bg-[#020711] p-3 text-amber-100"><AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />Do not imply verification or physical readiness.</div>
          </div>
        </section>
      </div>

      <div className="mt-4 rounded-2xl border border-white/10 bg-[#020711] p-4">
        <div className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">Semantic change summary</div>
        <div className="mt-3 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <div className="rounded-xl border border-white/8 p-3 text-xs text-slate-300"><span className="text-emerald-300">Keep</span><div className="mt-1">Canonical object and evidence lineage</div></div>
          <div className="rounded-xl border border-white/8 p-3 text-xs text-slate-300"><span className="text-violet-300">Change</span><div className="mt-1">Implementation or interface candidate</div></div>
          <div className="rounded-xl border border-white/8 p-3 text-xs text-slate-300"><span className="text-rose-300">Resolve</span><div className="mt-1">Attached blockers and failed assumptions</div></div>
          <div className="rounded-xl border border-white/8 p-3 text-xs text-slate-300"><span className="text-amber-300">Re-check</span><div className="mt-1">Deterministic and physical evidence</div></div>
        </div>
      </div>

      <div className="mt-5 flex flex-wrap items-center justify-between gap-3">
        <div className="text-xs text-slate-500">This visual workbench remains read-only. Decisions use the existing revisioned review boundary.</div>
        <Link href={`/engineering/studio?project=${encodeURIComponent(projectId)}&stage=review`} className="inline-flex items-center gap-2 rounded-xl border border-violet-300/25 bg-violet-300/10 px-4 py-2 text-xs font-semibold text-violet-100 hover:bg-violet-300/15">Open revisioned review <ArrowRight className="h-3.5 w-3.5" /></Link>
      </div>
    </div>
  );
}

export function VerifyModePanel({
  projectId,
  sessionId,
  selectedObject,
  actions,
}: {
  projectId: string;
  sessionId: string;
  selectedObject: CanonicalVisualObject | null;
  actions: JsonRecord[];
}) {
  const failed = actions.filter((action) => text(action.status, '').toLowerCase() === 'failed');
  const completed = actions.filter((action) => ['completed', 'passed', 'succeeded'].includes(text(action.status, '').toLowerCase()));

  return (
    <div className="h-full min-h-[650px] rounded-3xl border border-white/10 bg-[#050b14] p-5 lg:p-7">
      <div className="flex flex-col gap-3 border-b border-white/10 pb-5 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <div className="text-[10px] font-semibold uppercase tracking-[0.2em] text-amber-300">Deterministic verification</div>
          <h2 className="mt-2 text-xl font-semibold text-white">Checks, failures, and repair eligibility</h2>
          <p className="mt-2 text-sm leading-6 text-slate-400">Tool results remain attached to the exact revision and affected object. A passing software check is not physical proof.</p>
        </div>
        <div className="flex gap-2 text-xs"><span className="rounded-full border border-rose-300/20 bg-rose-300/8 px-3 py-1.5 text-rose-100">{failed.length} failed</span><span className="rounded-full border border-emerald-300/20 bg-emerald-300/8 px-3 py-1.5 text-emerald-100">{completed.length} completed</span></div>
      </div>

      <div className="mt-5 grid gap-4 xl:grid-cols-[0.9fr_1.1fr]">
        <section className="rounded-2xl border border-white/10 bg-[#020711] p-4">
          <div className="flex items-center gap-2 text-xs font-semibold text-white"><Wrench className="h-4 w-4 text-amber-300" />Persisted tool history</div>
          <div className="mt-4 space-y-2">
            {actions.length ? actions.map((action, index) => {
              const status = text(action.status, 'unknown').toLowerCase();
              return (
                <div key={text(action.action_id, `action-${index}`)} className={`rounded-xl border p-3 ${statusTone(status)}`}>
                  <div className="flex items-center justify-between gap-3"><span className="text-xs font-semibold">{text(action.title || action.action_type, 'Engineering action')}</span><span className="text-[10px] uppercase tracking-[0.12em]">{status}</span></div>
                  <div className="mt-1 break-all font-mono text-[9px] opacity-60">{text(action.action_id, `action-${index}`)}</div>
                </div>
              );
            }) : <div className="rounded-xl border border-white/8 p-3 text-xs text-slate-500">No deterministic action is recorded in the active session.</div>}
          </div>
        </section>

        <section className="rounded-2xl border border-white/10 bg-[#020711] p-4">
          <div className="flex items-center gap-2 text-xs font-semibold text-white"><FileCheck2 className="h-4 w-4 text-cyan-300" />Selected-object verification ladder</div>
          <div className="mt-4 text-base font-semibold text-white">{selectedObject?.label || 'Select an object'}</div>
          <div className="mt-4 space-y-2 text-xs">
            <VerificationRow label="Canonical identity exists" complete={Boolean(selectedObject?.id)} detail={selectedObject?.id || 'No object selected'} />
            <VerificationRow label="Source evidence attached" complete={Boolean(selectedObject?.evidenceIds.length)} detail={`${selectedObject?.evidenceIds.length || 0} evidence identities`} />
            <VerificationRow label="No unresolved blocker" complete={!selectedObject?.blockers.length} detail={selectedObject?.blockers[0] || 'No blocker attached'} />
            <VerificationRow label="Deterministic check completed" complete={completed.length > 0 && failed.length === 0} detail={failed.length ? `${failed.length} persisted failure(s)` : completed.length ? `${completed.length} completed check(s)` : 'No completed check'} />
            <VerificationRow label="Physical evidence recorded" complete={false} detail="Not established by software results" physical />
          </div>
          {failed.length ? <div className="mt-4 rounded-xl border border-rose-300/20 bg-rose-300/5 p-3 text-xs leading-5 text-rose-100"><XCircle className="mr-2 inline h-3.5 w-3.5" />A failed parent result must remain immutable. Any repair is a separate proposed successor.</div> : null}
        </section>
      </div>

      <div className="mt-5 flex flex-wrap items-center justify-between gap-3">
        <div className="text-xs text-slate-500">Running or repairing tools remains behind the existing human-decision boundary.</div>
        <Link href={`/engineering/ai-studio?project=${encodeURIComponent(projectId)}${sessionId ? `&session=${encodeURIComponent(sessionId)}` : ''}`} className="inline-flex items-center gap-2 rounded-xl border border-amber-300/25 bg-amber-300/10 px-4 py-2 text-xs font-semibold text-amber-100 hover:bg-amber-300/15">Open deterministic review <ArrowRight className="h-3.5 w-3.5" /></Link>
      </div>
    </div>
  );
}

function VerificationRow({ label, complete, detail, physical = false }: { label: string; complete: boolean; detail: string; physical?: boolean }) {
  return (
    <div className="flex items-start gap-3 rounded-xl border border-white/8 p-3">
      {complete ? <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-300" /> : physical ? <Circle className="mt-0.5 h-4 w-4 shrink-0 text-cyan-300" /> : <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-300" />}
      <div><div className="font-semibold text-slate-200">{label}</div><div className="mt-1 leading-5 text-slate-500">{detail}</div></div>
    </div>
  );
}

export function BringUpModePanel({
  projectId,
  selectedObject,
  sourcesCount,
  actions,
  physicalGates,
}: {
  projectId: string;
  selectedObject: CanonicalVisualObject | null;
  sourcesCount: number;
  actions: JsonRecord[];
  physicalGates: Array<[string, unknown]>;
}) {
  const hasCompletedSoftwareCheck = actions.some((action) => ['completed', 'passed', 'succeeded'].includes(text(action.status, '').toLowerCase()));
  const anyGateOpen = physicalGates.some(([, value]) => value === true);
  const steps = [
    { label: 'Engineering sources registered', complete: sourcesCount > 0, detail: `${sourcesCount} registered source descriptor(s)` },
    { label: 'Selected object has evidence', complete: Boolean(selectedObject?.evidenceIds.length), detail: `${selectedObject?.evidenceIds.length || 0} evidence identities` },
    { label: 'Deterministic software check completed', complete: hasCompletedSoftwareCheck, detail: hasCompletedSoftwareCheck ? 'At least one completed result exists' : 'No completed result exists' },
    { label: 'Object blockers resolved', complete: !selectedObject?.blockers.length, detail: selectedObject?.blockers[0] || 'No blocker attached' },
    { label: 'Physical measurement captured', complete: false, detail: 'No measurement capture contract is implemented in this tranche' },
  ];

  return (
    <div className="h-full min-h-[650px] rounded-3xl border border-white/10 bg-[#050b14] p-5 lg:p-7">
      <div className="flex flex-col gap-3 border-b border-white/10 pb-5 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <div className="text-[10px] font-semibold uppercase tracking-[0.2em] text-cyan-300">Physical bring-up preparation</div>
          <h2 className="mt-2 text-xl font-semibold text-white">Procedure readiness and missing physical evidence</h2>
          <p className="mt-2 text-sm leading-6 text-slate-400">This projection prepares a safe bench sequence. It does not open a gate, control equipment, or invent a measurement.</p>
        </div>
        <span className={`rounded-full border px-3 py-1.5 text-xs ${anyGateOpen ? 'border-rose-300/20 bg-rose-300/8 text-rose-100' : 'border-emerald-300/20 bg-emerald-300/8 text-emerald-100'}`}>{anyGateOpen ? 'Physical gate open' : 'All physical gates closed'}</span>
      </div>

      <div className="mt-5 grid gap-4 xl:grid-cols-[1.05fr_0.95fr]">
        <section className="rounded-2xl border border-white/10 bg-[#020711] p-4">
          <div className="flex items-center gap-2 text-xs font-semibold text-white"><FlaskConical className="h-4 w-4 text-cyan-300" />Bring-up sequence for {selectedObject?.label || 'selected object'}</div>
          <div className="mt-4 space-y-2">
            {steps.map((step, index) => (
              <div key={step.label} className="flex items-start gap-3 rounded-xl border border-white/8 p-3 text-xs">
                {step.complete ? <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-300" /> : <Circle className="mt-0.5 h-4 w-4 shrink-0 text-slate-500" />}
                <div className="min-w-0"><div className="font-semibold text-slate-200">{index + 1}. {step.label}</div><div className="mt-1 leading-5 text-slate-500">{step.detail}</div></div>
              </div>
            ))}
          </div>
        </section>

        <section className="rounded-2xl border border-white/10 bg-[#020711] p-4">
          <div className="flex items-center gap-2 text-xs font-semibold text-white"><ShieldCheck className="h-4 w-4 text-emerald-300" />Authority gates</div>
          <div className="mt-4 space-y-2">
            {physicalGates.map(([label, value]) => (
              <div key={label} className="flex items-center justify-between rounded-xl border border-white/8 p-3 text-xs"><span className="text-slate-300">{label}</span><span className={value === true ? 'text-rose-200' : 'text-emerald-200'}>{value === true ? 'authorized' : 'closed'}</span></div>
            ))}
          </div>
          <div className="mt-4 rounded-xl border border-cyan-300/15 bg-cyan-300/5 p-3 text-xs leading-5 text-cyan-50">The next useful product tranche is a typed measurement record with instrument, expected value, observed value, tolerance, artifact, operator, and revision identity.</div>
        </section>
      </div>

      <div className="mt-5 flex flex-wrap items-center justify-between gap-3">
        <div className="text-xs text-slate-500">Until physical evidence capture exists, this mode remains a preparation and gap-analysis surface.</div>
        <Link href={`/engineering/studio?project=${encodeURIComponent(projectId)}&stage=evidence`} className="inline-flex items-center gap-2 rounded-xl border border-cyan-300/25 bg-cyan-300/10 px-4 py-2 text-xs font-semibold text-cyan-100 hover:bg-cyan-300/15">Open project evidence <ArrowRight className="h-3.5 w-3.5" /></Link>
      </div>
    </div>
  );
}

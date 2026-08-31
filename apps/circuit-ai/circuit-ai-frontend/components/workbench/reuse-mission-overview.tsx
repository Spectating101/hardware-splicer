'use client';

import { useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import {
  ArrowRight,
  Boxes,
  CircleDollarSign,
  GitCompareArrows,
  PackageCheck,
  Recycle,
  ScanSearch,
  ShieldAlert,
  Target,
} from 'lucide-react';
import {
  constructorCandidateMap,
  constructorCandidates,
  constructorResources,
  constructorTarget,
} from '@/lib/workbench-constructor-demo';
import type { ConstructorCandidateId } from '@/lib/machine-workbench-store';

const steps = [
  { id: 'inventory', label: 'Inventory', icon: Boxes, detail: 'What hardware do we actually have?' },
  { id: 'goal', label: 'Goal', icon: Target, detail: 'What useful system are we trying to make?' },
  { id: 'candidates', label: 'Candidates', icon: GitCompareArrows, detail: 'Compare reuse, cost and integration risk.' },
  { id: 'resolve', label: 'Resolve', icon: ShieldAlert, detail: 'Close measurements, interfaces and missing evidence.' },
  { id: 'verify', label: 'Verify', icon: ScanSearch, detail: 'Use exact engineering evidence where it matters.' },
  { id: 'build', label: 'Build', icon: PackageCheck, detail: 'Export only when the remaining gates are understood.' },
] as const;

export function ReuseMissionOverview() {
  const router = useRouter();
  const [selectedCandidateId, setSelectedCandidateId] = useState<ConstructorCandidateId>('balanced');
  const candidate = constructorCandidateMap.get(selectedCandidateId) ?? constructorCandidateMap.get('balanced');

  const inventory = useMemo(() => {
    const salvaged = constructorResources.filter((resource) => resource.kind === 'salvaged' || resource.kind === 'owned').length;
    const procurable = constructorResources.filter((resource) => resource.kind === 'procurable').length;
    const designed = constructorResources.filter((resource) => resource.kind === 'designed').length;
    return { salvaged, procurable, designed, total: constructorResources.length };
  }, []);

  function openWorkbench(stage: 'inventory' | 'goal' | 'candidates' | 'resolve' | 'verify') {
    const params = new URLSearchParams({ stage, candidate: selectedCandidateId });
    router.push(`/workbench?${params.toString()}`);
  }

  return (
    <main className="min-h-screen bg-[#040811] text-slate-100">
      <div className="mx-auto max-w-7xl px-4 py-6 lg:px-6 lg:py-8">
        <div className="flex flex-col gap-5 border-b border-white/10 pb-6 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-3xl">
            <div className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.2em] text-cyan-300">
              <Recycle className="h-4 w-4" /> Reuse-first mission
            </div>
            <h1 className="mt-2 text-2xl font-semibold tracking-tight text-white sm:text-3xl">Turn available hardware into a defensible build.</h1>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-400">
              Start from what is already available, compare architectures, resolve the risky gaps, then drop into the engineering workbench only where evidence is needed.
            </p>
          </div>
          <div className="rounded-xl border border-white/10 bg-white/[0.025] px-4 py-3 lg:min-w-[300px]">
            <div className="text-[9px] font-semibold uppercase tracking-[0.18em] text-slate-500">Current mission</div>
            <div className="mt-1 text-sm font-semibold text-white">{constructorTarget.title}</div>
            <div className="mt-1 text-[11px] leading-5 text-slate-500">{constructorTarget.prompt}</div>
          </div>
        </div>

        <section className="mt-6 grid gap-2 md:grid-cols-3 xl:grid-cols-6" aria-label="Reuse mission stages">
          {steps.map((step, index) => {
            const Icon = step.icon;
            const buildBlocked = step.id === 'build' && (candidate?.blockerCount ?? 0) > 0;
            return (
              <div key={step.id} className="rounded-xl border border-white/8 bg-white/[0.02] p-3">
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <Icon className="h-3.5 w-3.5 text-cyan-300" />
                    <span className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-300">{step.label}</span>
                  </div>
                  <span className="text-[9px] text-slate-700">0{index + 1}</span>
                </div>
                <p className="mt-2 text-[10px] leading-4 text-slate-500">{step.detail}</p>
                {buildBlocked ? <div className="mt-2 text-[9px] font-medium text-red-300/80">Blocked · {candidate?.blockerCount} gates remain</div> : null}
              </div>
            );
          })}
        </section>

        <section className="mt-6 grid gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
          <div className="min-w-0">
            <div className="mb-3 flex flex-wrap items-end justify-between gap-3">
              <div>
                <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-500">Choose the strategy</div>
                <h2 className="mt-1 text-lg font-semibold text-white">Three ways to satisfy the same goal</h2>
              </div>
              <div className="text-[10px] text-slate-600">Changing the objective changes the candidate, not the evidence gates.</div>
            </div>

            <div className="grid gap-3 lg:grid-cols-3">
              {constructorCandidates.map((item) => {
                const selected = item.id === selectedCandidateId;
                return (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => setSelectedCandidateId(item.id)}
                    aria-pressed={selected}
                    className={`rounded-xl border p-4 text-left transition ${selected ? 'border-cyan-300/30 bg-cyan-300/[0.06]' : 'border-white/8 bg-white/[0.02] hover:border-white/15 hover:bg-white/[0.035]'}`}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <div className="text-sm font-semibold text-white">{item.name}</div>
                        <div className="mt-1 text-[9px] uppercase tracking-[0.14em] text-slate-600">{item.strategyMode}</div>
                      </div>
                      {selected ? <span className="rounded-full border border-cyan-300/20 bg-cyan-300/8 px-2 py-0.5 text-[8px] font-semibold uppercase tracking-[0.12em] text-cyan-200">selected</span> : null}
                    </div>
                    <p className="mt-3 min-h-12 text-[11px] leading-5 text-slate-400">{item.tagline}</p>
                    <div className="mt-3 grid grid-cols-3 gap-2">
                      <div className="rounded-lg border border-white/7 bg-black/10 p-2">
                        <Recycle className="h-3.5 w-3.5 text-slate-500" />
                        <div className="mt-1 text-sm font-semibold text-white">{item.reusePercent}%</div>
                        <div className="text-[8px] uppercase tracking-[0.1em] text-slate-600">reuse</div>
                      </div>
                      <div className="rounded-lg border border-white/7 bg-black/10 p-2">
                        <CircleDollarSign className="h-3.5 w-3.5 text-slate-500" />
                        <div className="mt-1 text-sm font-semibold text-white">NT${item.costNtd.toLocaleString()}</div>
                        <div className="text-[8px] uppercase tracking-[0.1em] text-slate-600">new spend</div>
                      </div>
                      <div className="rounded-lg border border-white/7 bg-black/10 p-2">
                        <ShieldAlert className="h-3.5 w-3.5 text-slate-500" />
                        <div className={`mt-1 text-sm font-semibold ${item.blockerCount === 0 ? 'text-emerald-300' : 'text-red-300'}`}>{item.blockerCount}</div>
                        <div className="text-[8px] uppercase tracking-[0.1em] text-slate-600">gates</div>
                      </div>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          <aside className="rounded-xl border border-white/10 bg-[#07101d] p-4">
            <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-cyan-300">Selected plan</div>
            <div className="mt-2 text-lg font-semibold text-white">{candidate?.name}</div>
            <p className="mt-1 text-[11px] leading-5 text-slate-400">{candidate?.note}</p>

            <div className="mt-4 grid grid-cols-3 gap-2 border-y border-white/8 py-3 text-center">
              <div>
                <div className="text-lg font-semibold text-white">{inventory.total}</div>
                <div className="text-[8px] uppercase tracking-[0.12em] text-slate-600">resources</div>
              </div>
              <div>
                <div className="text-lg font-semibold text-cyan-200">{inventory.salvaged}</div>
                <div className="text-[8px] uppercase tracking-[0.12em] text-slate-600">on hand</div>
              </div>
              <div>
                <div className="text-lg font-semibold text-red-300">{candidate?.unknownCount}</div>
                <div className="text-[8px] uppercase tracking-[0.12em] text-slate-600">unknowns</div>
              </div>
            </div>

            <div className="mt-4 space-y-2">
              <button type="button" onClick={() => openWorkbench('inventory')} className="flex w-full items-center justify-between rounded-lg border border-white/10 bg-white/[0.025] px-3 py-2.5 text-left text-[11px] font-medium text-slate-200 transition hover:bg-white/[0.05]">
                Review available hardware <ArrowRight className="h-3.5 w-3.5 text-slate-500" />
              </button>
              <button type="button" onClick={() => openWorkbench('goal')} className="flex w-full items-center justify-between rounded-lg border border-white/10 bg-white/[0.025] px-3 py-2.5 text-left text-[11px] font-medium text-slate-200 transition hover:bg-white/[0.05]">
                Inspect goal contract <ArrowRight className="h-3.5 w-3.5 text-slate-500" />
              </button>
              <button type="button" onClick={() => openWorkbench('resolve')} className="flex w-full items-center justify-between rounded-lg border border-amber-300/15 bg-amber-300/[0.035] px-3 py-2.5 text-left text-[11px] font-medium text-amber-100 transition hover:bg-amber-300/[0.06]">
                Resolve {candidate?.blockerCount} blocking gates <ArrowRight className="h-3.5 w-3.5 text-amber-300/70" />
              </button>
              <button type="button" onClick={() => openWorkbench('verify')} className="flex w-full items-center justify-between rounded-lg border border-cyan-300/15 bg-cyan-300/[0.035] px-3 py-2.5 text-left text-[11px] font-medium text-cyan-100 transition hover:bg-cyan-300/[0.06]">
                Open engineering verification <ArrowRight className="h-3.5 w-3.5 text-cyan-300/70" />
              </button>
              <button type="button" disabled={(candidate?.blockerCount ?? 0) > 0} title={(candidate?.blockerCount ?? 0) > 0 ? 'Build package remains blocked until the candidate gates are resolved.' : 'Open build package'} className="flex w-full items-center justify-between rounded-lg border border-emerald-300/15 bg-emerald-300/[0.035] px-3 py-2.5 text-left text-[11px] font-medium text-emerald-100 transition enabled:hover:bg-emerald-300/[0.06] disabled:cursor-not-allowed disabled:opacity-35">
                Build package <PackageCheck className="h-3.5 w-3.5" />
              </button>
            </div>

            <div className="mt-4 rounded-lg border border-white/8 bg-black/10 px-3 py-2 text-[9px] leading-4 text-slate-600">
              Mission view organizes the decision flow. Engineering authority remains evidence-bound inside the canonical workbench.
            </div>
          </aside>
        </section>
      </div>
    </main>
  );
}

'use client';

import { useState } from 'react';
import { Activity, CircleDollarSign, GitCompareArrows, Recycle, Ruler, ShieldCheck } from 'lucide-react';
import { BrepAdapterSynthesisControl } from '@/components/workbench/brep-adapter-synthesis-control';
import { GeometryInterrogationPanel } from '@/components/workbench/geometry-interrogation-panel';
import { constructorCandidates } from '@/lib/workbench-constructor-demo';
import { useMachineWorkbenchStore, type ConstructorCandidateId } from '@/lib/machine-workbench-store';

function riskTone(risk: string) {
  if (risk === 'low') return 'text-emerald-300';
  if (risk === 'high') return 'text-red-300';
  return 'text-amber-300';
}

function plannerTone(source: string) {
  if (source === 'live') return 'border-emerald-300/20 bg-emerald-300/8 text-emerald-200';
  if (source === 'loading') return 'border-sky-300/20 bg-sky-300/8 text-sky-200';
  return 'border-amber-300/15 bg-amber-300/[0.05] text-amber-200/80';
}

export function CandidateArchitectureTray() {
  const [trayMode, setTrayMode] = useState<'candidates' | 'geometry'>('candidates');
  const activeCandidateId = useMachineWorkbenchStore((state) => state.activeCandidateId);
  const plannerSource = useMachineWorkbenchStore((state) => state.plannerSource);
  const plannerMessage = useMachineWorkbenchStore((state) => state.plannerMessage);
  const plannerProjections = useMachineWorkbenchStore((state) => state.plannerProjections);
  const setActiveCandidateId = useMachineWorkbenchStore((state) => state.setActiveCandidateId);
  const setSelectedEntityId = useMachineWorkbenchStore((state) => state.setSelectedEntityId);
  const requestFrameSelection = useMachineWorkbenchStore((state) => state.requestFrameSelection);

  function activate(id: ConstructorCandidateId) {
    setActiveCandidateId(id);
    setSelectedEntityId('deck-001');
    window.setTimeout(requestFrameSelection, 0);
  }

  return (
    <section className="shrink-0 border-t border-white/10 bg-[#060d18] px-3 py-2.5">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-2">
          <GitCompareArrows className="h-3.5 w-3.5 shrink-0 text-cyan-300" />
          <span className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-400">Architecture candidates</span>
          <span title={plannerMessage} className={`rounded-full border px-2 py-0.5 text-[8px] font-semibold uppercase tracking-[0.12em] ${plannerTone(plannerSource)}`}>
            planner {plannerSource}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex rounded-lg border border-white/10 bg-black/20 p-0.5">
            <button
              type="button"
              onClick={() => setTrayMode('candidates')}
              aria-pressed={trayMode === 'candidates'}
              className={`inline-flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-[9px] font-semibold uppercase tracking-[0.09em] ${trayMode === 'candidates' ? 'bg-cyan-300/10 text-cyan-100' : 'text-slate-500 hover:bg-white/5 hover:text-white'}`}
            >
              <GitCompareArrows className="h-3 w-3" /> Candidates
            </button>
            <button
              type="button"
              onClick={() => setTrayMode('geometry')}
              aria-pressed={trayMode === 'geometry'}
              className={`inline-flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-[9px] font-semibold uppercase tracking-[0.09em] ${trayMode === 'geometry' ? 'bg-cyan-300/10 text-cyan-100' : 'text-slate-500 hover:bg-white/5 hover:text-white'}`}
            >
              <Ruler className="h-3 w-3" /> Geometry
            </button>
          </div>
          <span className="hidden text-[10px] text-slate-600 2xl:block">Objective changes the candidate. Evidence gates do not.</span>
        </div>
      </div>

      {trayMode === 'geometry' ? (
        <div className="max-h-[520px] space-y-3 overflow-auto" data-testid="construct-geometry-tray">
          <GeometryInterrogationPanel />
          <BrepAdapterSynthesisControl />
        </div>
      ) : (
        <div className="grid gap-2 lg:grid-cols-3">
          {constructorCandidates.map((candidate) => {
            const active = activeCandidateId === candidate.id;
            const planner = plannerProjections[candidate.id];
            const plannerLive = plannerSource === 'live' && Boolean(planner);
            const gateCount = plannerLive ? planner?.openGateCount ?? candidate.blockerCount : candidate.blockerCount;
            const missingCount = plannerLive ? planner?.missingCapabilities.length ?? candidate.unknownCount : candidate.unknownCount;
            const coveragePercent = plannerLive ? Math.round((planner?.coverageScore ?? 0) * 100) : null;
            return (
              <button
                key={candidate.id}
                type="button"
                onClick={() => activate(candidate.id)}
                aria-pressed={active}
                className={`rounded-xl border p-3 text-left transition ${active ? 'border-cyan-300/25 bg-cyan-300/[0.06] shadow-[0_0_28px_rgba(34,211,238,0.06)]' : 'border-white/8 bg-white/[0.02] hover:border-white/15 hover:bg-white/[0.035]'}`}
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="text-xs font-semibold text-white">{candidate.name}</div>
                    <div className="mt-0.5 flex items-center gap-1.5 text-[9px] uppercase tracking-[0.14em] text-slate-600">
                      <span>{candidate.strategyMode}</span>
                      {plannerLive ? <><span>·</span><span className="text-emerald-300/70">resource_strategy.v1</span></> : null}
                    </div>
                  </div>
                  {active ? <span className="rounded-full border border-cyan-300/20 bg-cyan-300/8 px-2 py-0.5 text-[8px] font-semibold uppercase tracking-[0.12em] text-cyan-200">working</span> : null}
                </div>
                <p className="mt-2 text-[10px] leading-4 text-slate-500">{plannerLive ? planner?.readinessReason : candidate.tagline}</p>
                <div className="mt-2 grid grid-cols-4 gap-1.5">
                  <div className="rounded-md border border-white/7 bg-black/10 p-1.5">
                    <CircleDollarSign className="h-3 w-3 text-slate-500" />
                    <div className="mt-1 text-[10px] font-semibold text-slate-200">{plannerLive ? `$${(planner?.procurementCostUsd ?? 0).toFixed(0)}` : `NT$${candidate.costNtd.toLocaleString()}`}</div>
                    <div className="text-[8px] text-slate-600">{plannerLive ? 'planner buy' : 'scenario cash'}</div>
                  </div>
                  <div className="rounded-md border border-white/7 bg-black/10 p-1.5">
                    {plannerLive ? <Activity className="h-3 w-3 text-slate-500" /> : <Recycle className="h-3 w-3 text-slate-500" />}
                    <div className="mt-1 text-[10px] font-semibold text-slate-200">{plannerLive ? `${coveragePercent}%` : `${candidate.reusePercent}%`}</div>
                    <div className="text-[8px] text-slate-600">{plannerLive ? 'coverage' : 'reuse'}</div>
                  </div>
                  <div className="rounded-md border border-white/7 bg-black/10 p-1.5">
                    <ShieldCheck className="h-3 w-3 text-slate-500" />
                    <div className={`mt-1 text-[10px] font-semibold uppercase ${riskTone(candidate.risk)}`}>{candidate.risk}</div>
                    <div className="text-[8px] text-slate-600">scenario risk</div>
                  </div>
                  <div className="rounded-md border border-white/7 bg-black/10 p-1.5">
                    <div className="text-[10px] font-semibold text-red-300">{gateCount}</div>
                    <div className="mt-1 text-[8px] text-slate-600">{plannerLive ? 'planner gates' : 'blockers'}</div>
                    <div className="text-[8px] text-amber-300/70">{missingCount} {plannerLive ? 'missing caps' : 'unknown'}</div>
                  </div>
                </div>
              </button>
            );
          })}
        </div>
      )}
    </section>
  );
}

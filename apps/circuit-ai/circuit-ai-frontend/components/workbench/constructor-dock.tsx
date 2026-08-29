'use client';

import { Activity, Boxes, Crosshair, PackageSearch, ShieldAlert, Target } from 'lucide-react';
import {
  constructorCandidateMap,
  constructorRequirements,
  constructorResources,
  constructorTarget,
  type RequirementState,
} from '@/lib/workbench-constructor-demo';
import { useMachineWorkbenchStore } from '@/lib/machine-workbench-store';

function requirementTone(state: RequirementState) {
  if (state === 'pass') return 'border-emerald-300/20 bg-emerald-300/[0.055] text-emerald-200';
  if (state === 'partial') return 'border-sky-300/20 bg-sky-300/[0.055] text-sky-200';
  if (state === 'blocked') return 'border-red-300/20 bg-red-300/[0.055] text-red-200';
  return 'border-amber-300/20 bg-amber-300/[0.055] text-amber-200';
}

function decisionTone(decision: string) {
  if (decision === 'reject') return 'text-red-300';
  if (decision === 'hold') return 'text-amber-300';
  if (decision === 'reuse' || decision === 'reuse_pending') return 'text-cyan-300';
  if (decision === 'buy') return 'text-violet-300';
  return 'text-orange-300';
}

function normalizeId(value: string) {
  return value.trim().toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
}

export function ConstructorDock() {
  const tab = useMachineWorkbenchStore((state) => state.constructorDockTab);
  const activeCandidateId = useMachineWorkbenchStore((state) => state.activeCandidateId);
  const selectedResourceId = useMachineWorkbenchStore((state) => state.selectedResourceId);
  const plannerSource = useMachineWorkbenchStore((state) => state.plannerSource);
  const plannerMessage = useMachineWorkbenchStore((state) => state.plannerMessage);
  const plannerProjection = useMachineWorkbenchStore((state) => state.plannerProjections[state.activeCandidateId]);
  const setTab = useMachineWorkbenchStore((state) => state.setConstructorDockTab);
  const setSelectedResourceId = useMachineWorkbenchStore((state) => state.setSelectedResourceId);
  const setSelectedEntityId = useMachineWorkbenchStore((state) => state.setSelectedEntityId);
  const requestFrameSelection = useMachineWorkbenchStore((state) => state.requestFrameSelection);
  const activeCandidate = constructorCandidateMap.get(activeCandidateId) ?? constructorCandidateMap.get('balanced');
  const livePlanner = plannerSource === 'live' && Boolean(plannerProjection);
  const liveSelected = new Set((plannerProjection?.selectedResourceIds ?? []).map(normalizeId));

  function inspectResource(resourceId: string, mappedEntityId?: string) {
    setSelectedResourceId(resourceId);
    if (mappedEntityId) {
      setSelectedEntityId(mappedEntityId);
      window.setTimeout(requestFrameSelection, 0);
    }
  }

  return (
    <aside className="flex h-full min-h-0 flex-col border-r border-white/10 bg-[#07101d]">
      <div className="border-b border-white/10 p-3">
        <div className="flex items-center justify-between gap-2">
          <div className="text-[9px] font-semibold uppercase tracking-[0.2em] text-cyan-300">Constructor</div>
          <span title={plannerMessage} className={`inline-flex items-center gap-1 rounded-full border px-1.5 py-0.5 text-[7px] font-semibold uppercase tracking-[0.1em] ${livePlanner ? 'border-emerald-300/20 bg-emerald-300/8 text-emerald-200' : plannerSource === 'loading' ? 'border-sky-300/20 bg-sky-300/8 text-sky-200' : 'border-amber-300/15 bg-amber-300/[0.05] text-amber-200/75'}`}>
            <Activity className="h-2.5 w-2.5" /> {livePlanner ? 'live planner' : plannerSource}
          </span>
        </div>
        <div className="mt-2 flex rounded-lg border border-white/10 bg-black/20 p-0.5">
          <button type="button" onClick={() => setTab('target')} className={`flex flex-1 items-center justify-center gap-2 rounded-md px-2 py-2 text-[10px] font-medium ${tab === 'target' ? 'bg-cyan-300/10 text-cyan-100' : 'text-slate-500 hover:text-white'}`}>
            <Target className="h-3.5 w-3.5" /> Target
          </button>
          <button type="button" onClick={() => setTab('resources')} className={`flex flex-1 items-center justify-center gap-2 rounded-md px-2 py-2 text-[10px] font-medium ${tab === 'resources' ? 'bg-cyan-300/10 text-cyan-100' : 'text-slate-500 hover:text-white'}`}>
            <Boxes className="h-3.5 w-3.5" /> Resources
          </button>
        </div>
      </div>

      {tab === 'target' ? (
        <div className="min-h-0 flex-1 overflow-auto p-3">
          <div className="rounded-xl border border-cyan-300/15 bg-cyan-300/[0.035] p-3">
            <div className="flex items-start gap-2">
              <Target className="mt-0.5 h-4 w-4 shrink-0 text-cyan-300" />
              <div>
                <div className="text-xs font-semibold text-white">{constructorTarget.title}</div>
                <p className="mt-1 text-[10px] leading-4 text-slate-400">{constructorTarget.prompt}</p>
              </div>
            </div>
          </div>

          {livePlanner ? (
            <div className="mt-3 rounded-lg border border-emerald-300/15 bg-emerald-300/[0.035] p-2.5">
              <div className="flex items-center justify-between gap-3 text-[8px] font-semibold uppercase tracking-[0.13em] text-emerald-200/80">
                <span>resource_strategy.v1</span>
                <span>{Math.round((plannerProjection?.coverageScore ?? 0) * 100)}% capability coverage</span>
              </div>
              <div className="mt-1 text-[9px] leading-4 text-slate-400">{plannerProjection?.readinessReason}</div>
              {(plannerProjection?.missingCapabilities.length ?? 0) > 0 ? <div className="mt-1 text-[8px] text-amber-300/75">Missing: {plannerProjection?.missingCapabilities.join(', ')}</div> : null}
            </div>
          ) : (
            <div className="mt-3 rounded-lg border border-amber-300/10 bg-amber-300/[0.025] px-2.5 py-2 text-[8px] leading-4 text-amber-100/55">{plannerMessage}</div>
          )}

          <div className="mt-4 flex items-center justify-between">
            <span className="text-[9px] font-semibold uppercase tracking-[0.16em] text-slate-500">Target contract projection</span>
            <span className="text-[9px] text-slate-600">{activeCandidate?.name}</span>
          </div>
          <div className="mt-2 space-y-1.5">
            {constructorRequirements.map((requirement) => {
              const state = activeCandidate?.requirementStates[requirement.id] ?? 'unknown';
              return (
                <div key={requirement.id} className="rounded-lg border border-white/8 bg-white/[0.02] px-2.5 py-2">
                  <div className="flex items-center gap-2">
                    <span className={`rounded border px-1.5 py-0.5 text-[8px] font-semibold uppercase tracking-[0.12em] ${requirementTone(state)}`}>{state}</span>
                    <span className="min-w-0 flex-1 truncate text-[10px] font-medium text-slate-200">{requirement.label}</span>
                    {requirement.hard ? <ShieldAlert className="h-3 w-3 shrink-0 text-slate-600" /> : null}
                  </div>
                  <div className="mt-1 pl-[52px] text-[9px] text-slate-600">{requirement.target}</div>
                </div>
              );
            })}
          </div>
        </div>
      ) : (
        <div className="min-h-0 flex-1 overflow-auto p-3">
          <div className="mb-3 flex items-center gap-2 rounded-lg border border-white/8 bg-white/[0.02] px-2.5 py-2 text-[9px] leading-4 text-slate-500">
            <PackageSearch className="h-3.5 w-3.5 shrink-0" /> {livePlanner ? 'Candidate membership below is selected by the live resource planner.' : 'Owned, salvaged, procurable and designed parts share one resource pool.'}
          </div>
          <div className="space-y-2">
            {constructorResources.map((resource) => {
              const selected = selectedResourceId === resource.id;
              const used = livePlanner ? liveSelected.has(normalizeId(resource.id)) : activeCandidate?.resourceIds.includes(resource.id);
              return (
                <button
                  key={resource.id}
                  type="button"
                  onClick={() => inspectResource(resource.id, resource.mappedEntityId)}
                  className={`w-full rounded-lg border p-2.5 text-left transition ${selected ? 'border-cyan-300/25 bg-cyan-300/[0.06]' : used ? 'border-white/12 bg-white/[0.03] hover:border-cyan-300/15' : 'border-white/7 bg-black/10 opacity-60 hover:opacity-90'}`}
                >
                  <div className="flex items-start gap-2">
                    <Crosshair className={`mt-0.5 h-3.5 w-3.5 shrink-0 ${used ? 'text-cyan-300' : 'text-slate-600'}`} />
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <span className="truncate text-[10px] font-medium text-slate-100">{resource.name}</span>
                        {used ? <span className="rounded bg-cyan-300/8 px-1.5 py-0.5 text-[7px] font-semibold uppercase tracking-[0.1em] text-cyan-300">{livePlanner ? 'planner selected' : 'candidate'}</span> : null}
                      </div>
                      <div className="mt-1 flex items-center gap-2 text-[8px] uppercase tracking-[0.12em] text-slate-600">
                        <span>{resource.kind}</span><span>·</span><span className={decisionTone(resource.decision)}>{resource.decision}</span><span>·</span><span>{resource.costNtd ? `NT$${resource.costNtd.toLocaleString()}` : 'owned'}</span>
                      </div>
                      <p className="mt-1.5 text-[9px] leading-4 text-slate-500">{resource.note}</p>
                    </div>
                  </div>
                </button>
              );
            })}
          </div>
        </div>
      )}
    </aside>
  );
}

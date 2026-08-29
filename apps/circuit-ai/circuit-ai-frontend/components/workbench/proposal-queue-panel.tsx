'use client';

import { Check, CirclePause, Crosshair, GitPullRequestArrow, ShieldAlert } from 'lucide-react';
import {
  constructorCandidateMap,
  constructorProposalMap,
  constructorResourceMap,
  type ConstructorProposal,
} from '@/lib/workbench-constructor-demo';
import { useMachineWorkbenchStore } from '@/lib/machine-workbench-store';

function opTone(operation: string) {
  if (operation === 'REJECT') return 'text-red-300 border-red-300/20 bg-red-300/[0.05]';
  if (operation === 'MEASURE') return 'text-amber-300 border-amber-300/20 bg-amber-300/[0.05]';
  if (operation === 'GENERATE') return 'text-orange-300 border-orange-300/20 bg-orange-300/[0.05]';
  if (operation === 'REPLACE') return 'text-violet-300 border-violet-300/20 bg-violet-300/[0.05]';
  return 'text-cyan-300 border-cyan-300/20 bg-cyan-300/[0.05]';
}

function stateLabel(proposal: ConstructorProposal, override?: 'accepted' | 'held') {
  if (override) return override;
  return proposal.state;
}

export function ProposalQueuePanel() {
  const activeCandidateId = useMachineWorkbenchStore((state) => state.activeCandidateId);
  const selectedProposalId = useMachineWorkbenchStore((state) => state.selectedProposalId);
  const proposalDecisions = useMachineWorkbenchStore((state) => state.proposalDecisions);
  const setSelectedProposalId = useMachineWorkbenchStore((state) => state.setSelectedProposalId);
  const setSelectedEntityId = useMachineWorkbenchStore((state) => state.setSelectedEntityId);
  const setSelectedResourceId = useMachineWorkbenchStore((state) => state.setSelectedResourceId);
  const setProposalDecision = useMachineWorkbenchStore((state) => state.setProposalDecision);
  const requestFrameSelection = useMachineWorkbenchStore((state) => state.requestFrameSelection);
  const candidate = constructorCandidateMap.get(activeCandidateId) ?? constructorCandidateMap.get('balanced');
  const proposals = candidate?.proposalIds.map((id) => constructorProposalMap.get(id)).filter((proposal): proposal is ConstructorProposal => Boolean(proposal)) ?? [];

  function inspectProposal(proposal: ConstructorProposal) {
    setSelectedProposalId(proposal.id);
    if (proposal.resourceId) setSelectedResourceId(proposal.resourceId);
    if (proposal.entityId) {
      setSelectedEntityId(proposal.entityId);
      window.setTimeout(requestFrameSelection, 0);
    }
  }

  return (
    <aside className="flex h-full min-h-0 flex-col border-l border-white/10 bg-[#07101d]">
      <div className="border-b border-white/10 p-3">
        <div className="flex items-center gap-2">
          <GitPullRequestArrow className="h-3.5 w-3.5 text-cyan-300" />
          <span className="text-[9px] font-semibold uppercase tracking-[0.18em] text-cyan-300">Proposal queue</span>
        </div>
        <div className="mt-2 text-xs font-semibold text-white">{candidate?.name}</div>
        <p className="mt-1 text-[9px] leading-4 text-slate-500">{candidate?.note}</p>
        <div className="mt-2 rounded-lg border border-amber-300/10 bg-amber-300/[0.035] px-2.5 py-2 text-[9px] leading-4 text-amber-100/65">
          Accepting a proposal changes the <strong className="font-semibold text-amber-100">working design only</strong>. It never promotes engineering authority or physical-build permission.
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-auto p-3">
        <div className="space-y-2">
          {proposals.map((proposal) => {
            const selected = selectedProposalId === proposal.id;
            const decision = proposalDecisions[proposal.id];
            const effectiveState = stateLabel(proposal, decision);
            const resource = proposal.resourceId ? constructorResourceMap.get(proposal.resourceId) : null;
            return (
              <div key={proposal.id} className={`rounded-xl border p-3 transition ${selected ? 'border-cyan-300/25 bg-cyan-300/[0.045]' : 'border-white/8 bg-white/[0.02]'}`}>
                <button type="button" aria-label={`Inspect proposal ${proposal.title}`} onClick={() => inspectProposal(proposal)} className="w-full text-left">
                  <div className="flex items-start gap-2">
                    <span className={`rounded border px-1.5 py-0.5 text-[7px] font-semibold tracking-[0.12em] ${opTone(proposal.operation)}`}>{proposal.operation}</span>
                    <div className="min-w-0 flex-1">
                      <div className="text-[10px] font-medium text-slate-100">{proposal.title}</div>
                      {resource ? <div className="mt-0.5 text-[8px] uppercase tracking-[0.12em] text-slate-600">{resource.kind} · {resource.name}</div> : null}
                    </div>
                    <Crosshair className="mt-0.5 h-3 w-3 shrink-0 text-slate-600" />
                  </div>
                  <p className="mt-2 text-[9px] leading-4 text-slate-500">{proposal.rationale}</p>
                  <div className="mt-2 flex gap-2 rounded-md border border-white/6 bg-black/10 px-2 py-1.5 text-[8px] leading-3 text-slate-600">
                    <ShieldAlert className="mt-0.5 h-3 w-3 shrink-0" /> {proposal.consequence}
                  </div>
                </button>

                <div className="mt-2 flex items-center gap-1.5 border-t border-white/7 pt-2">
                  <span className="mr-auto text-[8px] uppercase tracking-[0.12em] text-slate-600">{effectiveState}</span>
                  {proposal.state !== 'rejected' ? (
                    <>
                      <button type="button" aria-label={`Hold proposal ${proposal.title}`} onClick={() => setProposalDecision(proposal.id, 'held')} className={`inline-flex items-center gap-1 rounded-md border px-2 py-1 text-[8px] font-medium ${decision === 'held' ? 'border-amber-300/25 bg-amber-300/8 text-amber-200' : 'border-white/8 text-slate-500 hover:text-amber-200'}`}>
                        <CirclePause className="h-3 w-3" /> Hold
                      </button>
                      <button type="button" aria-label={`Accept proposal ${proposal.title} to working candidate`} onClick={() => setProposalDecision(proposal.id, 'accepted')} className={`inline-flex items-center gap-1 rounded-md border px-2 py-1 text-[8px] font-medium ${decision === 'accepted' ? 'border-emerald-300/25 bg-emerald-300/8 text-emerald-200' : 'border-white/8 text-slate-500 hover:text-emerald-200'}`}>
                        <Check className="h-3 w-3" /> Accept to working
                      </button>
                    </>
                  ) : null}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </aside>
  );
}

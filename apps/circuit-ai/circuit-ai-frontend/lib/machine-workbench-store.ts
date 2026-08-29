'use client';

import { create } from 'zustand';

export type WorkbenchLens = 'authority' | 'interfaces' | 'provenance' | 'constraints';
export type WorkbenchBottomTab = 'evidence' | 'interfaces' | 'constraints' | 'verification' | 'history';
export type WorkbenchView = 'assembly' | 'pcb';
export type WorkbenchCameraPreset = 'iso' | 'top' | 'front' | 'right';
export type WorkbenchPhase = 'construct' | 'inspect';
export type ConstructorDockTab = 'target' | 'resources';
export type ConstructorCandidateId = 'balanced' | 'max-reuse' | 'low-risk';
export type PlannerSourceState = 'loading' | 'live' | 'fixture';

export type MechanicalGeometryEvidence = {
  entityId: string;
  resourceId: string;
  sourceId: string;
  modelId: string;
  contentHash: string;
  authority: 'declared';
  units: string;
  sizeMm: [number, number, number];
  minimumMm: [number, number, number];
  maximumMm: [number, number, number];
  pointCount: number;
  unresolved: Array<{ field?: string; reason?: string }>;
  stepPointEnvelopeOnly: true;
  fullBrepCollision: false;
  fabricationAuthorized: false;
};

export type PlannerCandidateProjection = {
  strategyMode: 'hybrid' | 'constrained' | 'open_procurement';
  readinessStatus: string;
  readinessReason: string;
  coverageScore: number;
  openGateCount: number;
  blockedResourceCount: number;
  selectedResourceIds: string[];
  missingCapabilities: string[];
  procurementItemCount: number;
  procurementCostUsd: number;
  mechanicalGeometryByEntity?: Record<string, MechanicalGeometryEvidence>;
};

export type MachineWorkbenchState = {
  selectedEntityId: string;
  activeLens: WorkbenchLens;
  activeBottomTab: WorkbenchBottomTab;
  activeView: WorkbenchView;
  phase: WorkbenchPhase;
  constructorDockTab: ConstructorDockTab;
  activeCandidateId: ConstructorCandidateId;
  selectedResourceId: string | null;
  selectedProposalId: string | null;
  proposalDecisions: Record<string, 'accepted' | 'held'>;
  plannerSource: PlannerSourceState;
  plannerMessage: string;
  plannerProjections: Partial<Record<ConstructorCandidateId, PlannerCandidateProjection>>;
  isolatedEntityId: string | null;
  exploded: boolean;
  xray: boolean;
  immersive: boolean;
  cameraPreset: WorkbenchCameraPreset;
  frameRequest: number;
  setSelectedEntityId: (id: string) => void;
  setActiveLens: (lens: WorkbenchLens) => void;
  setActiveBottomTab: (tab: WorkbenchBottomTab) => void;
  setActiveView: (view: WorkbenchView) => void;
  setPhase: (phase: WorkbenchPhase) => void;
  setConstructorDockTab: (tab: ConstructorDockTab) => void;
  setActiveCandidateId: (id: ConstructorCandidateId) => void;
  setSelectedResourceId: (id: string | null) => void;
  setSelectedProposalId: (id: string | null) => void;
  setProposalDecision: (id: string, decision: 'accepted' | 'held') => void;
  setPlannerState: (source: PlannerSourceState, message: string, projections?: Partial<Record<ConstructorCandidateId, PlannerCandidateProjection>>) => void;
  setMechanicalGeometryEvidence: (candidateId: ConstructorCandidateId, evidence: MechanicalGeometryEvidence) => void;
  setIsolatedEntityId: (id: string | null) => void;
  setCameraPreset: (preset: WorkbenchCameraPreset) => void;
  requestFrameSelection: () => void;
  toggleExploded: () => void;
  toggleXray: () => void;
  toggleImmersive: () => void;
  resetViewState: () => void;
};

const STRATEGY_BY_CANDIDATE: Record<ConstructorCandidateId, PlannerCandidateProjection['strategyMode']> = {
  balanced: 'hybrid',
  'max-reuse': 'constrained',
  'low-risk': 'open_procurement',
};

function emptyProjection(candidateId: ConstructorCandidateId): PlannerCandidateProjection {
  return {
    strategyMode: STRATEGY_BY_CANDIDATE[candidateId],
    readinessStatus: 'fixture',
    readinessReason: 'No live planner projection is attached.',
    coverageScore: 0,
    openGateCount: 0,
    blockedResourceCount: 0,
    selectedResourceIds: [],
    missingCapabilities: [],
    procurementItemCount: 0,
    procurementCostUsd: 0,
    mechanicalGeometryByEntity: {},
  };
}

function mergeGeometryIntoPlannerState(
  existing: Partial<Record<ConstructorCandidateId, PlannerCandidateProjection>>,
  incoming: Partial<Record<ConstructorCandidateId, PlannerCandidateProjection>>,
) {
  const merged: Partial<Record<ConstructorCandidateId, PlannerCandidateProjection>> = {};
  for (const id of ['balanced', 'max-reuse', 'low-risk'] as ConstructorCandidateId[]) {
    const next = incoming[id];
    if (!next) continue;
    merged[id] = {
      ...next,
      mechanicalGeometryByEntity: {
        ...(next.mechanicalGeometryByEntity ?? {}),
        ...(existing[id]?.mechanicalGeometryByEntity ?? {}),
      },
    };
  }
  return merged;
}

export const useMachineWorkbenchStore = create<MachineWorkbenchState>((set) => ({
  selectedEntityId: 'deck-001',
  activeLens: 'authority',
  activeBottomTab: 'evidence',
  activeView: 'assembly',
  phase: 'construct',
  constructorDockTab: 'target',
  activeCandidateId: 'balanced',
  selectedResourceId: null,
  selectedProposalId: null,
  proposalDecisions: {},
  plannerSource: 'loading',
  plannerMessage: 'Checking Hardware-Splicer resource planner…',
  plannerProjections: {},
  isolatedEntityId: null,
  exploded: false,
  xray: false,
  immersive: false,
  cameraPreset: 'iso',
  frameRequest: 0,
  setSelectedEntityId: (selectedEntityId) => set({ selectedEntityId }),
  setActiveLens: (activeLens) => set({ activeLens }),
  setActiveBottomTab: (activeBottomTab) => set({ activeBottomTab }),
  setActiveView: (activeView) => set({ activeView }),
  setPhase: (phase) => set({ phase, immersive: false }),
  setConstructorDockTab: (constructorDockTab) => set({ constructorDockTab }),
  setActiveCandidateId: (activeCandidateId) => set({ activeCandidateId, selectedProposalId: null, selectedResourceId: null }),
  setSelectedResourceId: (selectedResourceId) => set({ selectedResourceId }),
  setSelectedProposalId: (selectedProposalId) => set({ selectedProposalId }),
  setProposalDecision: (id, decision) => set((state) => ({ proposalDecisions: { ...state.proposalDecisions, [id]: decision } })),
  setPlannerState: (plannerSource, plannerMessage, plannerProjections) => set((state) => ({
    plannerSource,
    plannerMessage,
    plannerProjections: plannerProjections
      ? mergeGeometryIntoPlannerState(state.plannerProjections, plannerProjections)
      : state.plannerProjections,
  })),
  setMechanicalGeometryEvidence: (candidateId, evidence) => set((state) => {
    const current = state.plannerProjections[candidateId] ?? emptyProjection(candidateId);
    return {
      plannerProjections: {
        ...state.plannerProjections,
        [candidateId]: {
          ...current,
          mechanicalGeometryByEntity: {
            ...(current.mechanicalGeometryByEntity ?? {}),
            [evidence.entityId]: evidence,
          },
        },
      },
      frameRequest: state.frameRequest + 1,
    };
  }),
  setIsolatedEntityId: (isolatedEntityId) => set({ isolatedEntityId }),
  setCameraPreset: (cameraPreset) => set({ cameraPreset }),
  requestFrameSelection: () => set((state) => ({ frameRequest: state.frameRequest + 1 })),
  toggleExploded: () => set((state) => ({ exploded: !state.exploded })),
  toggleXray: () => set((state) => ({ xray: !state.xray })),
  toggleImmersive: () => set((state) => ({ immersive: !state.immersive })),
  resetViewState: () =>
    set((state) => ({
      activeLens: 'authority',
      activeBottomTab: 'evidence',
      activeView: 'assembly',
      constructorDockTab: 'target',
      selectedResourceId: null,
      selectedProposalId: null,
      isolatedEntityId: null,
      exploded: false,
      xray: false,
      immersive: false,
      cameraPreset: 'iso',
      frameRequest: state.frameRequest + 1,
    })),
}));

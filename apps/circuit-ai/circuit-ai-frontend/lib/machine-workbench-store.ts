'use client';

import { create } from 'zustand';

export type WorkbenchLens = 'authority' | 'interfaces' | 'provenance' | 'constraints';
export type WorkbenchBottomTab = 'evidence' | 'interfaces' | 'constraints' | 'verification' | 'history';
export type WorkbenchView = 'assembly' | 'pcb';
export type WorkbenchCameraPreset = 'iso' | 'top' | 'front' | 'right';
export type WorkbenchPhase = 'construct' | 'inspect';
export type ConstructorDockTab = 'target' | 'resources';
export type ConstructorCandidateId = 'balanced' | 'max-reuse' | 'low-risk';

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
  setIsolatedEntityId: (id: string | null) => void;
  setCameraPreset: (preset: WorkbenchCameraPreset) => void;
  requestFrameSelection: () => void;
  toggleExploded: () => void;
  toggleXray: () => void;
  toggleImmersive: () => void;
  resetViewState: () => void;
};

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
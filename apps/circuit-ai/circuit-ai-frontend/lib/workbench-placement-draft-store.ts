'use client';

import { create } from 'zustand';
import type { ConstructorCandidateId } from '@/lib/machine-workbench-store';

export type AssemblyEditTool = 'select' | 'move' | 'rotate';

export type DeclaredPlacementDraft = {
  candidateId: ConstructorCandidateId;
  entityId: string;
  resourceId: string;
  modelId: string;
  translationMm: [number, number, number];
  rotationDegXyz: [number, number, number];
  updatedAt: number;
};

type PlacementDraftState = {
  tool: AssemblyEditTool;
  draftsByCandidate: Partial<Record<ConstructorCandidateId, Record<string, DeclaredPlacementDraft>>>;
  commitRequest: { candidateId: ConstructorCandidateId; entityId: string; requestId: number } | null;
  setTool: (tool: AssemblyEditTool) => void;
  setDraft: (draft: Omit<DeclaredPlacementDraft, 'updatedAt'>) => void;
  clearDraft: (candidateId: ConstructorCandidateId, entityId: string) => void;
  requestCommit: (candidateId: ConstructorCandidateId, entityId: string) => void;
  clearCommitRequest: () => void;
  resetEditing: () => void;
};

export const useWorkbenchPlacementDraftStore = create<PlacementDraftState>((set) => ({
  tool: 'select',
  draftsByCandidate: {
    balanced: {},
    'max-reuse': {},
    'low-risk': {},
  },
  commitRequest: null,
  setTool: (tool) => set({ tool }),
  setDraft: (draft) => set((state) => ({
    draftsByCandidate: {
      ...state.draftsByCandidate,
      [draft.candidateId]: {
        ...(state.draftsByCandidate[draft.candidateId] ?? {}),
        [draft.entityId]: {
          ...draft,
          updatedAt: Date.now(),
        },
      },
    },
  })),
  clearDraft: (candidateId, entityId) => set((state) => {
    const bucket = { ...(state.draftsByCandidate[candidateId] ?? {}) };
    delete bucket[entityId];
    return {
      draftsByCandidate: {
        ...state.draftsByCandidate,
        [candidateId]: bucket,
      },
    };
  }),
  requestCommit: (candidateId, entityId) => set((state) => ({
    commitRequest: {
      candidateId,
      entityId,
      requestId: (state.commitRequest?.requestId ?? 0) + 1,
    },
  })),
  clearCommitRequest: () => set({ commitRequest: null }),
  resetEditing: () => set({ tool: 'select', commitRequest: null }),
}));

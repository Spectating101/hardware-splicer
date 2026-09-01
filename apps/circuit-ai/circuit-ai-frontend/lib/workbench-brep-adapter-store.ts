'use client';

import { create } from 'zustand';
import type { ConstructorCandidateId } from '@/lib/machine-workbench-store';

export type BrepAdapterRequiredEvidence = {
  field: string;
  reason: string;
};

export type BrepAdapterCandidateEvidence = {
  adapterId: string;
  family: 'bridge_block_v0';
  frameId: string;
  firstAnchorId: string;
  secondAnchorId: string;
  firstEntityId: string;
  secondEntityId: string;
  firstPlacementId: string;
  secondPlacementId: string;
  firstContentHash: string;
  secondContentHash: string;
  status: 'ready' | 'unknown';
  kernelAvailable: boolean;
  kernel: string | null;
  geometricCandidatePassed: boolean | null;
  axis: [number, number, number] | null;
  midpointMm: [number, number, number] | null;
  lengthMm: number | null;
  widthMm: number;
  thicknessMm: number;
  volumeMm3: number | null;
  firstParentMinimumDistanceMm: number | null;
  secondParentMinimumDistanceMm: number | null;
  firstParentIntersectionVolumeMm3: number | null;
  secondParentIntersectionVolumeMm3: number | null;
  firstParentContactPassed: boolean | null;
  secondParentContactPassed: boolean | null;
  firstParentPenetrationPassed: boolean | null;
  secondParentPenetrationPassed: boolean | null;
  generatedSourceId: string | null;
  generatedModelId: string | null;
  generatedContentHash: string | null;
  generatedStepContent: string | null;
  bboxMinimumMm: [number, number, number] | null;
  bboxMaximumMm: [number, number, number] | null;
  vertexCount: number;
  triangleCount: number;
  verticesMm: [number, number, number][];
  triangles: [number, number, number][];
  requiredEvidence: BrepAdapterRequiredEvidence[];
  authority: 'declared';
  geometricCandidateOnly: true;
  fabricationAuthorized: false;
};

type AdapterStatus = 'idle' | 'loading' | 'ready' | 'unknown' | 'error';

type BrepAdapterState = {
  candidatesByArchitecture: Partial<Record<ConstructorCandidateId, BrepAdapterCandidateEvidence>>;
  status: AdapterStatus;
  message: string;
  setCandidate: (candidateId: ConstructorCandidateId, candidate: BrepAdapterCandidateEvidence) => void;
  setFeedback: (status: AdapterStatus, message: string) => void;
  clearCandidate: (candidateId: ConstructorCandidateId, message?: string) => void;
};

export const useWorkbenchBrepAdapterStore = create<BrepAdapterState>((set) => ({
  candidatesByArchitecture: {},
  status: 'idle',
  message: 'Choose two exact planar anchors to synthesize a bounded bridge candidate.',
  setCandidate: (candidateId, candidate) => set((state) => ({
    candidatesByArchitecture: {
      ...state.candidatesByArchitecture,
      [candidateId]: candidate,
    },
    status: candidate.status === 'ready' ? 'ready' : 'unknown',
    message: candidate.status === 'ready'
      ? candidate.geometricCandidatePassed
        ? 'Generated bridge satisfies the bounded exact parent contact/penetration checks. Fabrication remains blocked.'
        : 'Generated bridge exists, but exact parent contact/penetration checks rejected it. Fabrication remains blocked.'
      : candidate.requiredEvidence[0]?.reason || 'Adapter synthesis remains unresolved.',
  })),
  setFeedback: (status, message) => set({ status, message }),
  clearCandidate: (candidateId, message) => set((state) => {
    const next = { ...state.candidatesByArchitecture };
    delete next[candidateId];
    return {
      candidatesByArchitecture: next,
      status: 'idle',
      message: message || 'Generated adapter candidate cleared.',
    };
  }),
}));

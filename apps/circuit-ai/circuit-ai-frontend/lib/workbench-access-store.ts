'use client';

import { create } from 'zustand';
import type { ConstructorCandidateId } from '@/lib/machine-workbench-store';

export type DeclaredAccessEvidence = {
  accessId: string;
  interfaceId: string;
  entityId: string;
  resourceId: string;
  frameId: string;
  face: '+x' | '-x' | '+y' | '-y' | '+z' | '-z';
  widthMm: number;
  heightMm: number;
  depthMm: number;
  offsetUMm: number;
  offsetVMm: number;
  minimumMm: [number, number, number];
  maximumMm: [number, number, number];
  anchorPointMm: [number, number, number];
  outwardNormal: [number, number, number];
  authority: 'declared';
  aabbOnly: true;
  connectorMatingVerified: false;
  cableRoutingVerified: false;
  serviceAccessVerified: false;
  fullBrepCollision: false;
  fabricationAuthorized: false;
};

type AccessState = {
  accessByCandidate: Partial<Record<ConstructorCandidateId, Record<string, DeclaredAccessEvidence>>>;
  setAccess: (candidateId: ConstructorCandidateId, access: DeclaredAccessEvidence) => void;
  clearAccess: (candidateId: ConstructorCandidateId, accessId: string) => void;
  clearAccessForEntity: (candidateId: ConstructorCandidateId, entityId: string) => void;
};

export const useWorkbenchAccessStore = create<AccessState>((set) => ({
  accessByCandidate: {},
  setAccess: (candidateId, access) => set((state) => ({
    accessByCandidate: {
      ...state.accessByCandidate,
      [candidateId]: {
        ...(state.accessByCandidate[candidateId] ?? {}),
        [access.accessId]: access,
      },
    },
  })),
  clearAccess: (candidateId, accessId) => set((state) => {
    const current = { ...(state.accessByCandidate[candidateId] ?? {}) };
    delete current[accessId];
    return {
      accessByCandidate: {
        ...state.accessByCandidate,
        [candidateId]: current,
      },
    };
  }),
  clearAccessForEntity: (candidateId, entityId) => set((state) => {
    const current = { ...(state.accessByCandidate[candidateId] ?? {}) };
    for (const [accessId, access] of Object.entries(current)) {
      if (access.entityId === entityId) delete current[accessId];
    }
    return {
      accessByCandidate: {
        ...state.accessByCandidate,
        [candidateId]: current,
      },
    };
  }),
}));

'use client';

import { create } from 'zustand';
import type { ConstructorCandidateId } from '@/lib/machine-workbench-store';

export type DeclaredPlacementEvidence = {
  placementId: string;
  entityId: string;
  resourceId: string;
  modelId: string;
  frameId: string;
  translationMm: [number, number, number];
  rotationDegXyz: [number, number, number];
  minimumMm: [number, number, number];
  maximumMm: [number, number, number];
  sizeMm: [number, number, number];
  authority: 'declared';
  aabbOnly: true;
  fullBrepCollision: false;
  fabricationAuthorized: false;
};

type GeometryReport = Record<string, unknown>;

type PlacementState = {
  placementsByCandidate: Partial<Record<ConstructorCandidateId, Record<string, DeclaredPlacementEvidence>>>;
  geometryReportsByCandidate: Partial<Record<ConstructorCandidateId, Record<string, GeometryReport>>>;
  setGeometryReport: (candidateId: ConstructorCandidateId, resourceId: string, report: GeometryReport) => void;
  setPlacement: (candidateId: ConstructorCandidateId, placement: DeclaredPlacementEvidence) => void;
  clearPlacement: (candidateId: ConstructorCandidateId, entityId: string) => void;
};

export const useWorkbenchPlacementStore = create<PlacementState>((set) => ({
  placementsByCandidate: {},
  geometryReportsByCandidate: {},
  setGeometryReport: (candidateId, resourceId, report) => set((state) => {
    const placements = { ...(state.placementsByCandidate[candidateId] ?? {}) };
    for (const [entityId, placement] of Object.entries(placements)) {
      if (placement.resourceId === resourceId) delete placements[entityId];
    }
    return {
      geometryReportsByCandidate: {
        ...state.geometryReportsByCandidate,
        [candidateId]: {
          ...(state.geometryReportsByCandidate[candidateId] ?? {}),
          [resourceId]: report,
        },
      },
      placementsByCandidate: {
        ...state.placementsByCandidate,
        [candidateId]: placements,
      },
    };
  }),
  setPlacement: (candidateId, placement) => set((state) => ({
    placementsByCandidate: {
      ...state.placementsByCandidate,
      [candidateId]: {
        ...(state.placementsByCandidate[candidateId] ?? {}),
        [placement.entityId]: placement,
      },
    },
  })),
  clearPlacement: (candidateId, entityId) => set((state) => {
    const current = { ...(state.placementsByCandidate[candidateId] ?? {}) };
    delete current[entityId];
    return {
      placementsByCandidate: {
        ...state.placementsByCandidate,
        [candidateId]: current,
      },
    };
  }),
}));

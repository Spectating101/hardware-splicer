'use client';

import { create } from 'zustand';
import {
  useMachineWorkbenchStore,
  type ConstructorCandidateId,
} from '@/lib/machine-workbench-store';

export type BrepSurfaceAnchorEvidence = {
  anchorId: string;
  interfaceId: string;
  entityId: string;
  resourceId: string;
  sourceId: string;
  modelId: string;
  contentHash: string;
  frameId: string;
  placementId: string;
  translationMm: [number, number, number];
  rotationDegXyz: [number, number, number];
  probePointMm: [number, number, number];
  anchorPointMm: [number, number, number];
  outwardNormal: [number, number, number];
  snapDistanceMm: number;
  faceIndex: number;
  faceGeomType: string;
  faceAreaMm2: number;
  authority: 'declared';
  connectorMatingVerified: false;
  physicalMeasurement: false;
  fabricationAuthorized: false;
};

export type ArmedBrepAnchorPick = {
  candidateId: ConstructorCandidateId;
  entityId: string;
  resourceId: string;
  interfaceId: string;
};

export type BrepAnchorPickStatus = 'idle' | 'armed' | 'loading' | 'success' | 'unknown' | 'error';

type BrepAnchorState = {
  anchorsByCandidate: Partial<Record<ConstructorCandidateId, Record<string, BrepSurfaceAnchorEvidence>>>;
  armedPick: ArmedBrepAnchorPick | null;
  pickStatus: BrepAnchorPickStatus;
  pickMessage: string;
  armPick: (pick: ArmedBrepAnchorPick) => void;
  cancelPick: () => void;
  setPickFeedback: (status: BrepAnchorPickStatus, message: string) => void;
  setAnchor: (candidateId: ConstructorCandidateId, anchor: BrepSurfaceAnchorEvidence) => void;
  clearAnchor: (candidateId: ConstructorCandidateId, anchorId: string) => void;
  clearAnchorsForEntity: (candidateId: ConstructorCandidateId, entityId: string) => void;
};

export const useWorkbenchBrepAnchorStore = create<BrepAnchorState>((set, get) => ({
  // Exact anchors are intentionally absent after a project reload until OCCT is run
  // again. Stable empty buckets prevent UI selectors from returning fresh fallback
  // objects while that absence is being represented honestly.
  anchorsByCandidate: {
    balanced: {},
    'max-reuse': {},
    'low-risk': {},
  },
  armedPick: null,
  pickStatus: 'idle',
  pickMessage: '',
  armPick: (armedPick) => set({
    armedPick,
    pickStatus: 'armed',
    pickMessage: 'Click the exact BREP mesh to send a bounded surface probe to OCCT.',
  }),
  cancelPick: () => set({ armedPick: null, pickStatus: 'idle', pickMessage: '' }),
  setPickFeedback: (pickStatus, pickMessage) => set({ pickStatus, pickMessage }),
  setAnchor: (candidateId, anchor) => {
    const activePick = get().armedPick;
    const acceptsActivePick = Boolean(
      activePick
      && activePick.candidateId === candidateId
      && activePick.entityId === anchor.entityId
      && activePick.resourceId === anchor.resourceId
      && activePick.interfaceId === anchor.interfaceId,
    );
    if (acceptsActivePick) {
      // A surface-pick gesture can also produce a separate click on synthetic scene
      // geometry underneath the exact mesh. Reassert the accepted exact anchor's
      // owning entity only while this same pick is still active; stale/cancelled
      // async responses must not steal the user's later selection.
      useMachineWorkbenchStore.setState({ selectedEntityId: anchor.entityId });
    }
    set((state) => ({
      anchorsByCandidate: {
        ...state.anchorsByCandidate,
        [candidateId]: {
          ...(state.anchorsByCandidate[candidateId] ?? {}),
          [anchor.anchorId]: anchor,
        },
      },
      armedPick: null,
      pickStatus: 'success',
      pickMessage: `${anchor.interfaceId} anchored to exact BREP face ${anchor.faceIndex} at ${anchor.snapDistanceMm.toFixed(3)} mm snap distance.`,
    }));
  },
  clearAnchor: (candidateId, anchorId) => set((state) => {
    const current = { ...(state.anchorsByCandidate[candidateId] ?? {}) };
    delete current[anchorId];
    return {
      anchorsByCandidate: {
        ...state.anchorsByCandidate,
        [candidateId]: current,
      },
    };
  }),
  clearAnchorsForEntity: (candidateId, entityId) => set((state) => {
    const current = { ...(state.anchorsByCandidate[candidateId] ?? {}) };
    for (const [anchorId, anchor] of Object.entries(current)) {
      if (anchor.entityId === entityId) delete current[anchorId];
    }
    const armedPick = state.armedPick?.candidateId === candidateId && state.armedPick.entityId === entityId
      ? null
      : state.armedPick;
    return {
      anchorsByCandidate: {
        ...state.anchorsByCandidate,
        [candidateId]: current,
      },
      armedPick,
      pickStatus: armedPick ? state.pickStatus : 'idle',
      pickMessage: armedPick ? state.pickMessage : '',
    };
  }),
}));

'use client';

import { create } from 'zustand';
import {
  useMachineWorkbenchStore,
  type ConstructorCandidateId,
} from '@/lib/machine-workbench-store';
import { useWorkbenchPlacementStore } from '@/lib/workbench-placement-store';
import {
  getRegisteredWorkbenchStepSource,
  useWorkbenchProjectSourceStore,
} from '@/lib/workbench-project-sources';

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
  rehydrateAnchor: (candidateId: ConstructorCandidateId, anchor: BrepSurfaceAnchorEvidence) => void;
  clearAnchor: (candidateId: ConstructorCandidateId, anchorId: string) => void;
  clearAnchorsForEntity: (candidateId: ConstructorCandidateId, entityId: string) => void;
};

function sameTuple(left: [number, number, number], right: [number, number, number]) {
  return left.every((value, index) => value === right[index]);
}

function anchorStillMatchesCurrentPlacement(candidateId: ConstructorCandidateId, anchor: BrepSurfaceAnchorEvidence) {
  const placement = useWorkbenchPlacementStore.getState().placementsByCandidate[candidateId]?.[anchor.entityId];
  return Boolean(
    placement
    && placement.resourceId === anchor.resourceId
    && placement.modelId === anchor.modelId
    && placement.frameId === anchor.frameId
    && placement.placementId === anchor.placementId
    && sameTuple(placement.translationMm, anchor.translationMm)
    && sameTuple(placement.rotationDegXyz, anchor.rotationDegXyz),
  );
}

export const useWorkbenchBrepAnchorStore = create<BrepAnchorState>((set, get) => {
  function commitAnchor(candidateId: ConstructorCandidateId, anchor: BrepSurfaceAnchorEvidence, updatePickFeedback: boolean) {
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
      ...(updatePickFeedback ? {
        armedPick: null,
        pickStatus: 'success' as const,
        pickMessage: `${anchor.interfaceId} anchored to exact BREP face ${anchor.faceIndex} at ${anchor.snapDistanceMm.toFixed(3)} mm snap distance.`,
      } : {}),
    }));
  }

  return {
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
      const projectState = useWorkbenchProjectSourceStore.getState();
      const registeredSource = getRegisteredWorkbenchStepSource(projectState, candidateId, anchor.resourceId);
      const durableProjectAnchor = Boolean(
        registeredSource
        && projectState.status === 'bound'
        && projectState.projectId === registeredSource.projectId
        && Number.isInteger(projectState.revision)
        && Number(projectState.revision) >= 1
        && registeredSource.entityId === anchor.entityId
        && registeredSource.sourceId === anchor.sourceId
        && registeredSource.modelId === anchor.modelId
        && registeredSource.contentHash === anchor.contentHash,
      );

      if (!durableProjectAnchor || !registeredSource || !projectState.projectId || !projectState.revision) {
        commitAnchor(candidateId, anchor, true);
        return;
      }

      set({
        pickStatus: 'loading',
        pickMessage: 'Exact OCCT surface resolved; persisting source- and pose-bound probe intent before exposing the anchor…',
      });
      void (async () => {
        try {
          const response = await fetch(
            `/api/proxy/engineering/projects/${encodeURIComponent(projectState.projectId!)}/workbench/anchor-intents`,
            {
              method: 'POST',
              headers: { 'content-type': 'application/json' },
              body: JSON.stringify({
                expected_revision: projectState.revision,
                candidate_id: candidateId,
                resource_id: anchor.resourceId,
                entity_id: anchor.entityId,
                interface_id: anchor.interfaceId,
                anchor_id: anchor.anchorId,
                source_id: anchor.sourceId,
                model_id: anchor.modelId,
                content_hash: anchor.contentHash,
                placement_id: anchor.placementId,
                target_frame: anchor.frameId,
                translation_mm: anchor.translationMm,
                rotation_deg_xyz: anchor.rotationDegXyz,
                probe_point_mm: anchor.probePointMm,
                max_snap_distance_mm: 5,
                authority: 'declared',
              }),
              cache: 'no-store',
            },
          );
          const payload = await response.json() as Record<string, unknown>;
          const detail = payload.detail && typeof payload.detail === 'object' ? payload.detail as Record<string, unknown> : {};
          if (!response.ok || payload.ok !== true) {
            throw new Error(String(detail.message || payload.error || `workbench anchor intent HTTP ${response.status}`));
          }
          if (
            payload.registered_source_hash_reverified !== true
            || payload.kernel_result_persisted !== false
            || payload.physical_authority_unchanged !== true
          ) {
            throw new Error('Durable anchor-intent response violated the probe-only/non-authoritative contract.');
          }
          const durable = payload.workbench_anchor_intent && typeof payload.workbench_anchor_intent === 'object'
            ? payload.workbench_anchor_intent as Record<string, unknown>
            : {};
          if (
            durable.anchor_id !== anchor.anchorId
            || durable.interface_id !== anchor.interfaceId
            || durable.source_id !== anchor.sourceId
            || durable.model_id !== anchor.modelId
            || durable.content_hash !== anchor.contentHash
            || durable.placement_id !== anchor.placementId
            || durable.kernel_result_persisted !== false
            || durable.requires_occt_resnap_on_reopen !== true
          ) {
            throw new Error('Durable anchor intent disagrees with the current exact surface probe dependencies.');
          }
          const revision = Number(payload.revision);
          if (!Number.isInteger(revision) || revision < 1) {
            throw new Error('Durable anchor intent did not return a valid project revision.');
          }
          const latestProject = useWorkbenchProjectSourceStore.getState();
          const latestRegistered = getRegisteredWorkbenchStepSource(latestProject, candidateId, anchor.resourceId);
          if (
            latestProject.projectId !== projectState.projectId
            || latestRegistered?.sourceId !== anchor.sourceId
            || latestRegistered?.contentHash !== anchor.contentHash
            || !anchorStillMatchesCurrentPlacement(candidateId, anchor)
          ) {
            throw new Error('Anchor dependencies changed while durable probe intent was being persisted.');
          }
          latestProject.setProjectRevision(projectState.projectId!, revision);
          commitAnchor(candidateId, anchor, true);
        } catch (error: unknown) {
          set({
            armedPick: null,
            pickStatus: 'error',
            pickMessage: error instanceof Error ? error.message : String(error),
          });
        }
      })();
    },
    rehydrateAnchor: (candidateId, anchor) => {
      if (!anchorStillMatchesCurrentPlacement(candidateId, anchor)) return;
      commitAnchor(candidateId, anchor, false);
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
  };
});

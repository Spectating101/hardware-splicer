'use client';

import type { ConstructorCandidateId, MechanicalGeometryEvidence } from '@/lib/machine-workbench-store';
import { useMachineWorkbenchStore } from '@/lib/machine-workbench-store';
import { useWorkbenchAccessStore } from '@/lib/workbench-access-store';
import { useWorkbenchBrepAnchorStore } from '@/lib/workbench-brep-anchor-store';
import { useWorkbenchPlacementDraftStore } from '@/lib/workbench-placement-draft-store';
import { useWorkbenchPlacementStore, type DeclaredPlacementEvidence } from '@/lib/workbench-placement-store';
import {
  getRegisteredWorkbenchStepSource,
  useWorkbenchProjectSourceStore,
} from '@/lib/workbench-project-sources';

function record(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {};
}

function tuple3(value: unknown): [number, number, number] | null {
  if (!Array.isArray(value) || value.length !== 3) return null;
  const rows = value.map(Number);
  return rows.every(Number.isFinite) ? rows as [number, number, number] : null;
}

function sameTuple(left: [number, number, number], right: [number, number, number]) {
  return left.every((value, index) => value === right[index]);
}

export function useDeclaredPlacementActions({
  candidateId,
  resourceId,
  entityId,
  modelId,
  evidence,
}: {
  candidateId: ConstructorCandidateId;
  resourceId: string;
  entityId: string;
  modelId: string;
  evidence: MechanicalGeometryEvidence;
}) {
  const existing = useWorkbenchPlacementStore((state) => state.placementsByCandidate[candidateId]?.[entityId]);
  const geometryReport = useWorkbenchPlacementStore((state) => state.geometryReportsByCandidate[candidateId]?.[resourceId]);
  const setPlacement = useWorkbenchPlacementStore((state) => state.setPlacement);
  const clearPlacement = useWorkbenchPlacementStore((state) => state.clearPlacement);
  const clearAccessForEntity = useWorkbenchAccessStore((state) => state.clearAccessForEntity);
  const clearAnchorsForEntity = useWorkbenchBrepAnchorStore((state) => state.clearAnchorsForEntity);
  const clearDraft = useWorkbenchPlacementDraftStore((state) => state.clearDraft);
  const clearBrepRenderMeshEvidence = useMachineWorkbenchStore((state) => state.clearBrepRenderMeshEvidence);
  const setMechanicalGeometryEvidence = useMachineWorkbenchStore((state) => state.setMechanicalGeometryEvidence);
  const setSelectedEntityId = useMachineWorkbenchStore((state) => state.setSelectedEntityId);
  const requestFrameSelection = useMachineWorkbenchStore((state) => state.requestFrameSelection);
  const projectSourceState = useWorkbenchProjectSourceStore();
  const setProjectRevision = useWorkbenchProjectSourceStore((state) => state.setProjectRevision);
  const registeredSource = getRegisteredWorkbenchStepSource(projectSourceState, candidateId, resourceId);
  const projectIntent = projectSourceState.status !== 'unbound';
  const registeredReady = Boolean(
    registeredSource
    && projectSourceState.status === 'bound'
    && projectSourceState.projectId === registeredSource.projectId
    && Number.isInteger(projectSourceState.revision)
    && Number(projectSourceState.revision) >= 1
    && registeredSource.entityId === entityId
    && registeredSource.modelId === modelId
    && registeredSource.sourceId === evidence.sourceId
    && registeredSource.contentHash === evidence.contentHash,
  );

  async function commitPose(
    translationMm: [number, number, number],
    rotationDegXyz: [number, number, number],
  ) {
    if (!geometryReport) throw new Error('Parsed STEP report is unavailable; re-attach the source before placing it.');
    if (projectIntent && !registeredReady) {
      throw new Error('Durable project placement requires the current registered STEP occurrence binding and project revision.');
    }

    const placementId = `placement-${candidateId}-${resourceId}`;
    const response = await fetch('/api/proxy/engineering/mechanical/geometry/place', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({
        geometry: geometryReport,
        placements: [{
          placement_id: placementId,
          object_id: entityId,
          model_id: modelId,
          target_frame: 'assembly',
          translation_mm: translationMm,
          rotation_deg_xyz: rotationDegXyz,
          authority: 'declared',
        }],
      }),
      cache: 'no-store',
    });
    const payload = record(await response.json());
    if (!response.ok || payload.ok !== true) {
      throw new Error(String(payload.error || `mechanical placement HTTP ${response.status}`));
    }
    const boxes = Array.isArray(payload.clearance_boxes) ? payload.clearance_boxes : [];
    const box = record(boxes[0]);
    const minimumMm = tuple3(box.minimum_mm);
    const maximumMm = tuple3(box.maximum_mm);
    if (!minimumMm || !maximumMm) throw new Error('HS placement response did not contain a bounded assembly-frame AABB.');
    const sizeMm = maximumMm.map((value, index) => value - minimumMm[index]) as [number, number, number];
    if (sizeMm.some((value) => value <= 0)) throw new Error('Placed envelope has a zero-size axis.');

    const placement: DeclaredPlacementEvidence = {
      placementId,
      entityId,
      resourceId,
      modelId,
      frameId: String(box.frame_id || 'assembly'),
      translationMm,
      rotationDegXyz,
      minimumMm,
      maximumMm,
      sizeMm,
      authority: 'declared',
      aabbOnly: true,
      fullBrepCollision: false,
      fabricationAuthorized: false,
    };

    let durableRevision: number | null = null;
    if (projectIntent) {
      if (!registeredSource || !projectSourceState.projectId || !registeredReady) {
        throw new Error('Registered project source identity disappeared before placement persistence.');
      }
      const persistResponse = await fetch(
        `/api/proxy/engineering/projects/${encodeURIComponent(projectSourceState.projectId)}/workbench/placements`,
        {
          method: 'POST',
          headers: { 'content-type': 'application/json' },
          body: JSON.stringify({
            expected_revision: projectSourceState.revision,
            candidate_id: candidateId,
            resource_id: resourceId,
            entity_id: entityId,
            source_id: registeredSource.sourceId,
            model_id: registeredSource.modelId,
            content_hash: registeredSource.contentHash,
            placement_id: placementId,
            target_frame: placement.frameId,
            translation_mm: translationMm,
            rotation_deg_xyz: rotationDegXyz,
            authority: 'declared',
          }),
          cache: 'no-store',
        },
      );
      const persistPayload = record(await persistResponse.json());
      if (!persistResponse.ok || persistPayload.ok !== true) {
        throw new Error(String(record(persistPayload.detail).message || persistPayload.error || `workbench placement HTTP ${persistResponse.status}`));
      }
      if (
        persistPayload.registered_source_hash_reverified !== true
        || persistPayload.derived_geometry_persisted !== false
        || persistPayload.physical_authority_unchanged !== true
      ) {
        throw new Error('Durable workbench placement response violated the source-bound transform-only authority contract.');
      }
      const durable = record(persistPayload.workbench_placement);
      const durableTranslation = tuple3(durable.translation_mm);
      const durableRotation = tuple3(durable.rotation_deg_xyz);
      if (
        durable.candidate_id !== candidateId
        || durable.resource_id !== resourceId
        || durable.entity_id !== entityId
        || durable.source_id !== registeredSource.sourceId
        || durable.model_id !== registeredSource.modelId
        || durable.content_hash !== registeredSource.contentHash
        || durable.placement_id !== placementId
        || durable.target_frame !== placement.frameId
        || durable.authority !== 'declared'
        || !durableTranslation
        || !durableRotation
        || !sameTuple(durableTranslation, translationMm)
        || !sameTuple(durableRotation, rotationDegXyz)
      ) {
        throw new Error('Durable workbench placement identity disagrees with the current declared source and pose.');
      }
      durableRevision = Number(persistPayload.revision);
      if (!Number.isInteger(durableRevision) || durableRevision < 1) {
        throw new Error('Durable workbench placement did not return a valid project revision.');
      }
      setProjectRevision(projectSourceState.projectId, durableRevision);
    }

    // Pose-derived evidence is invalid after any declared transform change. Keep
    // the source identity, invalidate derived claims, then project the new pose.
    clearAccessForEntity(candidateId, entityId);
    clearAnchorsForEntity(candidateId, entityId);
    clearBrepRenderMeshEvidence(candidateId, entityId);
    setPlacement(candidateId, placement);
    setMechanicalGeometryEvidence(candidateId, evidence);
    clearDraft(candidateId, entityId);
    setSelectedEntityId(entityId);
    window.setTimeout(requestFrameSelection, 0);

    return { placement, durableRevision };
  }

  async function clearPose() {
    if (!existing) return { durableRevision: null };
    if (projectIntent && !registeredReady) {
      throw new Error('Durable project placement clear requires the current registered STEP occurrence binding and project revision.');
    }

    let durableRevision: number | null = null;
    if (projectIntent) {
      if (!registeredSource || !projectSourceState.projectId || !registeredReady) {
        throw new Error('Registered project source identity disappeared before placement clear.');
      }
      const response = await fetch(
        `/api/proxy/engineering/projects/${encodeURIComponent(projectSourceState.projectId)}/workbench/placements/clear`,
        {
          method: 'POST',
          headers: { 'content-type': 'application/json' },
          body: JSON.stringify({
            expected_revision: projectSourceState.revision,
            candidate_id: candidateId,
            resource_id: resourceId,
            entity_id: entityId,
            source_id: registeredSource.sourceId,
            model_id: registeredSource.modelId,
            content_hash: registeredSource.contentHash,
            placement_id: existing.placementId,
          }),
          cache: 'no-store',
        },
      );
      const payload = record(await response.json());
      if (!response.ok || payload.ok !== true) {
        throw new Error(String(record(payload.detail).message || payload.error || `workbench placement clear HTTP ${response.status}`));
      }
      if (payload.physical_authority_unchanged !== true) {
        throw new Error('Durable workbench placement clear violated the non-authoritative contract.');
      }
      durableRevision = Number(payload.revision);
      if (!Number.isInteger(durableRevision) || durableRevision < 1) {
        throw new Error('Durable workbench placement clear did not return a valid project revision.');
      }
      setProjectRevision(projectSourceState.projectId, durableRevision);
    }

    clearAccessForEntity(candidateId, entityId);
    clearAnchorsForEntity(candidateId, entityId);
    clearBrepRenderMeshEvidence(candidateId, entityId);
    clearPlacement(candidateId, entityId);
    clearDraft(candidateId, entityId);
    setMechanicalGeometryEvidence(candidateId, evidence);
    return { durableRevision };
  }

  return {
    existing,
    projectIntent,
    registeredReady,
    commitPose,
    clearPose,
  };
}

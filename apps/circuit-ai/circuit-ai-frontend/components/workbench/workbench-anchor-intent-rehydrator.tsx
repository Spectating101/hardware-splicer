'use client';

import { useEffect } from 'react';
import type { ConstructorCandidateId } from '@/lib/machine-workbench-store';
import {
  useWorkbenchBrepAnchorStore,
  type BrepSurfaceAnchorEvidence,
} from '@/lib/workbench-brep-anchor-store';
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

function candidateId(value: unknown): ConstructorCandidateId | null {
  return value === 'balanced' || value === 'max-reuse' || value === 'low-risk' ? value : null;
}

function durableAnchorIntents(snapshot: Record<string, unknown>) {
  const rows = Array.isArray(snapshot.machineWorkbenchAnchorIntents)
    ? snapshot.machineWorkbenchAnchorIntents
    : [];
  return rows.flatMap((value) => {
    const row = record(value);
    const resolvedCandidateId = candidateId(row.candidate_id);
    const translationMm = tuple3(row.translation_mm);
    const rotationDegXyz = tuple3(row.rotation_deg_xyz);
    const probePointMm = tuple3(row.probe_point_mm);
    const maxSnapDistanceMm = Number(row.max_snap_distance_mm);
    const contentHash = typeof row.content_hash === 'string' ? row.content_hash : '';
    if (
      row.schema_version !== 'hardware_splicer.workbench_brep_anchor_intent.v1'
      || !resolvedCandidateId
      || typeof row.resource_id !== 'string'
      || typeof row.entity_id !== 'string'
      || typeof row.interface_id !== 'string'
      || typeof row.anchor_id !== 'string'
      || typeof row.source_id !== 'string'
      || typeof row.model_id !== 'string'
      || !/^sha256:[0-9a-f]{64}$/.test(contentHash)
      || typeof row.placement_id !== 'string'
      || row.target_frame !== 'assembly'
      || !translationMm
      || !rotationDegXyz
      || !probePointMm
      || !Number.isFinite(maxSnapDistanceMm)
      || maxSnapDistanceMm < 0
      || row.authority !== 'declared'
      || row.kernel_result_persisted !== false
      || row.face_identity_persisted !== false
      || row.surface_normal_persisted !== false
      || row.requires_occt_resnap_on_reopen !== true
      || row.physical_authority_unchanged !== true
      || row.connector_mating_verified !== false
      || row.fabrication_authorized !== false
    ) return [];
    return [{
      candidateId: resolvedCandidateId,
      resourceId: row.resource_id,
      entityId: row.entity_id,
      interfaceId: row.interface_id,
      anchorId: row.anchor_id,
      sourceId: row.source_id,
      modelId: row.model_id,
      contentHash,
      placementId: row.placement_id,
      translationMm,
      rotationDegXyz,
      probePointMm,
      maxSnapDistanceMm,
    }];
  });
}

export function WorkbenchAnchorIntentRehydrator() {
  const projectId = useWorkbenchProjectSourceStore((state) => state.projectId);
  const projectStatus = useWorkbenchProjectSourceStore((state) => state.status);
  const rehydrateAnchor = useWorkbenchBrepAnchorStore((state) => state.rehydrateAnchor);

  useEffect(() => {
    if (projectStatus !== 'bound' || !projectId) return;
    let cancelled = false;

    void (async () => {
      try {
        const response = await fetch(`/api/proxy/engineering/projects/${encodeURIComponent(projectId)}`, {
          cache: 'no-store',
        });
        const payload = record(await response.json());
        if (!response.ok || payload.ok === false || cancelled) return;
        const project = Object.keys(record(payload.project)).length > 0 ? record(payload.project) : payload;
        const snapshot = Object.keys(record(project.snapshot)).length > 0 ? record(project.snapshot) : project;
        const intents = durableAnchorIntents(snapshot);

        for (const intent of intents) {
          if (cancelled) return;
          const projectState = useWorkbenchProjectSourceStore.getState();
          const registered = getRegisteredWorkbenchStepSource(projectState, intent.candidateId, intent.resourceId);
          if (
            !registered
            || registered.projectId !== projectId
            || registered.entityId !== intent.entityId
            || registered.sourceId !== intent.sourceId
            || registered.modelId !== intent.modelId
            || registered.contentHash !== intent.contentHash
          ) continue;

          const anchorResponse = await fetch('/api/proxy/engineering/mechanical/geometry/brep/anchor/stored', {
            method: 'POST',
            headers: { 'content-type': 'application/json' },
            body: JSON.stringify({
              project_id: projectId,
              anchor_id: intent.anchorId,
              interface_id: intent.interfaceId,
              source: {
                source_id: intent.sourceId,
                model_id: intent.modelId,
                content_hash: intent.contentHash,
              },
              placement: {
                placement_id: intent.placementId,
                object_id: intent.entityId,
                model_id: intent.modelId,
                target_frame: 'assembly',
                translation_mm: intent.translationMm,
                rotation_deg_xyz: intent.rotationDegXyz,
                authority: 'declared',
              },
              probe_point_mm: intent.probePointMm,
              max_snap_distance_mm: intent.maxSnapDistanceMm,
            }),
            cache: 'no-store',
          });
          const anchorPayload = record(await anchorResponse.json());
          if (
            !anchorResponse.ok
            || anchorPayload.ok !== true
            || anchorPayload.exact_brep_surface_anchor_evaluated !== true
            || anchorPayload.registered_source_materialized !== true
            || anchorPayload.registered_source_hash_reverified !== true
            || anchorPayload.raw_registered_source_bytes_returned !== false
            || anchorPayload.authority !== 'declared'
            || anchorPayload.connector_mating_verified !== false
            || anchorPayload.physical_measurement !== false
            || anchorPayload.fabrication_authorized !== false
          ) continue;
          const report = record(anchorPayload.brep_surface_anchor);
          const anchorPointMm = tuple3(report.anchor_point_mm);
          const outwardNormal = tuple3(report.outward_normal);
          const probePointMm = tuple3(report.probe_point_mm);
          const snapDistanceMm = Number(report.snap_distance_mm);
          const faceIndex = Number(report.face_index);
          const faceAreaMm2 = Number(report.face_area_mm2);
          if (
            report.status !== 'ready'
            || report.anchor_id !== intent.anchorId
            || report.interface_id !== intent.interfaceId
            || report.source_id !== intent.sourceId
            || report.model_id !== intent.modelId
            || report.content_hash !== intent.contentHash
            || report.object_id !== intent.entityId
            || report.placement_id !== intent.placementId
            || report.frame_id !== 'assembly'
            || !anchorPointMm
            || !outwardNormal
            || !probePointMm
            || !Number.isFinite(snapDistanceMm)
            || snapDistanceMm < 0
            || snapDistanceMm > intent.maxSnapDistanceMm
            || !Number.isInteger(faceIndex)
            || faceIndex < 0
            || !Number.isFinite(faceAreaMm2)
            || faceAreaMm2 <= 0
            || Math.abs(Math.hypot(...outwardNormal) - 1) > 1e-5
          ) continue;

          const anchor: BrepSurfaceAnchorEvidence = {
            anchorId: intent.anchorId,
            interfaceId: intent.interfaceId,
            entityId: intent.entityId,
            resourceId: intent.resourceId,
            sourceId: intent.sourceId,
            modelId: intent.modelId,
            contentHash: intent.contentHash,
            frameId: 'assembly',
            placementId: intent.placementId,
            translationMm: intent.translationMm,
            rotationDegXyz: intent.rotationDegXyz,
            probePointMm,
            anchorPointMm,
            outwardNormal,
            snapDistanceMm,
            faceIndex,
            faceGeomType: String(report.face_geom_type || 'unknown'),
            faceAreaMm2,
            authority: 'declared',
            connectorMatingVerified: false,
            physicalMeasurement: false,
            fabricationAuthorized: false,
          };
          rehydrateAnchor(intent.candidateId, anchor);
        }
      } catch {
        // Rehydration is fail-closed: source/placement durability remains valid even
        // when optional OCCT anchor recreation is unavailable. No stale anchor is
        // manufactured from persisted face output because none is stored.
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [projectId, projectStatus, rehydrateAnchor]);

  return null;
}

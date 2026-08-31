'use client';

import { useEffect } from 'react';
import {
  type ConstructorCandidateId,
  type MechanicalGeometryEvidence,
  useMachineWorkbenchStore,
} from '@/lib/machine-workbench-store';
import {
  type ProjectSourceDescriptor,
  type ProjectStepBindingDescriptor,
  useWorkbenchProjectSourceStore,
} from '@/lib/workbench-project-sources';
import {
  type DeclaredPlacementEvidence,
  useWorkbenchPlacementStore,
} from '@/lib/workbench-placement-store';

function record(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {};
}

function tuple3(value: unknown): [number, number, number] | null {
  if (!Array.isArray(value) || value.length !== 3) return null;
  const rows = value.map(Number);
  return rows.every(Number.isFinite) ? rows as [number, number, number] : null;
}

function normalizeMillimeters(value: [number, number, number], units: string) {
  if (units === 'mm') return value;
  if (units === 'm') return value.map((row) => row * 1000) as [number, number, number];
  return null;
}

function candidateId(value: unknown): ConstructorCandidateId | undefined {
  return value === 'balanced' || value === 'max-reuse' || value === 'low-risk'
    ? value
    : undefined;
}

function projectSources(snapshot: Record<string, unknown>): ProjectSourceDescriptor[] {
  const rows = Array.isArray(snapshot.engineeringSources) ? snapshot.engineeringSources : [];
  return rows.flatMap((value) => {
    const row = record(value);
    const sourceId = typeof row.source_id === 'string' ? row.source_id : '';
    const contentHash = typeof row.content_hash === 'string' ? row.content_hash : '';
    if (!sourceId || !/^sha256:[0-9a-f]{64}$/.test(contentHash)) return [];
    const metadata = record(row.metadata);
    return [{
      sourceId,
      contentHash,
      originalFilename: typeof metadata.original_filename === 'string' ? metadata.original_filename : undefined,
      parserRoute: typeof metadata.parser_route === 'string' ? metadata.parser_route : undefined,
    }];
  });
}

function explicitProjectBindings(snapshot: Record<string, unknown>): ProjectStepBindingDescriptor[] {
  const rows = Array.isArray(snapshot.machineWorkbenchStepBindings)
    ? snapshot.machineWorkbenchStepBindings
    : [];
  return rows.flatMap((value) => {
    const row = record(value);
    const resolvedCandidateId = candidateId(row.candidate_id);
    const resourceId = typeof row.resource_id === 'string' ? row.resource_id.trim() : '';
    const entityId = typeof row.entity_id === 'string' ? row.entity_id.trim() : '';
    const sourceId = typeof row.source_id === 'string' ? row.source_id.trim() : '';
    const modelId = typeof row.model_id === 'string' ? row.model_id.trim() : '';
    const contentHash = typeof row.content_hash === 'string' ? row.content_hash : '';
    if (
      row.schema_version !== 'hardware_splicer.workbench_step_binding.v1'
      || !resolvedCandidateId
      || !resourceId
      || !entityId
      || !sourceId
      || !modelId
      || !/^sha256:[0-9a-f]{64}$/.test(contentHash)
      || row.source_binding_only !== true
      || row.physical_authority_unchanged !== true
      || row.automatic_authorization !== false
    ) return [];
    return [{
      candidateId: resolvedCandidateId,
      resourceId,
      entityId,
      sourceId,
      modelId,
      contentHash,
    }];
  });
}

function legacyProjectBindings(
  snapshot: Record<string, unknown>,
  sources: ProjectSourceDescriptor[],
): ProjectStepBindingDescriptor[] {
  const allowed = new Set(sources.map((source) => `${source.sourceId}::${source.contentHash}`));
  const rows = Array.isArray(snapshot.engineeringSources) ? snapshot.engineeringSources : [];
  return rows.flatMap((value) => {
    const row = record(value);
    const metadata = record(row.metadata);
    const resolvedCandidateId = candidateId(metadata.workbench_candidate_id);
    const resourceId = typeof metadata.workbench_resource_id === 'string' ? metadata.workbench_resource_id.trim() : '';
    const entityId = typeof metadata.workbench_entity_id === 'string' ? metadata.workbench_entity_id.trim() : '';
    const sourceId = typeof row.source_id === 'string' ? row.source_id.trim() : '';
    const contentHash = typeof row.content_hash === 'string' ? row.content_hash : '';
    if (
      metadata.parser_route !== 'step_geometry'
      || !resolvedCandidateId
      || !resourceId
      || !entityId
      || !sourceId
      || !/^sha256:[0-9a-f]{64}$/.test(contentHash)
      || !allowed.has(`${sourceId}::${contentHash}`)
    ) return [];
    return [{
      candidateId: resolvedCandidateId,
      resourceId,
      entityId,
      sourceId,
      modelId: sourceId,
      contentHash,
    }];
  });
}

type ProjectPlacementIntent = {
  candidateId: ConstructorCandidateId;
  resourceId: string;
  entityId: string;
  sourceId: string;
  modelId: string;
  contentHash: string;
  placementId: string;
  frameId: 'assembly';
  translationMm: [number, number, number];
  rotationDegXyz: [number, number, number];
};

function projectPlacements(snapshot: Record<string, unknown>): ProjectPlacementIntent[] {
  const rows = Array.isArray(snapshot.machineWorkbenchPlacements)
    ? snapshot.machineWorkbenchPlacements
    : [];
  return rows.flatMap((value) => {
    const row = record(value);
    const resolvedCandidateId = candidateId(row.candidate_id);
    const resourceId = typeof row.resource_id === 'string' ? row.resource_id.trim() : '';
    const entityId = typeof row.entity_id === 'string' ? row.entity_id.trim() : '';
    const sourceId = typeof row.source_id === 'string' ? row.source_id.trim() : '';
    const modelId = typeof row.model_id === 'string' ? row.model_id.trim() : '';
    const contentHash = typeof row.content_hash === 'string' ? row.content_hash : '';
    const placementId = typeof row.placement_id === 'string' ? row.placement_id.trim() : '';
    const translationMm = tuple3(row.translation_mm);
    const rotationDegXyz = tuple3(row.rotation_deg_xyz);
    if (
      row.schema_version !== 'hardware_splicer.workbench_declared_placement.v1'
      || !resolvedCandidateId
      || !resourceId
      || !entityId
      || !sourceId
      || !modelId
      || !placementId
      || !/^sha256:[0-9a-f]{64}$/.test(contentHash)
      || row.target_frame !== 'assembly'
      || !translationMm
      || !rotationDegXyz
      || row.authority !== 'declared'
      || row.source_binding_required !== true
      || row.registered_source_hash_reverified !== true
      || row.derived_geometry_persisted !== false
      || row.physical_authority_unchanged !== true
      || row.automatic_authorization !== false
    ) return [];
    return [{
      candidateId: resolvedCandidateId,
      resourceId,
      entityId,
      sourceId,
      modelId,
      contentHash,
      placementId,
      frameId: 'assembly' as const,
      translationMm,
      rotationDegXyz,
    }];
  });
}

function parserGeometryForBinding(
  snapshot: Record<string, unknown>,
  binding: ProjectStepBindingDescriptor,
): Record<string, unknown> | null {
  const rows = Array.isArray(snapshot.engineeringSourceParserRuns)
    ? snapshot.engineeringSourceParserRuns
    : [];
  const run = rows.map(record).find((row) => (
    row.parser_route === 'step_geometry'
    && row.status === 'parsed'
    && row.source_id === binding.sourceId
    && row.content_hash === binding.contentHash
    && row.automatic_authorization === false
  ));
  if (!run) return null;
  const parsedOutput = record(run.parsed_output);
  const stepModel = record(parsedOutput.step_model);
  const geometry = record(parsedOutput.mechanical_geometry);
  if (
    stepModel.source_id !== binding.sourceId
    || stepModel.model_id !== binding.modelId
    || stepModel.content_hash !== binding.contentHash
    || !Object.keys(geometry).length
  ) return null;
  return geometry;
}

function geometryEvidence(
  binding: ProjectStepBindingDescriptor,
  geometry: Record<string, unknown>,
): MechanicalGeometryEvidence | null {
  const models = Array.isArray(geometry.models) ? geometry.models : [];
  const model = models.map(record).find((row) => (
    row.source_id === binding.sourceId
    && row.model_id === binding.modelId
    && row.content_hash === binding.contentHash
  ));
  if (!model) return null;
  const boundingBox = record(model.bounding_box);
  const rawSize = tuple3(boundingBox.size);
  const rawMinimum = tuple3(boundingBox.minimum);
  const rawMaximum = tuple3(boundingBox.maximum);
  const units = String(boundingBox.units || model.units || 'unknown');
  if (!rawSize || !rawMinimum || !rawMaximum) return null;
  const sizeMm = normalizeMillimeters(rawSize, units);
  const minimumMm = normalizeMillimeters(rawMinimum, units);
  const maximumMm = normalizeMillimeters(rawMaximum, units);
  if (!sizeMm || !minimumMm || !maximumMm || sizeMm.some((value) => value <= 0)) return null;
  const unresolved = Array.isArray(model.unresolved)
    ? model.unresolved.map((value) => {
        const row = record(value);
        return {
          field: typeof row.field === 'string' ? row.field : undefined,
          reason: typeof row.reason === 'string' ? row.reason : undefined,
        };
      })
    : [];
  return {
    entityId: binding.entityId,
    resourceId: binding.resourceId,
    sourceId: binding.sourceId,
    modelId: binding.modelId,
    contentHash: binding.contentHash,
    authority: 'declared',
    units: 'mm',
    sizeMm,
    minimumMm,
    maximumMm,
    pointCount: Number(boundingBox.point_count || model.cartesian_point_count || 0),
    unresolved,
    stepPointEnvelopeOnly: true,
    fullBrepCollision: false,
    fabricationAuthorized: false,
  };
}

function placementMatchesBinding(intent: ProjectPlacementIntent, binding: ProjectStepBindingDescriptor) {
  return intent.candidateId === binding.candidateId
    && intent.resourceId === binding.resourceId
    && intent.entityId === binding.entityId
    && intent.sourceId === binding.sourceId
    && intent.modelId === binding.modelId
    && intent.contentHash === binding.contentHash;
}

export function WorkbenchProjectBridge() {
  const beginProjectLoad = useWorkbenchProjectSourceStore((state) => state.beginProjectLoad);
  const bindProject = useWorkbenchProjectSourceStore((state) => state.bindProject);
  const failProjectLoad = useWorkbenchProjectSourceStore((state) => state.failProjectLoad);
  const clearProject = useWorkbenchProjectSourceStore((state) => state.clearProject);
  const setGeometryReport = useWorkbenchPlacementStore((state) => state.setGeometryReport);
  const setPlacement = useWorkbenchPlacementStore((state) => state.setPlacement);
  const setMechanicalGeometryEvidence = useMachineWorkbenchStore((state) => state.setMechanicalGeometryEvidence);

  useEffect(() => {
    const projectId = new URLSearchParams(window.location.search).get('project')?.trim() ?? '';
    if (!projectId) {
      clearProject();
      return;
    }

    let cancelled = false;
    beginProjectLoad(projectId);

    void (async () => {
      try {
        const response = await fetch(`/api/proxy/engineering/projects/${encodeURIComponent(projectId)}`, {
          cache: 'no-store',
        });
        const payload = record(await response.json());
        if (!response.ok || payload.ok === false) {
          const detail = record(payload.detail);
          throw new Error(String(detail.message || payload.error || `project HTTP ${response.status}`));
        }
        const project = Object.keys(record(payload.project)).length > 0 ? record(payload.project) : payload;
        const snapshot = Object.keys(record(project.snapshot)).length > 0 ? record(project.snapshot) : project;
        const revision = Number(project.revision);
        if (!Number.isInteger(revision) || revision < 1) {
          throw new Error('Project response did not include a valid durable revision.');
        }
        const sources = projectSources(snapshot);
        const explicitBindings = explicitProjectBindings(snapshot);
        const bindings = explicitBindings.length > 0
          ? explicitBindings
          : legacyProjectBindings(snapshot, sources);
        const placements = projectPlacements(snapshot);

        for (const binding of bindings) {
          if (cancelled) return;
          const geometry = parserGeometryForBinding(snapshot, binding);
          if (!geometry) continue;
          const evidence = geometryEvidence(binding, geometry);
          if (!evidence) continue;
          setGeometryReport(binding.candidateId, binding.resourceId, geometry);
          setMechanicalGeometryEvidence(binding.candidateId, evidence);

          const intent = placements.find((row) => placementMatchesBinding(row, binding));
          if (!intent) continue;
          try {
            const placementResponse = await fetch('/api/proxy/engineering/mechanical/geometry/place', {
              method: 'POST',
              headers: { 'content-type': 'application/json' },
              body: JSON.stringify({
                geometry,
                placements: [{
                  placement_id: intent.placementId,
                  object_id: intent.entityId,
                  model_id: intent.modelId,
                  target_frame: intent.frameId,
                  translation_mm: intent.translationMm,
                  rotation_deg_xyz: intent.rotationDegXyz,
                  authority: 'declared',
                }],
              }),
              cache: 'no-store',
            });
            const placementPayload = record(await placementResponse.json());
            if (!placementResponse.ok || placementPayload.ok !== true) continue;
            const boxes = Array.isArray(placementPayload.clearance_boxes) ? placementPayload.clearance_boxes : [];
            const box = record(boxes[0]);
            const minimumMm = tuple3(box.minimum_mm);
            const maximumMm = tuple3(box.maximum_mm);
            if (!minimumMm || !maximumMm || box.frame_id !== intent.frameId) continue;
            const sizeMm = maximumMm.map((value, index) => value - minimumMm[index]) as [number, number, number];
            if (sizeMm.some((value) => value <= 0)) continue;
            const placement: DeclaredPlacementEvidence = {
              placementId: intent.placementId,
              entityId: intent.entityId,
              resourceId: intent.resourceId,
              modelId: intent.modelId,
              frameId: intent.frameId,
              translationMm: intent.translationMm,
              rotationDegXyz: intent.rotationDegXyz,
              minimumMm,
              maximumMm,
              sizeMm,
              authority: 'declared',
              aabbOnly: true,
              fullBrepCollision: false,
              fabricationAuthorized: false,
            };
            if (cancelled) return;
            setPlacement(binding.candidateId, placement);
            setMechanicalGeometryEvidence(binding.candidateId, evidence);
          } catch {
            // A durable transform whose derived placement cannot be recomputed is not
            // restored as scene truth. The registered source remains available so the
            // operator can explicitly re-place it against the current backend.
          }
        }

        if (cancelled) return;
        bindProject(projectId, revision, sources, bindings);
      } catch (error: unknown) {
        if (cancelled) return;
        failProjectLoad(projectId, error instanceof Error ? error.message : String(error));
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [beginProjectLoad, bindProject, clearProject, failProjectLoad, setGeometryReport, setMechanicalGeometryEvidence, setPlacement]);

  return null;
}

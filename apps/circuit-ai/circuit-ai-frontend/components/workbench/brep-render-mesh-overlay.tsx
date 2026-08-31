'use client';

import type { ThreeEvent } from '@react-three/fiber';
import { Html, Line } from '@react-three/drei';
import { useEffect, useMemo } from 'react';
import { BufferGeometry, Float32BufferAttribute, Vector3 } from 'three';
import { buildCandidateMachineProjection } from '@/lib/workbench-machine-projection';
import {
  useMachineWorkbenchStore,
  type BrepRenderMeshEvidence,
  type ConstructorCandidateId,
} from '@/lib/machine-workbench-store';
import {
  useWorkbenchPlacementStore,
  type DeclaredPlacementEvidence,
} from '@/lib/workbench-placement-store';
import {
  useWorkbenchBrepAnchorStore,
  type BrepSurfaceAnchorEvidence,
} from '@/lib/workbench-brep-anchor-store';
import { getSessionStepSource } from '@/lib/workbench-session-step-sources';
import {
  getRegisteredWorkbenchStepSource,
  useWorkbenchProjectSourceStore,
} from '@/lib/workbench-project-sources';

const SCENE_UNITS_PER_MM = 0.025;
const EMPTY_PLACEMENTS: Record<string, DeclaredPlacementEvidence> = {};
const EMPTY_MESHES: Record<string, BrepRenderMeshEvidence> = {};
const EMPTY_ANCHORS: Record<string, BrepSurfaceAnchorEvidence> = {};

function record(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {};
}

function tuple3(value: unknown): [number, number, number] | null {
  if (!Array.isArray(value) || value.length !== 3) return null;
  const rows = value.map(Number);
  return rows.every(Number.isFinite) ? rows as [number, number, number] : null;
}

function canonicalPointToScene(point: [number, number, number]): [number, number, number] {
  const [xMm, yMm, zMm] = point;
  return [xMm * SCENE_UNITS_PER_MM, zMm * SCENE_UNITS_PER_MM, yMm * SCENE_UNITS_PER_MM];
}

function canonicalVectorToScene(vector: [number, number, number]): [number, number, number] {
  const [x, y, z] = vector;
  return [x, z, y];
}

function scenePointToCanonicalMm(point: Vector3): [number, number, number] {
  return [
    point.x / SCENE_UNITS_PER_MM,
    point.z / SCENE_UNITS_PER_MM,
    point.y / SCENE_UNITS_PER_MM,
  ];
}

function sameTuple(left: [number, number, number], right: [number, number, number]) {
  return left.every((value, index) => value === right[index]);
}

function meshMatchesPlacement(mesh: BrepRenderMeshEvidence, placement: DeclaredPlacementEvidence | undefined) {
  return Boolean(
    placement
    && mesh.entityId === placement.entityId
    && mesh.resourceId === placement.resourceId
    && mesh.modelId === placement.modelId
    && mesh.frameId === placement.frameId
    && mesh.placementId === placement.placementId
    && sameTuple(mesh.translationMm, placement.translationMm)
    && sameTuple(mesh.rotationDegXyz, placement.rotationDegXyz),
  );
}

function anchorMatchesCurrentGeometry(
  anchor: BrepSurfaceAnchorEvidence,
  placement: DeclaredPlacementEvidence | undefined,
  mesh: BrepRenderMeshEvidence | undefined,
) {
  return Boolean(
    placement
    && mesh
    && anchor.entityId === placement.entityId
    && anchor.resourceId === placement.resourceId
    && anchor.modelId === placement.modelId
    && anchor.contentHash === mesh.contentHash
    && anchor.frameId === placement.frameId
    && anchor.placementId === placement.placementId
    && sameTuple(anchor.translationMm, placement.translationMm)
    && sameTuple(anchor.rotationDegXyz, placement.rotationDegXyz),
  );
}

function ExactAnchor({ anchor, selected }: { anchor: BrepSurfaceAnchorEvidence; selected: boolean }) {
  const point = canonicalPointToScene(anchor.anchorPointMm);
  const normal = canonicalVectorToScene(anchor.outwardNormal);
  const normalEnd: [number, number, number] = [
    point[0] + normal[0] * 0.72,
    point[1] + normal[1] * 0.72,
    point[2] + normal[2] * 0.72,
  ];
  const labelPosition: [number, number, number] = [point[0], point[1] + 0.34, point[2]];

  return (
    <group>
      <mesh position={point} renderOrder={12}>
        <sphereGeometry args={[0.105, 18, 18]} />
        <meshBasicMaterial color="#f0abfc" depthWrite={false} />
      </mesh>
      <Line points={[point, normalEnd]} color="#e879f9" lineWidth={2.4} transparent opacity={0.95} />
      {selected ? (
        <Html center position={labelPosition} distanceFactor={9}>
          <div
            data-testid="exact-brep-surface-anchor"
            data-anchor-id={anchor.anchorId}
            data-interface-id={anchor.interfaceId}
            data-face-index={anchor.faceIndex}
            className="pointer-events-none whitespace-nowrap rounded-md border border-fuchsia-300/30 bg-slate-950/94 px-2.5 py-1.5 text-[9px] font-semibold text-fuchsia-50 shadow-2xl"
          >
            <div>{anchor.interfaceId} · DECLARED BREP ANCHOR</div>
            <div className="mt-0.5 text-[8px] uppercase tracking-[0.1em] text-fuchsia-300">{anchor.faceGeomType} face {anchor.faceIndex} · snap {anchor.snapDistanceMm.toFixed(3)} mm</div>
            <div className="mt-0.5 text-[7px] font-medium normal-case tracking-normal text-slate-500">Exact point + outward normal · mating remains unverified.</div>
          </div>
        </Html>
      ) : null}
    </group>
  );
}

function ExactMesh({
  candidateId,
  mesh,
  placement,
  selected,
}: {
  candidateId: ConstructorCandidateId;
  mesh: BrepRenderMeshEvidence;
  placement: DeclaredPlacementEvidence;
  selected: boolean;
}) {
  const armedPick = useWorkbenchBrepAnchorStore((state) => state.armedPick);
  const setPickFeedback = useWorkbenchBrepAnchorStore((state) => state.setPickFeedback);
  const setAnchor = useWorkbenchBrepAnchorStore((state) => state.setAnchor);
  const geometry = useMemo(() => {
    const resolved = new BufferGeometry();
    const positions = new Float32Array(mesh.vertexCount * 3);
    mesh.verticesMm.forEach((vertex, index) => {
      const scene = canonicalPointToScene(vertex);
      positions[index * 3] = scene[0];
      positions[index * 3 + 1] = scene[1];
      positions[index * 3 + 2] = scene[2];
    });
    resolved.setAttribute('position', new Float32BufferAttribute(positions, 3));
    resolved.setIndex(mesh.triangles.flat());
    resolved.computeVertexNormals();
    resolved.computeBoundingBox();
    resolved.computeBoundingSphere();
    return resolved;
  }, [mesh]);

  useEffect(() => () => geometry.dispose(), [geometry]);

  const center = geometry.boundingBox?.getCenter(new Vector3());
  const labelPosition: [number, number, number] = center
    ? [center.x, (geometry.boundingBox?.max.y ?? center.y) + 0.38, center.z]
    : [0, 0, 0];
  const pickArmed = Boolean(
    armedPick
    && armedPick.candidateId === candidateId
    && armedPick.entityId === mesh.entityId
    && armedPick.resourceId === mesh.resourceId,
  );

  async function handleSurfacePick(event: ThreeEvent<PointerEvent>) {
    if (!pickArmed || !armedPick) return;
    event.stopPropagation();

    const sessionSource = getSessionStepSource(candidateId, mesh.resourceId);
    const projectSourceState = useWorkbenchProjectSourceStore.getState();
    const registeredSource = getRegisteredWorkbenchStepSource(projectSourceState, candidateId, mesh.resourceId);
    const registeredReady = Boolean(
      registeredSource
      && projectSourceState.status === 'bound'
      && projectSourceState.projectId === registeredSource.projectId
      && registeredSource.entityId === mesh.entityId
      && registeredSource.modelId === mesh.modelId
      && registeredSource.contentHash === mesh.contentHash,
    );
    const sessionReady = Boolean(
      sessionSource
      && sessionSource.modelId === mesh.modelId
      && sessionSource.contentHash === mesh.contentHash,
    );
    if (!registeredReady && !sessionReady) {
      setPickFeedback('error', 'Surface pick rejected: no explicit registered-project source or matching session STEP is available for this exact mesh.');
      return;
    }
    const sourceIdentity = registeredReady && registeredSource ? registeredSource : sessionSource;
    if (!sourceIdentity) return;

    const localScenePoint = event.eventObject.worldToLocal(event.point.clone());
    const probePointMm = scenePointToCanonicalMm(localScenePoint);
    const anchorId = `anchor-${candidateId}-${mesh.entityId}-${armedPick.interfaceId}`;
    setPickFeedback(
      'loading',
      registeredReady
        ? 'Reopening the registered STEP blob, re-verifying its hash, and snapping the 3D probe to the nearest exact OCCT face…'
        : 'Snapping the 3D probe to the nearest exact OCCT face…',
    );

    try {
      const endpoint = registeredReady
        ? '/api/proxy/engineering/mechanical/geometry/brep/anchor/stored'
        : '/api/proxy/engineering/mechanical/geometry/brep/anchor';
      const response = await fetch(endpoint, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({
          project_id: registeredReady && registeredSource ? registeredSource.projectId : 'deck-001',
          anchor_id: anchorId,
          interface_id: armedPick.interfaceId,
          source: registeredReady
            ? {
                source_id: sourceIdentity.sourceId,
                model_id: sourceIdentity.modelId,
                content_hash: sourceIdentity.contentHash,
              }
            : {
                source_id: sourceIdentity.sourceId,
                model_id: sourceIdentity.modelId,
                content_hash: sourceIdentity.contentHash,
                content: sessionSource?.content,
              },
          placement: {
            placement_id: placement.placementId,
            object_id: placement.entityId,
            model_id: placement.modelId,
            target_frame: placement.frameId,
            translation_mm: placement.translationMm,
            rotation_deg_xyz: placement.rotationDegXyz,
            authority: 'declared',
          },
          probe_point_mm: probePointMm,
          max_snap_distance_mm: 5,
        }),
        cache: 'no-store',
      });
      const payload = record(await response.json());
      if (!response.ok || payload.ok !== true) throw new Error(String(record(payload.detail).message || payload.error || `BREP anchor HTTP ${response.status}`));
      if (
        payload.raw_step_bytes_returned !== false
        || payload.authority !== 'declared'
        || payload.connector_mating_verified !== false
        || payload.physical_measurement !== false
        || payload.fabrication_authorized !== false
      ) {
        throw new Error('HS BREP anchor response violated the declared/non-authoritative boundary.');
      }
      if (registeredReady && (
        payload.registered_source_materialized !== true
        || payload.registered_source_hash_reverified !== true
        || payload.raw_registered_source_bytes_returned !== false
      )) {
        throw new Error('Stored BREP anchor response did not prove registered-blob materialization and hash re-verification.');
      }
      const report = record(payload.brep_surface_anchor);
      if (payload.exact_brep_surface_anchor_evaluated !== true || report.status !== 'ready') {
        const required = Array.isArray(report.required_evidence) ? report.required_evidence.map(record) : [];
        setPickFeedback('unknown', `Exact surface anchor UNKNOWN · ${String(required[0]?.reason || 'OCCT did not return a bounded surface anchor.')}`);
        return;
      }
      if (
        report.content_hash !== mesh.contentHash
        || report.model_id !== mesh.modelId
        || report.frame_id !== placement.frameId
        || report.placement_id !== placement.placementId
        || report.interface_id !== armedPick.interfaceId
      ) {
        throw new Error('HS BREP anchor identity disagrees with the selected exact mesh, pose, or interface.');
      }

      const anchorPointMm = tuple3(report.anchor_point_mm);
      const outwardNormal = tuple3(report.outward_normal);
      const echoedProbe = tuple3(report.probe_point_mm);
      const snapDistanceMm = Number(report.snap_distance_mm);
      const faceIndex = Number(report.face_index);
      const faceAreaMm2 = Number(report.face_area_mm2);
      if (!anchorPointMm || !outwardNormal || !echoedProbe) throw new Error('HS BREP anchor returned malformed point/normal evidence.');
      if (!Number.isFinite(snapDistanceMm) || snapDistanceMm < 0 || snapDistanceMm > 5) throw new Error('HS BREP anchor snap distance violates the bounded request.');
      if (!Number.isInteger(faceIndex) || faceIndex < 0 || !Number.isFinite(faceAreaMm2) || faceAreaMm2 <= 0) throw new Error('HS BREP anchor returned malformed face identity.');
      const normalLength = Math.hypot(...outwardNormal);
      if (Math.abs(normalLength - 1) > 1e-5) throw new Error('HS BREP anchor returned a non-unit surface normal.');

      setAnchor(candidateId, {
        anchorId,
        interfaceId: armedPick.interfaceId,
        entityId: mesh.entityId,
        resourceId: mesh.resourceId,
        sourceId: mesh.sourceId,
        modelId: mesh.modelId,
        contentHash: mesh.contentHash,
        frameId: placement.frameId,
        placementId: placement.placementId,
        translationMm: placement.translationMm,
        rotationDegXyz: placement.rotationDegXyz,
        probePointMm: echoedProbe,
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
      });
    } catch (error: unknown) {
      setPickFeedback('error', error instanceof Error ? error.message : String(error));
    }
  }

  return (
    <group onPointerDown={handleSurfacePick}>
      <mesh geometry={geometry} castShadow receiveShadow renderOrder={5}>
        <meshStandardMaterial color={pickArmed ? '#d946ef' : '#38bdf8'} roughness={0.42} metalness={0.18} transparent opacity={0.86} />
      </mesh>
      <mesh geometry={geometry} scale={[1.001, 1.001, 1.001]} renderOrder={6}>
        <meshBasicMaterial color={pickArmed ? '#f5d0fe' : '#a5f3fc'} transparent opacity={pickArmed ? 0.58 : selected ? 0.48 : 0.18} wireframe depthWrite={false} />
      </mesh>
      {selected ? (
        <Html center position={labelPosition} distanceFactor={9}>
          <div
            data-testid="exact-brep-render-mesh"
            data-entity-id={mesh.entityId}
            data-content-hash={mesh.contentHash}
            data-surface-pick-armed={pickArmed ? 'true' : 'false'}
            className={`pointer-events-none whitespace-nowrap rounded-md border bg-slate-950/94 px-2.5 py-1.5 text-[9px] font-semibold shadow-2xl ${pickArmed ? 'border-fuchsia-300/40 text-fuchsia-50' : 'border-cyan-300/30 text-cyan-50'}`}
          >
            <div>{pickArmed ? 'SURFACE PICK ARMED' : 'EXACT BREP DISPLAY MESH'} · {mesh.triangleCount.toLocaleString()} triangles</div>
            <div className="mt-0.5 text-[7px] font-medium normal-case tracking-normal text-slate-500">Hash-bound STEP · declared {mesh.frameId} pose · render evidence only.</div>
          </div>
        </Html>
      ) : null}
    </group>
  );
}

export function BrepRenderMeshOverlays() {
  const phase = useMachineWorkbenchStore((state) => state.phase);
  const activeCandidateId = useMachineWorkbenchStore((state) => state.activeCandidateId);
  const plannerSource = useMachineWorkbenchStore((state) => state.plannerSource);
  const plannerProjection = useMachineWorkbenchStore((state) => state.plannerProjections[activeCandidateId]);
  const selectedEntityId = useMachineWorkbenchStore((state) => state.selectedEntityId);
  const isolatedEntityId = useMachineWorkbenchStore((state) => state.isolatedEntityId);
  const exploded = useMachineWorkbenchStore((state) => state.exploded);
  const meshes = plannerProjection?.brepRenderMeshByEntity ?? EMPTY_MESHES;
  const anchors = useWorkbenchBrepAnchorStore(
    (state) => state.anchorsByCandidate[activeCandidateId] ?? EMPTY_ANCHORS,
  );
  const placements = useWorkbenchPlacementStore(
    (state) => state.placementsByCandidate[activeCandidateId] ?? EMPTY_PLACEMENTS,
  );
  const candidateProjection = useMemo(
    () => buildCandidateMachineProjection(activeCandidateId, plannerSource, plannerProjection, placements),
    [activeCandidateId, plannerSource, plannerProjection, placements],
  );

  if (phase !== 'construct' || exploded) return null;

  return (
    <>
      {Object.values(meshes).map((mesh) => {
        const placement = placements[mesh.entityId];
        const part = candidateProjection.parts[mesh.entityId];
        if (!meshMatchesPlacement(mesh, placement) || !placement) return null;
        if (!part || part.visible === false || part.resourceId !== mesh.resourceId) return null;
        if (isolatedEntityId && isolatedEntityId !== mesh.entityId) return null;
        return (
          <ExactMesh
            key={`${mesh.entityId}-${mesh.contentHash}-${mesh.placementId}`}
            candidateId={activeCandidateId}
            mesh={mesh}
            placement={placement}
            selected={selectedEntityId === mesh.entityId}
          />
        );
      })}
      {Object.values(anchors).map((anchor) => {
        const placement = placements[anchor.entityId];
        const mesh = meshes[anchor.entityId];
        const part = candidateProjection.parts[anchor.entityId];
        if (!anchorMatchesCurrentGeometry(anchor, placement, mesh)) return null;
        if (!part || part.visible === false || part.resourceId !== anchor.resourceId) return null;
        if (isolatedEntityId && isolatedEntityId !== anchor.entityId) return null;
        return <ExactAnchor key={anchor.anchorId} anchor={anchor} selected={selectedEntityId === anchor.entityId} />;
      })}
    </>
  );
}

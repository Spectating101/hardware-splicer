'use client';

import { Html } from '@react-three/drei';
import { useEffect, useMemo } from 'react';
import { BufferGeometry, Float32BufferAttribute } from 'three';
import {
  useMachineWorkbenchStore,
  type BrepRenderMeshEvidence,
} from '@/lib/machine-workbench-store';
import {
  useWorkbenchPlacementStore,
  type DeclaredPlacementEvidence,
} from '@/lib/workbench-placement-store';

const SCENE_UNITS_PER_MM = 0.025;
const EMPTY_PLACEMENTS: Record<string, DeclaredPlacementEvidence> = {};
const EMPTY_MESHES: Record<string, BrepRenderMeshEvidence> = {};

function canonicalPointToScene(point: [number, number, number]): [number, number, number] {
  const [xMm, yMm, zMm] = point;
  return [xMm * SCENE_UNITS_PER_MM, zMm * SCENE_UNITS_PER_MM, yMm * SCENE_UNITS_PER_MM];
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

function ExactMesh({ mesh, selected }: { mesh: BrepRenderMeshEvidence; selected: boolean }) {
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

  const center = geometry.boundingBox?.getCenter({ x: 0, y: 0, z: 0 } as never);
  const labelPosition: [number, number, number] = center
    ? [center.x, (geometry.boundingBox?.max.y ?? center.y) + 0.38, center.z]
    : [0, 0, 0];

  return (
    <group>
      <mesh geometry={geometry} castShadow receiveShadow renderOrder={5}>
        <meshStandardMaterial color="#38bdf8" roughness={0.42} metalness={0.18} transparent opacity={0.86} />
      </mesh>
      <mesh geometry={geometry} scale={[1.001, 1.001, 1.001]} renderOrder={6}>
        <meshBasicMaterial color="#a5f3fc" transparent opacity={selected ? 0.48 : 0.18} wireframe depthWrite={false} />
      </mesh>
      {selected ? (
        <Html center position={labelPosition} distanceFactor={9}>
          <div
            data-testid="exact-brep-render-mesh"
            data-entity-id={mesh.entityId}
            data-content-hash={mesh.contentHash}
            className="pointer-events-none whitespace-nowrap rounded-md border border-cyan-300/30 bg-slate-950/94 px-2.5 py-1.5 text-[9px] font-semibold text-cyan-50 shadow-2xl"
          >
            <div>EXACT BREP DISPLAY MESH · {mesh.triangleCount.toLocaleString()} triangles</div>
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
  const selectedEntityId = useMachineWorkbenchStore((state) => state.selectedEntityId);
  const meshes = useMachineWorkbenchStore(
    (state) => state.plannerProjections[activeCandidateId]?.brepRenderMeshByEntity ?? EMPTY_MESHES,
  );
  const placements = useWorkbenchPlacementStore(
    (state) => state.placementsByCandidate[activeCandidateId] ?? EMPTY_PLACEMENTS,
  );

  if (phase !== 'construct') return null;

  return (
    <>
      {Object.values(meshes).map((mesh) => {
        const placement = placements[mesh.entityId];
        if (!meshMatchesPlacement(mesh, placement)) return null;
        return <ExactMesh key={`${mesh.entityId}-${mesh.contentHash}-${mesh.placementId}`} mesh={mesh} selected={selectedEntityId === mesh.entityId} />;
      })}
    </>
  );
}

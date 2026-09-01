'use client';

import { Html } from '@react-three/drei';
import { useEffect, useMemo } from 'react';
import { BufferGeometry, Float32BufferAttribute, Vector3 } from 'three';
import { useMachineWorkbenchStore } from '@/lib/machine-workbench-store';
import { useWorkbenchBrepAdapterStore } from '@/lib/workbench-brep-adapter-store';
import { useWorkbenchBrepAnchorStore } from '@/lib/workbench-brep-anchor-store';
import { useWorkbenchPlacementStore } from '@/lib/workbench-placement-store';

const SCENE_UNITS_PER_MM = 0.025;

function canonicalPointToScene(point: [number, number, number]): [number, number, number] {
  const [xMm, yMm, zMm] = point;
  return [xMm * SCENE_UNITS_PER_MM, zMm * SCENE_UNITS_PER_MM, yMm * SCENE_UNITS_PER_MM];
}

export function BrepGeneratedAdapterOverlay() {
  const phase = useMachineWorkbenchStore((state) => state.phase);
  const activeCandidateId = useMachineWorkbenchStore((state) => state.activeCandidateId);
  const candidate = useWorkbenchBrepAdapterStore((state) => state.candidatesByArchitecture[activeCandidateId]);
  const anchors = useWorkbenchBrepAnchorStore((state) => state.anchorsByCandidate[activeCandidateId]);
  const placements = useWorkbenchPlacementStore((state) => state.placementsByCandidate[activeCandidateId]);

  const dependenciesCurrent = Boolean(
    candidate
    && anchors?.[candidate.firstAnchorId]
    && anchors?.[candidate.secondAnchorId]
    && placements?.[candidate.firstEntityId]?.placementId === candidate.firstPlacementId
    && placements?.[candidate.secondEntityId]?.placementId === candidate.secondPlacementId
    && anchors[candidate.firstAnchorId].contentHash === candidate.firstContentHash
    && anchors[candidate.secondAnchorId].contentHash === candidate.secondContentHash,
  );

  const geometry = useMemo(() => {
    if (!candidate || !dependenciesCurrent || candidate.vertexCount <= 0 || candidate.triangleCount <= 0) return null;
    const resolved = new BufferGeometry();
    const positions = new Float32Array(candidate.vertexCount * 3);
    candidate.verticesMm.forEach((vertex, index) => {
      const scene = canonicalPointToScene(vertex);
      positions[index * 3] = scene[0];
      positions[index * 3 + 1] = scene[1];
      positions[index * 3 + 2] = scene[2];
    });
    resolved.setAttribute('position', new Float32BufferAttribute(positions, 3));
    resolved.setIndex(candidate.triangles.flat());
    resolved.computeVertexNormals();
    resolved.computeBoundingBox();
    resolved.computeBoundingSphere();
    return resolved;
  }, [candidate, dependenciesCurrent]);

  useEffect(() => () => geometry?.dispose(), [geometry]);

  if (phase !== 'construct' || !candidate || !dependenciesCurrent || !geometry) return null;
  const center = geometry.boundingBox?.getCenter(new Vector3()) ?? new Vector3();
  const top = geometry.boundingBox?.max.y ?? center.y;
  const labelPosition: [number, number, number] = [center.x, top + 0.34, center.z];
  const accepted = candidate.geometricCandidatePassed === true;

  return (
    <group>
      <mesh geometry={geometry} castShadow receiveShadow renderOrder={7}>
        <meshStandardMaterial color={accepted ? '#f59e0b' : '#ef4444'} roughness={0.4} metalness={0.12} transparent opacity={0.72} />
      </mesh>
      <mesh geometry={geometry} scale={[1.003, 1.003, 1.003]} renderOrder={8}>
        <meshBasicMaterial color={accepted ? '#fde68a' : '#fecaca'} transparent opacity={0.58} wireframe depthWrite={false} />
      </mesh>
      <Html center position={labelPosition} distanceFactor={9}>
        <div
          data-testid="brep-generated-adapter-overlay"
          data-adapter-id={candidate.adapterId}
          data-geometric-pass={accepted ? 'true' : candidate.geometricCandidatePassed === false ? 'false' : 'unknown'}
          className={`pointer-events-none whitespace-nowrap rounded-md border bg-slate-950/94 px-2.5 py-1.5 text-[9px] font-semibold shadow-2xl ${accepted ? 'border-amber-300/35 text-amber-50' : 'border-red-300/35 text-red-50'}`}
        >
          <div>GENERATED ADAPTER · {candidate.family}</div>
          <div className={`mt-0.5 text-[8px] uppercase tracking-[0.1em] ${accepted ? 'text-amber-300' : 'text-red-300'}`}>{accepted ? 'BOUNDED GEOMETRY PASS' : 'GEOMETRY NOT ACCEPTED'}</div>
          <div className="mt-0.5 text-[7px] font-medium normal-case tracking-normal text-slate-500">Exact parent checks only · fabrication remains blocked.</div>
        </div>
      </Html>
    </group>
  );
}

'use client';

import { Html, Line } from '@react-three/drei';
import { deck001EntityMap, deck001Interfaces } from '@/lib/workbench-demo';
import { useMachineWorkbenchStore } from '@/lib/machine-workbench-store';
import { useWorkbenchAccessStore, type DeclaredAccessEvidence } from '@/lib/workbench-access-store';
import { useWorkbenchPlacementDraftStore } from '@/lib/workbench-placement-draft-store';
import { useWorkbenchPlacementStore, type DeclaredPlacementEvidence } from '@/lib/workbench-placement-store';
import { AssemblyPlacementTools } from '@/components/workbench/assembly-placement-tools';
import { BrepRenderMeshOverlays } from '@/components/workbench/brep-render-mesh-overlay';

const SCENE_UNITS_PER_MM = 0.025;
const EMPTY_ACCESS_MAP: Record<string, DeclaredAccessEvidence> = {};
const EMPTY_PLACEMENT_MAP: Record<string, DeclaredPlacementEvidence> = {};

function canonicalPointToScene(point: [number, number, number]): [number, number, number] {
  const [xMm, yMm, zMm] = point;
  return [xMm * SCENE_UNITS_PER_MM, zMm * SCENE_UNITS_PER_MM, yMm * SCENE_UNITS_PER_MM];
}

function canonicalVectorToScene(vector: [number, number, number]): [number, number, number] {
  const [x, y, z] = vector;
  return [x, z, y];
}

function canonicalSizeToScene(minimumMm: [number, number, number], maximumMm: [number, number, number]): [number, number, number] {
  return [
    Math.max((maximumMm[0] - minimumMm[0]) * SCENE_UNITS_PER_MM, 0.02),
    Math.max((maximumMm[2] - minimumMm[2]) * SCENE_UNITS_PER_MM, 0.02),
    Math.max((maximumMm[1] - minimumMm[1]) * SCENE_UNITS_PER_MM, 0.02),
  ];
}

function aabbOverlaps(access: DeclaredAccessEvidence, placement: DeclaredPlacementEvidence) {
  if (access.frameId !== placement.frameId || access.entityId === placement.entityId) return false;
  return [0, 1, 2].every((axis) => (
    Math.min(access.maximumMm[axis], placement.maximumMm[axis])
      - Math.max(access.minimumMm[axis], placement.minimumMm[axis])
  ) > 0);
}

function AccessEnvelope({
  access,
  placements,
  selected,
}: {
  access: DeclaredAccessEvidence;
  placements: Record<string, DeclaredPlacementEvidence>;
  selected: boolean;
}) {
  const blockedBy = Object.values(placements).find((placement) => aabbOverlaps(access, placement));
  const blocked = Boolean(blockedBy);
  const color = blocked ? '#ef4444' : '#22d3ee';
  const centerMm = access.minimumMm.map(
    (value, index) => (value + access.maximumMm[index]) / 2,
  ) as [number, number, number];
  const center = canonicalPointToScene(centerMm);
  const size = canonicalSizeToScene(access.minimumMm, access.maximumMm);
  const anchor = canonicalPointToScene(access.anchorPointMm);
  const normal = canonicalVectorToScene(access.outwardNormal);
  const normalLength = Math.max(access.depthMm * SCENE_UNITS_PER_MM * 0.72, 0.32);
  const normalEnd: [number, number, number] = [
    anchor[0] + normal[0] * normalLength,
    anchor[1] + normal[1] * normalLength,
    anchor[2] + normal[2] * normalLength,
  ];
  const labelPosition: [number, number, number] = [
    center[0],
    center[1] + size[1] / 2 + 0.28,
    center[2],
  ];
  const interfaceName = deck001Interfaces.find((row) => row.id === access.interfaceId)?.name ?? access.interfaceId;
  const obstacleName = blockedBy ? deck001EntityMap.get(blockedBy.entityId)?.name ?? blockedBy.entityId : null;

  return (
    <group>
      <mesh position={center} renderOrder={8}>
        <boxGeometry args={size} />
        <meshBasicMaterial color={color} transparent opacity={blocked ? 0.14 : 0.075} depthWrite={false} />
      </mesh>
      <mesh position={center} renderOrder={9} scale={[1.003, 1.003, 1.003]}>
        <boxGeometry args={size} />
        <meshBasicMaterial color={color} transparent opacity={0.92} wireframe depthWrite={false} />
      </mesh>
      <mesh position={anchor} renderOrder={10}>
        <sphereGeometry args={[0.095, 18, 18]} />
        <meshBasicMaterial color="#fbbf24" depthWrite={false} />
      </mesh>
      <Line points={[anchor, normalEnd]} color={color} lineWidth={2.1} transparent opacity={0.95} />
      {selected || blocked ? (
        <Html center position={labelPosition} distanceFactor={9}>
          <div
            data-testid="declared-access-overlay"
            data-access-id={access.accessId}
            data-aabb-blocked={blocked ? 'true' : 'false'}
            className={`pointer-events-none whitespace-nowrap rounded-md border bg-slate-950/94 px-2.5 py-1.5 text-[9px] font-semibold shadow-2xl ${blocked ? 'border-red-300/30 text-red-100' : 'border-cyan-300/30 text-cyan-50'}`}
          >
            <div>{interfaceName} · {access.face} · DECLARED ACCESS AABB</div>
            <div className={`mt-0.5 text-[8px] uppercase tracking-[0.1em] ${blocked ? 'text-red-300' : 'text-cyan-300'}`}>
              {blocked ? `BLOCKED · overlaps ${obstacleName}` : 'FREE · no declared-placement overlap'}
            </div>
            <div className="mt-0.5 text-[7px] font-medium normal-case tracking-normal text-slate-500">Anchor + outward normal · AABB only · not service-access proof.</div>
          </div>
        </Html>
      ) : null}
    </group>
  );
}

export function DeclaredInterfaceAccessOverlays() {
  const phase = useMachineWorkbenchStore((state) => state.phase);
  const activeCandidateId = useMachineWorkbenchStore((state) => state.activeCandidateId);
  const selectedEntityId = useMachineWorkbenchStore((state) => state.selectedEntityId);
  const accessMap = useWorkbenchAccessStore((state) => state.accessByCandidate[activeCandidateId] ?? EMPTY_ACCESS_MAP);
  const placements = useWorkbenchPlacementStore((state) => state.placementsByCandidate[activeCandidateId] ?? EMPTY_PLACEMENT_MAP);
  const editTool = useWorkbenchPlacementDraftStore((state) => state.tool);
  const selectedDraft = useWorkbenchPlacementDraftStore(
    (state) => state.draftsByCandidate[activeCandidateId]?.[selectedEntityId],
  );
  const editingPose = editTool !== 'select' && Boolean(selectedDraft);

  if (phase !== 'construct') return null;

  return (
    <>
      <AssemblyPlacementTools />
      {!editingPose ? (
        <>
          <BrepRenderMeshOverlays />
          {Object.values(accessMap).map((access) => (
            <AccessEnvelope
              key={access.accessId}
              access={access}
              placements={placements}
              selected={selectedEntityId === access.entityId}
            />
          ))}
        </>
      ) : null}
    </>
  );
}

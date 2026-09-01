'use client';

import { Html, TransformControls } from '@react-three/drei';
import { Check, Loader2, MousePointer2, Move3D, Rotate3D, Undo2 } from 'lucide-react';
import { useEffect, useMemo, useRef, useState } from 'react';
import { Euler, Group, Matrix4, Quaternion, Vector3 } from 'three';
import { constructorResourceMap } from '@/lib/workbench-constructor-demo';
import {
  useMachineWorkbenchStore,
  type ConstructorCandidateId,
  type MechanicalGeometryEvidence,
} from '@/lib/machine-workbench-store';
import {
  useWorkbenchPlacementDraftStore,
  type AssemblyEditTool,
  type DeclaredPlacementDraft,
} from '@/lib/workbench-placement-draft-store';
import { useWorkbenchPlacementStore } from '@/lib/workbench-placement-store';
import { useDeclaredPlacementActions } from '@/lib/use-declared-placement-actions';

const SCENE_UNITS_PER_MM = 0.025;
const DEG = Math.PI / 180;
const RAD = 180 / Math.PI;

// Canonical STEP XYZ is displayed as scene XZY. P is its own inverse.
const AXIS_MAP = new Matrix4().set(
  1, 0, 0, 0,
  0, 0, 1, 0,
  0, 1, 0, 0,
  0, 0, 0, 1,
);

function rounded(value: number, precision = 100) {
  const result = Math.round(value * precision) / precision;
  return Object.is(result, -0) ? 0 : result;
}

function normalizeDegrees(value: number) {
  let result = value % 360;
  if (result > 180) result -= 360;
  if (result <= -180) result += 360;
  return rounded(result);
}

function closeTuple(left: [number, number, number], right: [number, number, number], tolerance = 0.005) {
  return left.every((value, index) => Math.abs(value - right[index]) <= tolerance);
}

function centerMm(evidence: MechanicalGeometryEvidence): [number, number, number] {
  return evidence.minimumMm.map(
    (value, index) => (value + evidence.maximumMm[index]) / 2,
  ) as [number, number, number];
}

function canonicalRotationMatrix(rotationDegXyz: [number, number, number]) {
  return new Matrix4().makeRotationFromEuler(new Euler(
    rotationDegXyz[0] * DEG,
    rotationDegXyz[1] * DEG,
    rotationDegXyz[2] * DEG,
    'XYZ',
  ));
}

function sceneQuaternion(rotationDegXyz: [number, number, number]) {
  const canonical = canonicalRotationMatrix(rotationDegXyz);
  const mapped = AXIS_MAP.clone().multiply(canonical).multiply(AXIS_MAP);
  return new Quaternion().setFromRotationMatrix(mapped);
}

function sceneCenterPosition(
  evidence: MechanicalGeometryEvidence,
  translationMm: [number, number, number],
  rotationDegXyz: [number, number, number],
) {
  const center = new Vector3(...centerMm(evidence));
  center.applyMatrix4(canonicalRotationMatrix(rotationDegXyz));
  center.add(new Vector3(...translationMm));
  return new Vector3(
    center.x * SCENE_UNITS_PER_MM,
    center.z * SCENE_UNITS_PER_MM,
    center.y * SCENE_UNITS_PER_MM,
  );
}

function canonicalPoseFromScene(
  evidence: MechanicalGeometryEvidence,
  position: Vector3,
  quaternion: Quaternion,
) {
  const sceneRotation = new Matrix4().makeRotationFromQuaternion(quaternion);
  const canonicalRotation = AXIS_MAP.clone().multiply(sceneRotation).multiply(AXIS_MAP);
  const euler = new Euler().setFromRotationMatrix(canonicalRotation, 'XYZ');
  const rotationDegXyz: [number, number, number] = [
    normalizeDegrees(euler.x * RAD),
    normalizeDegrees(euler.y * RAD),
    normalizeDegrees(euler.z * RAD),
  ];

  const canonicalWorldCenter = new Vector3(
    position.x / SCENE_UNITS_PER_MM,
    position.z / SCENE_UNITS_PER_MM,
    position.y / SCENE_UNITS_PER_MM,
  );
  const rotatedModelCenter = new Vector3(...centerMm(evidence)).applyMatrix4(canonicalRotation);
  const translation = canonicalWorldCenter.sub(rotatedModelCenter);
  const translationMm: [number, number, number] = [
    rounded(translation.x),
    rounded(translation.y),
    rounded(translation.z),
  ];
  return { translationMm, rotationDegXyz };
}

function poseFromExisting(
  candidateId: ConstructorCandidateId,
  entityId: string,
  resourceId: string,
  modelId: string,
): Omit<DeclaredPlacementDraft, 'updatedAt'> {
  const placement = useWorkbenchPlacementStore.getState().placementsByCandidate[candidateId]?.[entityId];
  return {
    candidateId,
    entityId,
    resourceId,
    modelId,
    translationMm: placement?.translationMm ?? [0, 0, 0],
    rotationDegXyz: placement?.rotationDegXyz ?? [0, 0, 0],
  };
}

function toolLabel(tool: AssemblyEditTool) {
  if (tool === 'move') return 'Move';
  if (tool === 'rotate') return 'Rotate';
  return 'Select';
}

function PoseGizmo({
  candidateId,
  entityId,
  resourceId,
  modelId,
  evidence,
}: {
  candidateId: ConstructorCandidateId;
  entityId: string;
  resourceId: string;
  modelId: string;
  evidence: MechanicalGeometryEvidence;
}) {
  const tool = useWorkbenchPlacementDraftStore((state) => state.tool);
  const draft = useWorkbenchPlacementDraftStore(
    (state) => state.draftsByCandidate[candidateId]?.[entityId],
  );
  const setDraft = useWorkbenchPlacementDraftStore((state) => state.setDraft);
  const groupRef = useRef<Group | null>(null);

  useEffect(() => {
    if (tool === 'select') return;
    if (draft && draft.resourceId === resourceId && draft.modelId === modelId) return;
    setDraft(poseFromExisting(candidateId, entityId, resourceId, modelId));
  }, [candidateId, draft, entityId, modelId, resourceId, setDraft, tool]);

  const effectiveDraft = draft && draft.resourceId === resourceId && draft.modelId === modelId
    ? draft
    : null;
  const size = useMemo(() => [
    Math.max(evidence.sizeMm[0] * SCENE_UNITS_PER_MM, 0.04),
    Math.max(evidence.sizeMm[2] * SCENE_UNITS_PER_MM, 0.04),
    Math.max(evidence.sizeMm[1] * SCENE_UNITS_PER_MM, 0.04),
  ] as [number, number, number], [evidence.sizeMm]);

  if (tool === 'select' || !effectiveDraft) return null;
  const activeDraft = effectiveDraft;

  const position = sceneCenterPosition(evidence, activeDraft.translationMm, activeDraft.rotationDegXyz);
  const quaternion = sceneQuaternion(activeDraft.rotationDegXyz);

  function captureObjectPose() {
    const group = groupRef.current;
    if (!group) return;
    const pose = canonicalPoseFromScene(evidence, group.position.clone(), group.quaternion.clone());
    // TransformControls also emits objectChange when React applies an externally
    // updated draft pose. Do not echo an identical pose back into Zustand: doing
    // so changes updatedAt, re-renders the controlled object and creates a loop.
    if (
      closeTuple(pose.translationMm, activeDraft.translationMm)
      && closeTuple(pose.rotationDegXyz, activeDraft.rotationDegXyz)
    ) return;
    setDraft({ candidateId, entityId, resourceId, modelId, ...pose });
  }

  return (
    <TransformControls
      mode={tool === 'move' ? 'translate' : 'rotate'}
      space="world"
      translationSnap={SCENE_UNITS_PER_MM}
      rotationSnap={15 * DEG}
      onObjectChange={captureObjectPose}
    >
      <group ref={groupRef} position={position} quaternion={quaternion}>
        <mesh renderOrder={20}>
          <boxGeometry args={size} />
          <meshBasicMaterial color="#c084fc" transparent opacity={0.12} depthWrite={false} />
        </mesh>
        <mesh scale={[1.004, 1.004, 1.004]} renderOrder={21}>
          <boxGeometry args={size} />
          <meshBasicMaterial color="#e9d5ff" transparent opacity={0.9} wireframe depthWrite={false} />
        </mesh>
        <Html center position={[0, size[1] / 2 + 0.34, 0]} distanceFactor={9}>
          <div data-testid="assembly-pose-draft-label" className="pointer-events-none whitespace-nowrap rounded-md border border-violet-300/35 bg-slate-950/95 px-2.5 py-1.5 text-[9px] font-semibold text-violet-50 shadow-2xl">
            DECLARED POSE DRAFT · {toolLabel(tool).toUpperCase()}
            <div className="mt-0.5 text-[7px] font-medium normal-case text-slate-500">1 mm translation snap · 15° rotation snap · not committed evidence</div>
          </div>
        </Html>
      </group>
    </TransformControls>
  );
}

function PoseToolbar({
  candidateId,
  entityId,
  resourceId,
  resourceName,
  modelId,
  evidence,
}: {
  candidateId: ConstructorCandidateId;
  entityId: string;
  resourceId: string;
  resourceName: string;
  modelId: string;
  evidence: MechanicalGeometryEvidence;
}) {
  const tool = useWorkbenchPlacementDraftStore((state) => state.tool);
  const draft = useWorkbenchPlacementDraftStore(
    (state) => state.draftsByCandidate[candidateId]?.[entityId],
  );
  const setTool = useWorkbenchPlacementDraftStore((state) => state.setTool);
  const setDraft = useWorkbenchPlacementDraftStore((state) => state.setDraft);
  const clearDraft = useWorkbenchPlacementDraftStore((state) => state.clearDraft);
  const setSelectedResourceId = useMachineWorkbenchStore((state) => state.setSelectedResourceId);
  const setConstructorDockTab = useMachineWorkbenchStore((state) => state.setConstructorDockTab);
  const { existing, projectIntent, registeredReady, commitPose } = useDeclaredPlacementActions({
    candidateId,
    resourceId,
    entityId,
    modelId,
    evidence,
  });
  const [commitState, setCommitState] = useState<'idle' | 'loading' | 'success' | 'error'>('idle');
  const [message, setMessage] = useState('');
  const effectiveDraft = draft && draft.resourceId === resourceId && draft.modelId === modelId ? draft : null;

  function begin(toolValue: AssemblyEditTool) {
    setSelectedResourceId(resourceId);
    setConstructorDockTab('resources');
    if (toolValue !== 'select' && !effectiveDraft) {
      setDraft(poseFromExisting(candidateId, entityId, resourceId, modelId));
    }
    setTool(toolValue);
    setCommitState('idle');
    setMessage('');
  }

  function revert() {
    clearDraft(candidateId, entityId);
    setTool('select');
    setCommitState('idle');
    setMessage(existing ? 'Draft discarded; committed declared pose is unchanged.' : 'Draft discarded; no placement is committed.');
  }

  async function apply() {
    if (!effectiveDraft) return;
    setCommitState('loading');
    setMessage(projectIntent ? 'Persisting source-bound declared pose and invalidating pose-derived evidence…' : 'Applying declared pose and invalidating pose-derived evidence…');
    try {
      const result = await commitPose(effectiveDraft.translationMm, effectiveDraft.rotationDegXyz);
      setTool('select');
      setCommitState('success');
      setMessage(`Declared pose committed${result.durableRevision ? ` at project revision ${result.durableRevision}` : ''}. Exact mesh, anchors and access evidence must be recomputed for this pose.`);
    } catch (error: unknown) {
      setCommitState('error');
      setMessage(error instanceof Error ? error.message : String(error));
    }
  }

  const pose = effectiveDraft ?? (existing ? {
    translationMm: existing.translationMm,
    rotationDegXyz: existing.rotationDegXyz,
  } : null);

  return (
    <div className="pointer-events-auto absolute left-1/2 top-3 w-[min(760px,calc(100%-26px))] -translate-x-1/2 rounded-xl border border-violet-300/20 bg-[#07101d]/96 p-2 shadow-2xl backdrop-blur" data-testid="assembly-placement-toolbar">
      <div className="flex flex-wrap items-center gap-2">
        <div className="min-w-0 pr-2">
          <div className="truncate text-[9px] font-semibold uppercase tracking-[0.13em] text-violet-200">Assembly pose · {resourceName}</div>
          <div className="truncate text-[8px] text-slate-600">STEP {evidence.contentHash.slice(0, 12)}… · declared transform only</div>
        </div>
        <div className="flex rounded-lg border border-white/10 bg-black/20 p-0.5">
          {([
            ['select', 'Select', MousePointer2],
            ['move', 'Move', Move3D],
            ['rotate', 'Rotate', Rotate3D],
          ] as const).map(([id, label, Icon]) => (
            <button
              key={id}
              type="button"
              onClick={() => begin(id)}
              aria-pressed={tool === id}
              className={`inline-flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-[9px] font-semibold uppercase tracking-[0.09em] transition ${tool === id ? 'bg-violet-300/12 text-violet-100 ring-1 ring-violet-300/25' : 'text-slate-500 hover:bg-white/5 hover:text-white'}`}
            >
              <Icon className="h-3 w-3" /> {label}
            </button>
          ))}
        </div>
        {pose ? (
          <div className="hidden min-w-0 flex-1 text-right text-[8px] leading-4 text-slate-500 lg:block" data-testid="assembly-pose-readout">
            T [{pose.translationMm.map((value) => rounded(value)).join(', ')}] mm · R [{pose.rotationDegXyz.map((value) => rounded(value)).join(', ')}]°
          </div>
        ) : <div className="hidden flex-1 text-right text-[8px] text-slate-600 lg:block">No declared pose yet</div>}
        {effectiveDraft ? (
          <>
            <button type="button" onClick={revert} disabled={commitState === 'loading'} className="inline-flex items-center gap-1.5 rounded-md border border-white/10 px-2 py-1.5 text-[9px] font-semibold uppercase tracking-[0.09em] text-slate-400 hover:bg-white/5 hover:text-white disabled:opacity-50">
              <Undo2 className="h-3 w-3" /> Revert
            </button>
            <button
              type="button"
              onClick={() => void apply()}
              disabled={commitState === 'loading' || (projectIntent && !registeredReady)}
              title={projectIntent && !registeredReady ? 'Current project-bound STEP occurrence must be registered before the pose can be persisted.' : 'Commit this declared pose'}
              className="inline-flex items-center gap-1.5 rounded-md border border-violet-300/20 bg-violet-300/[0.08] px-2.5 py-1.5 text-[9px] font-semibold uppercase tracking-[0.09em] text-violet-100 hover:bg-violet-300/[0.13] disabled:cursor-not-allowed disabled:opacity-40"
            >
              {commitState === 'loading' ? <Loader2 className="h-3 w-3 animate-spin" /> : <Check className="h-3 w-3" />} Apply pose
            </button>
          </>
        ) : null}
      </div>
      {message ? <div className={`mt-1 px-1 text-[8px] leading-4 ${commitState === 'error' ? 'text-red-300/80' : commitState === 'success' ? 'text-emerald-300/75' : 'text-slate-500'}`}>{message}</div> : null}
      {tool !== 'select' ? <div className="mt-1 px-1 text-[8px] leading-4 text-amber-100/50">Pose-derived exact mesh, anchors and access envelopes are hidden during draft editing. Dragging changes only the declared pose draft; Apply pose is the authority boundary.</div> : null}
    </div>
  );
}

export function AssemblyPlacementTools() {
  const phase = useMachineWorkbenchStore((state) => state.phase);
  const activeCandidateId = useMachineWorkbenchStore((state) => state.activeCandidateId);
  const selectedEntityId = useMachineWorkbenchStore((state) => state.selectedEntityId);
  const plannerProjection = useMachineWorkbenchStore((state) => state.plannerProjections[activeCandidateId]);
  const evidence = plannerProjection?.mechanicalGeometryByEntity?.[selectedEntityId];
  const resourceName = evidence ? constructorResourceMap.get(evidence.resourceId)?.name ?? evidence.resourceId : '';

  if (phase !== 'construct' || !evidence) return null;

  return (
    <>
      <PoseGizmo
        candidateId={activeCandidateId}
        entityId={selectedEntityId}
        resourceId={evidence.resourceId}
        modelId={evidence.modelId}
        evidence={evidence}
      />
      <Html fullscreen style={{ pointerEvents: 'none' }}>
        <PoseToolbar
          candidateId={activeCandidateId}
          entityId={selectedEntityId}
          resourceId={evidence.resourceId}
          resourceName={resourceName}
          modelId={evidence.modelId}
          evidence={evidence}
        />
      </Html>
    </>
  );
}

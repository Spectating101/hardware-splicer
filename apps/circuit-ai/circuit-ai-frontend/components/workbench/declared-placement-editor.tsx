'use client';

import { useEffect, useState } from 'react';
import { Loader2, Move3D, Rotate3D, Trash2 } from 'lucide-react';
import type { ConstructorCandidateId, MechanicalGeometryEvidence } from '@/lib/machine-workbench-store';
import { useMachineWorkbenchStore } from '@/lib/machine-workbench-store';
import { useWorkbenchAccessStore } from '@/lib/workbench-access-store';
import { useWorkbenchPlacementStore, type DeclaredPlacementEvidence } from '@/lib/workbench-placement-store';
import { DeclaredClearanceChecker } from '@/components/workbench/declared-clearance-checker';
import { DeclaredInterfaceAccessEditor } from '@/components/workbench/declared-interface-access-editor';

function record(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {};
}

function tuple3(value: unknown): [number, number, number] | null {
  if (!Array.isArray(value) || value.length !== 3) return null;
  const rows = value.map(Number);
  return rows.every(Number.isFinite) ? rows as [number, number, number] : null;
}

function parseVector(values: string[]) {
  const parsed = values.map((value) => Number(value));
  return parsed.length === 3 && parsed.every(Number.isFinite) ? parsed as [number, number, number] : null;
}

export function DeclaredPlacementEditor({
  candidateId,
  resourceId,
  resourceName,
  entityId,
  modelId,
  evidence,
}: {
  candidateId: ConstructorCandidateId;
  resourceId: string;
  resourceName: string;
  entityId: string;
  modelId: string;
  evidence: MechanicalGeometryEvidence;
}) {
  const existing = useWorkbenchPlacementStore((state) => state.placementsByCandidate[candidateId]?.[entityId]);
  const geometryReport = useWorkbenchPlacementStore((state) => state.geometryReportsByCandidate[candidateId]?.[resourceId]);
  const setPlacement = useWorkbenchPlacementStore((state) => state.setPlacement);
  const clearPlacement = useWorkbenchPlacementStore((state) => state.clearPlacement);
  const clearAccessForEntity = useWorkbenchAccessStore((state) => state.clearAccessForEntity);
  const setMechanicalGeometryEvidence = useMachineWorkbenchStore((state) => state.setMechanicalGeometryEvidence);
  const setSelectedEntityId = useMachineWorkbenchStore((state) => state.setSelectedEntityId);
  const requestFrameSelection = useMachineWorkbenchStore((state) => state.requestFrameSelection);

  const [translation, setTranslation] = useState(() => (existing?.translationMm ?? [0, 0, 0]).map(String));
  const [rotation, setRotation] = useState(() => (existing?.rotationDegXyz ?? [0, 0, 0]).map(String));
  const [state, setState] = useState<'idle' | 'loading' | 'success' | 'error'>('idle');
  const [message, setMessage] = useState('');

  useEffect(() => {
    setTranslation((existing?.translationMm ?? [0, 0, 0]).map(String));
    setRotation((existing?.rotationDegXyz ?? [0, 0, 0]).map(String));
    setState('idle');
    setMessage('');
    // Identity changes are the only reset trigger. A placement write for the same
    // resource must not erase its just-returned backend status message.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [candidateId, resourceId, entityId]);

  useEffect(() => {
    if (!existing) clearAccessForEntity(candidateId, entityId);
  }, [candidateId, clearAccessForEntity, entityId, existing]);

  function updateVector(kind: 'translation' | 'rotation', index: number, value: string) {
    if (kind === 'translation') {
      setTranslation((current) => current.map((row, rowIndex) => rowIndex === index ? value : row));
    } else {
      setRotation((current) => current.map((row, rowIndex) => rowIndex === index ? value : row));
    }
  }

  async function applyPlacement() {
    const translationMm = parseVector(translation);
    const rotationDegXyz = parseVector(rotation);
    if (!translationMm || !rotationDegXyz) {
      setState('error');
      setMessage('Translation and rotation must be finite numbers.');
      return;
    }
    if (!geometryReport) {
      setState('error');
      setMessage('Parsed STEP report is unavailable; re-attach the source before placing it.');
      return;
    }

    const placementId = `placement-${candidateId}-${resourceId}`;
    setState('loading');
    setMessage('Transforming STEP envelope into the assembly frame…');
    try {
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
      // Interface/access geometry is derived from the parent pose, so every pose
      // change invalidates it before the new placement becomes visible.
      clearAccessForEntity(candidateId, entityId);
      setPlacement(candidateId, placement);
      // Re-write the same parsed evidence to create a new planner projection object;
      // the spatial adapter then composes the separately stored placement evidence.
      setMechanicalGeometryEvidence(candidateId, evidence);
      setSelectedEntityId(entityId);
      window.setTimeout(requestFrameSelection, 0);
      setState('success');
      setMessage(`${placement.frameId} AABB ${sizeMm.map((value) => Math.round(value * 100) / 100).join(' × ')} mm · DECLARED placement.`);
    } catch (error: unknown) {
      setState('error');
      setMessage(error instanceof Error ? error.message : String(error));
    }
  }

  function removePlacement() {
    clearAccessForEntity(candidateId, entityId);
    clearPlacement(candidateId, entityId);
    setMechanicalGeometryEvidence(candidateId, evidence);
    setState('idle');
    setMessage('Declared placement cleared; dependent interface access evidence was invalidated.');
  }

  return (
    <>
      <div className="mt-2 rounded-lg border border-violet-300/10 bg-violet-300/[0.025] p-2" data-testid="declared-placement-editor">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-1.5 text-[8px] font-semibold uppercase tracking-[0.12em] text-violet-200/80">
            <Move3D className="h-3 w-3" /> Declared assembly placement
          </div>
          <span className="text-[7px] uppercase tracking-[0.1em] text-slate-600">Rz·Ry·Rx · AABB only</span>
        </div>
        <div className="mt-2 grid grid-cols-3 gap-1.5">
          {['X', 'Y', 'Z'].map((axis, index) => (
            <label key={`t-${axis}`} className="text-[7px] uppercase tracking-[0.08em] text-slate-600">
              T{axis} mm
              <input
                value={translation[index]}
                onChange={(event) => updateVector('translation', index, event.target.value)}
                inputMode="decimal"
                aria-label={`Placement translation ${axis} mm for ${resourceName}`}
                className="mt-1 w-full rounded border border-white/8 bg-black/20 px-1.5 py-1 text-[9px] normal-case tracking-normal text-slate-200 outline-none focus:border-violet-300/25"
              />
            </label>
          ))}
        </div>
        <div className="mt-2 grid grid-cols-3 gap-1.5">
          {['X', 'Y', 'Z'].map((axis, index) => (
            <label key={`r-${axis}`} className="text-[7px] uppercase tracking-[0.08em] text-slate-600">
              R{axis} °
              <div className="relative mt-1">
                <Rotate3D className="pointer-events-none absolute left-1.5 top-1.5 h-2.5 w-2.5 text-slate-700" />
                <input
                  value={rotation[index]}
                  onChange={(event) => updateVector('rotation', index, event.target.value)}
                  inputMode="decimal"
                  aria-label={`Placement rotation ${axis} degrees for ${resourceName}`}
                  className="w-full rounded border border-white/8 bg-black/20 py-1 pl-5 pr-1 text-[9px] normal-case tracking-normal text-slate-200 outline-none focus:border-violet-300/25"
                />
              </div>
            </label>
          ))}
        </div>
        <div className="mt-2 flex items-center gap-1.5">
          <button
            type="button"
            onClick={applyPlacement}
            disabled={state === 'loading'}
            className="inline-flex items-center gap-1.5 rounded-md border border-violet-300/15 bg-violet-300/[0.05] px-2 py-1.5 text-[8px] font-semibold uppercase tracking-[0.09em] text-violet-200 hover:bg-violet-300/[0.09] disabled:opacity-50"
          >
            {state === 'loading' ? <Loader2 className="h-3 w-3 animate-spin" /> : <Move3D className="h-3 w-3" />}
            Apply declared placement
          </button>
          {existing ? (
            <button type="button" onClick={removePlacement} aria-label={`Clear declared placement for ${resourceName}`} className="rounded-md border border-white/8 p-1.5 text-slate-600 hover:text-red-300">
              <Trash2 className="h-3 w-3" />
            </button>
          ) : null}
        </div>
        {existing ? <div className="mt-1.5 text-[8px] leading-4 text-violet-200/65">Placed in {existing.frameId}: T [{existing.translationMm.join(', ')}] mm · R [{existing.rotationDegXyz.join(', ')}]° · DECLARED.</div> : null}
        {message ? <div className={`mt-1.5 text-[8px] leading-4 ${state === 'error' ? 'text-red-300/80' : state === 'success' ? 'text-emerald-300/75' : 'text-slate-500'}`}>{message}</div> : null}
        <div className="mt-1 text-[7px] leading-3 text-amber-100/45">Placement establishes a common coordinate frame only. It is not measurement, collision proof, fit proof, or fabrication authority.</div>
      </div>
      {existing ? (
        <DeclaredInterfaceAccessEditor
          candidateId={candidateId}
          resourceId={resourceId}
          resourceName={resourceName}
          entityId={entityId}
          placement={existing}
        />
      ) : null}
      <DeclaredClearanceChecker />
    </>
  );
}

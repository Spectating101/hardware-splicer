'use client';

import { useMemo } from 'react';
import {
  Box,
  Crosshair,
  GitBranch,
  Layers3,
  Ruler,
  ScanSearch,
  ShieldAlert,
  Waypoints,
} from 'lucide-react';
import { constructorResourceMap } from '@/lib/workbench-constructor-demo';
import { deck001EntityMap } from '@/lib/workbench-demo';
import { useMachineWorkbenchStore } from '@/lib/machine-workbench-store';
import { useWorkbenchAccessStore, type DeclaredAccessEvidence } from '@/lib/workbench-access-store';
import { useWorkbenchBrepAnchorStore, type BrepSurfaceAnchorEvidence } from '@/lib/workbench-brep-anchor-store';
import { useWorkbenchPlacementStore, type DeclaredPlacementEvidence } from '@/lib/workbench-placement-store';

const EMPTY_PLACEMENTS: Record<string, DeclaredPlacementEvidence> = {};
const EMPTY_ANCHORS: Record<string, BrepSurfaceAnchorEvidence> = {};
const EMPTY_ACCESS: Record<string, DeclaredAccessEvidence> = {};

function rounded(value: number, digits = 2) {
  const factor = 10 ** digits;
  const result = Math.round(value * factor) / factor;
  return Object.is(result, -0) ? 0 : result;
}

function tuple(value: [number, number, number]) {
  return `[${value.map((row) => rounded(row)).join(', ')}]`;
}

function sameTuple(left: [number, number, number], right: [number, number, number]) {
  return left.every((value, index) => Math.abs(value - right[index]) <= 0.005);
}

function aabbGap(left: DeclaredPlacementEvidence, right: DeclaredPlacementEvidence) {
  const axisGap = left.minimumMm.map((leftMin, axis) => {
    const leftMax = left.maximumMm[axis];
    const rightMin = right.minimumMm[axis];
    const rightMax = right.maximumMm[axis];
    if (leftMax < rightMin) return rightMin - leftMax;
    if (rightMax < leftMin) return leftMin - rightMax;
    return 0;
  });
  return Math.sqrt(axisGap.reduce((sum, value) => sum + value * value, 0));
}

function badgeClass(state: 'good' | 'warn' | 'muted') {
  if (state === 'good') return 'border-emerald-300/20 bg-emerald-300/[0.06] text-emerald-200';
  if (state === 'warn') return 'border-amber-300/20 bg-amber-300/[0.055] text-amber-100';
  return 'border-white/10 bg-white/[0.025] text-slate-400';
}

function Fact({ label, value, state = 'muted' }: { label: string; value: string; state?: 'good' | 'warn' | 'muted' }) {
  return (
    <div className={`rounded-lg border p-2.5 ${badgeClass(state)}`}>
      <div className="text-[8px] font-semibold uppercase tracking-[0.14em] opacity-60">{label}</div>
      <div className="mt-1 text-[11px] font-medium leading-4">{value}</div>
    </div>
  );
}

export function GeometryInterrogationPanel() {
  const activeCandidateId = useMachineWorkbenchStore((state) => state.activeCandidateId);
  const selectedEntityId = useMachineWorkbenchStore((state) => state.selectedEntityId);
  const plannerProjection = useMachineWorkbenchStore((state) => state.plannerProjections[activeCandidateId]);
  const setPhase = useMachineWorkbenchStore((state) => state.setPhase);
  const setConstructorDockTab = useMachineWorkbenchStore((state) => state.setConstructorDockTab);
  const setSelectedResourceId = useMachineWorkbenchStore((state) => state.setSelectedResourceId);
  const requestFrameSelection = useMachineWorkbenchStore((state) => state.requestFrameSelection);
  const setIsolatedEntityId = useMachineWorkbenchStore((state) => state.setIsolatedEntityId);
  const isolatedEntityId = useMachineWorkbenchStore((state) => state.isolatedEntityId);

  const candidatePlacements = useWorkbenchPlacementStore((state) => state.placementsByCandidate[activeCandidateId]);
  const candidateAnchors = useWorkbenchBrepAnchorStore((state) => state.anchorsByCandidate[activeCandidateId]);
  const candidateAccess = useWorkbenchAccessStore((state) => state.accessByCandidate[activeCandidateId]);

  const placements = candidatePlacements ?? EMPTY_PLACEMENTS;
  const anchors = candidateAnchors ?? EMPTY_ANCHORS;
  const access = candidateAccess ?? EMPTY_ACCESS;
  const geometry = plannerProjection?.mechanicalGeometryByEntity?.[selectedEntityId];
  const exactMesh = plannerProjection?.brepRenderMeshByEntity?.[selectedEntityId];
  const placement = placements[selectedEntityId];
  const entity = deck001EntityMap.get(selectedEntityId);
  const resourceName = geometry ? constructorResourceMap.get(geometry.resourceId)?.name ?? geometry.resourceId : entity?.name ?? selectedEntityId;

  const entityAnchors = useMemo(
    () => Object.values(anchors).filter((row) => row.entityId === selectedEntityId),
    [anchors, selectedEntityId],
  );
  const entityAccess = useMemo(
    () => Object.values(access).filter((row) => row.entityId === selectedEntityId),
    [access, selectedEntityId],
  );
  const nearest = useMemo(() => {
    if (!placement) return null;
    let best: { placement: DeclaredPlacementEvidence; gapMm: number } | null = null;
    for (const row of Object.values(placements)) {
      if (row.entityId === placement.entityId) continue;
      const gapMm = aabbGap(placement, row);
      if (!best || gapMm < best.gapMm) best = { placement: row, gapMm };
    }
    return best;
  }, [placement, placements]);

  if (!geometry) {
    return (
      <div className="flex min-h-[126px] items-center justify-center rounded-xl border border-dashed border-white/10 bg-white/[0.015] px-5 text-center" data-testid="geometry-interrogation-empty">
        <div>
          <ScanSearch className="mx-auto h-4 w-4 text-slate-600" />
          <div className="mt-2 text-xs font-medium text-slate-300">No live geometry attached to this selection</div>
          <div className="mt-1 max-w-xl text-[11px] leading-5 text-slate-600">Select a resource-backed machine entity and attach its STEP source. HS will keep point-envelope, placement, exact BREP and physical authority separate.</div>
        </div>
      </div>
    );
  }

  const exactMeshCurrent = Boolean(
    exactMesh
    && placement
    && exactMesh.resourceId === geometry.resourceId
    && exactMesh.modelId === geometry.modelId
    && exactMesh.contentHash === geometry.contentHash
    && exactMesh.placementId === placement.placementId
    && sameTuple(exactMesh.translationMm, placement.translationMm)
    && sameTuple(exactMesh.rotationDegXyz, placement.rotationDegXyz),
  );

  const unresolved = geometry.unresolved
    .map((row) => row.reason || row.field)
    .filter((row): row is string => Boolean(row));

  const nextAction = !placement
    ? 'Commit a declared assembly pose before pair clearance, anchors, or access checks.'
    : !exactMeshCurrent
      ? 'Resolve the current source + pose through OCCT before treating surface geometry as exact.'
      : entityAnchors.length === 0
        ? 'Pick exact BREP surfaces for interfaces that matter to mating or assembly.'
        : entityAccess.length === 0
          ? 'Declare interface access envelopes before claiming service or cable access.'
          : 'Run pair-specific exact clearance/mating checks against the nearest relevant neighbor.';

  function openResourceControls() {
    setPhase('construct');
    setConstructorDockTab('resources');
    setSelectedResourceId(geometry.resourceId);
  }

  return (
    <div className="space-y-3" data-testid="geometry-interrogation-panel">
      <div className="flex flex-wrap items-start justify-between gap-3 rounded-xl border border-cyan-300/15 bg-cyan-300/[0.035] p-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2 text-[9px] font-semibold uppercase tracking-[0.16em] text-cyan-300">
            <Ruler className="h-3.5 w-3.5" /> Sovereign geometry interrogation
          </div>
          <div className="mt-1 truncate text-xs font-semibold text-white">{resourceName}</div>
          <div className="mt-1 font-mono text-[9px] text-slate-500">{geometry.sourceId} · {geometry.modelId} · {geometry.contentHash.slice(0, 22)}…</div>
        </div>
        <div className="flex flex-wrap gap-1.5">
          <button type="button" onClick={requestFrameSelection} className="rounded-md border border-white/10 px-2.5 py-1.5 text-[9px] font-semibold uppercase tracking-[0.09em] text-slate-300 hover:bg-white/5">Frame</button>
          <button type="button" onClick={() => setIsolatedEntityId(isolatedEntityId === selectedEntityId ? null : selectedEntityId)} className="rounded-md border border-white/10 px-2.5 py-1.5 text-[9px] font-semibold uppercase tracking-[0.09em] text-slate-300 hover:bg-white/5">{isolatedEntityId === selectedEntityId ? 'Show machine' : 'Isolate'}</button>
          <button type="button" onClick={openResourceControls} className="rounded-md border border-cyan-300/20 bg-cyan-300/[0.06] px-2.5 py-1.5 text-[9px] font-semibold uppercase tracking-[0.09em] text-cyan-100 hover:bg-cyan-300/[0.1]">Resource controls</button>
        </div>
      </div>

      <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-4">
        <Fact label="Source envelope" value={`${geometry.sizeMm.map((row) => rounded(row)).join(' × ')} mm`} state="warn" />
        <Fact label="Assembly pose" value={placement ? `T ${tuple(placement.translationMm)} mm · R ${tuple(placement.rotationDegXyz)}°` : 'Not committed'} state={placement ? 'good' : 'warn'} />
        <Fact label="Exact BREP mesh" value={exactMeshCurrent && exactMesh ? `${exactMesh.triangleCount.toLocaleString()} triangles · ${exactMesh.kernel}` : 'Not current / not resolved'} state={exactMeshCurrent ? 'good' : 'warn'} />
        <Fact label="Physical authority" value="No measurement / fabrication authority" state="warn" />
      </div>

      <div className="grid gap-3 xl:grid-cols-[1.1fr_1fr_1fr]">
        <section className="rounded-xl border border-white/10 bg-white/[0.02] p-3">
          <div className="flex items-center gap-2 text-[9px] font-semibold uppercase tracking-[0.14em] text-slate-400"><Box className="h-3.5 w-3.5" /> Geometry facts</div>
          <div className="mt-2 space-y-1.5 text-[10px] leading-4">
            <div className="flex justify-between gap-4"><span className="text-slate-600">STEP point envelope</span><span className="text-right text-amber-100/80">DECLARED · {geometry.pointCount} points</span></div>
            <div className="flex justify-between gap-4"><span className="text-slate-600">Source min</span><span className="font-mono text-slate-300">{tuple(geometry.minimumMm)} mm</span></div>
            <div className="flex justify-between gap-4"><span className="text-slate-600">Source max</span><span className="font-mono text-slate-300">{tuple(geometry.maximumMm)} mm</span></div>
            {placement ? <div className="flex justify-between gap-4"><span className="text-slate-600">Assembly AABB</span><span className="font-mono text-slate-300">{tuple(placement.minimumMm)} → {tuple(placement.maximumMm)}</span></div> : null}
            {exactMeshCurrent && exactMesh ? <div className="flex justify-between gap-4"><span className="text-slate-600">OCCT tessellation</span><span className="text-emerald-200/80">{exactMesh.vertexCount.toLocaleString()} vertices · tol {rounded(exactMesh.toleranceMm, 4)} mm</span></div> : null}
            <div className="flex justify-between gap-4"><span className="text-slate-600">Mass / CG</span><span className="text-slate-500">NOT VERIFIED</span></div>
          </div>
        </section>

        <section className="rounded-xl border border-white/10 bg-white/[0.02] p-3">
          <div className="flex items-center gap-2 text-[9px] font-semibold uppercase tracking-[0.14em] text-slate-400"><Waypoints className="h-3.5 w-3.5" /> Interfaces & proximity</div>
          <div className="mt-2 grid grid-cols-2 gap-2">
            <Fact label="Exact anchors" value={String(entityAnchors.length)} state={entityAnchors.length ? 'good' : 'muted'} />
            <Fact label="Access envelopes" value={String(entityAccess.length)} state={entityAccess.length ? 'good' : 'muted'} />
          </div>
          <div className="mt-2 rounded-lg border border-white/8 bg-black/15 p-2.5 text-[10px] leading-4">
            <div className="text-[8px] font-semibold uppercase tracking-[0.13em] text-slate-600">Nearest declared AABB</div>
            {nearest ? (
              <div className="mt-1 text-slate-300">{deck001EntityMap.get(nearest.placement.entityId)?.name ?? nearest.placement.entityId} · <span className="text-amber-100">{rounded(nearest.gapMm, 3)} mm</span></div>
            ) : <div className="mt-1 text-slate-600">No second placed entity available.</div>}
            <div className="mt-1 text-[9px] text-slate-600">Screening aid only. AABB separation is not exact BREP clearance.</div>
          </div>
        </section>

        <section className="rounded-xl border border-white/10 bg-white/[0.02] p-3">
          <div className="flex items-center gap-2 text-[9px] font-semibold uppercase tracking-[0.14em] text-slate-400"><ShieldAlert className="h-3.5 w-3.5" /> Authority boundary</div>
          <div className="mt-2 space-y-1.5 text-[10px] leading-4">
            <div className="flex justify-between gap-4"><span className="text-slate-600">Exact surface identity</span><span className={exactMeshCurrent ? 'text-emerald-200' : 'text-amber-200'}>{exactMeshCurrent ? 'AVAILABLE' : 'UNRESOLVED'}</span></div>
            <div className="flex justify-between gap-4"><span className="text-slate-600">Whole-assembly collision</span><span className="text-slate-500">NOT VERIFIED</span></div>
            <div className="flex justify-between gap-4"><span className="text-slate-600">Service / cable access</span><span className="text-slate-500">NOT VERIFIED</span></div>
            <div className="flex justify-between gap-4"><span className="text-slate-600">Fabrication release</span><span className="text-red-200/70">BLOCKED</span></div>
          </div>
        </section>
      </div>

      <div className="grid gap-2 xl:grid-cols-[1fr_1fr]">
        <div className="rounded-lg border border-amber-300/15 bg-amber-300/[0.035] p-3">
          <div className="flex items-center gap-2 text-[9px] font-semibold uppercase tracking-[0.14em] text-amber-200"><Crosshair className="h-3.5 w-3.5" /> Next geometry action</div>
          <div className="mt-1 text-[11px] leading-5 text-amber-100/75">{nextAction}</div>
        </div>
        <div className="rounded-lg border border-white/10 bg-white/[0.02] p-3">
          <div className="flex items-center gap-2 text-[9px] font-semibold uppercase tracking-[0.14em] text-slate-400"><GitBranch className="h-3.5 w-3.5" /> Source unresolved</div>
          <div className="mt-1 text-[11px] leading-5 text-slate-500">{unresolved.length ? unresolved.join(' · ') : 'No parser-level unresolved fields recorded. This does not promote geometry to physical measurement.'}</div>
        </div>
      </div>

      <div className="flex items-center gap-2 rounded-lg border border-violet-300/10 bg-violet-300/[0.025] px-3 py-2 text-[9px] leading-4 text-violet-100/55">
        <Layers3 className="h-3.5 w-3.5 shrink-0" /> Geometry interrogation reports what HS knows about the selected source and pose. It does not infer metrology, material, mass, connector semantics, or release authority from CAD appearance.
      </div>
    </div>
  );
}

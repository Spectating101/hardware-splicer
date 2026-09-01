'use client';

import { Download, Hammer, Link2, ShieldAlert, Sparkles } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { deck001EntityMap } from '@/lib/workbench-demo';
import { useMachineWorkbenchStore } from '@/lib/machine-workbench-store';
import {
  useWorkbenchBrepAdapterStore,
  type BrepAdapterCandidateEvidence,
  type BrepAdapterRequiredEvidence,
} from '@/lib/workbench-brep-adapter-store';
import {
  useWorkbenchBrepAnchorStore,
  type BrepSurfaceAnchorEvidence,
} from '@/lib/workbench-brep-anchor-store';
import {
  getRegisteredWorkbenchStepSource,
  useWorkbenchProjectSourceStore,
} from '@/lib/workbench-project-sources';
import { getSessionStepSource } from '@/lib/workbench-session-step-sources';
import {
  useWorkbenchPlacementStore,
  type DeclaredPlacementEvidence,
} from '@/lib/workbench-placement-store';

const EMPTY_ANCHORS: Record<string, BrepSurfaceAnchorEvidence> = {};
const EMPTY_PLACEMENTS: Record<string, DeclaredPlacementEvidence> = {};

function record(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {};
}

function tuple3(value: unknown): [number, number, number] | null {
  if (!Array.isArray(value) || value.length !== 3) return null;
  const rows = value.map(Number);
  return rows.every(Number.isFinite) ? rows as [number, number, number] : null;
}

function tupleRows(value: unknown): [number, number, number][] {
  if (!Array.isArray(value)) return [];
  return value.map(tuple3).filter((row): row is [number, number, number] => row !== null);
}

function triangleRows(value: unknown): [number, number, number][] {
  if (!Array.isArray(value)) return [];
  return value
    .map((row) => Array.isArray(row) && row.length === 3 ? row.map(Number) : null)
    .filter((row): row is number[] => row !== null && row.every(Number.isInteger))
    .map((row) => row as [number, number, number]);
}

function sameTuple(left: [number, number, number], right: [number, number, number]) {
  return left.every((value, index) => value === right[index]);
}

function anchorMatchesPlacement(anchor: BrepSurfaceAnchorEvidence, placement: DeclaredPlacementEvidence | undefined) {
  return Boolean(
    placement
    && anchor.entityId === placement.entityId
    && anchor.resourceId === placement.resourceId
    && anchor.modelId === placement.modelId
    && anchor.frameId === placement.frameId
    && anchor.placementId === placement.placementId
    && sameTuple(anchor.translationMm, placement.translationMm)
    && sameTuple(anchor.rotationDegXyz, placement.rotationDegXyz),
  );
}

function anchorPayload(anchor: BrepSurfaceAnchorEvidence) {
  return {
    anchor_id: anchor.anchorId,
    interface_id: anchor.interfaceId,
    object_id: anchor.entityId,
    source_id: anchor.sourceId,
    model_id: anchor.modelId,
    content_hash: anchor.contentHash,
    placement_id: anchor.placementId,
    frame_id: anchor.frameId,
    anchor_point_mm: anchor.anchorPointMm,
    outward_normal: anchor.outwardNormal,
    face_index: anchor.faceIndex,
    face_geom_type: anchor.faceGeomType,
    authority: 'declared',
    status: 'ready',
    kernel_surface_snap: true,
    connector_mating_verified: false,
    physical_measurement: false,
    fabrication_authorized: false,
  };
}

function placementPayload(placement: DeclaredPlacementEvidence) {
  return {
    placement_id: placement.placementId,
    object_id: placement.entityId,
    model_id: placement.modelId,
    target_frame: placement.frameId,
    translation_mm: placement.translationMm,
    rotation_deg_xyz: placement.rotationDegXyz,
    authority: 'declared',
  };
}

function evidenceRows(value: unknown): BrepAdapterRequiredEvidence[] {
  if (!Array.isArray(value)) return [];
  return value.map(record).map((row) => ({
    field: String(row.field || 'unknown'),
    reason: String(row.reason || 'Additional engineering evidence is required.'),
  }));
}

function nullableNumber(value: unknown) {
  if (value === null || value === undefined) return null;
  const resolved = Number(value);
  return Number.isFinite(resolved) ? resolved : null;
}

function candidateFromReport(report: Record<string, unknown>, payload: Record<string, unknown>): BrepAdapterCandidateEvidence {
  const status = report.status === 'ready' ? 'ready' : 'unknown';
  const verticesMm = tupleRows(report.vertices_mm);
  const triangles = triangleRows(report.triangles);
  const vertexCount = Number(report.vertex_count || 0);
  const triangleCount = Number(report.triangle_count || 0);
  if (verticesMm.length !== vertexCount || triangles.length !== triangleCount) {
    throw new Error('Generated adapter mesh payload is malformed or incomplete.');
  }
  if (
    payload.geometric_candidate_only !== true
    || payload.fabrication_authorized !== false
    || payload.manufacturing_authorized !== false
    || payload.parent_raw_step_bytes_returned !== false
  ) {
    throw new Error('Adapter synthesis response violated the geometric-candidate authority boundary.');
  }

  return {
    adapterId: String(report.adapter_id),
    family: 'bridge_block_v0',
    frameId: String(report.frame_id),
    firstAnchorId: String(report.first_anchor_id),
    secondAnchorId: String(report.second_anchor_id),
    firstEntityId: String(report.first_object_id),
    secondEntityId: String(report.second_object_id),
    firstPlacementId: String(report.first_placement_id),
    secondPlacementId: String(report.second_placement_id),
    firstContentHash: String(report.first_content_hash),
    secondContentHash: String(report.second_content_hash),
    status,
    kernelAvailable: payload.kernel_available === true,
    kernel: report.kernel ? String(report.kernel) : null,
    geometricCandidatePassed: typeof report.geometric_candidate_passed === 'boolean' ? report.geometric_candidate_passed : null,
    axis: tuple3(report.adapter_axis),
    midpointMm: tuple3(report.adapter_midpoint_mm),
    lengthMm: nullableNumber(report.length_mm),
    widthMm: Number(report.width_mm),
    thicknessMm: Number(report.thickness_mm),
    volumeMm3: nullableNumber(report.volume_mm3),
    firstParentMinimumDistanceMm: nullableNumber(report.first_parent_minimum_distance_mm),
    secondParentMinimumDistanceMm: nullableNumber(report.second_parent_minimum_distance_mm),
    firstParentIntersectionVolumeMm3: nullableNumber(report.first_parent_intersection_volume_mm3),
    secondParentIntersectionVolumeMm3: nullableNumber(report.second_parent_intersection_volume_mm3),
    firstParentContactPassed: typeof report.first_parent_contact_passed === 'boolean' ? report.first_parent_contact_passed : null,
    secondParentContactPassed: typeof report.second_parent_contact_passed === 'boolean' ? report.second_parent_contact_passed : null,
    firstParentPenetrationPassed: typeof report.first_parent_penetration_passed === 'boolean' ? report.first_parent_penetration_passed : null,
    secondParentPenetrationPassed: typeof report.second_parent_penetration_passed === 'boolean' ? report.second_parent_penetration_passed : null,
    generatedSourceId: report.generated_source_id ? String(report.generated_source_id) : null,
    generatedModelId: report.generated_model_id ? String(report.generated_model_id) : null,
    generatedContentHash: report.generated_content_hash ? String(report.generated_content_hash) : null,
    generatedStepContent: report.generated_step_content ? String(report.generated_step_content) : null,
    bboxMinimumMm: tuple3(report.bbox_minimum_mm),
    bboxMaximumMm: tuple3(report.bbox_maximum_mm),
    vertexCount,
    triangleCount,
    verticesMm,
    triangles,
    requiredEvidence: evidenceRows(report.required_evidence),
    authority: 'declared',
    geometricCandidateOnly: true,
    fabricationAuthorized: false,
  };
}

function label(anchor: BrepSurfaceAnchorEvidence) {
  const entity = deck001EntityMap.get(anchor.entityId)?.name ?? anchor.entityId;
  return `${entity} · ${anchor.interfaceId} · face ${anchor.faceIndex}`;
}

export function BrepAdapterSynthesisControl() {
  const activeCandidateId = useMachineWorkbenchStore((state) => state.activeCandidateId);
  const selectedEntityId = useMachineWorkbenchStore((state) => state.selectedEntityId);
  const anchors = useWorkbenchBrepAnchorStore((state) => state.anchorsByCandidate[activeCandidateId] ?? EMPTY_ANCHORS);
  const placements = useWorkbenchPlacementStore((state) => state.placementsByCandidate[activeCandidateId] ?? EMPTY_PLACEMENTS);
  const projectState = useWorkbenchProjectSourceStore();
  const candidate = useWorkbenchBrepAdapterStore((state) => state.candidatesByArchitecture[activeCandidateId]);
  const status = useWorkbenchBrepAdapterStore((state) => state.status);
  const message = useWorkbenchBrepAdapterStore((state) => state.message);
  const setCandidate = useWorkbenchBrepAdapterStore((state) => state.setCandidate);
  const setFeedback = useWorkbenchBrepAdapterStore((state) => state.setFeedback);
  const clearCandidate = useWorkbenchBrepAdapterStore((state) => state.clearCandidate);
  const [firstAnchorId, setFirstAnchorId] = useState('');
  const [secondAnchorId, setSecondAnchorId] = useState('');
  const [widthMm, setWidthMm] = useState(20);
  const [thicknessMm, setThicknessMm] = useState(4);

  const eligibleAnchors = useMemo(
    () => Object.values(anchors).filter((anchor) => (
      anchor.faceGeomType.toUpperCase() === 'PLANE'
      && anchorMatchesPlacement(anchor, placements[anchor.entityId])
    )),
    [anchors, placements],
  );

  useEffect(() => {
    const selectedAnchor = eligibleAnchors.find((anchor) => anchor.entityId === selectedEntityId) ?? eligibleAnchors[0];
    const first = eligibleAnchors.some((anchor) => anchor.anchorId === firstAnchorId) ? firstAnchorId : selectedAnchor?.anchorId ?? '';
    const firstRow = eligibleAnchors.find((anchor) => anchor.anchorId === first);
    const second = eligibleAnchors.some((anchor) => anchor.anchorId === secondAnchorId && anchor.entityId !== firstRow?.entityId)
      ? secondAnchorId
      : eligibleAnchors.find((anchor) => anchor.entityId !== firstRow?.entityId)?.anchorId ?? '';
    if (first !== firstAnchorId) setFirstAnchorId(first);
    if (second !== secondAnchorId) setSecondAnchorId(second);
  }, [eligibleAnchors, firstAnchorId, secondAnchorId, selectedEntityId]);

  const firstAnchor = eligibleAnchors.find((anchor) => anchor.anchorId === firstAnchorId);
  const secondAnchor = eligibleAnchors.find((anchor) => anchor.anchorId === secondAnchorId);
  const canSynthesize = Boolean(
    firstAnchor
    && secondAnchor
    && firstAnchor.entityId !== secondAnchor.entityId
    && Number.isFinite(widthMm)
    && widthMm >= 0.5
    && widthMm <= 250
    && Number.isFinite(thicknessMm)
    && thicknessMm >= 0.5
    && thicknessMm <= 250,
  );

  async function synthesize() {
    if (!firstAnchor || !secondAnchor || !canSynthesize) return;
    const firstPlacement = placements[firstAnchor.entityId];
    const secondPlacement = placements[secondAnchor.entityId];
    if (!firstPlacement || !secondPlacement) return;

    clearCandidate(activeCandidateId, 'Synthesizing a fresh exact-anchor bridge candidate…');
    setFeedback('loading', 'Generating a bounded bridge in isolated CadQuery/OCCT and checking exact parent contact/penetration…');

    try {
      const firstRegistered = getRegisteredWorkbenchStepSource(projectState, activeCandidateId, firstAnchor.resourceId);
      const secondRegistered = getRegisteredWorkbenchStepSource(projectState, activeCandidateId, secondAnchor.resourceId);
      const firstSession = getSessionStepSource(activeCandidateId, firstAnchor.resourceId);
      const secondSession = getSessionStepSource(activeCandidateId, secondAnchor.resourceId);
      const registeredMode = Boolean(
        firstRegistered
        && secondRegistered
        && projectState.status === 'bound'
        && projectState.projectId
        && firstRegistered.projectId === projectState.projectId
        && secondRegistered.projectId === projectState.projectId,
      );
      const sessionMode = Boolean(firstSession && secondSession);
      if (!registeredMode && !sessionMode) {
        throw new Error('Adapter synthesis needs both parents from the same durable project or both as matching session STEP sources. Mixed source authority is refused.');
      }

      const adapterId = `adapter-${activeCandidateId}-${firstAnchor.entityId}-${secondAnchor.entityId}`;
      const sourcePayload = (registered: typeof firstRegistered, session: typeof firstSession) => registeredMode && registered
        ? {
            source_id: registered.sourceId,
            model_id: registered.modelId,
            content_hash: registered.contentHash,
          }
        : {
            source_id: session!.sourceId,
            model_id: session!.modelId,
            content_hash: session!.contentHash,
            content: session!.content,
          };
      const body = {
        project_id: registeredMode ? projectState.projectId : 'deck-001',
        adapter_id: adapterId,
        first: {
          source: sourcePayload(firstRegistered, firstSession),
          placement: placementPayload(firstPlacement),
          anchor: anchorPayload(firstAnchor),
        },
        second: {
          source: sourcePayload(secondRegistered, secondSession),
          placement: placementPayload(secondPlacement),
          anchor: anchorPayload(secondAnchor),
        },
        parameters: {
          family: 'bridge_block_v0',
          width_mm: widthMm,
          thickness_mm: thicknessMm,
          max_axis_alignment_error_deg: 10,
          contact_distance_tolerance_mm: 0.05,
          penetration_volume_tolerance_mm3: 0.001,
          tessellation_tolerance_mm: 0.5,
          tessellation_angular_tolerance_rad: 0.1,
        },
        timeout_s: 90,
      };
      const endpoint = registeredMode
        ? '/api/proxy/engineering/mechanical/geometry/brep/adapter/synthesize/stored'
        : '/api/proxy/engineering/mechanical/geometry/brep/adapter/synthesize';
      const response = await fetch(endpoint, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify(body),
        cache: 'no-store',
      });
      const payload = record(await response.json());
      if (!response.ok || payload.ok !== true) {
        throw new Error(String(record(payload.detail).message || payload.error || `BREP adapter HTTP ${response.status}`));
      }
      if (registeredMode && (
        payload.registered_sources_materialized !== true
        || payload.registered_source_hashes_reverified !== true
        || payload.raw_registered_parent_bytes_returned !== false
      )) {
        throw new Error('Stored adapter response did not prove registered-source materialization and hash re-verification.');
      }
      const report = record(payload.brep_adapter_candidate);
      if (
        report.first_anchor_id !== firstAnchor.anchorId
        || report.second_anchor_id !== secondAnchor.anchorId
        || report.first_placement_id !== firstPlacement.placementId
        || report.second_placement_id !== secondPlacement.placementId
        || report.first_content_hash !== firstAnchor.contentHash
        || report.second_content_hash !== secondAnchor.contentHash
      ) {
        throw new Error('Generated adapter dependencies disagree with the selected exact anchors or committed parent poses.');
      }
      setCandidate(activeCandidateId, candidateFromReport(report, payload));
    } catch (error: unknown) {
      setFeedback('error', error instanceof Error ? error.message : String(error));
    }
  }

  function downloadStep() {
    if (!candidate?.generatedStepContent) return;
    const blob = new Blob([candidate.generatedStepContent], { type: 'model/step' });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = `${candidate.adapterId}.step`;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
  }

  return (
    <section className="rounded-xl border border-amber-300/15 bg-amber-300/[0.025] p-3" data-testid="brep-adapter-synthesis-control">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2 text-[9px] font-semibold uppercase tracking-[0.16em] text-amber-200">
            <Hammer className="h-3.5 w-3.5" /> Adapter synthesis · bridge_block_v0
          </div>
          <div className="mt-1 max-w-3xl text-[10px] leading-4 text-slate-500">
            Two exact planar anchors define a bounded generated bridge. HS re-checks exact parent contact and penetration; mounting, material, strength and fabrication authority remain unresolved.
          </div>
        </div>
        <span className="rounded-full border border-red-300/15 bg-red-300/[0.04] px-2 py-1 text-[8px] font-semibold uppercase tracking-[0.12em] text-red-200">fabrication blocked</span>
      </div>

      <div className="mt-3 grid gap-2 lg:grid-cols-[1fr_1fr_110px_110px_auto]">
        <label className="text-[9px] font-semibold uppercase tracking-[0.1em] text-slate-500">
          Anchor A
          <select aria-label="Adapter anchor A" value={firstAnchorId} onChange={(event) => setFirstAnchorId(event.target.value)} className="mt-1 w-full rounded-md border border-white/10 bg-[#07101d] px-2 py-2 text-[10px] font-medium normal-case tracking-normal text-slate-200 outline-none focus:border-cyan-300/30">
            <option value="">Choose exact anchor</option>
            {eligibleAnchors.map((anchor) => <option key={anchor.anchorId} value={anchor.anchorId}>{label(anchor)}</option>)}
          </select>
        </label>
        <label className="text-[9px] font-semibold uppercase tracking-[0.1em] text-slate-500">
          Anchor B
          <select aria-label="Adapter anchor B" value={secondAnchorId} onChange={(event) => setSecondAnchorId(event.target.value)} className="mt-1 w-full rounded-md border border-white/10 bg-[#07101d] px-2 py-2 text-[10px] font-medium normal-case tracking-normal text-slate-200 outline-none focus:border-cyan-300/30">
            <option value="">Choose exact anchor</option>
            {eligibleAnchors.filter((anchor) => anchor.entityId !== firstAnchor?.entityId).map((anchor) => <option key={anchor.anchorId} value={anchor.anchorId}>{label(anchor)}</option>)}
          </select>
        </label>
        <label className="text-[9px] font-semibold uppercase tracking-[0.1em] text-slate-500">
          Width mm
          <input aria-label="Adapter width mm" type="number" min="0.5" max="250" step="0.5" value={widthMm} onChange={(event) => setWidthMm(Number(event.target.value))} className="mt-1 w-full rounded-md border border-white/10 bg-[#07101d] px-2 py-2 text-[10px] font-medium normal-case tracking-normal text-slate-200 outline-none focus:border-cyan-300/30" />
        </label>
        <label className="text-[9px] font-semibold uppercase tracking-[0.1em] text-slate-500">
          Thick mm
          <input aria-label="Adapter thickness mm" type="number" min="0.5" max="250" step="0.5" value={thicknessMm} onChange={(event) => setThicknessMm(Number(event.target.value))} className="mt-1 w-full rounded-md border border-white/10 bg-[#07101d] px-2 py-2 text-[10px] font-medium normal-case tracking-normal text-slate-200 outline-none focus:border-cyan-300/30" />
        </label>
        <button type="button" onClick={synthesize} disabled={!canSynthesize || status === 'loading'} className="self-end rounded-md border border-amber-300/20 bg-amber-300/[0.07] px-3 py-2 text-[9px] font-semibold uppercase tracking-[0.1em] text-amber-100 transition hover:bg-amber-300/[0.12] disabled:cursor-not-allowed disabled:opacity-35">
          <span className="inline-flex items-center gap-1.5"><Sparkles className="h-3 w-3" /> {status === 'loading' ? 'Synthesizing…' : 'Synthesize'}</span>
        </button>
      </div>

      {eligibleAnchors.length < 2 ? (
        <div className="mt-3 flex items-start gap-2 rounded-lg border border-white/8 bg-black/15 p-2.5 text-[10px] leading-4 text-slate-500">
          <Link2 className="mt-0.5 h-3.5 w-3.5 shrink-0" /> Pick exact planar BREP surfaces on two different placed components first.
        </div>
      ) : null}

      <div className={`mt-3 rounded-lg border p-2.5 text-[10px] leading-4 ${status === 'error' ? 'border-red-300/20 bg-red-300/[0.04] text-red-100' : status === 'ready' ? 'border-emerald-300/15 bg-emerald-300/[0.035] text-emerald-100' : 'border-white/8 bg-black/15 text-slate-400'}`} data-testid="brep-adapter-synthesis-feedback" data-status={status}>
        {message}
      </div>

      {candidate ? (
        <div className="mt-3 grid gap-3 xl:grid-cols-[1.1fr_1fr]" data-testid="brep-adapter-synthesis-result" data-geometric-pass={candidate.geometricCandidatePassed === null ? 'unknown' : candidate.geometricCandidatePassed ? 'true' : 'false'}>
          <div className="rounded-lg border border-white/10 bg-black/15 p-3">
            <div className="flex items-center justify-between gap-3">
              <div>
                <div className="text-[9px] font-semibold uppercase tracking-[0.14em] text-slate-400">Generated geometric candidate</div>
                <div className="mt-1 font-mono text-[10px] text-slate-200">{candidate.adapterId}</div>
              </div>
              <span className={`rounded-full border px-2 py-1 text-[8px] font-semibold uppercase tracking-[0.1em] ${candidate.geometricCandidatePassed ? 'border-emerald-300/20 bg-emerald-300/[0.06] text-emerald-200' : 'border-amber-300/20 bg-amber-300/[0.05] text-amber-100'}`}>
                {candidate.geometricCandidatePassed ? 'geometry pass' : candidate.status === 'ready' ? 'geometry rejected' : 'unknown'}
              </span>
            </div>
            <div className="mt-2 grid grid-cols-2 gap-2 text-[9px]">
              <div className="rounded-md border border-white/7 p-2"><div className="text-slate-600">Span</div><div className="mt-0.5 text-slate-200">{candidate.lengthMm?.toFixed(3) ?? '—'} mm</div></div>
              <div className="rounded-md border border-white/7 p-2"><div className="text-slate-600">Cross-section</div><div className="mt-0.5 text-slate-200">{candidate.widthMm} × {candidate.thicknessMm} mm</div></div>
              <div className="rounded-md border border-white/7 p-2"><div className="text-slate-600">Parent A</div><div className="mt-0.5 text-slate-200">d {candidate.firstParentMinimumDistanceMm?.toFixed(4) ?? '—'} · V∩ {candidate.firstParentIntersectionVolumeMm3?.toFixed(5) ?? '—'}</div></div>
              <div className="rounded-md border border-white/7 p-2"><div className="text-slate-600">Parent B</div><div className="mt-0.5 text-slate-200">d {candidate.secondParentMinimumDistanceMm?.toFixed(4) ?? '—'} · V∩ {candidate.secondParentIntersectionVolumeMm3?.toFixed(5) ?? '—'}</div></div>
            </div>
            {candidate.generatedContentHash ? <div className="mt-2 truncate font-mono text-[8px] text-slate-600">{candidate.generatedContentHash}</div> : null}
            {candidate.generatedStepContent ? (
              <button type="button" onClick={downloadStep} className="mt-2 inline-flex items-center gap-1.5 rounded-md border border-white/10 px-2.5 py-1.5 text-[9px] font-semibold uppercase tracking-[0.09em] text-slate-300 hover:bg-white/5">
                <Download className="h-3 w-3" /> Export generated STEP
              </button>
            ) : null}
          </div>
          <div className="rounded-lg border border-red-300/15 bg-red-300/[0.025] p-3">
            <div className="flex items-center gap-2 text-[9px] font-semibold uppercase tracking-[0.14em] text-red-200"><ShieldAlert className="h-3.5 w-3.5" /> Still unresolved</div>
            <div className="mt-2 space-y-1.5 text-[9px] leading-4 text-slate-400">
              {candidate.requiredEvidence.length ? candidate.requiredEvidence.map((row) => (
                <div key={`${row.field}-${row.reason}`}><span className="font-semibold text-slate-300">{row.field}</span> · {row.reason}</div>
              )) : <div>No additional evidence rows were returned, but fabrication authority remains blocked.</div>}
            </div>
          </div>
        </div>
      ) : null}
    </section>
  );
}
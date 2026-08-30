'use client';

import { Activity, Loader2, Route, TriangleAlert } from 'lucide-react';
import { useEffect, useMemo, useRef, useState } from 'react';
import type { ConstructorCandidateId } from '@/lib/machine-workbench-store';
import {
  useWorkbenchBrepAnchorStore,
  type BrepSurfaceAnchorEvidence,
} from '@/lib/workbench-brep-anchor-store';
import { getSessionStepSource } from '@/lib/workbench-session-step-sources';

const EMPTY_ANCHORS: Record<string, BrepSurfaceAnchorEvidence> = {};
const MAX_REFINEMENT_TOTAL_POSE_BUDGET = 256;

function record(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {};
}

function finite(value: unknown): number | null {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function anchorFingerprint(anchor: BrepSurfaceAnchorEvidence) {
  return [
    anchor.anchorId,
    anchor.interfaceId,
    anchor.entityId,
    anchor.resourceId,
    anchor.sourceId,
    anchor.modelId,
    anchor.contentHash,
    anchor.frameId,
    anchor.placementId,
    ...anchor.translationMm,
    ...anchor.rotationDegXyz,
    ...anchor.anchorPointMm,
    ...anchor.outwardNormal,
    anchor.faceIndex,
  ].join('|');
}

type AnchorPair = {
  key: string;
  moving: BrepSurfaceAnchorEvidence;
  fixed: BrepSurfaceAnchorEvidence;
};

export function BrepMatingPathRefinementControl({
  candidateId,
  entityId,
}: {
  candidateId: ConstructorCandidateId;
  entityId: string;
}) {
  const candidateAnchors = useWorkbenchBrepAnchorStore((state) => state.anchorsByCandidate[candidateId]);
  const anchors = candidateAnchors ?? EMPTY_ANCHORS;
  const pairs = useMemo(() => {
    const rows = Object.values(anchors);
    const result: AnchorPair[] = [];
    for (const moving of rows.filter((anchor) => anchor.entityId === entityId)) {
      for (const fixed of rows.filter(
        (anchor) => anchor.entityId !== entityId && anchor.interfaceId === moving.interfaceId,
      )) {
        const key = `${moving.anchorId}::${fixed.anchorId}`;
        if (!result.some((row) => row.key === key)) result.push({ key, moving, fixed });
      }
    }
    return result.sort((left, right) => left.key.localeCompare(right.key));
  }, [anchors, entityId]);

  const activePair = pairs[0] ?? null;
  const movingSource = activePair
    ? getSessionStepSource(candidateId, activePair.moving.resourceId)
    : null;
  const fixedSource = activePair
    ? getSessionStepSource(candidateId, activePair.fixed.resourceId)
    : null;
  const sourceReady = Boolean(
    activePair
    && movingSource
    && fixedSource
    && movingSource.entityId === activePair.moving.entityId
    && fixedSource.entityId === activePair.fixed.entityId
    && movingSource.modelId === activePair.moving.modelId
    && fixedSource.modelId === activePair.fixed.modelId
    && movingSource.contentHash === activePair.moving.contentHash
    && fixedSource.contentHash === activePair.fixed.contentHash,
  );

  const [endTranslation, setEndTranslation] = useState(['', '', '']);
  const [sampleCount, setSampleCount] = useState('9');
  const [contactTolerance, setContactTolerance] = useState('0.001');
  const [refinementDepth, setRefinementDepth] = useState('8');
  const [fractionTolerance, setFractionTolerance] = useState('0.001');
  const [state, setState] = useState<'idle' | 'loading' | 'success' | 'unknown' | 'error'>('idle');
  const [message, setMessage] = useState('');
  const [report, setReport] = useState<Record<string, unknown> | null>(null);
  const [evaluatedFingerprint, setEvaluatedFingerprint] = useState<string | null>(null);

  useEffect(() => {
    if (!activePair) {
      setEndTranslation(['', '', '']);
      setState('idle');
      setMessage('');
      setReport(null);
      setEvaluatedFingerprint(null);
      return;
    }
    setEndTranslation(activePair.moving.translationMm.map((value) => String(value)));
    setState('idle');
    setMessage('');
    setReport(null);
    setEvaluatedFingerprint(null);
  }, [activePair?.key]);

  const currentFingerprint = activePair
    ? [
        anchorFingerprint(activePair.moving),
        anchorFingerprint(activePair.fixed),
        endTranslation.join(','),
        sampleCount,
        contactTolerance,
        refinementDepth,
        fractionTolerance,
      ].join('::')
    : '';
  const currentFingerprintRef = useRef(currentFingerprint);
  currentFingerprintRef.current = currentFingerprint;

  useEffect(() => {
    if (evaluatedFingerprint && evaluatedFingerprint !== currentFingerprint) {
      setState('idle');
      setMessage('');
      setReport(null);
      setEvaluatedFingerprint(null);
    }
  }, [currentFingerprint, evaluatedFingerprint]);

  if (!activePair) return null;

  async function refineTransitions() {
    if (!activePair || !movingSource || !fixedSource || !sourceReady) {
      setState('error');
      setMessage('Adaptive refinement needs both current hash-bound session STEP sources.');
      return;
    }

    const end = endTranslation.map(finite);
    const samples = finite(sampleCount);
    const contact = finite(contactTolerance);
    const depth = finite(refinementDepth);
    const fraction = finite(fractionTolerance);
    if (end.some((value) => value === null)) {
      setState('error');
      setMessage('Refinement end translation must contain three finite millimetre values.');
      return;
    }
    if (samples === null || !Number.isInteger(samples) || samples < 2 || samples > 33) {
      setState('error');
      setMessage('Coarse sample count must be an integer from 2 through 33.');
      return;
    }
    if (contact === null || contact < 0) {
      setState('error');
      setMessage('Contact tolerance must be a finite non-negative millimetre value.');
      return;
    }
    if (depth === null || !Number.isInteger(depth) || depth < 1 || depth > 12) {
      setState('error');
      setMessage('Refinement depth must be an integer from 1 through 12.');
      return;
    }
    if (fraction === null || fraction < 0.000001 || fraction > 0.25) {
      setState('error');
      setMessage('Refinement fraction tolerance must be between 0.000001 and 0.25.');
      return;
    }
    const worstCasePoseCount = samples + 2 * (samples - 1) * (depth + 2);
    if (worstCasePoseCount > MAX_REFINEMENT_TOTAL_POSE_BUDGET) {
      setState('error');
      setMessage(
        `Adaptive refinement worst-case exact pose budget ${worstCasePoseCount} exceeds ${MAX_REFINEMENT_TOTAL_POSE_BUDGET}; reduce coarse samples or max bisection depth.`,
      );
      return;
    }
    const endValues = end as [number, number, number];
    if (endValues.every((value, index) => Math.abs(value - activePair.moving.translationMm[index]) <= 1e-12)) {
      setState('error');
      setMessage('Declare a non-zero moving translation path before refining transitions.');
      return;
    }

    const requestFingerprint = currentFingerprint;
    setState('loading');
    setMessage('Sampling the declared path, then adaptively narrowing exact BREP predicate changes…');
    setReport(null);
    try {
      const response = await fetch('/api/proxy/engineering/mechanical/geometry/brep/mating-path/refine', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({
          project_id: 'deck-001',
          sweep_id: `mating-path-refine-${candidateId}-${activePair.moving.entityId}-${activePair.fixed.entityId}`,
          moving_source: {
            source_id: movingSource.sourceId,
            model_id: movingSource.modelId,
            content_hash: movingSource.contentHash,
            content: movingSource.content,
          },
          fixed_source: {
            source_id: fixedSource.sourceId,
            model_id: fixedSource.modelId,
            content_hash: fixedSource.contentHash,
            content: fixedSource.content,
          },
          moving_start_placement: {
            placement_id: activePair.moving.placementId,
            object_id: activePair.moving.entityId,
            model_id: activePair.moving.modelId,
            target_frame: activePair.moving.frameId,
            translation_mm: activePair.moving.translationMm,
            rotation_deg_xyz: activePair.moving.rotationDegXyz,
            authority: 'declared',
          },
          moving_end_placement: {
            placement_id: `${activePair.moving.placementId}:mating-path-refine-end`,
            object_id: activePair.moving.entityId,
            model_id: activePair.moving.modelId,
            target_frame: activePair.moving.frameId,
            translation_mm: endValues,
            rotation_deg_xyz: activePair.moving.rotationDegXyz,
            authority: 'declared',
          },
          fixed_placement: {
            placement_id: activePair.fixed.placementId,
            object_id: activePair.fixed.entityId,
            model_id: activePair.fixed.modelId,
            target_frame: activePair.fixed.frameId,
            translation_mm: activePair.fixed.translationMm,
            rotation_deg_xyz: activePair.fixed.rotationDegXyz,
            authority: 'declared',
          },
          sample_count: samples,
          contact_distance_tolerance_mm: contact,
          refinement_max_depth: depth,
          refinement_fraction_tolerance: fraction,
        }),
        cache: 'no-store',
      });
      const payload = record(await response.json());
      if (!response.ok || payload.ok !== true) {
        const detail = record(payload.detail);
        throw new Error(String(detail.message || payload.error || `mating-path refinement HTTP ${response.status}`));
      }
      if (requestFingerprint !== currentFingerprintRef.current) return;
      const refinement = record(payload.brep_mating_path_refinement);
      if (
        payload.adaptive_transition_refinement !== true
        || payload.transition_brackets_only !== true
        || payload.unique_transition_pose_verified !== false
        || payload.monotonicity_inside_bracket_verified !== false
        || payload.continuous_path_verified !== false
        || payload.continuous_collision_free_verified !== false
        || payload.aabb_fallback_used !== false
        || payload.connector_mating_verified !== false
        || payload.whole_assembly_collision !== false
        || payload.physical_measurement !== false
        || payload.fabrication_authorized !== false
      ) {
        throw new Error('Transition refinement response crossed the bounded evidence/authority contract.');
      }
      if (
        refinement.moving_source_id !== movingSource.sourceId
        || refinement.fixed_source_id !== fixedSource.sourceId
        || refinement.moving_model_id !== movingSource.modelId
        || refinement.fixed_model_id !== fixedSource.modelId
        || refinement.moving_content_hash !== movingSource.contentHash
        || refinement.fixed_content_hash !== fixedSource.contentHash
        || refinement.moving_object_id !== activePair.moving.entityId
        || refinement.fixed_object_id !== activePair.fixed.entityId
        || refinement.frame_id !== activePair.moving.frameId
        || Number(refinement.coarse_sample_count) !== samples
        || Number(refinement.refinement_max_depth) !== depth
      ) {
        throw new Error('Transition refinement response identity does not match the active exact-anchor pair.');
      }

      setEvaluatedFingerprint(requestFingerprint);
      setReport(refinement);
      const status = String(refinement.status || 'unknown');
      if (status === 'unknown' || payload.refinement_evaluated !== true) {
        setState('unknown');
        const required = Array.isArray(refinement.required_evidence)
          ? refinement.required_evidence.map(record)
          : [];
        setMessage(String(required[0]?.reason || 'Adaptive exact-BREP transition refinement remains UNKNOWN.'));
        return;
      }
      const refinedCount = finite(refinement.refined_boundary_count) ?? 0;
      const extraPoses = finite(refinement.refinement_evaluated_pose_count) ?? 0;
      setState('success');
      setMessage(
        status === 'not_required'
          ? 'The coarse exact samples contain no adjacent clearance/interference predicate change to refine.'
          : `Refined ${refinedCount} predicate-change bracket${refinedCount === 1 ? '' : 's'} with ${extraPoses} additional exact BREP pose evaluations.`,
      );
    } catch (error: unknown) {
      if (requestFingerprint !== currentFingerprintRef.current) return;
      setState('error');
      setMessage(error instanceof Error ? error.message : String(error));
      setReport(null);
      setEvaluatedFingerprint(null);
    }
  }

  const brackets = report && Array.isArray(report.brackets) ? report.brackets.map(record) : [];
  const totalEvaluations = report ? finite(report.total_exact_pose_evaluations) : null;

  return (
    <div className="mt-2 rounded-lg border border-rose-300/10 bg-rose-300/[0.025] p-2" data-testid="brep-mating-path-refinement-control">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-1.5 text-[8px] font-semibold uppercase tracking-[0.12em] text-rose-200/85">
          <Route className="h-3 w-3" /> Adaptive transition brackets
        </div>
        <span className="text-[7px] uppercase tracking-[0.1em] text-slate-600">exact OCCT · range only</span>
      </div>
      <div className="mt-1 text-[8px] leading-4 text-slate-500">
        Coarse-sample {activePair.moving.entityId} against {activePair.fixed.entityId}, then bisect only predicate-changing intervals. No unique contact pose or continuous clearance is inferred.
      </div>
      {!sourceReady ? (
        <div className="mt-1.5 text-[8px] leading-4 text-amber-200/75">
          Current session STEP bytes are not available for both hash-bound anchors. Re-import/re-anchor before refinement.
        </div>
      ) : null}
      <div className="mt-2 grid grid-cols-3 gap-1.5">
        {['X', 'Y', 'Z'].map((axis, index) => (
          <label key={axis} className="text-[7px] uppercase tracking-[0.08em] text-slate-600">
            End {axis} mm
            <input
              aria-label={`Adaptive refinement end translation ${axis}`}
              value={endTranslation[index]}
              onChange={(event) => setEndTranslation((current) => current.map((value, row) => row === index ? event.target.value : value))}
              className="mt-1 w-full rounded border border-white/8 bg-black/20 px-1.5 py-1.5 text-[9px] normal-case tracking-normal text-slate-200 outline-none focus:border-rose-300/25"
            />
          </label>
        ))}
      </div>
      <div className="mt-2 grid grid-cols-2 gap-1.5">
        <label className="text-[7px] uppercase tracking-[0.08em] text-slate-600">
          Coarse samples
          <input aria-label="Refined mating path coarse sample count" value={sampleCount} onChange={(event) => setSampleCount(event.target.value)} className="mt-1 w-full rounded border border-white/8 bg-black/20 px-1.5 py-1.5 text-[9px] text-slate-200 outline-none focus:border-rose-300/25" />
        </label>
        <label className="text-[7px] uppercase tracking-[0.08em] text-slate-600">
          Contact mm
          <input aria-label="Refined mating path contact tolerance mm" value={contactTolerance} onChange={(event) => setContactTolerance(event.target.value)} className="mt-1 w-full rounded border border-white/8 bg-black/20 px-1.5 py-1.5 text-[9px] text-slate-200 outline-none focus:border-rose-300/25" />
        </label>
        <label className="text-[7px] uppercase tracking-[0.08em] text-slate-600">
          Max bisection depth
          <input aria-label="Mating path refinement max depth" value={refinementDepth} onChange={(event) => setRefinementDepth(event.target.value)} className="mt-1 w-full rounded border border-white/8 bg-black/20 px-1.5 py-1.5 text-[9px] text-slate-200 outline-none focus:border-rose-300/25" />
        </label>
        <label className="text-[7px] uppercase tracking-[0.08em] text-slate-600">
          Fraction tolerance
          <input aria-label="Mating path refinement fraction tolerance" value={fractionTolerance} onChange={(event) => setFractionTolerance(event.target.value)} className="mt-1 w-full rounded border border-white/8 bg-black/20 px-1.5 py-1.5 text-[9px] text-slate-200 outline-none focus:border-rose-300/25" />
        </label>
      </div>
      <button
        type="button"
        onClick={refineTransitions}
        disabled={!sourceReady || state === 'loading'}
        className="mt-2 inline-flex items-center gap-1.5 rounded-md border border-rose-300/15 bg-rose-300/[0.04] px-2 py-1.5 text-[8px] font-semibold uppercase tracking-[0.08em] text-rose-100 hover:bg-rose-300/[0.08] disabled:cursor-not-allowed disabled:opacity-45"
      >
        {state === 'loading' ? <Loader2 className="h-3 w-3 animate-spin" /> : <Activity className="h-3 w-3" />}
        {state === 'loading' ? 'Refining transitions' : 'Refine sampled transitions'}
      </button>
      {message ? (
        <div
          data-testid="brep-mating-path-refinement-feedback"
          data-refinement-state={state}
          className={`mt-1.5 text-[8px] leading-4 ${state === 'success' ? 'text-emerald-300/75' : state === 'error' ? 'text-red-300/80' : state === 'unknown' ? 'text-amber-300/80' : 'text-slate-500'}`}
        >
          {message}
        </div>
      ) : null}
      {report && state === 'success' ? (
        <div data-testid="brep-mating-path-refinement-result" className="mt-2 space-y-1 rounded border border-white/8 bg-black/15 p-1.5">
          <div className="flex items-center justify-between gap-2 text-[7px] uppercase tracking-[0.08em] text-slate-500">
            <span>{brackets.length} predicate bracket{brackets.length === 1 ? '' : 's'}</span>
            <span>{totalEvaluations ?? '—'} total exact poses</span>
          </div>
          {brackets.map((row, index) => {
            const lowerFraction = finite(row.lower_fraction);
            const upperFraction = finite(row.upper_fraction);
            const lowerDistance = finite(row.lower_path_distance_mm);
            const upperDistance = finite(row.upper_path_distance_mm);
            const widthMm = finite(row.bracket_width_mm);
            return (
              <div key={`${String(row.kind)}-${index}`} data-testid="brep-transition-bracket" className="rounded border border-rose-300/10 bg-rose-300/[0.02] px-1.5 py-1 text-[7px] leading-3 text-slate-400">
                <div className="font-semibold uppercase tracking-[0.08em] text-rose-200/70">{String(row.kind || 'predicate boundary')}</div>
                <div>
                  fraction {lowerFraction?.toFixed(6) ?? '—'}–{upperFraction?.toFixed(6) ?? '—'} · path {lowerDistance?.toFixed(4) ?? '—'}–{upperDistance?.toFixed(4) ?? '—'} mm
                </div>
                <div>
                  {String(row.lower_state || 'unknown')} → {String(row.upper_state || 'unknown')} · bracket width {widthMm?.toFixed(4) ?? '—'} mm · {row.converged === true ? 'within tolerance' : 'depth bounded'}
                </div>
              </div>
            );
          })}
          {brackets.length === 0 ? <div className="text-[7px] text-slate-500">No adjacent coarse predicate change required refinement.</div> : null}
        </div>
      ) : null}
      <div className="mt-1.5 flex gap-1.5 text-[7px] leading-3 text-rose-100/45">
        <TriangleAlert className="mt-0.5 h-2.5 w-2.5 shrink-0" />
        Refined brackets localize sampled boolean predicate changes only. They do not prove a unique transition pose, monotonic behavior inside the bracket, continuous collision-free motion, connector mating, whole-assembly clearance, measurement truth, or fabrication authority.
      </div>
    </div>
  );
}

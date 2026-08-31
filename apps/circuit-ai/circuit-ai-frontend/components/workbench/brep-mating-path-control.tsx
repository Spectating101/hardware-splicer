'use client';

import { Activity, Loader2, Route, TriangleAlert } from 'lucide-react';
import { useEffect, useMemo, useRef, useState } from 'react';
import type { ConstructorCandidateId } from '@/lib/machine-workbench-store';
import {
  useWorkbenchBrepAnchorStore,
  type BrepSurfaceAnchorEvidence,
} from '@/lib/workbench-brep-anchor-store';
import { getSessionStepSource } from '@/lib/workbench-session-step-sources';
import {
  getRegisteredWorkbenchStepSource,
  useWorkbenchProjectSourceStore,
} from '@/lib/workbench-project-sources';

const EMPTY_ANCHORS: Record<string, BrepSurfaceAnchorEvidence> = {};

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

export function BrepMatingPathControl({
  candidateId,
  entityId,
}: {
  candidateId: ConstructorCandidateId;
  entityId: string;
}) {
  const candidateAnchors = useWorkbenchBrepAnchorStore((state) => state.anchorsByCandidate[candidateId]);
  const anchors = candidateAnchors ?? EMPTY_ANCHORS;
  const projectSourceState = useWorkbenchProjectSourceStore();
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

  const [pairKey, setPairKey] = useState('');
  const [endTranslation, setEndTranslation] = useState(['', '', '']);
  const [sampleCount, setSampleCount] = useState('9');
  const [engagementStart, setEngagementStart] = useState('');
  const [contactTolerance, setContactTolerance] = useState('0.001');
  const [state, setState] = useState<'idle' | 'loading' | 'success' | 'unknown' | 'error'>('idle');
  const [message, setMessage] = useState('');
  const [report, setReport] = useState<Record<string, unknown> | null>(null);
  const [evaluatedFingerprint, setEvaluatedFingerprint] = useState<string | null>(null);

  const activePair = pairs.find((row) => row.key === pairKey) ?? pairs[0] ?? null;
  const movingSessionSource = activePair ? getSessionStepSource(candidateId, activePair.moving.resourceId) : null;
  const fixedSessionSource = activePair ? getSessionStepSource(candidateId, activePair.fixed.resourceId) : null;
  const movingRegisteredSource = activePair
    ? getRegisteredWorkbenchStepSource(projectSourceState, candidateId, activePair.moving.resourceId)
    : null;
  const fixedRegisteredSource = activePair
    ? getRegisteredWorkbenchStepSource(projectSourceState, candidateId, activePair.fixed.resourceId)
    : null;
  const registeredReady = Boolean(
    activePair
    && projectSourceState.status === 'bound'
    && projectSourceState.projectId
    && movingRegisteredSource
    && fixedRegisteredSource
    && movingRegisteredSource.projectId === projectSourceState.projectId
    && fixedRegisteredSource.projectId === projectSourceState.projectId
    && movingRegisteredSource.entityId === activePair.moving.entityId
    && fixedRegisteredSource.entityId === activePair.fixed.entityId
    && movingRegisteredSource.modelId === activePair.moving.modelId
    && fixedRegisteredSource.modelId === activePair.fixed.modelId
    && movingRegisteredSource.contentHash === activePair.moving.contentHash
    && fixedRegisteredSource.contentHash === activePair.fixed.contentHash,
  );
  const sessionReady = Boolean(
    activePair
    && movingSessionSource
    && fixedSessionSource
    && movingSessionSource.entityId === activePair.moving.entityId
    && fixedSessionSource.entityId === activePair.fixed.entityId
    && movingSessionSource.modelId === activePair.moving.modelId
    && fixedSessionSource.modelId === activePair.fixed.modelId
    && movingSessionSource.contentHash === activePair.moving.contentHash
    && fixedSessionSource.contentHash === activePair.fixed.contentHash,
  );
  const sourceReady = registeredReady || sessionReady;
  const movingSource = registeredReady ? movingRegisteredSource : movingSessionSource;
  const fixedSource = registeredReady ? fixedRegisteredSource : fixedSessionSource;

  const currentFingerprint = activePair
    ? [
        anchorFingerprint(activePair.moving),
        anchorFingerprint(activePair.fixed),
        endTranslation.join(','),
        sampleCount,
        engagementStart,
        contactTolerance,
      ].join('::')
    : '';
  const currentFingerprintRef = useRef(currentFingerprint);
  currentFingerprintRef.current = currentFingerprint;

  useEffect(() => {
    if (!pairs.length) {
      setPairKey('');
      setEndTranslation(['', '', '']);
      setState('idle');
      setMessage('');
      setReport(null);
      setEvaluatedFingerprint(null);
      return;
    }
    const nextPair = pairs.find((row) => row.key === pairKey) ?? pairs[0];
    if (nextPair.key !== pairKey) setPairKey(nextPair.key);
    if (!endTranslation.every((value) => value.trim().length > 0)) {
      setEndTranslation(nextPair.moving.translationMm.map((value) => String(value)));
    }
  }, [endTranslation, pairKey, pairs]);

  useEffect(() => {
    if (evaluatedFingerprint && evaluatedFingerprint !== currentFingerprint) {
      setState('idle');
      setMessage('');
      setReport(null);
      setEvaluatedFingerprint(null);
    }
  }, [currentFingerprint, evaluatedFingerprint]);

  if (!activePair) return null;

  async function evaluatePath() {
    if (!activePair || !movingSource || !fixedSource || !sourceReady) {
      setState('error');
      setMessage('Exact mating-path evidence needs both anchors backed by either matching session STEP sources or matching registered project sources. Mixed/unbound provenance is refused.');
      return;
    }
    const end = endTranslation.map(finite);
    const samples = finite(sampleCount);
    const engagement = engagementStart.trim() ? finite(engagementStart) : null;
    const contact = finite(contactTolerance);
    if (end.some((value) => value === null) || end.some((value) => !Number.isFinite(value))) {
      setState('error');
      setMessage('Moving end translation must contain three finite millimetre values.');
      return;
    }
    if (samples === null || !Number.isInteger(samples) || samples < 2 || samples > 33) {
      setState('error');
      setMessage('Sample count must be an integer from 2 through 33.');
      return;
    }
    if (engagement !== null && (engagement < 0 || engagement > 1)) {
      setState('error');
      setMessage('Engagement start fraction must be blank or between 0 and 1.');
      return;
    }
    if (contact === null || contact < 0) {
      setState('error');
      setMessage('Contact tolerance must be a finite non-negative millimetre value.');
      return;
    }
    const endValues = end as [number, number, number];
    if (endValues.every((value, index) => Math.abs(value - activePair.moving.translationMm[index]) <= 1e-12)) {
      setState('error');
      setMessage('Declare a non-zero moving translation path before evaluating exact BREP samples.');
      return;
    }

    const requestFingerprint = currentFingerprint;
    setState('loading');
    setMessage(
      registeredReady
        ? 'Reopening both registered STEP blobs, re-verifying both hashes, then evaluating bounded exact BREP poses along the declared translation path…'
        : 'Evaluating bounded exact BREP poses along the declared translation path…',
    );
    setReport(null);
    try {
      const endpoint = registeredReady
        ? '/api/proxy/engineering/mechanical/geometry/brep/mating-path/stored'
        : '/api/proxy/engineering/mechanical/geometry/brep/mating-path';
      const response = await fetch(endpoint, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({
          project_id: registeredReady && movingRegisteredSource ? movingRegisteredSource.projectId : 'deck-001',
          sweep_id: `mating-path-${candidateId}-${activePair.moving.entityId}-${activePair.fixed.entityId}`,
          moving_source: registeredReady
            ? {
                source_id: movingSource.sourceId,
                model_id: movingSource.modelId,
                content_hash: movingSource.contentHash,
              }
            : {
                source_id: movingSource.sourceId,
                model_id: movingSource.modelId,
                content_hash: movingSource.contentHash,
                content: movingSessionSource?.content,
              },
          fixed_source: registeredReady
            ? {
                source_id: fixedSource.sourceId,
                model_id: fixedSource.modelId,
                content_hash: fixedSource.contentHash,
              }
            : {
                source_id: fixedSource.sourceId,
                model_id: fixedSource.modelId,
                content_hash: fixedSource.contentHash,
                content: fixedSessionSource?.content,
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
            placement_id: `${activePair.moving.placementId}:mating-path-end`,
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
          engagement_start_fraction: engagement,
          contact_distance_tolerance_mm: contact,
        }),
        cache: 'no-store',
      });
      const payload = record(await response.json());
      if (!response.ok || payload.ok !== true) {
        const detail = record(payload.detail);
        throw new Error(String(detail.message || payload.error || `mating-path HTTP ${response.status}`));
      }
      if (requestFingerprint !== currentFingerprintRef.current) return;
      const sweep = record(payload.brep_mating_path);
      if (
        payload.sampled_path_only !== true
        || payload.continuous_path_verified !== false
        || payload.continuous_collision_free_verified !== false
        || payload.aabb_fallback_used !== false
        || payload.connector_mating_verified !== false
        || payload.whole_assembly_collision !== false
        || payload.physical_measurement !== false
        || payload.fabrication_authorized !== false
      ) {
        throw new Error('Mating-path response crossed the bounded evidence/authority contract.');
      }
      if (registeredReady && (
        payload.registered_sources_materialized !== true
        || payload.registered_source_hashes_reverified !== true
        || payload.moving_registered_source_hash_reverified !== true
        || payload.fixed_registered_source_hash_reverified !== true
        || payload.raw_registered_source_bytes_returned !== false
      )) {
        throw new Error('Stored mating-path response did not prove both registered blobs were independently hash re-verified.');
      }
      if (
        sweep.moving_source_id !== movingSource.sourceId
        || sweep.fixed_source_id !== fixedSource.sourceId
        || sweep.moving_model_id !== movingSource.modelId
        || sweep.fixed_model_id !== fixedSource.modelId
        || sweep.moving_content_hash !== movingSource.contentHash
        || sweep.fixed_content_hash !== fixedSource.contentHash
        || sweep.moving_object_id !== activePair.moving.entityId
        || sweep.fixed_object_id !== activePair.fixed.entityId
        || sweep.frame_id !== activePair.moving.frameId
        || Number(sweep.sample_count) !== samples
      ) {
        throw new Error('Mating-path response identity does not match the active exact-anchor pair.');
      }
      setEvaluatedFingerprint(requestFingerprint);
      setReport(sweep);
      if (String(sweep.status) !== 'ready' || payload.sampled_path_evaluated !== true) {
        setState('unknown');
        const required = Array.isArray(sweep.required_evidence) ? sweep.required_evidence.map(record) : [];
        setMessage(String(required[0]?.reason || 'Exact sampled path evidence remains UNKNOWN.'));
        return;
      }
      setState('success');
      setMessage(
        payload.sampled_path_interference_free === true
          ? `All evaluated BREP samples are free of volumetric interference. This is sampled evidence, not continuous-path proof.${registeredReady ? ' Both registered source hashes were reverified server-side.' : ''}`
          : 'At least one evaluated BREP sample has volumetric interference. The declared sampled path is not clear.',
      );
    } catch (error: unknown) {
      if (requestFingerprint !== currentFingerprintRef.current) return;
      setState('error');
      setMessage(error instanceof Error ? error.message : String(error));
      setReport(null);
      setEvaluatedFingerprint(null);
    }
  }

  const firstContactIndex = report ? finite(report.first_contact_sample_index) : null;
  const firstContactDistance = report ? finite(report.first_contact_path_distance_mm) : null;
  const firstInterferenceIndex = report ? finite(report.first_interference_sample_index) : null;
  const firstInterferenceDistance = report ? finite(report.first_interference_path_distance_mm) : null;
  const evaluatedSamples = report ? finite(report.evaluated_sample_count) : null;
  const engagementEvaluated = report?.engagement_region_evaluated === true;
  const engagementClear = report?.engagement_region_interference_free;

  return (
    <div className="mt-2 rounded-lg border border-orange-300/10 bg-orange-300/[0.025] p-2" data-testid="brep-mating-path-control">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-1.5 text-[9px] font-semibold uppercase tracking-[0.12em] text-orange-200/85">
          <Route className="h-3 w-3" /> Sampled mating path
        </div>
        <span className="text-[8px] uppercase tracking-[0.1em] text-slate-600">exact BREP · not continuous</span>
      </div>
      <div className="mt-1 text-[9px] leading-4 text-slate-500">
        Moving {activePair.moving.entityId} along a declared translation path against fixed {activePair.fixed.entityId} · {activePair.moving.interfaceId}.
      </div>
      {!sourceReady ? (
        <div className="mt-1.5 text-[9px] leading-4 text-amber-200/75">
          Both anchors must resolve through one provenance lane: two matching registered project STEP sources or two matching session STEP sources. Mixed/unbound sources are not evaluated.
        </div>
      ) : registeredReady ? (
        <div className="mt-1.5 text-[8px] leading-4 text-emerald-200/60">Registered-project path · both blobs are reopened and hash reverified server-side for each evaluation.</div>
      ) : null}
      <div className="mt-2 grid grid-cols-3 gap-1.5">
        {['X', 'Y', 'Z'].map((axis, index) => (
          <label key={axis} className="text-[8px] uppercase tracking-[0.08em] text-slate-600">
            End {axis} mm
            <input
              aria-label={`Mating path end translation ${axis}`}
              value={endTranslation[index]}
              onChange={(event) => setEndTranslation((current) => current.map((value, row) => row === index ? event.target.value : value))}
              className="mt-1 w-full rounded border border-white/8 bg-black/20 px-1.5 py-1.5 text-[10px] normal-case tracking-normal text-slate-200 outline-none focus:border-orange-300/25"
            />
          </label>
        ))}
      </div>
      <div className="mt-2 grid grid-cols-3 gap-1.5">
        <label className="text-[8px] uppercase tracking-[0.08em] text-slate-600">
          Samples
          <input aria-label="Mating path sample count" value={sampleCount} onChange={(event) => setSampleCount(event.target.value)} className="mt-1 w-full rounded border border-white/8 bg-black/20 px-1.5 py-1.5 text-[10px] text-slate-200 outline-none focus:border-orange-300/25" />
        </label>
        <label className="text-[8px] uppercase tracking-[0.08em] text-slate-600">
          Engage at 0–1
          <input aria-label="Mating path engagement start fraction" placeholder="optional" value={engagementStart} onChange={(event) => setEngagementStart(event.target.value)} className="mt-1 w-full rounded border border-white/8 bg-black/20 px-1.5 py-1.5 text-[10px] normal-case tracking-normal text-slate-200 outline-none focus:border-orange-300/25" />
        </label>
        <label className="text-[8px] uppercase tracking-[0.08em] text-slate-600">
          Contact mm
          <input aria-label="Mating path contact tolerance mm" value={contactTolerance} onChange={(event) => setContactTolerance(event.target.value)} className="mt-1 w-full rounded border border-white/8 bg-black/20 px-1.5 py-1.5 text-[10px] text-slate-200 outline-none focus:border-orange-300/25" />
        </label>
      </div>
      <button
        type="button"
        onClick={evaluatePath}
        disabled={!sourceReady || state === 'loading'}
        className="mt-2 inline-flex items-center gap-1.5 rounded-md border border-orange-300/15 bg-orange-300/[0.04] px-2 py-1.5 text-[9px] font-semibold uppercase tracking-[0.08em] text-orange-200 hover:bg-orange-300/[0.08] disabled:cursor-not-allowed disabled:opacity-45"
      >
        {state === 'loading' ? <Loader2 className="h-3 w-3 animate-spin" /> : <Activity className="h-3 w-3" />}
        {state === 'loading' ? 'Evaluating sampled path' : 'Evaluate sampled path'}
      </button>
      {message ? (
        <div
          data-testid="brep-mating-path-feedback"
          data-path-status={state}
          className={`mt-1.5 flex gap-1.5 text-[9px] leading-4 ${state === 'success' ? 'text-emerald-300/75' : state === 'error' ? 'text-red-300/80' : state === 'unknown' ? 'text-amber-300/80' : 'text-slate-500'}`}
        >
          {state === 'error' || state === 'unknown' ? <TriangleAlert className="mt-0.5 h-3 w-3 shrink-0" /> : null}
          <span>{message}</span>
        </div>
      ) : null}
      {report && state === 'success' ? (
        <div className="mt-1.5 rounded border border-white/8 bg-black/15 p-1.5 text-[8px] leading-4 text-slate-400" data-testid="brep-mating-path-result">
          <div>{evaluatedSamples ?? '—'} exact samples · path {finite(report.path_length_mm)?.toFixed(3) ?? '—'} mm</div>
          <div>first sampled contact: {firstContactIndex === null ? 'none observed' : `#${firstContactIndex} at ${firstContactDistance?.toFixed(3) ?? '—'} mm`}</div>
          <div>first sampled interference: {firstInterferenceIndex === null ? 'none observed' : `#${firstInterferenceIndex} at ${firstInterferenceDistance?.toFixed(3) ?? '—'} mm`}</div>
          <div>engagement region: {!engagementEvaluated ? 'not declared/evaluated' : engagementClear === true ? 'sampled clear' : engagementClear === false ? 'sampled interference' : 'unknown'}</div>
        </div>
      ) : null}
      <div className="mt-1 text-[8px] leading-4 text-orange-100/45">
        Exact OCCT checks occur only at the declared bounded samples. Unsampled motion remains unverified; this does not establish continuous collision clearance, connector mating, retention, protocol/pins, physical fit, or fabrication authority.
      </div>
    </div>
  );
}

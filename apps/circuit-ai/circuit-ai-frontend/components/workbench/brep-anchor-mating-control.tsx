'use client';

import { CheckCircle2, GitCompareArrows, Loader2, TriangleAlert } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import type { ConstructorCandidateId } from '@/lib/machine-workbench-store';
import {
  useWorkbenchBrepAnchorStore,
  type BrepSurfaceAnchorEvidence,
} from '@/lib/workbench-brep-anchor-store';

const EMPTY_ANCHORS: Record<string, BrepSurfaceAnchorEvidence> = {};

function record(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {};
}

function finite(value: unknown): number | null {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function format(value: unknown, digits = 3) {
  const parsed = finite(value);
  return parsed === null ? '—' : parsed.toFixed(digits);
}

function toApiAnchor(anchor: BrepSurfaceAnchorEvidence) {
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

type AnchorPair = {
  key: string;
  first: BrepSurfaceAnchorEvidence;
  second: BrepSurfaceAnchorEvidence;
};

export function BrepAnchorMatingControl({
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
    for (const local of rows.filter((anchor) => anchor.entityId === entityId)) {
      for (const other of rows.filter(
        (anchor) => anchor.entityId !== entityId && anchor.interfaceId === local.interfaceId,
      )) {
        const ordered = [local, other].sort((left, right) => left.anchorId.localeCompare(right.anchorId));
        const first = ordered[0];
        const second = ordered[1];
        const key = `${first.anchorId}::${second.anchorId}`;
        if (!result.some((row) => row.key === key)) result.push({ key, first, second });
      }
    }
    return result.sort((left, right) => left.key.localeCompare(right.key));
  }, [anchors, entityId]);

  const [pairKey, setPairKey] = useState('');
  const [normalTolerance, setNormalTolerance] = useState('5');
  const [lateralTolerance, setLateralTolerance] = useState('0.5');
  const [targetAxialOffset, setTargetAxialOffset] = useState('0');
  const [axialTolerance, setAxialTolerance] = useState('0.5');
  const [axis, setAxis] = useState(['', '', '']);
  const [axisTolerance, setAxisTolerance] = useState('5');
  const [requiredEngagement, setRequiredEngagement] = useState('');
  const [declaredEngagement, setDeclaredEngagement] = useState('');
  const [state, setState] = useState<'idle' | 'loading' | 'success' | 'unknown' | 'error'>('idle');
  const [message, setMessage] = useState('');
  const [report, setReport] = useState<Record<string, unknown> | null>(null);

  useEffect(() => {
    if (!pairs.length) {
      setPairKey('');
      setState('idle');
      setMessage('');
      setReport(null);
      return;
    }
    if (!pairs.some((pair) => pair.key === pairKey)) {
      setPairKey(pairs[0].key);
      setState('idle');
      setMessage('');
      setReport(null);
    }
  }, [pairKey, pairs]);

  if (!pairs.length) return null;

  const pair = pairs.find((row) => row.key === pairKey) ?? pairs[0];

  function parseRequiredNumber(label: string, raw: string, minimum = 0) {
    const value = Number(raw);
    if (!Number.isFinite(value) || value < minimum) throw new Error(`${label} must be a finite number ≥ ${minimum}.`);
    return value;
  }

  function parseSignedNumber(label: string, raw: string) {
    const value = Number(raw);
    if (!Number.isFinite(value)) throw new Error(`${label} must be a finite number.`);
    return value;
  }

  function parseOptionalNumber(label: string, raw: string) {
    if (!raw.trim()) return null;
    return parseRequiredNumber(label, raw);
  }

  function parseAxis() {
    const populated = axis.map((value) => value.trim() !== '');
    if (populated.every((value) => !value)) return null;
    if (!populated.every(Boolean)) throw new Error('Declared mating axis must contain X, Y and Z, or be left fully blank.');
    const values = axis.map(Number);
    if (!values.every(Number.isFinite)) throw new Error('Declared mating axis must contain finite numbers.');
    if (Math.hypot(values[0], values[1], values[2]) <= 1e-12) throw new Error('Declared mating axis must be non-zero.');
    return values as [number, number, number];
  }

  async function evaluateMating() {
    const selectedAxis = parseAxis();
    const requiredDepth = parseOptionalNumber('Required engagement depth', requiredEngagement);
    const declaredDepth = parseOptionalNumber('Declared engagement depth', declaredEngagement);
    if (declaredDepth !== null && requiredDepth === null) {
      setState('error');
      setMessage('Declared engagement depth needs a required engagement depth to compare against.');
      setReport(null);
      return;
    }

    setState('loading');
    setMessage('Evaluating exact anchor geometry against the declared mating tolerances…');
    setReport(null);
    try {
      const response = await fetch('/api/proxy/engineering/mechanical/geometry/brep/mating', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({
          project_id: 'deck-001',
          mating_id: `mating-${pair.first.interfaceId}-${pair.first.anchorId}-${pair.second.anchorId}`,
          first_anchor: toApiAnchor(pair.first),
          second_anchor: toApiAnchor(pair.second),
          requirements: {
            max_normal_opposition_error_deg: parseRequiredNumber('Normal opposition tolerance', normalTolerance),
            max_lateral_offset_mm: parseRequiredNumber('Lateral offset tolerance', lateralTolerance),
            target_axial_offset_mm: parseSignedNumber('Target axial offset', targetAxialOffset),
            axial_offset_tolerance_mm: parseRequiredNumber('Axial offset tolerance', axialTolerance),
            declared_mating_axis: selectedAxis,
            max_axis_alignment_error_deg: parseRequiredNumber('Axis alignment tolerance', axisTolerance),
            required_engagement_depth_mm: requiredDepth,
            declared_engagement_depth_mm: declaredDepth,
          },
        }),
        cache: 'no-store',
      });
      const payload = record(await response.json());
      if (!response.ok || payload.ok !== true) {
        const detail = record(payload.detail);
        throw new Error(String(detail.message || payload.error || `BREP mating HTTP ${response.status}`));
      }
      if (
        payload.geometric_mating_only !== true
        || payload.connector_mating_verified !== false
        || payload.physical_measurement !== false
        || payload.fabrication_authorized !== false
      ) {
        throw new Error('HS mating response violated the declared-geometry authority boundary.');
      }
      const nextReport = record(payload.brep_anchor_mating);
      if (
        nextReport.first_anchor_id !== pair.first.anchorId
        || nextReport.second_anchor_id !== pair.second.anchorId
        || nextReport.interface_id !== pair.first.interfaceId
        || nextReport.frame_id !== pair.first.frameId
      ) {
        throw new Error('HS mating response identity disagrees with the selected exact anchor pair.');
      }
      setReport(nextReport);
      if (nextReport.status === 'unknown' || payload.mating_geometry_evaluated !== true) {
        const required = Array.isArray(nextReport.required_evidence) ? nextReport.required_evidence.map(record) : [];
        setState('unknown');
        setMessage(`Mating geometry UNKNOWN · ${String(required[0]?.reason || 'required geometric evidence is incomplete')}`);
        return;
      }
      const passed = payload.geometric_mating_passed === true;
      setState('success');
      setMessage(
        passed
          ? 'Exact anchors are WITHIN the declared geometric mating tolerances.'
          : 'Exact anchors are OUTSIDE the declared geometric mating tolerances.',
      );
    } catch (error: unknown) {
      setState('error');
      setMessage(error instanceof Error ? error.message : String(error));
      setReport(null);
    }
  }

  function updateAxis(index: number, value: string) {
    setAxis((current) => current.map((row, rowIndex) => rowIndex === index ? value : row));
  }

  const geometricPassed = report?.geometric_mating_passed;

  return (
    <div className="mt-2 rounded-lg border border-emerald-300/10 bg-emerald-300/[0.025] p-2" data-testid="brep-anchor-mating-control">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-1.5 text-[8px] font-semibold uppercase tracking-[0.12em] text-emerald-200/80">
          <GitCompareArrows className="h-3 w-3" /> Exact anchor mating geometry
        </div>
        <span className="text-[7px] uppercase tracking-[0.1em] text-slate-600">pairwise · declared tolerances</span>
      </div>
      {pairs.length > 1 ? (
        <label className="mt-2 block text-[7px] uppercase tracking-[0.08em] text-slate-600">
          Exact anchor pair
          <select
            aria-label="Exact BREP mating anchor pair"
            value={pair.key}
            onChange={(event) => setPairKey(event.target.value)}
            className="mt-1 w-full rounded border border-white/8 bg-black/20 px-1.5 py-1.5 text-[8px] normal-case tracking-normal text-slate-200"
          >
            {pairs.map((row) => <option key={row.key} value={row.key}>{row.first.interfaceId} · {row.first.entityId} ↔ {row.second.entityId}</option>)}
          </select>
        </label>
      ) : (
        <div className="mt-1 text-[8px] text-slate-500">{pair.first.interfaceId} · {pair.first.entityId} ↔ {pair.second.entityId}</div>
      )}
      <div className="mt-2 grid grid-cols-2 gap-1.5">
        <label className="text-[7px] uppercase tracking-[0.08em] text-slate-600">Normal error ≤ °<input aria-label="Maximum normal opposition error degrees" value={normalTolerance} onChange={(event) => setNormalTolerance(event.target.value)} className="mt-1 w-full rounded border border-white/8 bg-black/20 px-1.5 py-1 text-[9px] text-slate-200" /></label>
        <label className="text-[7px] uppercase tracking-[0.08em] text-slate-600">Lateral ≤ mm<input aria-label="Maximum mating lateral offset mm" value={lateralTolerance} onChange={(event) => setLateralTolerance(event.target.value)} className="mt-1 w-full rounded border border-white/8 bg-black/20 px-1.5 py-1 text-[9px] text-slate-200" /></label>
        <label className="text-[7px] uppercase tracking-[0.08em] text-slate-600">Target axial mm<input aria-label="Target mating axial offset mm" value={targetAxialOffset} onChange={(event) => setTargetAxialOffset(event.target.value)} className="mt-1 w-full rounded border border-white/8 bg-black/20 px-1.5 py-1 text-[9px] text-slate-200" /></label>
        <label className="text-[7px] uppercase tracking-[0.08em] text-slate-600">Axial ± mm<input aria-label="Mating axial offset tolerance mm" value={axialTolerance} onChange={(event) => setAxialTolerance(event.target.value)} className="mt-1 w-full rounded border border-white/8 bg-black/20 px-1.5 py-1 text-[9px] text-slate-200" /></label>
      </div>
      <div className="mt-2 text-[7px] uppercase tracking-[0.08em] text-slate-600">Declared mating axis · optional for coaxiality</div>
      <div className="mt-1 grid grid-cols-4 gap-1">
        {['X', 'Y', 'Z'].map((label, index) => <input key={label} aria-label={`Declared mating axis ${label}`} placeholder={label} value={axis[index]} onChange={(event) => updateAxis(index, event.target.value)} className="rounded border border-white/8 bg-black/20 px-1 py-1 text-[8px] text-slate-200" />)}
        <input aria-label="Maximum mating axis alignment error degrees" value={axisTolerance} onChange={(event) => setAxisTolerance(event.target.value)} title="Axis alignment tolerance degrees" className="rounded border border-white/8 bg-black/20 px-1 py-1 text-[8px] text-slate-200" />
      </div>
      <div className="mt-2 grid grid-cols-2 gap-1.5">
        <label className="text-[7px] uppercase tracking-[0.08em] text-slate-600">Required engagement mm<input aria-label="Required mating engagement depth mm" placeholder="optional" value={requiredEngagement} onChange={(event) => setRequiredEngagement(event.target.value)} className="mt-1 w-full rounded border border-white/8 bg-black/20 px-1.5 py-1 text-[9px] text-slate-200" /></label>
        <label className="text-[7px] uppercase tracking-[0.08em] text-slate-600">Declared engagement mm<input aria-label="Declared mating engagement depth mm" placeholder="not inferred" value={declaredEngagement} onChange={(event) => setDeclaredEngagement(event.target.value)} className="mt-1 w-full rounded border border-white/8 bg-black/20 px-1.5 py-1 text-[9px] text-slate-200" /></label>
      </div>
      <button
        type="button"
        onClick={evaluateMating}
        disabled={state === 'loading'}
        className="mt-2 inline-flex items-center gap-1.5 rounded-md border border-emerald-300/15 bg-emerald-300/[0.05] px-2 py-1.5 text-[8px] font-semibold uppercase tracking-[0.08em] text-emerald-200 hover:bg-emerald-300/[0.09] disabled:opacity-50"
      >
        {state === 'loading' ? <Loader2 className="h-3 w-3 animate-spin" /> : geometricPassed === true ? <CheckCircle2 className="h-3 w-3" /> : <GitCompareArrows className="h-3 w-3" />}
        Evaluate anchor mating
      </button>
      {message ? (
        <div data-testid="brep-anchor-mating-feedback" data-mating-status={state} className={`mt-1.5 text-[8px] leading-4 ${state === 'success' && geometricPassed === true ? 'text-emerald-300/80' : state === 'error' ? 'text-red-300/80' : 'text-amber-300/80'}`}>{message}</div>
      ) : null}
      {report ? (
        <div data-testid="brep-anchor-mating-result" data-geometric-pass={String(report.geometric_mating_passed)} className="mt-1.5 grid grid-cols-2 gap-x-2 gap-y-1 text-[7px] leading-3 text-slate-500">
          <span>Separation</span><span className="text-right text-slate-300">{format(report.anchor_separation_mm)} mm</span>
          <span>Normal opposition error</span><span className="text-right text-slate-300">{format(report.normal_opposition_error_deg)}°</span>
          <span>Axial offset / error</span><span className="text-right text-slate-300">{format(report.signed_axial_offset_mm)} / {format(report.axial_offset_error_mm)} mm</span>
          <span>Lateral offset</span><span className="text-right text-slate-300">{format(report.lateral_offset_mm)} mm</span>
          <span>Coaxiality</span><span className="text-right text-slate-300">{report.coaxiality_evaluated === true ? `${format(report.coaxial_offset_mm)} mm` : 'not evaluated · declare axis'}</span>
          <span>Engagement</span><span className="text-right text-slate-300">{report.engagement_evaluated === true ? `${format(report.declared_engagement_depth_mm)} / ${format(report.required_engagement_depth_mm)} mm` : 'not kernel-inferred'}</span>
        </div>
      ) : null}
      {state === 'success' && geometricPassed === false ? <div className="mt-1 text-[7px] text-amber-300/60"><TriangleAlert className="mr-1 inline h-2.5 w-2.5" />One or more declared geometric tolerances failed.</div> : null}
      <div className="mt-1 text-[7px] leading-3 text-emerald-100/45">A pass means only that these two exact BREP surface anchors satisfy the declared geometry tolerances. Protocol, pins, retention, swept insertion collision, physical fit and connector mating remain unverified.</div>
    </div>
  );
}

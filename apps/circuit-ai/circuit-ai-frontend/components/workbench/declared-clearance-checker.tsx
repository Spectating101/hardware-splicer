'use client';

import { useEffect, useMemo, useState } from 'react';
import { AlertTriangle, Box, CheckCircle2, Loader2, Ruler } from 'lucide-react';
import { constructorResourceMap } from '@/lib/workbench-constructor-demo';
import { deck001EntityMap } from '@/lib/workbench-demo';
import { useMachineWorkbenchStore } from '@/lib/machine-workbench-store';
import { useWorkbenchPlacementStore, type DeclaredPlacementEvidence } from '@/lib/workbench-placement-store';
import { getSessionStepSource } from '@/lib/workbench-session-step-sources';

const EMPTY_PLACEMENTS: Record<string, DeclaredPlacementEvidence> = {};
const EMPTY_REPORTS: Record<string, Record<string, unknown>> = {};

function record(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {};
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

export function DeclaredClearanceChecker() {
  const activeCandidateId = useMachineWorkbenchStore((state) => state.activeCandidateId);
  const setActiveLens = useMachineWorkbenchStore((state) => state.setActiveLens);
  const setActiveBottomTab = useMachineWorkbenchStore((state) => state.setActiveBottomTab);
  const setSelectedEntityId = useMachineWorkbenchStore((state) => state.setSelectedEntityId);
  const candidatePlacements = useWorkbenchPlacementStore((state) => state.placementsByCandidate[activeCandidateId]);
  const candidateReports = useWorkbenchPlacementStore((state) => state.geometryReportsByCandidate[activeCandidateId]);
  const placementsMap = candidatePlacements ?? EMPTY_PLACEMENTS;
  const reportsMap = candidateReports ?? EMPTY_REPORTS;
  const placements = useMemo(() => Object.values(placementsMap), [placementsMap]);
  const [firstId, setFirstId] = useState('');
  const [secondId, setSecondId] = useState('');
  const [minimumClearance, setMinimumClearance] = useState('2');
  const [state, setState] = useState<'idle' | 'loading' | 'pass' | 'fail' | 'unknown' | 'error'>('idle');
  const [message, setMessage] = useState('');
  const [exactState, setExactState] = useState<'idle' | 'loading' | 'pass' | 'fail' | 'unknown' | 'error'>('idle');
  const [exactMessage, setExactMessage] = useState('');

  useEffect(() => {
    if (placements.length < 2) return;
    if (!placements.some((row) => row.entityId === firstId)) setFirstId(placements[0].entityId);
    if (!placements.some((row) => row.entityId === secondId) || firstId === secondId) {
      setSecondId(placements.find((row) => row.entityId !== (firstId || placements[0].entityId))?.entityId ?? placements[1].entityId);
    }
  }, [firstId, placements, secondId]);

  useEffect(() => {
    setState('idle');
    setMessage('');
    setExactState('idle');
    setExactMessage('');
  }, [activeCandidateId, firstId, minimumClearance, placementsMap, secondId]);

  if (placements.length < 2) return null;

  const firstPlacement = placementsMap[firstId];
  const secondPlacement = placementsMap[secondId];
  const firstSessionSource = firstPlacement ? getSessionStepSource(activeCandidateId, firstPlacement.resourceId) : null;
  const secondSessionSource = secondPlacement ? getSessionStepSource(activeCandidateId, secondPlacement.resourceId) : null;
  const exactSourcesReady = Boolean(
    firstPlacement
    && secondPlacement
    && firstSessionSource
    && secondSessionSource
    && firstSessionSource.modelId === firstPlacement.modelId
    && secondSessionSource.modelId === secondPlacement.modelId,
  );

  function nameFor(entityId: string) {
    const placement = placementsMap[entityId];
    return constructorResourceMap.get(placement?.resourceId ?? '')?.name
      ?? deck001EntityMap.get(entityId)?.name
      ?? entityId;
  }

  function focusConstraint(entityId: string) {
    setActiveLens('constraints');
    setActiveBottomTab('constraints');
    setSelectedEntityId(entityId);
  }

  function parsedRequirement() {
    const required = Number(minimumClearance);
    return Number.isFinite(required) && required >= 0 ? required : null;
  }

  async function checkClearance() {
    const first = placementsMap[firstId];
    const second = placementsMap[secondId];
    const required = parsedRequirement();
    if (!first || !second || first.entityId === second.entityId) {
      setState('error');
      setMessage('Select two different placed resources.');
      return;
    }
    if (required === null) {
      setState('error');
      setMessage('Minimum clearance must be a non-negative number.');
      return;
    }

    const modelMap = new Map<string, Record<string, unknown>>();
    for (const placement of placements) {
      const report = record(reportsMap[placement.resourceId]);
      const models = Array.isArray(report.models) ? report.models : [];
      for (const model of models) {
        const item = record(model);
        if (typeof item.model_id === 'string') modelMap.set(item.model_id, item);
      }
    }
    if (!modelMap.has(first.modelId) || !modelMap.has(second.modelId)) {
      setState('error');
      setMessage('Parsed STEP provenance is missing for one placed resource; re-attach its source.');
      return;
    }

    const geometry = {
      schema_version: 'hardware_splicer.mechanical_geometry_report.v1',
      project_id: 'deck-001',
      models: [...modelMap.values()],
      mounts: [],
      checks: [],
      status: 'candidate',
      required_evidence: [],
      metadata: { composed_for: 'declared_aabb_clearance' },
    };
    const boxes = [first, second].map((placement) => ({
      object_id: placement.entityId,
      frame_id: placement.frameId,
      minimum_mm: placement.minimumMm,
      maximum_mm: placement.maximumMm,
      source_model_id: placement.modelId,
      state: 'declared_placement',
      metadata: {
        placement_id: placement.placementId,
        placement_authority: 'declared',
        aabb_only: true,
        full_brep_collision: false,
      },
    }));

    setState('loading');
    setMessage('Running bounded AABB clearance check…');
    try {
      const response = await fetch('/api/proxy/engineering/mechanical/fit/check', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({
          geometry,
          clearance_boxes: boxes,
          clearance_requirements: [{
            requirement_id: `clearance-${first.entityId}-${second.entityId}`,
            first_object_id: first.entityId,
            second_object_id: second.entityId,
            minimum_clearance_mm: required,
            applicable_states: ['declared_placement'],
          }],
          fastener_stacks: [],
          normal_tolerance_deg: 5,
        }),
        cache: 'no-store',
      });
      const payload = record(await response.json());
      if (!response.ok || payload.ok !== true) throw new Error(String(payload.error || `mechanical fit HTTP ${response.status}`));
      const fit = record(payload.mechanical_fit);
      const checks = Array.isArray(fit.checks) ? fit.checks.map(record) : [];
      const clearance = checks.find((row) => row.category === 'aabb_clearance');
      if (!clearance) throw new Error('HS fit response did not include the requested AABB clearance check.');
      const checkStatus = String(clearance.status || 'unknown');
      setState(checkStatus === 'pass' ? 'pass' : checkStatus === 'fail' ? 'fail' : 'unknown');
      setMessage(String(clearance.message || 'No fit message returned.'));
      if (checkStatus !== 'pass') focusConstraint(first.entityId);
    } catch (error: unknown) {
      setState('error');
      setMessage(error instanceof Error ? error.message : String(error));
    }
  }

  async function checkExactBrepClearance() {
    const first = placementsMap[firstId];
    const second = placementsMap[secondId];
    const required = parsedRequirement();
    if (!first || !second || first.entityId === second.entityId) {
      setExactState('error');
      setExactMessage('Select two different placed resources.');
      return;
    }
    if (required === null) {
      setExactState('error');
      setExactMessage('Minimum clearance must be a non-negative number.');
      return;
    }
    const firstSource = getSessionStepSource(activeCandidateId, first.resourceId);
    const secondSource = getSessionStepSource(activeCandidateId, second.resourceId);
    if (!firstSource || !secondSource) {
      setExactState('unknown');
      setExactMessage('Exact BREP is unavailable for this session pair; re-attach both original STEP sources or use canonical registered project sources.');
      return;
    }
    if (firstSource.modelId !== first.modelId || secondSource.modelId !== second.modelId) {
      setExactState('error');
      setExactMessage('Session STEP identity no longer matches the declared placement; re-attach and replace the source before exact checking.');
      return;
    }

    setExactState('loading');
    setExactMessage('Running isolated CadQuery/OCCT pair clearance…');
    try {
      const response = await fetch('/api/proxy/engineering/mechanical/geometry/brep/interference', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({
          project_id: 'deck-001',
          first_source: {
            source_id: firstSource.sourceId,
            model_id: firstSource.modelId,
            content: firstSource.content,
          },
          second_source: {
            source_id: secondSource.sourceId,
            model_id: secondSource.modelId,
            content: secondSource.content,
          },
          first_placement: placementPayload(first),
          second_placement: placementPayload(second),
          minimum_clearance_mm: required,
        }),
        cache: 'no-store',
      });
      const payload = record(await response.json());
      if (!response.ok || payload.ok !== true) throw new Error(String(payload.error || `exact BREP HTTP ${response.status}`));
      if (payload.aabb_fallback_used !== false) throw new Error('HS exact BREP response did not preserve the no-AABB-fallback contract.');

      if (payload.exact_pair_interference_evaluated !== true || payload.exact_minimum_clearance_evaluated !== true) {
        const report = record(payload.brep_interference);
        const requiredEvidence = Array.isArray(report.required_evidence) ? report.required_evidence.map(record) : [];
        const reason = String(requiredEvidence[0]?.reason || payload.minimum_clearance_message || 'Pairwise exact kernel evidence is unavailable.');
        setExactState('unknown');
        setExactMessage(`Exact BREP UNKNOWN · ${reason}`);
        focusConstraint(first.entityId);
        return;
      }

      const interference = payload.exact_solid_interference === true;
      const passed = payload.minimum_clearance_passed === true;
      const distance = Number(payload.minimum_distance_mm);
      const volume = Number(payload.intersection_volume_mm3);
      if (!Number.isFinite(distance) || !Number.isFinite(volume)) throw new Error('HS exact BREP response omitted finite distance/intersection evidence.');
      const resultMessage = String(payload.minimum_clearance_message || 'Exact BREP minimum-clearance result returned.');
      const detail = interference
        ? `PAIR SOLID INTERFERENCE · ${volume.toFixed(3)} mm³ intersection.`
        : `NO SOLID OVERLAP · ${distance.toFixed(3)} mm minimum BREP distance.`;
      setExactState(passed ? 'pass' : 'fail');
      setExactMessage(`${resultMessage} ${detail}`);
      if (!passed) focusConstraint(first.entityId);
    } catch (error: unknown) {
      setExactState('error');
      setExactMessage(error instanceof Error ? error.message : String(error));
    }
  }

  return (
    <div className="mb-3 rounded-lg border border-amber-300/12 bg-amber-300/[0.025] p-2.5" data-testid="declared-clearance-checker">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-1.5 text-[8px] font-semibold uppercase tracking-[0.12em] text-amber-200/80"><Ruler className="h-3 w-3" /> Placed-envelope clearance</div>
        <span className="text-[7px] uppercase tracking-[0.1em] text-slate-600">same-frame AABB only</span>
      </div>
      <div className="mt-2 grid grid-cols-2 gap-1.5">
        <label className="text-[7px] uppercase tracking-[0.08em] text-slate-600">First
          <select aria-label="First placed resource for clearance" value={firstId} onChange={(event) => setFirstId(event.target.value)} className="mt-1 w-full rounded border border-white/8 bg-[#08111e] px-1.5 py-1 text-[9px] normal-case tracking-normal text-slate-300 outline-none">
            {placements.map((row) => <option key={row.entityId} value={row.entityId}>{nameFor(row.entityId)}</option>)}
          </select>
        </label>
        <label className="text-[7px] uppercase tracking-[0.08em] text-slate-600">Second
          <select aria-label="Second placed resource for clearance" value={secondId} onChange={(event) => setSecondId(event.target.value)} className="mt-1 w-full rounded border border-white/8 bg-[#08111e] px-1.5 py-1 text-[9px] normal-case tracking-normal text-slate-300 outline-none">
            {placements.map((row) => <option key={row.entityId} value={row.entityId}>{nameFor(row.entityId)}</option>)}
          </select>
        </label>
      </div>
      <div className="mt-2 flex items-end gap-2">
        <label className="min-w-0 flex-1 text-[7px] uppercase tracking-[0.08em] text-slate-600">Minimum clearance mm
          <input aria-label="Minimum declared clearance mm" value={minimumClearance} onChange={(event) => setMinimumClearance(event.target.value)} inputMode="decimal" className="mt-1 w-full rounded border border-white/8 bg-black/20 px-1.5 py-1 text-[9px] normal-case tracking-normal text-slate-200 outline-none" />
        </label>
        <button type="button" onClick={checkClearance} disabled={state === 'loading'} className="inline-flex items-center gap-1.5 rounded-md border border-amber-300/15 bg-amber-300/[0.04] px-2 py-1.5 text-[8px] font-semibold uppercase tracking-[0.08em] text-amber-200 hover:bg-amber-300/[0.08] disabled:opacity-50">
          {state === 'loading' ? <Loader2 className="h-3 w-3 animate-spin" /> : state === 'pass' ? <CheckCircle2 className="h-3 w-3" /> : <AlertTriangle className="h-3 w-3" />} Check AABB clearance
        </button>
      </div>
      {message ? <div className={`mt-2 text-[8px] leading-4 ${state === 'pass' ? 'text-emerald-300/80' : state === 'fail' ? 'text-red-300/80' : state === 'unknown' ? 'text-amber-300/75' : state === 'error' ? 'text-red-300/75' : 'text-slate-500'}`}>{message}</div> : null}
      <div className="mt-1 text-[7px] leading-3 text-amber-100/45">A pass applies only to declared axis-aligned envelopes in the common frame. It does not establish BREP collision freedom, deformation margin, service access, or structural safety.</div>

      <div className="mt-3 border-t border-white/8 pt-2.5" data-testid="exact-brep-clearance-checker">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-1.5 text-[8px] font-semibold uppercase tracking-[0.12em] text-cyan-200/80"><Box className="h-3 w-3" /> Exact STEP solid pair</div>
          <span className="text-[7px] uppercase tracking-[0.1em] text-slate-600">CadQuery/OCCT · no AABB fallback</span>
        </div>
        <div className="mt-1.5 text-[7px] leading-3 text-slate-500">
          {exactSourcesReady
            ? 'Both canonical STEP uploads are available in this browser session for an isolated exact pair check.'
            : 'Exact pair evidence needs both original STEP uploads in this browser session. Canonical persisted projects use registered hash-reverified sources server-side.'}
        </div>
        <button
          type="button"
          onClick={checkExactBrepClearance}
          disabled={exactState === 'loading' || !exactSourcesReady}
          className="mt-2 inline-flex items-center gap-1.5 rounded-md border border-cyan-300/15 bg-cyan-300/[0.04] px-2 py-1.5 text-[8px] font-semibold uppercase tracking-[0.08em] text-cyan-200 hover:bg-cyan-300/[0.08] disabled:cursor-not-allowed disabled:opacity-40"
        >
          {exactState === 'loading' ? <Loader2 className="h-3 w-3 animate-spin" /> : exactState === 'pass' ? <CheckCircle2 className="h-3 w-3" /> : <Box className="h-3 w-3" />}
          Check exact BREP clearance
        </button>
        {exactMessage ? <div className={`mt-2 text-[8px] leading-4 ${exactState === 'pass' ? 'text-emerald-300/80' : exactState === 'fail' ? 'text-red-300/80' : exactState === 'unknown' ? 'text-amber-300/75' : exactState === 'error' ? 'text-red-300/75' : 'text-slate-500'}`}>{exactMessage}</div> : null}
        <div className="mt-1 text-[7px] leading-3 text-cyan-100/45">Exact means this placed STEP solid pair only. It does not establish full-assembly collision freedom, connector mating, cable routing, service ergonomics, structural safety, measurement truth, or fabrication authority.</div>
      </div>
    </div>
  );
}
'use client';

import { useEffect, useMemo, useState } from 'react';
import { AlertTriangle, CheckCircle2, Loader2, Ruler } from 'lucide-react';
import { constructorResourceMap } from '@/lib/workbench-constructor-demo';
import { deck001EntityMap } from '@/lib/workbench-demo';
import { useMachineWorkbenchStore } from '@/lib/machine-workbench-store';
import { useWorkbenchPlacementStore } from '@/lib/workbench-placement-store';

function record(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {};
}

export function DeclaredClearanceChecker() {
  const activeCandidateId = useMachineWorkbenchStore((state) => state.activeCandidateId);
  const setActiveLens = useMachineWorkbenchStore((state) => state.setActiveLens);
  const setActiveBottomTab = useMachineWorkbenchStore((state) => state.setActiveBottomTab);
  const setSelectedEntityId = useMachineWorkbenchStore((state) => state.setSelectedEntityId);
  const placementsMap = useWorkbenchPlacementStore((state) => state.placementsByCandidate[activeCandidateId] ?? {});
  const reportsMap = useWorkbenchPlacementStore((state) => state.geometryReportsByCandidate[activeCandidateId] ?? {});
  const placements = useMemo(() => Object.values(placementsMap), [placementsMap]);
  const [firstId, setFirstId] = useState('');
  const [secondId, setSecondId] = useState('');
  const [minimumClearance, setMinimumClearance] = useState('2');
  const [state, setState] = useState<'idle' | 'loading' | 'pass' | 'fail' | 'unknown' | 'error'>('idle');
  const [message, setMessage] = useState('');

  useEffect(() => {
    if (placements.length < 2) return;
    if (!placements.some((row) => row.entityId === firstId)) setFirstId(placements[0].entityId);
    if (!placements.some((row) => row.entityId === secondId) || firstId === secondId) {
      setSecondId(placements.find((row) => row.entityId !== (firstId || placements[0].entityId))?.entityId ?? placements[1].entityId);
    }
  }, [firstId, placements, secondId]);

  if (placements.length < 2) return null;

  function nameFor(entityId: string) {
    const placement = placementsMap[entityId];
    return constructorResourceMap.get(placement?.resourceId ?? '')?.name
      ?? deck001EntityMap.get(entityId)?.name
      ?? entityId;
  }

  async function checkClearance() {
    const first = placementsMap[firstId];
    const second = placementsMap[secondId];
    const required = Number(minimumClearance);
    if (!first || !second || first.entityId === second.entityId) {
      setState('error');
      setMessage('Select two different placed resources.');
      return;
    }
    if (!Number.isFinite(required) || required < 0) {
      setState('error');
      setMessage('Minimum clearance must be a non-negative number.');
      return;
    }

    const modelMap = new Map();
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
      const status = String(clearance.status || 'unknown');
      setState(status === 'pass' ? 'pass' : status === 'fail' ? 'fail' : 'unknown');
      setMessage(String(clearance.message || 'No fit message returned.'));
      if (status !== 'pass') {
        setActiveLens('constraints');
        setActiveBottomTab('constraints');
        setSelectedEntityId(first.entityId);
      }
    } catch (error: unknown) {
      setState('error');
      setMessage(error instanceof Error ? error.message : String(error));
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
    </div>
  );
}

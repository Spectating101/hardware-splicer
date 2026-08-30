'use client';

import { useEffect, useMemo, useState } from 'react';
import { Cable, CheckCircle2, Loader2, ShieldAlert, Trash2 } from 'lucide-react';
import { deck001EntityMap, deck001Interfaces } from '@/lib/workbench-demo';
import type { ConstructorCandidateId } from '@/lib/machine-workbench-store';
import { useMachineWorkbenchStore } from '@/lib/machine-workbench-store';
import { useWorkbenchAccessStore, type DeclaredAccessEvidence } from '@/lib/workbench-access-store';
import { useWorkbenchPlacementStore, type DeclaredPlacementEvidence } from '@/lib/workbench-placement-store';

const FACES: DeclaredAccessEvidence['face'][] = ['+x', '-x', '+y', '-y', '+z', '-z'];

function record(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {};
}

function tuple3(value: unknown): [number, number, number] | null {
  if (!Array.isArray(value) || value.length !== 3) return null;
  const rows = value.map(Number);
  return rows.every(Number.isFinite) ? rows as [number, number, number] : null;
}

function finite(value: string): number | null {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

export function DeclaredInterfaceAccessEditor({
  candidateId,
  resourceId,
  resourceName,
  entityId,
  placement,
}: {
  candidateId: ConstructorCandidateId;
  resourceId: string;
  resourceName: string;
  entityId: string;
  placement: DeclaredPlacementEvidence;
}) {
  const interfaces = useMemo(
    () => deck001Interfaces.filter((row) => row.from === entityId || row.to === entityId),
    [entityId],
  );
  const placementsMap = useWorkbenchPlacementStore((state) => state.placementsByCandidate[candidateId] ?? {});
  const otherPlacements = useMemo(
    () => Object.values(placementsMap).filter((row) => row.entityId !== entityId),
    [entityId, placementsMap],
  );
  const accessMap = useWorkbenchAccessStore((state) => state.accessByCandidate[candidateId] ?? {});
  const setAccess = useWorkbenchAccessStore((state) => state.setAccess);
  const clearAccess = useWorkbenchAccessStore((state) => state.clearAccess);
  const setActiveLens = useMachineWorkbenchStore((state) => state.setActiveLens);
  const setActiveBottomTab = useMachineWorkbenchStore((state) => state.setActiveBottomTab);
  const setSelectedEntityId = useMachineWorkbenchStore((state) => state.setSelectedEntityId);

  const [interfaceId, setInterfaceId] = useState(interfaces[0]?.id ?? '');
  const [face, setFace] = useState<DeclaredAccessEvidence['face']>('+x');
  const [width, setWidth] = useState('20');
  const [height, setHeight] = useState('10');
  const [depth, setDepth] = useState('30');
  const [offsetU, setOffsetU] = useState('0');
  const [offsetV, setOffsetV] = useState('0');
  const [obstacleId, setObstacleId] = useState(otherPlacements[0]?.entityId ?? '');
  const [minimumClearance, setMinimumClearance] = useState('0');
  const [state, setState] = useState<'idle' | 'loading' | 'success' | 'error'>('idle');
  const [message, setMessage] = useState('');
  const [checkState, setCheckState] = useState<'idle' | 'loading' | 'pass' | 'fail' | 'unknown' | 'error'>('idle');
  const [checkMessage, setCheckMessage] = useState('');

  const accessId = interfaceId ? `access-${candidateId}-${resourceId}-${interfaceId}` : '';
  const existing = accessId ? accessMap[accessId] : undefined;

  useEffect(() => {
    setInterfaceId(interfaces[0]?.id ?? '');
    setFace('+x');
    setWidth('20');
    setHeight('10');
    setDepth('30');
    setOffsetU('0');
    setOffsetV('0');
    setState('idle');
    setMessage('');
    setCheckState('idle');
    setCheckMessage('');
  }, [candidateId, entityId, resourceId, interfaces]);

  useEffect(() => {
    if (!otherPlacements.some((row) => row.entityId === obstacleId)) {
      setObstacleId(otherPlacements[0]?.entityId ?? '');
    }
  }, [obstacleId, otherPlacements]);

  if (!interfaces.length) return null;

  async function buildAccessEnvelope() {
    const widthMm = finite(width);
    const heightMm = finite(height);
    const depthMm = finite(depth);
    const offsetUMm = finite(offsetU);
    const offsetVMm = finite(offsetV);
    if (
      widthMm === null || heightMm === null || depthMm === null ||
      offsetUMm === null || offsetVMm === null ||
      widthMm <= 0 || heightMm <= 0 || depthMm <= 0
    ) {
      setState('error');
      setMessage('Access width, height and depth must be positive finite numbers; offsets must be finite.');
      return;
    }

    setState('loading');
    setMessage('Building declared interface access envelope…');
    setCheckState('idle');
    setCheckMessage('');
    try {
      const response = await fetch('/api/proxy/engineering/mechanical/interfaces/access-envelope', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({
          object_box: {
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
          },
          access: {
            access_id: accessId,
            interface_id: interfaceId,
            object_id: entityId,
            frame_id: placement.frameId,
            face,
            width_mm: widthMm,
            height_mm: heightMm,
            depth_mm: depthMm,
            offset_u_mm: offsetUMm,
            offset_v_mm: offsetVMm,
            authority: 'declared',
          },
        }),
        cache: 'no-store',
      });
      const payload = record(await response.json());
      if (!response.ok || payload.ok !== true) throw new Error(String(payload.error || `interface access HTTP ${response.status}`));
      const box = record(payload.access_box);
      const metadata = record(box.metadata);
      const minimumMm = tuple3(box.minimum_mm);
      const maximumMm = tuple3(box.maximum_mm);
      const anchorPointMm = tuple3(metadata.anchor_point_mm);
      const outwardNormal = tuple3(metadata.outward_normal);
      if (!minimumMm || !maximumMm || !anchorPointMm || !outwardNormal) throw new Error('HS access response is missing bounded anchor/envelope geometry.');

      const evidence: DeclaredAccessEvidence = {
        accessId,
        interfaceId,
        entityId,
        resourceId,
        frameId: String(box.frame_id || placement.frameId),
        face,
        widthMm,
        heightMm,
        depthMm,
        offsetUMm,
        offsetVMm,
        minimumMm,
        maximumMm,
        anchorPointMm,
        outwardNormal,
        authority: 'declared',
        aabbOnly: true,
        connectorMatingVerified: false,
        cableRoutingVerified: false,
        serviceAccessVerified: false,
        fullBrepCollision: false,
        fabricationAuthorized: false,
      };
      setAccess(candidateId, evidence);
      setState('success');
      setMessage(`${interfaces.find((row) => row.id === interfaceId)?.name ?? interfaceId} · ${face} · ${widthMm} × ${heightMm} × ${depthMm} mm access AABB · DECLARED.`);
    } catch (error: unknown) {
      setState('error');
      setMessage(error instanceof Error ? error.message : String(error));
    }
  }

  async function checkAccessClearance() {
    if (!existing) {
      setCheckState('error');
      setCheckMessage('Build the access envelope before checking its clearance.');
      return;
    }
    const obstacle = placementsMap[obstacleId];
    const required = finite(minimumClearance);
    if (!obstacle) {
      setCheckState('error');
      setCheckMessage('Select another explicitly placed resource as the obstacle.');
      return;
    }
    if (required === null || required < 0) {
      setCheckState('error');
      setCheckMessage('Minimum clearance must be a non-negative finite number.');
      return;
    }

    setCheckState('loading');
    setCheckMessage('Checking access envelope against placed obstacle…');
    try {
      const response = await fetch('/api/proxy/engineering/mechanical/fit/check', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({
          geometry: {
            schema_version: 'hardware_splicer.mechanical_geometry_report.v1',
            project_id: 'deck-001',
            models: [],
            mounts: [],
            checks: [],
            status: 'candidate',
            required_evidence: [],
            metadata: { composed_for: 'declared_interface_access_clearance' },
          },
          clearance_boxes: [
            {
              object_id: `access:${existing.accessId}`,
              frame_id: existing.frameId,
              minimum_mm: existing.minimumMm,
              maximum_mm: existing.maximumMm,
              source_model_id: placement.modelId,
              state: 'declared_access_envelope',
              metadata: { interface_id: existing.interfaceId, aabb_only: true, full_brep_collision: false },
            },
            {
              object_id: obstacle.entityId,
              frame_id: obstacle.frameId,
              minimum_mm: obstacle.minimumMm,
              maximum_mm: obstacle.maximumMm,
              source_model_id: obstacle.modelId,
              state: 'declared_placement',
              metadata: { placement_id: obstacle.placementId, aabb_only: true, full_brep_collision: false },
            },
          ],
          clearance_requirements: [{
            requirement_id: `access-clear-${existing.accessId}-${obstacle.entityId}`,
            first_object_id: `access:${existing.accessId}`,
            second_object_id: obstacle.entityId,
            minimum_clearance_mm: required,
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
      if (!clearance) throw new Error('HS fit response did not include access-envelope clearance.');
      const status = String(clearance.status || 'unknown');
      setCheckState(status === 'pass' ? 'pass' : status === 'fail' ? 'fail' : 'unknown');
      setCheckMessage(String(clearance.message || 'No access-clearance message returned.'));
      if (status !== 'pass') {
        setActiveLens('constraints');
        setActiveBottomTab('constraints');
        setSelectedEntityId(entityId);
      }
    } catch (error: unknown) {
      setCheckState('error');
      setCheckMessage(error instanceof Error ? error.message : String(error));
    }
  }

  function removeAccess() {
    if (accessId) clearAccess(candidateId, accessId);
    setState('idle');
    setMessage('Declared interface access envelope cleared.');
    setCheckState('idle');
    setCheckMessage('');
  }

  return (
    <div className="mt-2 rounded-lg border border-orange-300/10 bg-orange-300/[0.025] p-2" data-testid="declared-interface-access-editor">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-1.5 text-[9px] font-semibold uppercase tracking-[0.12em] text-orange-200/80"><Cable className="h-3 w-3" /> Interface access envelope</div>
        <span className="text-[8px] uppercase tracking-[0.1em] text-slate-600">placed parent · AABB only</span>
      </div>
      <div className="mt-2 grid grid-cols-[1fr_64px] gap-1.5">
        <label className="text-[8px] uppercase tracking-[0.08em] text-slate-600">Interface
          <select aria-label={`Interface access for ${resourceName}`} value={interfaceId} onChange={(event) => setInterfaceId(event.target.value)} className="mt-1 w-full rounded border border-white/8 bg-[#08111e] px-1.5 py-1 text-[10px] normal-case tracking-normal text-slate-300 outline-none">
            {interfaces.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}
          </select>
        </label>
        <label className="text-[8px] uppercase tracking-[0.08em] text-slate-600">Face
          <select aria-label={`Interface access face for ${resourceName}`} value={face} onChange={(event) => setFace(event.target.value as DeclaredAccessEvidence['face'])} className="mt-1 w-full rounded border border-white/8 bg-[#08111e] px-1.5 py-1 text-[10px] normal-case tracking-normal text-slate-300 outline-none">
            {FACES.map((row) => <option key={row} value={row}>{row}</option>)}
          </select>
        </label>
      </div>
      <div className="mt-2 grid grid-cols-3 gap-1.5">
        <label className="text-[8px] uppercase tracking-[0.08em] text-slate-600">Width mm
          <input aria-label={`Width interface access mm for ${resourceName}`} value={width} onChange={(event) => setWidth(event.target.value)} inputMode="decimal" className="mt-1 w-full rounded border border-white/8 bg-black/20 px-1.5 py-1 text-[10px] normal-case tracking-normal text-slate-200 outline-none" />
        </label>
        <label className="text-[8px] uppercase tracking-[0.08em] text-slate-600">Height mm
          <input aria-label={`Height interface access mm for ${resourceName}`} value={height} onChange={(event) => setHeight(event.target.value)} inputMode="decimal" className="mt-1 w-full rounded border border-white/8 bg-black/20 px-1.5 py-1 text-[10px] normal-case tracking-normal text-slate-200 outline-none" />
        </label>
        <label className="text-[8px] uppercase tracking-[0.08em] text-slate-600">Depth mm
          <input aria-label={`Depth interface access mm for ${resourceName}`} value={depth} onChange={(event) => setDepth(event.target.value)} inputMode="decimal" className="mt-1 w-full rounded border border-white/8 bg-black/20 px-1.5 py-1 text-[10px] normal-case tracking-normal text-slate-200 outline-none" />
        </label>
      </div>
      <div className="mt-2 grid grid-cols-2 gap-1.5">
        <label className="text-[8px] uppercase tracking-[0.08em] text-slate-600">Offset U mm
          <input aria-label={`Interface access offset U mm for ${resourceName}`} value={offsetU} onChange={(event) => setOffsetU(event.target.value)} inputMode="decimal" className="mt-1 w-full rounded border border-white/8 bg-black/20 px-1.5 py-1 text-[10px] normal-case tracking-normal text-slate-200 outline-none" />
        </label>
        <label className="text-[8px] uppercase tracking-[0.08em] text-slate-600">Offset V mm
          <input aria-label={`Interface access offset V mm for ${resourceName}`} value={offsetV} onChange={(event) => setOffsetV(event.target.value)} inputMode="decimal" className="mt-1 w-full rounded border border-white/8 bg-black/20 px-1.5 py-1 text-[10px] normal-case tracking-normal text-slate-200 outline-none" />
        </label>
      </div>
      <div className="mt-2 flex items-center gap-1.5">
        <button type="button" onClick={buildAccessEnvelope} disabled={state === 'loading'} className="inline-flex items-center gap-1.5 rounded-md border border-orange-300/15 bg-orange-300/[0.04] px-2 py-1.5 text-[9px] font-semibold uppercase tracking-[0.08em] text-orange-200 hover:bg-orange-300/[0.08] disabled:opacity-50">
          {state === 'loading' ? <Loader2 className="h-3 w-3 animate-spin" /> : <Cable className="h-3 w-3" />} Build access envelope
        </button>
        {existing ? <button type="button" onClick={removeAccess} aria-label={`Clear interface access for ${resourceName}`} className="rounded-md border border-white/8 p-1.5 text-slate-600 hover:text-red-300"><Trash2 className="h-3 w-3" /></button> : null}
      </div>
      {message ? <div className={`mt-1.5 text-[9px] leading-4 ${state === 'error' ? 'text-red-300/80' : state === 'success' ? 'text-emerald-300/75' : 'text-slate-500'}`}>{message}</div> : null}

      {existing && otherPlacements.length ? (
        <div className="mt-2 border-t border-white/8 pt-2">
          <div className="grid grid-cols-[1fr_82px] gap-1.5">
            <label className="text-[8px] uppercase tracking-[0.08em] text-slate-600">Obstacle
              <select aria-label={`Access obstacle for ${resourceName}`} value={obstacleId} onChange={(event) => setObstacleId(event.target.value)} className="mt-1 w-full rounded border border-white/8 bg-[#08111e] px-1.5 py-1 text-[10px] normal-case tracking-normal text-slate-300 outline-none">
                {otherPlacements.map((row) => <option key={row.entityId} value={row.entityId}>{deck001EntityMap.get(row.entityId)?.name ?? row.entityId}</option>)}
              </select>
            </label>
            <label className="text-[8px] uppercase tracking-[0.08em] text-slate-600">Min clear mm
              <input aria-label={`Interface access minimum clearance mm for ${resourceName}`} value={minimumClearance} onChange={(event) => setMinimumClearance(event.target.value)} inputMode="decimal" className="mt-1 w-full rounded border border-white/8 bg-black/20 px-1.5 py-1 text-[10px] normal-case tracking-normal text-slate-200 outline-none" />
            </label>
          </div>
          <button type="button" onClick={checkAccessClearance} disabled={checkState === 'loading'} className="mt-2 inline-flex items-center gap-1.5 rounded-md border border-amber-300/15 bg-amber-300/[0.04] px-2 py-1.5 text-[9px] font-semibold uppercase tracking-[0.08em] text-amber-200 hover:bg-amber-300/[0.08] disabled:opacity-50">
            {checkState === 'loading' ? <Loader2 className="h-3 w-3 animate-spin" /> : checkState === 'pass' ? <CheckCircle2 className="h-3 w-3" /> : <ShieldAlert className="h-3 w-3" />} Check interface access
          </button>
          {checkMessage ? <div className={`mt-1.5 text-[9px] leading-4 ${checkState === 'pass' ? 'text-emerald-300/80' : checkState === 'fail' ? 'text-red-300/80' : checkState === 'error' ? 'text-red-300/75' : 'text-amber-300/70'}`}>{checkMessage}</div> : null}
        </div>
      ) : null}

      <div className="mt-1.5 text-[8px] leading-4 text-orange-100/45">This is an interface-centered keep-out/access prism, not connector mating, cable routing, service ergonomics, BREP collision truth, or fabrication authority.</div>
    </div>
  );
}

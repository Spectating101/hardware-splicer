'use client';

import { Crosshair, MousePointer2, X } from 'lucide-react';
import { useMemo, useState } from 'react';
import type { ConstructorCandidateId } from '@/lib/machine-workbench-store';
import { deck001Interfaces } from '@/lib/workbench-demo';
import { useWorkbenchBrepAnchorStore } from '@/lib/workbench-brep-anchor-store';

export function BrepSurfaceAnchorControl({
  candidateId,
  entityId,
  resourceId,
  resourceName,
}: {
  candidateId: ConstructorCandidateId;
  entityId: string;
  resourceId: string;
  resourceName: string;
}) {
  const interfaces = useMemo(
    () => deck001Interfaces.filter((row) => row.from === entityId || row.to === entityId),
    [entityId],
  );
  const [interfaceId, setInterfaceId] = useState(() => interfaces[0]?.id ?? '');
  const armedPick = useWorkbenchBrepAnchorStore((state) => state.armedPick);
  const anchors = useWorkbenchBrepAnchorStore((state) => state.anchorsByCandidate[candidateId] ?? {});
  const armPick = useWorkbenchBrepAnchorStore((state) => state.armPick);
  const cancelPick = useWorkbenchBrepAnchorStore((state) => state.cancelPick);

  if (!interfaces.length) return null;

  const selectedInterface = interfaces.find((row) => row.id === interfaceId) ?? interfaces[0];
  const armed = Boolean(
    armedPick
    && armedPick.candidateId === candidateId
    && armedPick.entityId === entityId
    && armedPick.resourceId === resourceId,
  );
  const entityAnchors = Object.values(anchors).filter((anchor) => anchor.entityId === entityId);

  function arm() {
    if (!selectedInterface) return;
    armPick({
      candidateId,
      entityId,
      resourceId,
      interfaceId: selectedInterface.id,
    });
  }

  return (
    <div className="mt-2 rounded-lg border border-fuchsia-300/10 bg-fuchsia-300/[0.025] p-2" data-testid="brep-surface-anchor-control">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-1.5 text-[8px] font-semibold uppercase tracking-[0.12em] text-fuchsia-200/80">
          <Crosshair className="h-3 w-3" /> Exact BREP surface anchor
        </div>
        <span className="text-[7px] uppercase tracking-[0.1em] text-slate-600">OCCT point + normal</span>
      </div>
      <label className="mt-2 block text-[7px] uppercase tracking-[0.08em] text-slate-600">
        Bind picked surface to interface
        <select
          aria-label={`BREP anchor interface for ${resourceName}`}
          value={selectedInterface?.id ?? ''}
          onChange={(event) => setInterfaceId(event.target.value)}
          className="mt-1 w-full rounded border border-white/8 bg-black/20 px-1.5 py-1.5 text-[9px] normal-case tracking-normal text-slate-200 outline-none focus:border-fuchsia-300/25"
        >
          {interfaces.map((row) => (
            <option key={row.id} value={row.id}>{row.name} · {row.kind}</option>
          ))}
        </select>
      </label>
      <div className="mt-2 flex items-center gap-1.5">
        <button
          type="button"
          onClick={armed ? cancelPick : arm}
          className={`inline-flex items-center gap-1.5 rounded-md border px-2 py-1.5 text-[8px] font-semibold uppercase tracking-[0.08em] ${armed ? 'border-amber-300/20 bg-amber-300/[0.06] text-amber-200' : 'border-fuchsia-300/15 bg-fuchsia-300/[0.04] text-fuchsia-200 hover:bg-fuchsia-300/[0.08]'}`}
        >
          {armed ? <X className="h-3 w-3" /> : <MousePointer2 className="h-3 w-3" />}
          {armed ? 'Cancel surface pick' : 'Arm surface pick'}
        </button>
        {entityAnchors.length ? <span className="text-[7px] text-emerald-300/65">{entityAnchors.length} declared anchor{entityAnchors.length === 1 ? '' : 's'}</span> : null}
      </div>
      {armed ? (
        <div className="mt-1.5 text-[8px] leading-4 text-amber-200/75">
          Click this exact BREP mesh in the 3D scene. The click is only a probe; OCCT snaps it to the nearest exact face and returns the surface point + normal.
        </div>
      ) : null}
      <div className="mt-1 text-[7px] leading-3 text-fuchsia-100/45">
        Interface binding is DECLARED geometry evidence only. It does not verify connector mating, fit, serviceability, measurement truth, or fabrication authority.
      </div>
    </div>
  );
}

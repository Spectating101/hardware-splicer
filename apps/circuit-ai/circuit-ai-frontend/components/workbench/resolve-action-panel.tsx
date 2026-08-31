'use client';

import { Camera, FileSearch, PlugZap, Ruler, ShieldAlert, Wrench } from 'lucide-react';
import { constructorCandidateMap, constructorResources } from '@/lib/workbench-constructor-demo';
import type { ConstructorCandidateId } from '@/lib/machine-workbench-store';
import { useWorkbenchDonorIntakeStore } from '@/lib/workbench-donor-intake-store';

type ResolveAction = {
  id: string;
  title: string;
  detail: string;
  evidence: string;
  resourceId: string;
  kind: 'identify' | 'measure' | 'geometry' | 'test';
  priority: number;
};

const RESOURCE_ACTIONS: Record<string, Omit<ResolveAction, 'id' | 'resourceId' | 'priority'>> = {
  'res-mainboard-donor': {
    title: 'Confirm donor mainboard identity and input power',
    detail: 'The compute island is reusable only after the exact board revision and DC input contract are known.',
    evidence: 'Photograph model/revision markings; record input voltage, polarity and bounded current demand.',
    kind: 'identify',
  },
  'res-display-controlled': {
    title: 'Identify the donor display + controller pair',
    detail: 'Keep the panel, controller and cable together instead of inferring a raw-panel interface.',
    evidence: 'Capture panel/controller labels and cable path; confirm supply voltage and video interface.',
    kind: 'identify',
  },
  'res-display-raw': {
    title: 'Characterize the raw donor LCD before reuse',
    detail: 'A free panel is not useful until HS knows its model, link type, supply and backlight requirements.',
    evidence: 'Photograph the panel label; locate a datasheet/manual; confirm connector and power requirements.',
    kind: 'identify',
  },
  'res-keyboard-donor': {
    title: 'Confirm the donor keyboard input path',
    detail: 'Prefer preserving a complete USB HID path before considering deeper matrix rewiring.',
    evidence: 'Confirm USB enumeration and key input; photograph controller/connector markings if the path is unclear.',
    kind: 'test',
  },
  'res-battery-new': {
    title: 'Measure the whole-machine power envelope',
    detail: 'Battery choice remains provisional until startup and steady compute demand are bounded.',
    evidence: 'Record source voltage, current limit, startup current and steady current under a current-limited supply.',
    kind: 'measure',
  },
  'res-pd-module': {
    title: 'Match USB-C PD profiles to measured load',
    detail: 'The PD path cannot close from nominal labels alone when the machine load is still uncertain.',
    evidence: 'Record available PD profiles and compare them with measured startup/steady load and thermal behavior.',
    kind: 'measure',
  },
  'res-cooling-donor': {
    title: 'Confirm donor cooling fit and control',
    detail: 'The original cooling island is valuable if its mechanical fit, connector and fan control remain valid.',
    evidence: 'Measure mounting envelope; identify fan connector/control; verify safe spin-up.',
    kind: 'measure',
  },
  'res-shell-generated': {
    title: 'Attach measured geometry before fabrication',
    detail: 'The chassis should absorb real donor geometry rather than force components into an assumed envelope.',
    evidence: 'Attach STEP geometry where available, otherwise capture critical dimensions and mounting locations.',
    kind: 'geometry',
  },
};

function iconFor(kind: ResolveAction['kind']) {
  if (kind === 'identify') return FileSearch;
  if (kind === 'measure') return Ruler;
  if (kind === 'geometry') return Wrench;
  return PlugZap;
}

function authorityPriority(authority: string) {
  if (authority === 'blocked') return 0;
  if (authority === 'partial') return 1;
  if (authority === 'proposed') return 2;
  return 3;
}

export function ResolveActionPanel({
  candidateId,
  onOpenResource,
}: {
  candidateId: ConstructorCandidateId;
  onOpenResource: (resourceId: string) => void;
}) {
  const candidate = constructorCandidateMap.get(candidateId) ?? constructorCandidateMap.get('balanced');
  const donorResources = useWorkbenchDonorIntakeStore((state) => state.resources);

  const donorActions: ResolveAction[] = donorResources.slice(0, 2).map((resource, index) => ({
    id: `donor-${resource.resourceId}`,
    title: `Confirm ${resource.name}`,
    detail: 'HS can use this photo observation for planning, but it is not yet an authorized reusable component.',
    evidence: 'Capture model/label, condition, critical dimensions, connector identity and power/interface evidence.',
    resourceId: resource.resourceId,
    kind: 'identify',
    priority: index,
  }));

  const candidateActions: ResolveAction[] = (candidate?.resourceIds ?? [])
    .map((resourceId) => {
      const resource = constructorResources.find((row) => row.id === resourceId);
      const template = RESOURCE_ACTIONS[resourceId];
      if (!resource || !template || resource.authority === 'verified') return null;
      return {
        id: `resource-${resourceId}`,
        resourceId,
        priority: authorityPriority(resource.authority),
        ...template,
      } satisfies ResolveAction;
    })
    .filter((row): row is ResolveAction => Boolean(row))
    .sort((a, b) => a.priority - b.priority)
    .slice(0, donorActions.length > 0 ? 4 : 5);

  const actions = [...donorActions, ...candidateActions];

  return (
    <section className="mt-6 rounded-xl border border-amber-300/15 bg-amber-300/[0.025] p-4" aria-label="Practical evidence closures">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.18em] text-amber-300">
            <ShieldAlert className="h-4 w-4" /> Resolve what actually blocks the build
          </div>
          <h2 className="mt-1 text-base font-semibold text-white">Do the next useful observation, measurement or fit check.</h2>
          <p className="mt-1 max-w-3xl text-[11px] leading-5 text-slate-400">These are evidence closures for the selected architecture. Completing one should reduce uncertainty; it does not automatically authorize the whole build.</p>
        </div>
        <div className="text-[10px] text-slate-600">{actions.length} practical next actions · {candidate?.name}</div>
      </div>

      <div className="mt-4 grid gap-2 lg:grid-cols-2 xl:grid-cols-3" data-testid="resolve-action-list">
        {actions.map((action) => {
          const Icon = iconFor(action.kind);
          return (
            <button
              key={action.id}
              type="button"
              onClick={() => onOpenResource(action.resourceId)}
              className="group rounded-lg border border-white/8 bg-black/10 p-3 text-left transition hover:border-amber-300/20 hover:bg-amber-300/[0.035]"
              aria-label={`Resolve ${action.title}`}
            >
              <div className="flex items-start gap-2">
                <div className="rounded-md border border-amber-300/15 bg-amber-300/[0.04] p-1.5 text-amber-200"><Icon className="h-3.5 w-3.5" /></div>
                <div className="min-w-0 flex-1">
                  <div className="text-[11px] font-semibold text-slate-100 group-hover:text-white">{action.title}</div>
                  <div className="mt-1 text-[10px] leading-4 text-slate-500">{action.detail}</div>
                  <div className="mt-2 flex items-start gap-1.5 border-t border-white/7 pt-2 text-[9px] leading-4 text-amber-100/55">
                    <Camera className="mt-0.5 h-3 w-3 shrink-0" /> {action.evidence}
                  </div>
                </div>
              </div>
            </button>
          );
        })}
      </div>
    </section>
  );
}

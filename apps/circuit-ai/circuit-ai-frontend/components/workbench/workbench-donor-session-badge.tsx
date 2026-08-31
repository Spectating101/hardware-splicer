'use client';

import { useEffect } from 'react';
import { Camera, ShieldAlert } from 'lucide-react';
import { useMachineWorkbenchStore } from '@/lib/machine-workbench-store';
import { useWorkbenchDonorIntakeStore } from '@/lib/workbench-donor-intake-store';

export function WorkbenchDonorSessionBadge() {
  const resources = useWorkbenchDonorIntakeStore((state) => state.resources);
  const hydrated = useWorkbenchDonorIntakeStore((state) => state.hydrated);
  const hydrate = useWorkbenchDonorIntakeStore((state) => state.hydrate);
  const selectedResourceId = useMachineWorkbenchStore((state) => state.selectedResourceId);
  const focused = resources.find((resource) => resource.resourceId === selectedResourceId) ?? null;

  useEffect(() => hydrate(), [hydrate]);
  if (!hydrated || resources.length === 0) return null;

  return (
    <div className="fixed right-4 top-[72px] z-50 max-w-[320px] rounded-lg border border-amber-300/20 bg-[#07101d]/95 px-3 py-2 shadow-xl backdrop-blur" data-testid="workbench-donor-session">
      <div className="flex items-center gap-2 text-[9px] font-semibold uppercase tracking-[0.12em] text-amber-200">
        <Camera className="h-3.5 w-3.5" /> {resources.length} provisional donor {resources.length === 1 ? 'resource' : 'resources'}
      </div>
      {focused ? (
        <div className="mt-2 border-t border-white/8 pt-2" data-testid="focused-donor-resource">
          <div className="text-[10px] font-semibold text-white">Resolve · {focused.name}</div>
          <div className="mt-1 text-[9px] uppercase tracking-[0.1em] text-slate-600">{focused.capabilities.join(' · ')}</div>
          <div className="mt-1.5 flex items-start gap-1.5 text-[9px] leading-4 text-amber-100/60">
            <ShieldAlert className="mt-0.5 h-3 w-3 shrink-0" /> Capture model/label, condition, dimensions, connector identity and power/interface evidence before authorizing reuse.
          </div>
        </div>
      ) : (
        <div className="mt-1 text-[9px] leading-4 text-slate-500">Photo-derived observations affect candidate planning only. Engineering authority remains unresolved.</div>
      )}
    </div>
  );
}

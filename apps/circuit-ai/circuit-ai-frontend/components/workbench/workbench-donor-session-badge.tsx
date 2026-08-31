'use client';

import { useEffect } from 'react';
import { Camera } from 'lucide-react';
import { useWorkbenchDonorIntakeStore } from '@/lib/workbench-donor-intake-store';

export function WorkbenchDonorSessionBadge() {
  const resources = useWorkbenchDonorIntakeStore((state) => state.resources);
  const hydrated = useWorkbenchDonorIntakeStore((state) => state.hydrated);
  const hydrate = useWorkbenchDonorIntakeStore((state) => state.hydrate);

  useEffect(() => hydrate(), [hydrate]);
  if (!hydrated || resources.length === 0) return null;

  return (
    <div className="fixed right-4 top-[72px] z-50 max-w-[280px] rounded-lg border border-amber-300/20 bg-[#07101d]/95 px-3 py-2 shadow-xl backdrop-blur" data-testid="workbench-donor-session">
      <div className="flex items-center gap-2 text-[9px] font-semibold uppercase tracking-[0.12em] text-amber-200">
        <Camera className="h-3.5 w-3.5" /> {resources.length} provisional donor {resources.length === 1 ? 'resource' : 'resources'}
      </div>
      <div className="mt-1 text-[9px] leading-4 text-slate-500">Photo-derived observations affect candidate planning only. Engineering authority remains unresolved.</div>
    </div>
  );
}

'use client';

import Link from 'next/link';
import { ExternalLink, Eye, EyeOff, LockKeyhole } from 'lucide-react';
import { authorityLabel, deck001EntityMap } from '@/lib/workbench-demo';
import { useWorkbenchStore } from '@/lib/workbench-store';

function authorityClasses(state: string) {
  if (state === 'verified') return 'border-emerald-300/25 bg-emerald-300/10 text-emerald-200';
  if (state === 'partial') return 'border-sky-300/25 bg-sky-300/10 text-sky-200';
  if (state === 'blocked') return 'border-red-300/25 bg-red-300/10 text-red-200';
  if (state === 'unknown') return 'border-amber-300/25 bg-amber-300/10 text-amber-200';
  return 'border-violet-300/25 bg-violet-300/10 text-violet-200';
}

export function EntityInspectorPanel() {
  const selectedEntityId = useWorkbenchStore((state) => state.selectedEntityId);
  const isolatedEntityId = useWorkbenchStore((state) => state.isolatedEntityId);
  const setIsolatedEntityId = useWorkbenchStore((state) => state.setIsolatedEntityId);
  const entity = deck001EntityMap.get(selectedEntityId) ?? deck001EntityMap.get('deck-001');

  if (!entity) return null;

  const isolated = isolatedEntityId === entity.id;

  return (
    <aside className="flex h-full min-h-0 flex-col border-l border-white/10 bg-[#07101d]">
      <div className="border-b border-white/10 px-4 py-3">
        <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-cyan-300">Inspector</div>
        <div className="mt-2 flex items-start justify-between gap-3">
          <div className="min-w-0">
            <h2 className="truncate text-sm font-semibold text-white">{entity.name}</h2>
            <p className="mt-1 text-xs leading-5 text-slate-400">{entity.summary}</p>
          </div>
          <span className={`shrink-0 rounded-full border px-2 py-1 text-[9px] font-semibold tracking-[0.12em] ${authorityClasses(entity.authority)}`}>
            {authorityLabel(entity.authority)}
          </span>
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-auto p-4">
        <div className="grid grid-cols-2 gap-2">
          <div className="rounded-lg border border-white/10 bg-white/[0.025] p-3">
            <div className="text-[9px] uppercase tracking-[0.14em] text-slate-500">Kind</div>
            <div className="mt-1 text-xs font-medium text-slate-200">{entity.kind}</div>
          </div>
          <div className="rounded-lg border border-white/10 bg-white/[0.025] p-3">
            <div className="text-[9px] uppercase tracking-[0.14em] text-slate-500">Source</div>
            <div className="mt-1 text-xs font-medium text-slate-200">{entity.source}</div>
          </div>
          <div className="col-span-2 rounded-lg border border-white/10 bg-white/[0.025] p-3">
            <div className="text-[9px] uppercase tracking-[0.14em] text-slate-500">Domain</div>
            <div className="mt-1 text-xs font-medium text-slate-200">{entity.domain}</div>
          </div>
        </div>

        <section className="mt-5">
          <h3 className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">Current facts</h3>
          <div className="mt-2 divide-y divide-white/8 rounded-lg border border-white/10 bg-black/10">
            {entity.facts.map((fact) => (
              <div key={fact.label} className="grid grid-cols-[105px_1fr] gap-3 px-3 py-2.5 text-xs">
                <span className="text-slate-500">{fact.label}</span>
                <span className="text-right font-medium text-slate-200">{fact.value}</span>
              </div>
            ))}
          </div>
        </section>

        <section className="mt-5">
          <div className="flex items-center justify-between gap-2">
            <h3 className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">Unresolved</h3>
            <span className="text-[10px] text-slate-600">{entity.unresolved.length}</span>
          </div>
          {entity.unresolved.length ? (
            <div className="mt-2 space-y-2">
              {entity.unresolved.map((item) => (
                <div key={item} className="flex gap-2 rounded-md border border-amber-300/10 bg-amber-300/[0.035] px-3 py-2 text-xs text-amber-100/80">
                  <LockKeyhole className="mt-0.5 h-3.5 w-3.5 shrink-0 text-amber-300/80" />
                  <span>{item}</span>
                </div>
              ))}
            </div>
          ) : (
            <div className="mt-2 rounded-md border border-emerald-300/10 bg-emerald-300/[0.035] px-3 py-2 text-xs text-emerald-100/75">
              No unresolved facts recorded for this fixture entity.
            </div>
          )}
        </section>
      </div>

      <div className="space-y-2 border-t border-white/10 p-3">
        {entity.spatial ? (
          <button
            type="button"
            onClick={() => setIsolatedEntityId(isolated ? null : entity.id)}
            className="flex w-full items-center justify-center gap-2 rounded-md border border-white/10 bg-white/[0.035] px-3 py-2 text-xs font-medium text-slate-200 transition hover:bg-white/[0.07]"
          >
            {isolated ? <Eye className="h-3.5 w-3.5" /> : <EyeOff className="h-3.5 w-3.5" />}
            {isolated ? 'Show full machine' : 'Isolate in viewport'}
          </button>
        ) : null}
        {(entity.id === 'cmp-mainboard' || entity.id === 'ss-compute') ? (
          <Link href="/cad" className="flex w-full items-center justify-center gap-2 rounded-md border border-cyan-300/20 bg-cyan-300/8 px-3 py-2 text-xs font-medium text-cyan-100 transition hover:bg-cyan-300/12">
            Open board-level CAD <ExternalLink className="h-3.5 w-3.5" />
          </Link>
        ) : null}
      </div>
    </aside>
  );
}

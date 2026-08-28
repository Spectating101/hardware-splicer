'use client';

import {
  Activity,
  GitBranch,
  History,
  Link2,
  ShieldAlert,
} from 'lucide-react';
import {
  deck001Constraints,
  deck001Evidence,
  deck001History,
  deck001Interfaces,
  deck001Verifications,
} from '@/lib/workbench-demo';
import { useWorkbenchStore, type WorkbenchBottomTab } from '@/lib/workbench-store';

const tabs: Array<{ id: WorkbenchBottomTab; label: string; icon: typeof Activity }> = [
  { id: 'evidence', label: 'Evidence', icon: Activity },
  { id: 'interfaces', label: 'Interfaces', icon: Link2 },
  { id: 'constraints', label: 'Constraints', icon: ShieldAlert },
  { id: 'verification', label: 'Verification', icon: GitBranch },
  { id: 'history', label: 'History', icon: History },
];

function stateClass(state: string) {
  if (state === 'verified' || state === 'passed' || state === 'satisfied') return 'text-emerald-300';
  if (state === 'blocked' || state === 'open') return 'text-red-300';
  if (state === 'unknown' || state === 'planned') return 'text-amber-300';
  return 'text-sky-300';
}

export function WorkbenchBottomPanel() {
  const activeBottomTab = useWorkbenchStore((state) => state.activeBottomTab);
  const setActiveBottomTab = useWorkbenchStore((state) => state.setActiveBottomTab);
  const selectedEntityId = useWorkbenchStore((state) => state.selectedEntityId);
  const setSelectedEntityId = useWorkbenchStore((state) => state.setSelectedEntityId);

  const selectedFilter = (entityId: string) => selectedEntityId === 'deck-001' || entityId === selectedEntityId;

  return (
    <section className="flex min-h-[210px] flex-col border-t border-white/10 bg-[#060d18]">
      <div className="flex items-center gap-1 overflow-x-auto border-b border-white/10 px-2 py-1.5">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          const active = activeBottomTab === tab.id;
          return (
            <button
              key={tab.id}
              type="button"
              onClick={() => setActiveBottomTab(tab.id)}
              className={`inline-flex items-center gap-2 rounded-md px-3 py-1.5 text-[11px] font-medium transition ${
                active ? 'bg-cyan-300/10 text-cyan-100 ring-1 ring-cyan-300/20' : 'text-slate-500 hover:bg-white/5 hover:text-slate-200'
              }`}
            >
              <Icon className="h-3.5 w-3.5" />
              {tab.label}
            </button>
          );
        })}
        <div className="ml-auto hidden text-[10px] uppercase tracking-[0.14em] text-slate-600 lg:block">
          filtered by current selection where applicable
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-auto p-3">
        {activeBottomTab === 'evidence' ? (
          <div className="grid gap-2 xl:grid-cols-2">
            {deck001Evidence.filter((row) => selectedFilter(row.entityId)).map((row) => (
              <button key={row.id} type="button" onClick={() => setSelectedEntityId(row.entityId)} className="rounded-lg border border-white/10 bg-white/[0.025] p-3 text-left transition hover:bg-white/[0.05]">
                <div className="flex items-center justify-between gap-3">
                  <span className="text-xs font-medium text-slate-100">{row.title}</span>
                  <span className={`text-[9px] font-semibold uppercase tracking-[0.12em] ${stateClass(row.state)}`}>{row.state}</span>
                </div>
                <div className="mt-1 text-[10px] uppercase tracking-[0.12em] text-slate-600">{row.method}</div>
                <p className="mt-2 text-[11px] leading-5 text-slate-400">{row.note}</p>
              </button>
            ))}
          </div>
        ) : null}

        {activeBottomTab === 'interfaces' ? (
          <div className="grid gap-2 xl:grid-cols-2">
            {deck001Interfaces.filter((row) => selectedEntityId === 'deck-001' || row.from === selectedEntityId || row.to === selectedEntityId).map((row) => (
              <button key={row.id} type="button" onClick={() => setSelectedEntityId(row.authority === 'blocked' ? row.to : row.from)} className="rounded-lg border border-white/10 bg-white/[0.025] p-3 text-left transition hover:bg-white/[0.05]">
                <div className="flex items-center justify-between gap-3">
                  <span className="text-xs font-medium text-slate-100">{row.name}</span>
                  <span className={`text-[9px] font-semibold uppercase tracking-[0.12em] ${stateClass(row.authority)}`}>{row.authority}</span>
                </div>
                <div className="mt-2 text-[11px] text-slate-500">{row.kind} · {row.from} → {row.to}</div>
                {row.unresolved.length ? <div className="mt-2 text-[11px] text-amber-200/70">Open: {row.unresolved.join(', ')}</div> : null}
              </button>
            ))}
          </div>
        ) : null}

        {activeBottomTab === 'constraints' ? (
          <div className="space-y-2">
            {deck001Constraints.filter((row) => selectedFilter(row.entityId)).map((row) => (
              <button key={row.id} type="button" onClick={() => setSelectedEntityId(row.entityId)} className="flex w-full items-start gap-3 rounded-lg border border-white/10 bg-white/[0.025] p-3 text-left transition hover:bg-white/[0.05]">
                <ShieldAlert className={`mt-0.5 h-4 w-4 shrink-0 ${row.severity === 'blocking' ? 'text-red-300' : 'text-amber-300'}`} />
                <div className="min-w-0 flex-1">
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-xs font-medium text-slate-100">{row.title}</span>
                    <span className={`text-[9px] font-semibold uppercase tracking-[0.12em] ${stateClass(row.state)}`}>{row.state}</span>
                  </div>
                  <p className="mt-1 text-[11px] leading-5 text-slate-400">{row.note}</p>
                </div>
              </button>
            ))}
          </div>
        ) : null}

        {activeBottomTab === 'verification' ? (
          <div className="space-y-2">
            {deck001Verifications.filter((row) => selectedFilter(row.entityId)).map((row) => (
              <button key={row.id} type="button" onClick={() => setSelectedEntityId(row.entityId)} className="flex w-full items-center gap-3 rounded-lg border border-white/10 bg-white/[0.025] px-3 py-2.5 text-left transition hover:bg-white/[0.05]">
                <span className={`w-16 shrink-0 text-[9px] font-semibold uppercase tracking-[0.12em] ${stateClass(row.state)}`}>{row.state}</span>
                <span className="min-w-0 flex-1 truncate text-xs font-medium text-slate-100">{row.title}</span>
                <span className="hidden text-[10px] text-slate-500 md:block">{row.method}</span>
              </button>
            ))}
          </div>
        ) : null}

        {activeBottomTab === 'history' ? (
          <div className="space-y-2">
            {deck001History.filter((row) => selectedFilter(row.entityId)).map((row) => (
              <button key={row.id} type="button" onClick={() => setSelectedEntityId(row.entityId)} className="grid w-full grid-cols-[42px_1fr] gap-3 rounded-lg border border-white/10 bg-white/[0.025] p-3 text-left transition hover:bg-white/[0.05]">
                <span className="text-[10px] font-semibold text-cyan-300">{row.at}</span>
                <span>
                  <span className="block text-xs font-medium text-slate-100">{row.title}</span>
                  <span className="mt-1 block text-[11px] leading-5 text-slate-400">{row.note}</span>
                </span>
              </button>
            ))}
          </div>
        ) : null}
      </div>
    </section>
  );
}

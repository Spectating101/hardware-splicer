'use client';

import {
  Activity,
  History,
  Link2,
  Ruler,
  SearchX,
  ShieldAlert,
} from 'lucide-react';
import { GeometryInterrogationPanel } from '@/components/workbench/geometry-interrogation-panel';
import {
  deck001Constraints,
  deck001EntityMap,
  deck001Evidence,
  deck001History,
  deck001Interfaces,
  deck001Verifications,
} from '@/lib/workbench-demo';
import { useMachineWorkbenchStore, type WorkbenchBottomTab } from '@/lib/machine-workbench-store';

const tabs: Array<{ id: WorkbenchBottomTab; label: string; icon: typeof Activity }> = [
  { id: 'evidence', label: 'Evidence', icon: Activity },
  { id: 'interfaces', label: 'Interfaces', icon: Link2 },
  { id: 'constraints', label: 'Constraints', icon: ShieldAlert },
  { id: 'verification', label: 'Verification', icon: Ruler },
  { id: 'history', label: 'History', icon: History },
];

function stateClass(state: string) {
  if (state === 'verified' || state === 'passed' || state === 'satisfied') return 'text-emerald-300';
  if (state === 'blocked' || state === 'open') return 'text-red-300';
  if (state === 'unknown' || state === 'planned') return 'text-amber-300';
  return 'text-sky-300';
}

function entityFallsWithinSelection(entityId: string, selectedEntityId: string) {
  if (selectedEntityId === 'deck-001') return true;
  let current = deck001EntityMap.get(entityId);
  while (current) {
    if (current.id === selectedEntityId) return true;
    current = current.parentId ? deck001EntityMap.get(current.parentId) : undefined;
  }
  return false;
}

function EmptyState({ noun, selection }: { noun: string; selection: string }) {
  return (
    <div className="flex min-h-[112px] items-center justify-center rounded-xl border border-dashed border-white/10 bg-white/[0.015] px-5 text-center">
      <div>
        <SearchX className="mx-auto h-4 w-4 text-slate-600" />
        <div className="mt-2 text-xs font-medium text-slate-300">No {noun} bound to this scope</div>
        <div className="mt-1 text-[11px] text-slate-600">{selection} remains selected; choose a child entity or another tray for adjacent engineering context.</div>
      </div>
    </div>
  );
}

export function WorkbenchBottomPanel() {
  const activeBottomTab = useMachineWorkbenchStore((state) => state.activeBottomTab);
  const setActiveBottomTab = useMachineWorkbenchStore((state) => state.setActiveBottomTab);
  const selectedEntityId = useMachineWorkbenchStore((state) => state.selectedEntityId);
  const setSelectedEntityId = useMachineWorkbenchStore((state) => state.setSelectedEntityId);
  const selectedEntity = deck001EntityMap.get(selectedEntityId);

  const evidenceRows = deck001Evidence.filter((row) => entityFallsWithinSelection(row.entityId, selectedEntityId));
  const constraintRows = deck001Constraints.filter((row) => entityFallsWithinSelection(row.entityId, selectedEntityId));
  const verificationRows = deck001Verifications.filter((row) => entityFallsWithinSelection(row.entityId, selectedEntityId));
  const historyRows = deck001History.filter((row) => entityFallsWithinSelection(row.entityId, selectedEntityId));
  const interfaceRows = deck001Interfaces.filter((row) =>
    selectedEntityId === 'deck-001'
      || entityFallsWithinSelection(row.from, selectedEntityId)
      || entityFallsWithinSelection(row.to, selectedEntityId)
  );

  const selectionLabel = selectedEntity?.name ?? selectedEntityId;

  return (
    <section className={`flex min-h-[190px] flex-col border-t border-white/10 bg-[#060d18] ${activeBottomTab === 'verification' ? 'max-h-[390px]' : 'max-h-[290px]'}`}>
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
        <div className="ml-auto hidden items-center gap-2 text-[10px] uppercase tracking-[0.13em] text-slate-600 lg:flex">
          <span>scope</span>
          <span className="max-w-[210px] truncate rounded border border-white/8 bg-white/[0.025] px-2 py-1 text-slate-400">{selectionLabel}</span>
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-auto p-3">
        {activeBottomTab === 'evidence' ? (
          evidenceRows.length ? (
            <div className="grid gap-2 xl:grid-cols-2 2xl:grid-cols-3">
              {evidenceRows.map((row) => (
                <button key={row.id} type="button" onClick={() => setSelectedEntityId(row.entityId)} className="rounded-lg border border-white/10 bg-white/[0.025] p-3 text-left transition hover:border-cyan-300/15 hover:bg-white/[0.05]">
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-xs font-medium text-slate-100">{row.title}</span>
                    <span className={`text-[9px] font-semibold uppercase tracking-[0.12em] ${stateClass(row.state)}`}>{row.state}</span>
                  </div>
                  <div className="mt-1 text-[10px] uppercase tracking-[0.12em] text-slate-600">{row.method}</div>
                  <p className="mt-2 text-[11px] leading-5 text-slate-400">{row.note}</p>
                </button>
              ))}
            </div>
          ) : <EmptyState noun="evidence" selection={selectionLabel} />
        ) : null}

        {activeBottomTab === 'interfaces' ? (
          interfaceRows.length ? (
            <div className="grid gap-2 xl:grid-cols-2 2xl:grid-cols-3">
              {interfaceRows.map((row) => (
                <button key={row.id} type="button" onClick={() => setSelectedEntityId(row.authority === 'blocked' ? row.to : row.from)} className="rounded-lg border border-white/10 bg-white/[0.025] p-3 text-left transition hover:border-cyan-300/15 hover:bg-white/[0.05]">
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-xs font-medium text-slate-100">{row.name}</span>
                    <span className={`text-[9px] font-semibold uppercase tracking-[0.12em] ${stateClass(row.authority)}`}>{row.authority}</span>
                  </div>
                  <div className="mt-2 text-[11px] text-slate-500">{row.kind} · {row.from} → {row.to}</div>
                  {row.unresolved.length ? <div className="mt-2 text-[11px] text-amber-200/70">Open: {row.unresolved.join(', ')}</div> : null}
                </button>
              ))}
            </div>
          ) : <EmptyState noun="interfaces" selection={selectionLabel} />
        ) : null}

        {activeBottomTab === 'constraints' ? (
          constraintRows.length ? (
            <div className="grid gap-2 xl:grid-cols-2">
              {constraintRows.map((row) => (
                <button key={row.id} type="button" onClick={() => setSelectedEntityId(row.entityId)} className="flex w-full items-start gap-3 rounded-lg border border-white/10 bg-white/[0.025] p-3 text-left transition hover:border-cyan-300/15 hover:bg-white/[0.05]">
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
          ) : <EmptyState noun="constraints" selection={selectionLabel} />
        ) : null}

        {activeBottomTab === 'verification' ? (
          <div className="space-y-3">
            <GeometryInterrogationPanel />
            {verificationRows.length ? (
              <section>
                <div className="mb-2 text-[9px] font-semibold uppercase tracking-[0.14em] text-slate-600">Fixture verification records</div>
                <div className="grid gap-2 xl:grid-cols-2">
                  {verificationRows.map((row) => (
                    <button key={row.id} type="button" onClick={() => setSelectedEntityId(row.entityId)} className="flex w-full items-center gap-3 rounded-lg border border-white/10 bg-white/[0.025] px-3 py-2.5 text-left transition hover:border-cyan-300/15 hover:bg-white/[0.05]">
                      <span className={`w-16 shrink-0 text-[9px] font-semibold uppercase tracking-[0.12em] ${stateClass(row.state)}`}>{row.state}</span>
                      <span className="min-w-0 flex-1 truncate text-xs font-medium text-slate-100">{row.title}</span>
                      <span className="hidden text-[10px] text-slate-500 md:block">{row.method}</span>
                    </button>
                  ))}
                </div>
              </section>
            ) : null}
          </div>
        ) : null}

        {activeBottomTab === 'history' ? (
          historyRows.length ? (
            <div className="grid gap-2 xl:grid-cols-2">
              {historyRows.map((row) => (
                <button key={row.id} type="button" onClick={() => setSelectedEntityId(row.entityId)} className="grid w-full grid-cols-[42px_1fr] gap-3 rounded-lg border border-white/10 bg-white/[0.025] p-3 text-left transition hover:border-cyan-300/15 hover:bg-white/[0.05]">
                  <span className="text-[10px] font-semibold text-cyan-300">{row.at}</span>
                  <span>
                    <span className="block text-xs font-medium text-slate-100">{row.title}</span>
                    <span className="mt-1 block text-[11px] leading-5 text-slate-400">{row.note}</span>
                  </span>
                </button>
              ))}
            </div>
          ) : <EmptyState noun="history" selection={selectionLabel} />
        ) : null}
      </div>
    </section>
  );
}

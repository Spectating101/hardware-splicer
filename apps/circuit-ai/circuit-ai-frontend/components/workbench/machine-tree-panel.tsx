'use client';

import { useMemo, useState } from 'react';
import { ChevronDown, ChevronRight, Search } from 'lucide-react';
import { deck001Entities, deck001EntityMap, type WorkbenchEntity } from '@/lib/workbench-demo';
import { useMachineWorkbenchStore } from '@/lib/machine-workbench-store';

function stateDot(entity: WorkbenchEntity) {
  if (entity.authority === 'verified') return 'bg-emerald-400';
  if (entity.authority === 'partial') return 'bg-sky-400';
  if (entity.authority === 'blocked') return 'bg-red-400';
  if (entity.authority === 'unknown') return 'bg-amber-400';
  return 'bg-violet-400';
}

export function MachineTreePanel() {
  const selectedEntityId = useMachineWorkbenchStore((state) => state.selectedEntityId);
  const setSelectedEntityId = useMachineWorkbenchStore((state) => state.setSelectedEntityId);
  const requestFrameSelection = useMachineWorkbenchStore((state) => state.requestFrameSelection);
  const [query, setQuery] = useState('');
  const [collapsed, setCollapsed] = useState<Set<string>>(() => new Set());

  const normalizedQuery = query.trim().toLowerCase();
  const root = deck001EntityMap.get('deck-001');
  const subsystemIds = root?.children ?? [];

  const visibleSubsystems = useMemo(() => {
    if (!normalizedQuery) return subsystemIds;
    return subsystemIds.filter((id) => {
      const subsystem = deck001EntityMap.get(id);
      if (!subsystem) return false;
      if (`${subsystem.name} ${subsystem.domain}`.toLowerCase().includes(normalizedQuery)) return true;
      return subsystem.children.some((childId) => {
        const child = deck001EntityMap.get(childId);
        return child ? `${child.name} ${child.summary}`.toLowerCase().includes(normalizedQuery) : false;
      });
    });
  }, [normalizedQuery, subsystemIds]);

  function toggleCollapsed(id: string) {
    setCollapsed((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function selectAndFrame(id: string) {
    setSelectedEntityId(id);
    requestFrameSelection();
  }

  function EntityButton({ entity, depth = 0 }: { entity: WorkbenchEntity; depth?: number }) {
    const selected = selectedEntityId === entity.id;
    return (
      <button
        type="button"
        onClick={() => selectAndFrame(entity.id)}
        className={`group flex w-full items-start gap-2 rounded-md px-2 py-1.5 text-left transition ${
          selected ? 'bg-cyan-300/12 text-cyan-50 ring-1 ring-cyan-300/20' : 'text-slate-300 hover:bg-white/5 hover:text-white'
        }`}
        style={{ paddingLeft: `${8 + depth * 16}px` }}
      >
        <span className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${stateDot(entity)}`} />
        <span className="min-w-0 flex-1">
          <span className="block truncate text-xs font-medium">{entity.name}</span>
          <span className="block truncate text-[10px] uppercase tracking-[0.12em] text-slate-500">{entity.source} · {entity.domain}</span>
        </span>
      </button>
    );
  }

  return (
    <section className="flex h-full min-h-0 flex-col border-r border-white/10 bg-[#07101d]">
      <div className="border-b border-white/10 px-3 py-3">
        <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-cyan-300">Machine tree</div>
        <div className="mt-2 flex items-center gap-2 rounded-md border border-white/10 bg-black/20 px-2.5 py-2">
          <Search className="h-3.5 w-3.5 text-slate-500" />
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Find subsystem or part"
            className="min-w-0 flex-1 bg-transparent text-xs text-slate-200 outline-none placeholder:text-slate-600"
          />
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-auto px-2 py-2">
        {root ? <EntityButton entity={root} /> : null}
        <div className="mt-1 space-y-1">
          {visibleSubsystems.map((subsystemId) => {
            const subsystem = deck001EntityMap.get(subsystemId);
            if (!subsystem) return null;
            const isCollapsed = collapsed.has(subsystem.id);
            const children = subsystem.children
              .map((id) => deck001EntityMap.get(id))
              .filter((entity): entity is WorkbenchEntity => Boolean(entity))
              .filter((entity) => !normalizedQuery || `${entity.name} ${entity.summary}`.toLowerCase().includes(normalizedQuery));

            return (
              <div key={subsystem.id}>
                <div className="flex items-center gap-1">
                  <button
                    type="button"
                    onClick={() => toggleCollapsed(subsystem.id)}
                    className="rounded p-1 text-slate-500 hover:bg-white/5 hover:text-slate-200"
                    aria-label={`${isCollapsed ? 'Expand' : 'Collapse'} ${subsystem.name}`}
                  >
                    {isCollapsed ? <ChevronRight className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
                  </button>
                  <div className="min-w-0 flex-1"><EntityButton entity={subsystem} /></div>
                </div>
                {!isCollapsed ? (
                  <div className="ml-3 border-l border-white/8 pl-1">
                    {children.map((entity) => <EntityButton key={entity.id} entity={entity} depth={1} />)}
                  </div>
                ) : null}
              </div>
            );
          })}
        </div>
      </div>

      <div className="border-t border-white/10 px-3 py-2 text-[10px] leading-4 text-slate-500">
        {deck001Entities.length} entities · tree selections frame the shared 3D/evidence context.
      </div>
    </section>
  );
}

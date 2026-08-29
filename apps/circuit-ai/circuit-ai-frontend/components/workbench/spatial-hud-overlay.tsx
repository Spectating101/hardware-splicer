'use client';

import { constructorCandidateMap } from '@/lib/workbench-constructor-demo';
import { deck001Constraints, deck001EntityMap, deck001Interfaces } from '@/lib/workbench-demo';
import { useMachineWorkbenchStore } from '@/lib/machine-workbench-store';

function authorityTone(authority: string) {
  if (authority === 'verified') return 'text-emerald-300 border-emerald-300/25 bg-emerald-300/8';
  if (authority === 'blocked') return 'text-red-300 border-red-300/25 bg-red-300/8';
  if (authority === 'unknown') return 'text-amber-300 border-amber-300/25 bg-amber-300/8';
  if (authority === 'partial') return 'text-sky-300 border-sky-300/25 bg-sky-300/8';
  return 'text-violet-300 border-violet-300/25 bg-violet-300/8';
}

export function SpatialHudOverlay() {
  const selectedEntityId = useMachineWorkbenchStore((state) => state.selectedEntityId);
  const activeLens = useMachineWorkbenchStore((state) => state.activeLens);
  const phase = useMachineWorkbenchStore((state) => state.phase);
  const activeCandidateId = useMachineWorkbenchStore((state) => state.activeCandidateId);
  const immersive = useMachineWorkbenchStore((state) => state.immersive);
  const selected = deck001EntityMap.get(selectedEntityId) ?? deck001EntityMap.get('deck-001');
  const candidate = constructorCandidateMap.get(activeCandidateId) ?? constructorCandidateMap.get('balanced');

  if (!selected) return null;

  const scope = new Set<string>(
    selected.kind === 'machine'
      ? []
      : selected.spatial
        ? [selected.id]
        : selected.children,
  );
  const interfaces = deck001Interfaces.filter((link) =>
    selected.kind === 'machine' || scope.has(link.from) || scope.has(link.to),
  );
  const blockedInterfaces = interfaces.filter((link) => link.authority === 'blocked').length;
  const inspectionOpenConstraints = deck001Constraints.filter((constraint) =>
    (selected.kind === 'machine' || scope.has(constraint.entityId) || constraint.entityId === selected.id)
    && constraint.state === 'open',
  ).length;
  const openGates = phase === 'construct' ? candidate?.blockerCount ?? inspectionOpenConstraints : inspectionOpenConstraints;

  return (
    <div className="pointer-events-none absolute inset-0 z-10 overflow-hidden" aria-hidden="true">
      <style>{`
        @keyframes hs-hud-scan {
          0% { transform: translateY(-12px); opacity: 0; }
          12% { opacity: .35; }
          88% { opacity: .18; }
          100% { transform: translateY(520px); opacity: 0; }
        }
        @keyframes hs-hud-pulse {
          0%, 100% { opacity: .28; transform: scale(1); }
          50% { opacity: .7; transform: scale(1.05); }
        }
        @media (prefers-reduced-motion: reduce) {
          .hs-hud-scan, .hs-hud-pulse { animation: none !important; }
        }
      `}</style>

      {immersive ? (
        <>
          <div className="absolute inset-x-[9%] top-0 h-px bg-gradient-to-r from-transparent via-cyan-200/20 to-transparent" />
          <div className="hs-hud-scan absolute inset-x-[12%] top-0 h-px bg-gradient-to-r from-transparent via-cyan-200/45 to-transparent shadow-[0_0_18px_rgba(103,232,249,0.32)]" style={{ animation: 'hs-hud-scan 5.8s linear infinite' }} />
          <div className="absolute left-5 top-5 h-8 w-8 border-l border-t border-cyan-200/30" />
          <div className="absolute right-5 top-5 h-8 w-8 border-r border-t border-cyan-200/30" />
          <div className="absolute bottom-5 left-5 h-8 w-8 border-b border-l border-cyan-200/20" />
          <div className="absolute bottom-5 right-5 h-8 w-8 border-b border-r border-cyan-200/20" />
          <div className="absolute left-1/2 top-1/2 h-12 w-12 -translate-x-1/2 -translate-y-1/2 rounded-full border border-cyan-200/10">
            <div className="absolute left-1/2 top-[-10px] h-4 w-px -translate-x-1/2 bg-cyan-200/15" />
            <div className="absolute bottom-[-10px] left-1/2 h-4 w-px -translate-x-1/2 bg-cyan-200/15" />
            <div className="absolute left-[-10px] top-1/2 h-px w-4 -translate-y-1/2 bg-cyan-200/15" />
            <div className="absolute right-[-10px] top-1/2 h-px w-4 -translate-y-1/2 bg-cyan-200/15" />
          </div>
        </>
      ) : null}

      <div className={`absolute bottom-5 left-5 max-w-[390px] border-l border-cyan-200/20 pl-3 ${immersive ? '' : phase === 'construct' ? 'hidden' : 'hidden 2xl:block'}`}>
        <div className="flex items-center gap-2 text-[9px] font-semibold uppercase tracking-[0.2em] text-cyan-200/70">
          <span className="hs-hud-pulse h-1.5 w-1.5 rounded-full bg-cyan-200" style={{ animation: 'hs-hud-pulse 2.2s ease-in-out infinite' }} />
          {phase === 'construct' ? 'working architecture' : 'live spatial model'}
        </div>
        <div className="mt-1 truncate text-sm font-semibold text-slate-100">{phase === 'construct' ? candidate?.name ?? 'Working candidate' : selected.name}</div>
        <div className="mt-1 flex flex-wrap items-center gap-1.5 text-[9px] uppercase tracking-[0.11em] text-slate-500">
          {phase === 'construct' ? (
            <>
              <span>{candidate?.strategyMode}</span><span>·</span><span>{candidate?.reusePercent}% reuse</span><span>·</span><span>{candidate?.risk} risk</span><span>·</span><span>{activeLens} lens</span>
            </>
          ) : (
            <>
              <span>{selected.domain}</span><span>·</span><span>{selected.source}</span><span>·</span><span>{activeLens} lens</span>
            </>
          )}
        </div>
      </div>

      <div className={`absolute right-5 top-1/2 flex -translate-y-1/2 flex-col items-end gap-2 ${immersive ? '' : 'hidden 2xl:flex'}`}>
        <div className="mr-1 h-12 w-px bg-gradient-to-b from-transparent via-cyan-200/25 to-cyan-200/5" />
        <div className="min-w-[104px] rounded-md border border-white/10 bg-slate-950/74 px-2.5 py-2 text-right backdrop-blur">
          <div className="text-[8px] uppercase tracking-[0.16em] text-slate-600">interfaces</div>
          <div className="mt-0.5 text-sm font-semibold text-slate-200">{interfaces.length}</div>
        </div>
        <div className={`min-w-[104px] rounded-md border px-2.5 py-2 text-right backdrop-blur ${blockedInterfaces ? 'border-red-300/20 bg-red-300/[0.06]' : 'border-white/10 bg-slate-950/74'}`}>
          <div className="text-[8px] uppercase tracking-[0.16em] text-slate-600">blocked paths</div>
          <div className={`mt-0.5 text-sm font-semibold ${blockedInterfaces ? 'text-red-300' : 'text-slate-200'}`}>{blockedInterfaces}</div>
        </div>
        <div className={`min-w-[104px] rounded-md border px-2.5 py-2 text-right backdrop-blur ${openGates ? 'border-amber-300/20 bg-amber-300/[0.06]' : 'border-white/10 bg-slate-950/74'}`}>
          <div className="text-[8px] uppercase tracking-[0.16em] text-slate-600">{phase === 'construct' ? 'candidate gates' : 'open gates'}</div>
          <div className={`mt-0.5 text-sm font-semibold ${openGates ? 'text-amber-300' : 'text-slate-200'}`}>{openGates}</div>
        </div>
        <div className={`min-w-[104px] rounded-md border px-2.5 py-2 text-right backdrop-blur ${authorityTone(selected.authority)}`}>
          <div className="text-[8px] uppercase tracking-[0.16em] opacity-60">authority</div>
          <div className="mt-0.5 text-[10px] font-semibold uppercase tracking-[0.12em]">{selected.authority}</div>
        </div>
        <div className="mr-1 h-12 w-px bg-gradient-to-b from-cyan-200/5 via-cyan-200/20 to-transparent" />
      </div>
    </div>
  );
}

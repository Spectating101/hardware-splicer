'use client';

import { useState } from 'react';
import Link from 'next/link';
import {
  Activity,
  Box,
  CircuitBoard,
  Eye,
  GitBranch,
  Hammer,
  Layers3,
  LockKeyhole,
  Maximize2,
  Minimize2,
  RotateCcw,
  ScanSearch,
  ShieldAlert,
  Waypoints,
} from 'lucide-react';
import { PcbViewport, type SelectionState as PcbSelectionState } from '@/components/cad/pcb-viewport';
import { CandidateArchitectureTray } from '@/components/workbench/candidate-architecture-tray';
import { ConstructorDock } from '@/components/workbench/constructor-dock';
import { EntityInspectorPanel } from '@/components/workbench/entity-inspector-panel';
import { MachineAssemblyViewport } from '@/components/workbench/machine-assembly-viewport';
import { MachineTreePanel } from '@/components/workbench/machine-tree-panel';
import { ProposalQueuePanel } from '@/components/workbench/proposal-queue-panel';
import { SpatialHudOverlay } from '@/components/workbench/spatial-hud-overlay';
import { WorkbenchBottomPanel } from '@/components/workbench/workbench-bottom-panel';
import { usePageTitle } from '@/components/use-page-title';
import { constructorCandidateMap, constructorTarget } from '@/lib/workbench-constructor-demo';
import { deck001Constraints, deck001EntityMap } from '@/lib/workbench-demo';
import { workbenchPcbGeometry, workbenchPcbIssues } from '@/lib/workbench-pcb-demo';
import { useMachineWorkbenchStore, type WorkbenchLens } from '@/lib/machine-workbench-store';

const lenses: Array<{ id: WorkbenchLens; label: string; icon: typeof Eye }> = [
  { id: 'authority', label: 'Authority', icon: LockKeyhole },
  { id: 'interfaces', label: 'Interfaces', icon: Waypoints },
  { id: 'provenance', label: 'Provenance', icon: GitBranch },
  { id: 'constraints', label: 'Constraints', icon: ShieldAlert },
];

export function MachineWorkbench() {
  usePageTitle('Machine Constructor | Hardware Splicer');

  const activeLens = useMachineWorkbenchStore((state) => state.activeLens);
  const activeView = useMachineWorkbenchStore((state) => state.activeView);
  const phase = useMachineWorkbenchStore((state) => state.phase);
  const activeCandidateId = useMachineWorkbenchStore((state) => state.activeCandidateId);
  const exploded = useMachineWorkbenchStore((state) => state.exploded);
  const immersive = useMachineWorkbenchStore((state) => state.immersive);
  const selectedEntityId = useMachineWorkbenchStore((state) => state.selectedEntityId);
  const setActiveLens = useMachineWorkbenchStore((state) => state.setActiveLens);
  const setActiveView = useMachineWorkbenchStore((state) => state.setActiveView);
  const setPhase = useMachineWorkbenchStore((state) => state.setPhase);
  const setSelectedEntityId = useMachineWorkbenchStore((state) => state.setSelectedEntityId);
  const requestFrameSelection = useMachineWorkbenchStore((state) => state.requestFrameSelection);
  const toggleExploded = useMachineWorkbenchStore((state) => state.toggleExploded);
  const toggleImmersive = useMachineWorkbenchStore((state) => state.toggleImmersive);
  const resetViewState = useMachineWorkbenchStore((state) => state.resetViewState);
  const [pcbSelection, setPcbSelection] = useState<PcbSelectionState>({ footprintRef: null });

  const selected = deck001EntityMap.get(selectedEntityId) ?? deck001EntityMap.get('deck-001');
  const candidate = constructorCandidateMap.get(activeCandidateId) ?? constructorCandidateMap.get('balanced');
  const inspectBlockingConstraints = deck001Constraints.filter((constraint) => constraint.severity === 'blocking' && constraint.state === 'open').length;
  const blockerCount = phase === 'construct' ? candidate?.blockerCount ?? inspectBlockingConstraints : inspectBlockingConstraints;

  function frameMachineOverview() {
    setActiveView('assembly');
    setSelectedEntityId('deck-001');
    requestFrameSelection();
  }

  return (
    <main className="flex min-h-screen flex-col bg-[#040811] text-slate-100 xl:h-screen xl:min-h-0 xl:overflow-hidden">
      <header className="z-20 flex min-h-[62px] shrink-0 items-center gap-3 border-b border-white/10 bg-[#07101d]/95 px-3 py-2 backdrop-blur lg:px-4">
        <div className="flex min-w-0 items-center gap-3">
          <div className="rounded-lg border border-cyan-300/20 bg-cyan-300/8 p-2 text-cyan-200">
            {phase === 'construct' ? <Hammer className="h-4 w-4" /> : <Box className="h-4 w-4" />}
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <h1 className="truncate text-sm font-semibold text-white">{phase === 'construct' ? constructorTarget.title : 'DECK-001'}</h1>
              <span className="rounded border border-white/10 bg-white/5 px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-[0.12em] text-slate-400">{phase === 'construct' ? candidate?.name ?? 'working' : 'R0'}</span>
              {immersive ? <span className="rounded border border-cyan-300/20 bg-cyan-300/8 px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-[0.12em] text-cyan-200">Spatial focus</span> : null}
            </div>
            <div className="truncate text-[10px] uppercase tracking-[0.14em] text-slate-500">{phase === 'construct' ? 'Hardware constructor · target → resources → candidates → proposals' : 'Machine inspection · evidence and authority'}</div>
          </div>
        </div>

        {!immersive ? (
          <div className="ml-3 hidden rounded-lg border border-white/10 bg-black/20 p-0.5 md:flex">
            <button type="button" onClick={() => setPhase('construct')} className={`inline-flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-[9px] font-semibold uppercase tracking-[0.1em] ${phase === 'construct' ? 'bg-cyan-300/10 text-cyan-100' : 'text-slate-500 hover:text-white'}`}>
              <Hammer className="h-3 w-3" /> Construct
            </button>
            <button type="button" onClick={() => setPhase('inspect')} className={`inline-flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-[9px] font-semibold uppercase tracking-[0.1em] ${phase === 'inspect' ? 'bg-cyan-300/10 text-cyan-100' : 'text-slate-500 hover:text-white'}`}>
              <ScanSearch className="h-3 w-3" /> Inspect
            </button>
          </div>
        ) : null}

        <div className="ml-auto hidden items-center gap-2 lg:flex">
          <div className="flex items-center gap-2 rounded-lg border border-red-300/20 bg-red-300/[0.06] px-3 py-2 text-[10px] font-semibold uppercase tracking-[0.13em] text-red-200">
            <LockKeyhole className="h-3.5 w-3.5" />
            Build blocked · {blockerCount} {blockerCount === 1 ? 'gate' : 'gates'}
          </div>
          {!immersive ? (
            <>
              <Link href="/engineering/studio" className="rounded-md border border-white/10 px-3 py-2 text-[11px] font-medium text-slate-300 transition hover:bg-white/5 hover:text-white">Project Studio</Link>
              <Link href="/cad" className="rounded-md border border-cyan-300/15 bg-cyan-300/[0.04] px-3 py-2 text-[11px] font-medium text-cyan-100 transition hover:bg-cyan-300/[0.08]">PCB CAD</Link>
            </>
          ) : null}
        </div>
      </header>

      <div className="flex min-h-0 flex-1 flex-col">
        <div className={`grid min-h-[680px] flex-1 grid-cols-1 xl:min-h-0 ${immersive ? 'xl:grid-cols-1' : 'xl:grid-cols-[270px_minmax(0,1fr)_340px]'}`}>
          {!immersive ? (
            <div className="min-h-[300px] xl:min-h-0">
              {phase === 'construct' ? <ConstructorDock /> : <MachineTreePanel />}
            </div>
          ) : null}

          <section className="flex min-h-[520px] min-w-0 flex-col bg-[#050912] xl:min-h-0">
            <div className="flex flex-wrap items-center gap-2 border-b border-white/10 bg-[#07101d] px-3 py-2">
              <div className="flex items-center rounded-md border border-white/10 bg-black/20 p-0.5">
                <button
                  type="button"
                  onClick={() => setActiveView('assembly')}
                  className={`inline-flex items-center gap-2 rounded px-2.5 py-1.5 text-[10px] font-medium transition ${activeView === 'assembly' ? 'bg-white/10 text-white' : 'text-slate-500 hover:text-slate-200'}`}
                >
                  <Layers3 className="h-3.5 w-3.5" /> Working machine
                </button>
                <button
                  type="button"
                  onClick={() => {
                    if (immersive) toggleImmersive();
                    setActiveView('pcb');
                    setSelectedEntityId('cmp-mainboard');
                  }}
                  className={`inline-flex items-center gap-2 rounded px-2.5 py-1.5 text-[10px] font-medium transition ${activeView === 'pcb' ? 'bg-white/10 text-white' : 'text-slate-500 hover:text-slate-200'}`}
                >
                  <CircuitBoard className="h-3.5 w-3.5" /> Compute PCB
                </button>
              </div>

              <div className="h-5 w-px bg-white/10" />

              <div className="flex flex-wrap items-center gap-1">
                {lenses.map((lens) => {
                  const Icon = lens.icon;
                  const active = activeLens === lens.id;
                  return (
                    <button
                      key={lens.id}
                      type="button"
                      onClick={() => setActiveLens(lens.id)}
                      className={`inline-flex items-center gap-1.5 rounded-md px-2 py-1.5 text-[10px] font-medium transition ${active ? 'bg-cyan-300/10 text-cyan-100 ring-1 ring-cyan-300/20' : 'text-slate-500 hover:bg-white/5 hover:text-slate-200'}`}
                    >
                      <Icon className="h-3.5 w-3.5" /> {lens.label}
                    </button>
                  );
                })}
              </div>

              <div className="ml-auto flex items-center gap-1">
                <button
                  type="button"
                  onClick={frameMachineOverview}
                  disabled={activeView !== 'assembly'}
                  aria-label="Frame whole machine"
                  className="inline-flex items-center gap-1.5 rounded-md px-2 py-1.5 text-[10px] font-medium text-slate-500 transition hover:bg-white/5 hover:text-slate-200 disabled:cursor-not-allowed disabled:opacity-30"
                >
                  <Box className="h-3.5 w-3.5" /> Overview
                </button>
                <button
                  type="button"
                  onClick={toggleExploded}
                  disabled={activeView !== 'assembly'}
                  className={`inline-flex items-center gap-1.5 rounded-md px-2 py-1.5 text-[10px] font-medium transition ${exploded && activeView === 'assembly' ? 'bg-violet-300/10 text-violet-100' : 'text-slate-500 hover:bg-white/5 hover:text-slate-200 disabled:cursor-not-allowed disabled:opacity-30'}`}
                >
                  <Activity className="h-3.5 w-3.5" /> Explode
                </button>
                <button
                  type="button"
                  onClick={toggleImmersive}
                  disabled={activeView !== 'assembly'}
                  aria-label={immersive ? 'Exit immersive spatial mode' : 'Enter immersive spatial mode'}
                  aria-pressed={immersive}
                  className={`inline-flex items-center gap-1.5 rounded-md px-2 py-1.5 text-[10px] font-medium transition ${immersive && activeView === 'assembly' ? 'bg-cyan-300/10 text-cyan-100 ring-1 ring-cyan-300/20' : 'text-slate-500 hover:bg-white/5 hover:text-slate-200 disabled:cursor-not-allowed disabled:opacity-30'}`}
                >
                  {immersive ? <Minimize2 className="h-3.5 w-3.5" /> : <Maximize2 className="h-3.5 w-3.5" />}
                  {immersive ? 'Exit spatial' : 'Spatial focus'}
                </button>
                <button type="button" onClick={resetViewState} className="rounded-md p-1.5 text-slate-500 transition hover:bg-white/5 hover:text-slate-200" aria-label="Reset workbench view state">
                  <RotateCcw className="h-3.5 w-3.5" />
                </button>
              </div>
            </div>

            <div className="relative min-h-0 flex-1">
              {activeView === 'assembly' ? (
                <>
                  <MachineAssemblyViewport />
                  <SpatialHudOverlay />
                  {phase === 'construct' && !immersive ? (
                    <div className="pointer-events-none absolute left-4 bottom-4 max-w-[360px] rounded-xl border border-cyan-300/15 bg-[#06101c]/88 px-3 py-2 shadow-xl backdrop-blur">
                      <div className="text-[8px] font-semibold uppercase tracking-[0.18em] text-cyan-300">Working candidate · {candidate?.name}</div>
                      <div className="mt-1 text-[9px] leading-4 text-slate-400">{candidate?.tagline} <span className="text-slate-600">Candidate composition is exploratory; authority remains evidence-bound.</span></div>
                    </div>
                  ) : null}
                </>
              ) : (
                <div className="h-full min-h-[420px] bg-[#050912] xl:min-h-0">
                  <PcbViewport
                    geometry={workbenchPcbGeometry}
                    issues={workbenchPcbIssues}
                    selection={pcbSelection}
                    onSelectionChange={(selection) => {
                      setPcbSelection(selection);
                      setSelectedEntityId('cmp-mainboard');
                    }}
                    lenses={{ drc: true, netFocus: Boolean(pcbSelection.footprintRef) }}
                    renderMode="engineering"
                    topDown
                  />
                  <div className="pointer-events-none absolute left-4 top-4 max-w-[520px] rounded-lg border border-white/10 bg-slate-950/85 px-3 py-2 text-[10px] leading-4 text-slate-400 shadow-xl backdrop-blur">
                    Representative x86 board fixture in the existing HS PCB renderer. Geometry remains synthetic until donor identity and measurements close.
                  </div>
                </div>
              )}
            </div>

            <div className="flex shrink-0 items-center justify-between gap-3 border-t border-white/10 bg-[#07101d] px-3 py-1.5 text-[10px] text-slate-500">
              <span className="truncate">{phase === 'construct' ? <>Working candidate: <strong className="font-medium text-slate-300">{candidate?.name}</strong> · selected <strong className="font-medium text-slate-300">{selected?.name ?? 'DECK-001'}</strong></> : <>Selected: <strong className="font-medium text-slate-300">{selected?.name ?? 'DECK-001'}</strong></>}</span>
              <span className="hidden md:block">Orbit · inspect · frame · compare · semantic lenses</span>
            </div>
          </section>

          {!immersive ? (
            <div className="min-h-[360px] xl:min-h-0">
              {phase === 'construct' ? <ProposalQueuePanel /> : <EntityInspectorPanel />}
            </div>
          ) : null}
        </div>

        {!immersive ? (phase === 'construct' ? <CandidateArchitectureTray /> : <WorkbenchBottomPanel />) : null}
      </div>
    </main>
  );
}

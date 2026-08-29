'use client';

import { FormEvent, useEffect, useMemo, useRef, useState } from 'react';
import { Command, CornerDownLeft, Sparkles, X } from 'lucide-react';
import { constructorCandidateMap } from '@/lib/workbench-constructor-demo';
import { deck001EntityMap } from '@/lib/workbench-demo';
import { useMachineWorkbenchStore, type ConstructorCandidateId, type WorkbenchCameraPreset } from '@/lib/machine-workbench-store';

const QUICK_COMMANDS = [
  'build mode',
  'candidate max reuse',
  'show blockers',
  'focus power',
  'trace interfaces',
  'x-ray',
  'overview',
  'open compute board',
];

const ENTITY_ALIASES: Array<[string[], string]> = [
  [['power'], 'ss-power'],
  [['display', 'screen'], 'ss-display'],
  [['compute', 'computer'], 'ss-compute'],
  [['keyboard', 'input'], 'ss-input'],
  [['storage', 'nvme', 'ssd'], 'ss-storage'],
  [['thermal', 'cooling', 'fan'], 'ss-thermal'],
  [['enclosure', 'chassis', 'case'], 'ss-enclosure'],
  [['io', 'usb', 'breakout'], 'ss-io'],
  [['battery'], 'cmp-battery'],
  [['pd', 'power-path'], 'cmp-pd'],
  [['mainboard', 'motherboard'], 'cmp-mainboard'],
];

function entityForCommand(command: string) {
  for (const [aliases, entityId] of ENTITY_ALIASES) {
    if (aliases.some((alias) => command.includes(alias))) return deck001EntityMap.get(entityId) ?? null;
  }
  return null;
}

function candidateForCommand(command: string): ConstructorCandidateId | null {
  if (command.includes('max reuse') || command.includes('maximum reuse') || command.includes('reuse candidate')) return 'max-reuse';
  if (command.includes('low risk') || command.includes('lowest risk') || command.includes('safe candidate')) return 'low-risk';
  if (command.includes('balanced') || command.includes('hybrid candidate')) return 'balanced';
  return null;
}

export function SpatialCommandConsole() {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [lastResult, setLastResult] = useState('Ready for a spatial command.');
  const inputRef = useRef<HTMLInputElement | null>(null);

  const selectedEntityId = useMachineWorkbenchStore((state) => state.selectedEntityId);
  const activeView = useMachineWorkbenchStore((state) => state.activeView);
  const phase = useMachineWorkbenchStore((state) => state.phase);
  const activeCandidateId = useMachineWorkbenchStore((state) => state.activeCandidateId);
  const xray = useMachineWorkbenchStore((state) => state.xray);
  const exploded = useMachineWorkbenchStore((state) => state.exploded);
  const immersive = useMachineWorkbenchStore((state) => state.immersive);
  const setSelectedEntityId = useMachineWorkbenchStore((state) => state.setSelectedEntityId);
  const setActiveLens = useMachineWorkbenchStore((state) => state.setActiveLens);
  const setActiveBottomTab = useMachineWorkbenchStore((state) => state.setActiveBottomTab);
  const setActiveView = useMachineWorkbenchStore((state) => state.setActiveView);
  const setPhase = useMachineWorkbenchStore((state) => state.setPhase);
  const setConstructorDockTab = useMachineWorkbenchStore((state) => state.setConstructorDockTab);
  const setActiveCandidateId = useMachineWorkbenchStore((state) => state.setActiveCandidateId);
  const setIsolatedEntityId = useMachineWorkbenchStore((state) => state.setIsolatedEntityId);
  const setCameraPreset = useMachineWorkbenchStore((state) => state.setCameraPreset);
  const requestFrameSelection = useMachineWorkbenchStore((state) => state.requestFrameSelection);
  const toggleExploded = useMachineWorkbenchStore((state) => state.toggleExploded);
  const toggleXray = useMachineWorkbenchStore((state) => state.toggleXray);
  const toggleImmersive = useMachineWorkbenchStore((state) => state.toggleImmersive);

  const selected = deck001EntityMap.get(selectedEntityId) ?? deck001EntityMap.get('deck-001');
  const candidate = constructorCandidateMap.get(activeCandidateId);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault();
        setOpen((value) => !value);
        return;
      }
      if (event.key === 'Escape') setOpen(false);
    }
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, []);

  useEffect(() => {
    if (!open) return;
    const id = window.setTimeout(() => inputRef.current?.focus(), 40);
    return () => window.clearTimeout(id);
  }, [open]);

  const contextLabel = useMemo(() => phase === 'construct' ? `${candidate?.name ?? 'working'} candidate` : selected?.name ?? 'DECK-001', [candidate?.name, phase, selected]);

  function frame(entityId: string, preset?: WorkbenchCameraPreset) {
    setActiveView('assembly');
    setSelectedEntityId(entityId);
    setIsolatedEntityId(null);
    if (preset) setCameraPreset(preset);
    window.setTimeout(requestFrameSelection, 0);
  }

  function execute(raw: string) {
    const command = raw.trim().toLowerCase();
    if (!command) return;

    if (command.includes('build mode') || command.includes('construct mode') || command === 'construct') {
      setPhase('construct');
      setActiveView('assembly');
      setLastResult('Constructor restored: target, resources, candidates and design proposals are active.');
      setQuery('');
      return;
    }

    if (command.includes('inspect mode') || command === 'inspect') {
      setPhase('inspect');
      setLastResult('Machine inspection mode restored.');
      setQuery('');
      return;
    }

    if (command.includes('show resources') || command.includes('resource pool') || command === 'resources') {
      setPhase('construct');
      setConstructorDockTab('resources');
      setLastResult('Resource pool opened. Candidate resources remain evidence-bounded.');
      setQuery('');
      return;
    }

    if (command.includes('show target') || command.includes('requirements') || command === 'target') {
      setPhase('construct');
      setConstructorDockTab('target');
      setLastResult('Target contract opened against the working candidate.');
      setQuery('');
      return;
    }

    const candidateId = candidateForCommand(command);
    if (candidateId && (command.includes('candidate') || command.includes('architecture') || command.includes('switch') || command.includes('use'))) {
      setPhase('construct');
      setActiveCandidateId(candidateId);
      frame('deck-001', 'iso');
      const next = constructorCandidateMap.get(candidateId);
      setLastResult(`${next?.name ?? candidateId} is now the working architecture candidate. Authority gates are unchanged.`);
      setQuery('');
      return;
    }

    if (command.includes('open compute board') || command === 'pcb' || command.includes('open board')) {
      if (immersive) toggleImmersive();
      setActiveView('pcb');
      setSelectedEntityId('cmp-mainboard');
      setLastResult('Compute-board engineering view opened. Representative geometry remains synthetic.');
      setQuery('');
      return;
    }

    if (command.includes('overview') || command.includes('whole machine') || command.includes('show machine')) {
      frame('deck-001', 'iso');
      setLastResult('Whole-machine overview framed.');
      setQuery('');
      return;
    }

    if (command.includes('show blocker') || command.includes('blocked') || command.includes('constraint') || command.includes("can't build") || command.includes('cannot build')) {
      setActiveLens('constraints');
      setActiveBottomTab('constraints');
      frame('deck-001', 'iso');
      setLastResult('Blocking and unresolved paths surfaced across the machine.');
      setQuery('');
      return;
    }

    if (command.includes('trace') || command.includes('interface') || command.includes('dependency')) {
      setActiveLens('interfaces');
      setActiveBottomTab('interfaces');
      if (activeView !== 'assembly') setActiveView('assembly');
      requestFrameSelection();
      setLastResult(`Interface graph surfaced for ${contextLabel}.`);
      setQuery('');
      return;
    }

    if (command.includes('provenance') || command.includes('donor') || command.includes('source')) {
      setActiveLens('provenance');
      setActiveView('assembly');
      setLastResult('Provenance lens active: donor, new, generated and external origins are separated spatially.');
      setQuery('');
      return;
    }

    if (command.includes('authority') || command.includes('truth') || command.includes('verified')) {
      setActiveLens('authority');
      setActiveView('assembly');
      setLastResult('Authority lens active. Visual state now follows the evidence boundary.');
      setQuery('');
      return;
    }

    if (command === 'x-ray' || command === 'xray' || command.includes('see inside')) {
      setActiveView('assembly');
      if (!xray) toggleXray();
      setLastResult('Enclosure ghosted. Internal hardware remains selectable.');
      setQuery('');
      return;
    }

    if (command.includes('exit x-ray') || command.includes('exit xray') || command.includes('solid shell')) {
      if (xray) toggleXray();
      setLastResult('Opaque enclosure restored.');
      setQuery('');
      return;
    }

    if (command.includes('explode') || command.includes('pull apart')) {
      setActiveView('assembly');
      if (!exploded) toggleExploded();
      requestFrameSelection();
      setLastResult('Exploded inspection enabled. Geometry positions remain presentation-only.');
      setQuery('');
      return;
    }

    if (command.includes('collapse assembly') || command.includes('assemble')) {
      if (exploded) toggleExploded();
      requestFrameSelection();
      setLastResult('Assembly returned to nominal presentation positions.');
      setQuery('');
      return;
    }

    if (command.includes('spatial focus') || command.includes('immersive')) {
      setActiveView('assembly');
      if (!immersive) toggleImmersive();
      setLastResult('Spatial Focus enabled. Machine geometry now owns the workstation.');
      setQuery('');
      return;
    }

    if (command.includes('exit spatial') || command.includes('exit immersive')) {
      if (immersive) toggleImmersive();
      setLastResult('Full engineering panels restored.');
      setQuery('');
      return;
    }

    const preset: WorkbenchCameraPreset | null = command.includes('top view') || command === 'top'
      ? 'top'
      : command.includes('front view') || command === 'front'
        ? 'front'
        : command.includes('side view') || command === 'side'
          ? 'right'
          : command.includes('iso') || command.includes('isometric')
            ? 'iso'
            : null;
    if (preset) {
      setActiveView('assembly');
      setCameraPreset(preset);
      requestFrameSelection();
      setLastResult(`${preset.toUpperCase()} engineering camera applied to ${contextLabel}.`);
      setQuery('');
      return;
    }

    const entity = entityForCommand(command);
    if (entity && (command.includes('focus') || command.includes('frame') || command.includes('show') || command.includes('isolate'))) {
      frame(entity.id);
      if (command.includes('isolate')) {
        const spatialId = entity.spatial ? entity.id : entity.children.find((childId) => deck001EntityMap.get(childId)?.spatial) ?? null;
        setIsolatedEntityId(spatialId);
      }
      if (entity.id === 'ss-power' || entity.id === 'cmp-pd' || entity.id === 'cmp-battery') setActiveLens('constraints');
      setLastResult(`${entity.name} framed${command.includes('isolate') ? ' and isolated' : ''}.`);
      setQuery('');
      return;
    }

    setLastResult('Command not mapped yet. Try “build mode”, “candidate max reuse”, “show resources”, “show blockers”, “focus power”, “x-ray”, or “open compute board”.');
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    execute(query);
  }

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-label="Open spatial command console"
        className={`fixed left-1/2 z-[90] -translate-x-1/2 rounded-full border px-3.5 py-2 text-[10px] font-semibold uppercase tracking-[0.12em] shadow-2xl backdrop-blur transition ${immersive ? 'bottom-5 border-cyan-300/25 bg-[#06111d]/88 text-cyan-100 hover:bg-[#0a1a2b]' : 'top-[118px] border-white/10 bg-[#07101d]/92 text-slate-300 hover:border-cyan-300/25 hover:text-cyan-100'}`}
      >
        <span className="inline-flex items-center gap-2"><Command className="h-3.5 w-3.5" /> Spatial command <span className="text-slate-600">⌘K</span></span>
      </button>
    );
  }

  return (
    <div className="fixed inset-x-0 bottom-5 z-[100] flex justify-center px-4" aria-label="Spatial command console">
      <div className="w-full max-w-3xl overflow-hidden rounded-2xl border border-cyan-300/20 bg-[#06101c]/96 shadow-[0_26px_100px_rgba(0,0,0,0.62)] backdrop-blur-xl">
        <div className="flex items-center gap-3 border-b border-white/10 px-4 py-3">
          <div className="rounded-lg border border-cyan-300/20 bg-cyan-300/8 p-2 text-cyan-200"><Sparkles className="h-4 w-4" /></div>
          <div className="min-w-0 flex-1">
            <div className="text-[9px] font-semibold uppercase tracking-[0.2em] text-cyan-300">HS spatial command</div>
            <div className="mt-0.5 truncate text-[10px] text-slate-500">Deterministic constructor / viewport operations · current context: {contextLabel}</div>
          </div>
          <button type="button" onClick={() => setOpen(false)} className="rounded-md p-2 text-slate-500 hover:bg-white/5 hover:text-white" aria-label="Close spatial command console"><X className="h-4 w-4" /></button>
        </div>

        <form onSubmit={onSubmit} className="flex items-center gap-3 px-4 py-3">
          <Command className="h-4 w-4 shrink-0 text-cyan-300" />
          <input
            ref={inputRef}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="candidate max reuse · show resources · focus power · trace interfaces…"
            className="min-w-0 flex-1 bg-transparent text-sm text-slate-100 outline-none placeholder:text-slate-600"
            aria-label="Spatial command input"
          />
          <button type="submit" className="inline-flex items-center gap-1.5 rounded-md border border-white/10 bg-white/[0.04] px-2.5 py-1.5 text-[9px] font-semibold uppercase tracking-[0.1em] text-slate-300 hover:bg-white/[0.08] hover:text-white">
            Execute <CornerDownLeft className="h-3 w-3" />
          </button>
        </form>

        <div className="flex flex-wrap gap-1.5 border-t border-white/8 px-4 py-2.5">
          {QUICK_COMMANDS.map((command) => (
            <button key={command} type="button" onClick={() => execute(command)} className="rounded-full border border-white/8 bg-white/[0.025] px-2.5 py-1 text-[9px] text-slate-500 transition hover:border-cyan-300/15 hover:text-cyan-100">{command}</button>
          ))}
          <div className="ml-auto max-w-[42%] truncate text-[9px] text-slate-600">{lastResult}</div>
        </div>
      </div>
    </div>
  );
}
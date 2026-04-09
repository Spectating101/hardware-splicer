'use client';

import { useState, type ReactNode } from 'react';
import Link from 'next/link';
import {
  CircuitBoard,
  Cpu,
  FolderKanban,
  House,
  LayoutPanelTop,
  Minus,
  PanelLeftClose,
  Search,
  ScanSearch,
  SlidersHorizontal,
  Square,
  X,
} from 'lucide-react';
import { useStudioRuntime } from '@/components/studio-runtime';
import { cn } from '@/lib/utils';

type StudioNavItem = {
  href: string;
  label: string;
};

type StudioShellProps = {
  eyebrow: string;
  title: string;
  description: string;
  status?: string;
  commandBar?: ReactNode;
  actions?: ReactNode;
  defaultBottomOpen?: boolean;
  navItems: StudioNavItem[];
  activeHref: string;
  left: ReactNode;
  main: ReactNode;
  right: ReactNode;
  bottom?: ReactNode;
};

export function StudioShell({
  eyebrow,
  title,
  description,
  status,
  commandBar,
  actions,
  defaultBottomOpen = false,
  navItems,
  activeHref,
  left,
  main,
  right,
  bottom,
}: StudioShellProps) {
  const { state } = useStudioRuntime();
  const [bottomOpen, setBottomOpen] = useState(defaultBottomOpen);

  const iconForHref = (href: string) => {
    if (href === '/') return House;
    if (href === '/analyze') return ScanSearch;
    if (href === '/components') return Cpu;
    if (href === '/projects') return FolderKanban;
    return CircuitBoard;
  };

  const workflow = [
    {
      href: '/analyze',
      label: 'Board',
      detail: state.artifactName || 'No artifact',
      ready: Boolean(state.artifactName),
    },
    {
      href: '/analyze',
      label: 'Inspect',
      detail:
        state.detectionCount !== null
          ? `${state.detectionCount} detections`
          : state.analysisMode
            ? `${state.analysisMode} mode`
            : 'Awaiting run',
      ready: Boolean(state.analysisMode || state.detectionCount !== null),
    },
    {
      href: '/components',
      label: 'Parts',
      detail: state.focusedComponent ? state.focusedComponent.replaceAll('_', ' ') : 'No focus',
      ready: Boolean(state.focusedComponent),
    },
    {
      href: '/projects',
      label: 'Route',
      detail: state.focusedProject || 'No path',
      ready: Boolean(state.focusedProject),
    },
    {
      href: '/cad',
      label: 'CAD',
      detail: 'Downstream workspace',
      ready: false,
    },
  ];

  return (
    <div className="min-h-screen overflow-hidden bg-[radial-gradient(circle_at_top_left,rgba(34,211,238,0.08),transparent_18%),radial-gradient(circle_at_86%_6%,rgba(251,146,60,0.08),transparent_20%),linear-gradient(180deg,#02050a_0%,#040a12_100%)] text-slate-100">
      <main className="mx-auto max-w-[2200px] px-2 py-2 sm:px-3">
        <section className="overflow-hidden rounded-[1.35rem] border border-white/10 bg-[#060b13] shadow-[0_45px_120px_rgba(0,0,0,0.58)]">
          <div className="border-b border-white/10 bg-[linear-gradient(180deg,rgba(255,255,255,0.04),rgba(255,255,255,0.01))]">
            <div className="flex min-h-[38px] items-center gap-3 border-b border-white/8 px-4 text-sm">
              <Link href="/" className="flex items-center gap-3">
                <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-[linear-gradient(135deg,#0f172a,#2563eb,#f97316)] text-white shadow-[0_12px_28px_rgba(37,99,235,0.28)]">
                  <CircuitBoard className="h-4 w-4" />
                </div>
                <div>
                  <div className="text-[10px] font-semibold uppercase tracking-[0.28em] text-cyan-200">{eyebrow}</div>
                  <div className="text-xs font-semibold text-white">Circuit.AI Studio</div>
                </div>
              </Link>

              <div className="hidden items-center gap-5 lg:flex">
                {['File', 'Edit', 'View', 'Window', 'Inspect'].map((item) => (
                  <button key={item} type="button" className="text-xs font-medium text-slate-400 transition-colors hover:text-white">
                    {item}
                  </button>
                ))}
              </div>

              {commandBar ? (
                <div className="ml-auto hidden min-w-0 flex-1 items-center justify-end xl:flex">
                  {commandBar}
                </div>
              ) : (
                <div className="ml-auto hidden items-center gap-2 rounded-xl border border-white/8 bg-white/[0.03] px-3 py-1.5 text-[11px] text-slate-400 xl:flex">
                  <Search className="h-3.5 w-3.5 text-slate-500" />
                  Search commands, routes, tools
                </div>
              )}

              <div className="flex items-center gap-1.5 text-slate-500">
                <button type="button" className="flex h-7 w-7 items-center justify-center rounded-md hover:bg-white/6 hover:text-white" aria-label="Minimize">
                  <Minus className="h-4 w-4" />
                </button>
                <button type="button" className="flex h-7 w-7 items-center justify-center rounded-md hover:bg-white/6 hover:text-white" aria-label="Maximize">
                  <Square className="h-3.5 w-3.5" />
                </button>
                <button type="button" className="flex h-7 w-7 items-center justify-center rounded-md hover:bg-rose-500/16 hover:text-rose-100" aria-label="Close">
                  <X className="h-4 w-4" />
                </button>
              </div>
            </div>

            <div className="flex min-h-[46px] items-center gap-2 border-b border-white/8 px-4">
              {navItems.map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    'inline-flex h-9 items-center gap-2 rounded-t-xl border border-b-0 px-3 text-sm font-medium transition-colors',
                    activeHref === item.href
                      ? 'border-white/12 bg-[#091321] text-white'
                      : 'border-transparent bg-transparent text-slate-400 hover:text-white',
                  )}
                >
                  {item.label}
                </Link>
              ))}

              <div className="ml-auto hidden items-center gap-2 xl:flex">
                <div className="rounded-t-xl border border-white/12 border-b-0 bg-[#091321] px-3 py-2 text-xs font-medium text-slate-300">
                  workspace.circuit
                </div>
              </div>
            </div>

            <div className="grid gap-3 px-4 py-3 lg:grid-cols-[minmax(0,1fr)_auto]">
              <div className="hidden min-w-0 flex-1 items-center gap-3 lg:flex">
                <div className="flex min-w-0 flex-1 items-center gap-3 rounded-xl border border-white/10 bg-[#091321] px-3 py-2.5">
                  <LayoutPanelTop className="h-4 w-4 text-cyan-300" />
                  <div className="min-w-0">
                    <div className="truncate text-sm font-semibold text-white">{title}</div>
                    <div className="truncate text-xs text-slate-400">{description}</div>
                  </div>
                </div>
                {status ? (
                  <div className="rounded-full border border-emerald-400/20 bg-emerald-400/10 px-3 py-1.5 text-xs font-medium text-emerald-200">
                    {status}
                  </div>
                ) : null}
              </div>

              <div className="ml-auto flex items-center gap-2 justify-self-end">
                {actions ? <div className="hidden items-center gap-2 md:flex">{actions}</div> : null}
                <button
                  type="button"
                  className="flex h-10 w-10 items-center justify-center rounded-xl border border-white/10 bg-[#0a1321] text-slate-300"
                  aria-label="Studio layout"
                >
                  <PanelLeftClose className="h-4 w-4" />
                </button>
                <button
                  type="button"
                  className="flex h-10 w-10 items-center justify-center rounded-xl border border-white/10 bg-[#0a1321] text-slate-300"
                  aria-label="Workspace preferences"
                >
                  <SlidersHorizontal className="h-4 w-4" />
                </button>
              </div>

              <div className="hidden min-w-0 flex-wrap items-center gap-2 lg:flex lg:col-span-2">
                {workflow.map((item) => {
                  const active = activeHref === item.href;
                  return (
                    <Link
                      key={`${item.label}-${item.href}`}
                      href={item.href}
                      className={cn(
                        'group relative inline-flex items-center gap-2 rounded-full border px-3 py-2 text-sm transition-colors',
                        active
                          ? 'border-cyan-300/30 bg-cyan-300/10'
                          : item.ready
                            ? 'border-white/10 bg-[#091321] hover:border-white/18'
                            : 'border-white/8 bg-[#07101b]',
                      )}
                    >
                      <div className={cn('h-2 w-2 rounded-full', item.ready ? 'bg-cyan-300' : 'bg-slate-600')} />
                      <div className="text-[11px] font-semibold uppercase tracking-[0.2em] text-slate-400">{item.label}</div>
                      <div className="hidden xl:block text-sm font-semibold text-white">{item.detail}</div>
                      <div className="pointer-events-none absolute left-0 top-[calc(100%+0.5rem)] z-20 hidden w-56 rounded-[1rem] border border-white/10 bg-[#081423]/96 p-3 text-left shadow-[0_18px_40px_rgba(2,6,23,0.45)] backdrop-blur group-hover:block">
                        <div className="text-[11px] font-semibold uppercase tracking-[0.2em] text-slate-500">{item.label}</div>
                        <div className="mt-1 text-sm font-semibold text-white">{item.detail}</div>
                        <div className="mt-2 text-xs text-slate-400">{item.ready ? 'Active in current run' : 'Not focused yet'}</div>
                      </div>
                    </Link>
                  );
                })}
              </div>
            </div>
          </div>

          <section className={cn(
            'grid gap-px bg-white/8 lg:grid-cols-[54px_172px_minmax(0,1fr)_338px] lg:h-[calc(100vh-7.8rem)]',
            bottom && bottomOpen ? 'lg:grid-rows-[minmax(0,1fr)_170px]' : 'lg:grid-rows-[minmax(0,1fr)_46px]',
          )}>
            <aside className="hidden overflow-hidden bg-[linear-gradient(180deg,#050a12_0%,#09111e_100%)] lg:col-start-1 lg:block">
              <div className="flex h-full flex-col items-center justify-between py-4">
                <div className="flex flex-col items-center gap-3">
                  {navItems.map((item) => {
                    const Icon = iconForHref(item.href);
                    const active = activeHref === item.href;
                    return (
                      <Link
                        key={item.href}
                        href={item.href}
                        className={cn(
                          'flex h-11 w-11 items-center justify-center rounded-2xl border transition-colors',
                          active
                            ? 'border-cyan-300/30 bg-cyan-300/12 text-cyan-200 shadow-[0_12px_24px_rgba(34,211,238,0.14)]'
                            : 'border-white/8 bg-white/[0.03] text-slate-500 hover:border-white/15 hover:bg-white/[0.06] hover:text-white',
                        )}
                        title={item.label}
                      >
                        <Icon className="h-4 w-4" />
                      </Link>
                    );
                  })}
                </div>

                <div className="rounded-2xl border border-white/8 bg-white/[0.03] px-2 py-3 text-[10px] font-semibold uppercase tracking-[0.24em] text-slate-500 [writing-mode:vertical-rl]">
                  Studio
                </div>
              </div>
            </aside>

            <aside className="overflow-hidden bg-[linear-gradient(180deg,#07101b_0%,#0a1220_100%)] lg:col-start-2 lg:row-start-1">
              <div className="h-full overflow-y-auto p-3">{left}</div>
            </aside>

            <section className="overflow-hidden bg-[#060d17] lg:col-start-3 lg:row-start-1">
              <div className="h-full overflow-hidden">{main}</div>
            </section>

            <aside className="overflow-hidden bg-[linear-gradient(180deg,#07101b_0%,#0a1220_100%)] lg:col-start-4 lg:row-start-1">
              <div className="h-full overflow-y-auto p-3">{right}</div>
            </aside>

            {bottom ? (
              <section className="relative overflow-hidden bg-[linear-gradient(180deg,#060d17_0%,#081220_100%)] lg:col-start-2 lg:col-end-5 lg:row-start-2">
                <button
                  type="button"
                  onClick={() => setBottomOpen((open) => !open)}
                  className="absolute right-4 top-3 z-20 rounded-full border border-white/10 bg-[#081423] px-3 py-1.5 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-300 transition-colors hover:border-white/18 hover:text-white"
                >
                  {bottomOpen ? 'Hide Tray' : 'Open Tray'}
                </button>
                <div className="h-full overflow-hidden">{bottom}</div>
              </section>
            ) : null}
          </section>
        </section>
      </main>
    </div>
  );
}

'use client';

import { useState, type ReactNode } from 'react';
import Link from 'next/link';
import {
  CircuitBoard,
  Cpu,
  FolderKanban,
  House,
  LayoutPanelTop,
  Search,
  ScanSearch,
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
    <div className="circuit-chassis min-h-screen overflow-hidden text-slate-100">
      <main className="mx-auto max-w-[2240px] px-2 py-2 sm:px-4 sm:py-4">
        <section className="circuit-window overflow-hidden rounded-[1.6rem]">
          <div className="border-b border-white/10 bg-[linear-gradient(180deg,rgba(255,255,255,0.055),rgba(255,255,255,0.018))]">
            <div className="flex min-h-[44px] items-center gap-3 border-b border-white/8 px-4 text-sm">
              <Link href="/" className="flex items-center gap-3">
                <div className="flex h-8 w-8 items-center justify-center rounded-xl border border-white/10 bg-[linear-gradient(135deg,#09111f,#0e7490,#f97316)] text-white shadow-[0_16px_34px_rgba(34,211,238,0.18)]">
                  <CircuitBoard className="h-4 w-4" />
                </div>
                <div>
                  <div className="text-[10px] font-semibold uppercase tracking-[0.28em] text-cyan-200">{eyebrow}</div>
                  <div className="text-sm font-semibold tracking-tight text-white">Circuit.AI Studio</div>
                </div>
              </Link>

              <div className="hidden items-center gap-4 lg:flex">
                {['Live routes', 'Proxy guarded', 'Evidence first'].map((item) => (
                  <span key={item} className="rounded-full border border-white/8 bg-white/[0.025] px-2.5 py-1 text-[11px] font-medium text-slate-400">
                    {item}
                  </span>
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

              <div className="hidden items-center gap-2 rounded-full border border-emerald-300/18 bg-emerald-300/8 px-3 py-1.5 text-[11px] font-semibold uppercase tracking-[0.16em] text-emerald-100 sm:flex">
                <span className="h-2 w-2 rounded-full bg-emerald-300" />
                Professor mode
              </div>
            </div>

            <div className="flex min-h-[54px] items-center gap-2 border-b border-white/8 px-4">
              {navItems.map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    'inline-flex h-10 items-center gap-2 rounded-2xl border px-3.5 text-sm font-semibold transition-colors',
                    activeHref === item.href
                      ? 'border-cyan-300/22 bg-cyan-300/12 text-cyan-50 shadow-[0_14px_32px_rgba(34,211,238,0.08)]'
                      : 'border-white/8 bg-white/[0.025] text-slate-400 hover:border-white/16 hover:bg-white/[0.05] hover:text-white',
                  )}
                >
                  {item.label}
                </Link>
              ))}

              <div className="ml-auto hidden items-center gap-2 xl:flex">
                <div className="rounded-full border border-white/10 bg-[#091321] px-3 py-2 text-xs font-medium text-slate-300">
                  workspace.circuit
                </div>
              </div>
            </div>

            <div className="grid gap-3 px-4 py-4 lg:grid-cols-[minmax(0,1fr)_auto]">
              <div className="hidden min-w-0 flex-1 items-center gap-3 lg:flex">
                <div className="circuit-panel flex min-w-0 flex-1 items-center gap-3 rounded-[1.2rem] px-3.5 py-3">
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl border border-cyan-300/18 bg-cyan-300/10">
                    <LayoutPanelTop className="h-4 w-4 text-cyan-200" />
                  </div>
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
                <div className="hidden rounded-2xl border border-white/10 bg-[#0a1321] px-3 py-2 text-xs font-medium text-slate-300 lg:block">
                  Layout locked for evaluation
                </div>
              </div>

              <div className="hidden min-w-0 flex-wrap items-center gap-2 lg:flex lg:col-span-2">
                {workflow.map((item) => {
                  const active = activeHref === item.href;
                  return (
                    <Link
                      key={`${item.label}-${item.href}`}
                      href={item.href}
                      className={cn(
                        'group relative inline-flex min-w-[9.5rem] items-center gap-2 rounded-2xl border px-3 py-2 text-sm transition-colors',
                        active
                          ? 'border-cyan-300/30 bg-cyan-300/12'
                          : item.ready
                            ? 'border-white/10 bg-[#091321] hover:border-white/18'
                            : 'border-white/8 bg-[#07101b]',
                      )}
                    >
                      <div className={cn('h-2 w-2 rounded-full', item.ready ? 'bg-cyan-300' : 'bg-slate-600')} />
                      <div>
                        <div className="text-[10px] font-semibold uppercase tracking-[0.2em] text-slate-400">{item.label}</div>
                        <div className="hidden max-w-[11rem] truncate text-xs font-semibold text-white xl:block">{item.detail}</div>
                      </div>
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
            'grid gap-px bg-white/8 lg:grid-cols-[64px_248px_minmax(0,1fr)_360px] lg:h-[calc(100vh-9.7rem)]',
            bottom && bottomOpen ? 'lg:grid-rows-[minmax(0,1fr)_190px]' : 'lg:grid-rows-[minmax(0,1fr)_48px]',
          )}>
            <aside className="hidden overflow-hidden bg-[linear-gradient(180deg,#030812_0%,#08111e_100%)] lg:col-start-1 lg:block">
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

            <aside className="order-4 circuit-panel overflow-hidden rounded-none lg:order-none lg:col-start-2 lg:row-start-1">
              <div className="h-full overflow-y-auto p-4">{left}</div>
            </aside>

            <section className="order-1 overflow-hidden bg-[#050b14] lg:order-none lg:col-start-3 lg:row-start-1">
              <div className="h-full overflow-hidden">{main}</div>
            </section>

            <aside className="order-2 circuit-panel overflow-hidden lg:order-none lg:col-start-4 lg:row-start-1">
              <div className="h-full overflow-y-auto p-4">{right}</div>
            </aside>

            {bottom ? (
              <section className="order-3 relative overflow-hidden border-t border-white/8 bg-[linear-gradient(180deg,#060d17_0%,#081220_100%)] lg:order-none lg:col-start-2 lg:col-end-5 lg:row-start-2">
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

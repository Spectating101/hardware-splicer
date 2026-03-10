'use client';

import type { ReactNode } from 'react';
import Link from 'next/link';
import {
  CircuitBoard,
  Cpu,
  FolderKanban,
  House,
  PanelLeftClose,
  ScanSearch,
  SlidersHorizontal,
} from 'lucide-react';
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
  actions?: ReactNode;
  navItems: StudioNavItem[];
  activeHref: string;
  left: ReactNode;
  main: ReactNode;
  right: ReactNode;
};

export function StudioShell({
  eyebrow,
  title,
  description,
  status,
  actions,
  navItems,
  activeHref,
  left,
  main,
  right,
}: StudioShellProps) {
  const iconForHref = (href: string) => {
    if (href === '/') return House;
    if (href === '/analyze') return ScanSearch;
    if (href === '/components') return Cpu;
    if (href === '/projects') return FolderKanban;
    return CircuitBoard;
  };

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top_left,rgba(56,189,248,0.10),transparent_16%),radial-gradient(circle_at_80%_0%,rgba(249,115,22,0.08),transparent_18%),linear-gradient(180deg,#020617_0%,#050b14_100%)] text-slate-100">
      <main className="mx-auto max-w-[1820px] px-3 py-3 sm:px-4 lg:px-5">
        <section className="overflow-hidden rounded-[2rem] border border-white/10 bg-[linear-gradient(180deg,rgba(8,13,24,0.98),rgba(6,10,18,0.98))] shadow-[0_45px_120px_rgba(2,6,23,0.58)]">
          <div className="border-b border-white/10 bg-[linear-gradient(180deg,rgba(255,255,255,0.05),rgba(255,255,255,0.02))]">
            <div className="flex min-h-[68px] flex-wrap items-center gap-3 px-4 py-3 sm:px-5">
              <Link href="/" className="flex items-center gap-3">
                <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-[linear-gradient(135deg,#0f172a,#2563eb,#f97316)] text-white shadow-[0_14px_34px_rgba(37,99,235,0.30)]">
                  <CircuitBoard className="h-5 w-5" />
                </div>
                <div>
                  <div className="text-[11px] font-semibold uppercase tracking-[0.28em] text-cyan-200">{eyebrow}</div>
                  <div className="text-sm font-semibold text-white">Circuit.AI Studio</div>
                </div>
              </Link>

              <div className="hidden min-w-0 flex-1 items-center gap-3 lg:flex">
                <div className="min-w-0 flex-1 rounded-2xl border border-white/10 bg-white/[0.04] px-4 py-2.5">
                  <div className="truncate text-sm font-semibold text-white">{title}</div>
                  <div className="truncate text-xs text-slate-400">{description}</div>
                </div>
                {status ? (
                  <div className="rounded-full border border-emerald-400/20 bg-emerald-400/10 px-3 py-2 text-xs font-medium text-emerald-200">
                    {status}
                  </div>
                ) : null}
              </div>

              <div className="ml-auto flex items-center gap-2">
                {actions ? <div className="hidden items-center gap-2 md:flex">{actions}</div> : null}
                <button
                  type="button"
                  className="flex h-11 w-11 items-center justify-center rounded-2xl border border-white/10 bg-white/[0.05] text-slate-300"
                  aria-label="Studio layout"
                >
                  <PanelLeftClose className="h-4 w-4" />
                </button>
                <button
                  type="button"
                  className="flex h-11 w-11 items-center justify-center rounded-2xl border border-white/10 bg-white/[0.05] text-slate-300"
                  aria-label="Workspace preferences"
                >
                  <SlidersHorizontal className="h-4 w-4" />
                </button>
              </div>
            </div>

            <div className="flex flex-wrap gap-2 border-t border-white/8 px-4 py-3 sm:px-5">
              {navItems.map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    'rounded-xl px-3 py-2 text-sm font-medium transition-colors',
                    activeHref === item.href
                      ? 'bg-cyan-300 text-slate-950'
                      : 'text-slate-300 hover:bg-white/8 hover:text-white',
                  )}
                >
                  {item.label}
                </Link>
              ))}
              <div className="ml-auto hidden text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-500 xl:block">
                studio workspace
              </div>
            </div>
          </div>

          <section className="grid gap-px bg-white/8 lg:grid-cols-[64px_248px_minmax(0,1fr)_310px] lg:h-[calc(100vh-8.6rem)]">
            <aside className="hidden overflow-hidden bg-[linear-gradient(180deg,#07111d_0%,#09111f_100%)] lg:block">
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
                            : 'border-white/8 bg-white/[0.03] text-slate-400 hover:border-white/15 hover:bg-white/[0.06] hover:text-white',
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

            <aside className="overflow-hidden bg-[linear-gradient(180deg,#09111f_0%,#0b1322_100%)]">
              <div className="h-full overflow-y-auto p-3">{left}</div>
            </aside>

            <section className="overflow-hidden bg-[#07101d]">
              <div className="h-full overflow-hidden">{main}</div>
            </section>

            <aside className="overflow-hidden bg-[linear-gradient(180deg,#09111f_0%,#0b1322_100%)]">
              <div className="h-full overflow-y-auto p-3">{right}</div>
            </aside>
          </section>
        </section>
      </main>
    </div>
  );
}

'use client';

import type { ReactNode } from 'react';
import Link from 'next/link';
import { Crosshair, Grid2X2, Orbit, Radar, Route } from 'lucide-react';
import { cn } from '@/lib/utils';

export type CanvasTone = 'cyan' | 'amber' | 'emerald' | 'slate';

export type WorkbenchCanvasMetric = {
  label: string;
  value: string;
  tone?: CanvasTone;
};

export type WorkbenchCanvasNode = {
  id: string;
  title: string;
  description: string;
  badge?: string;
  x: string;
  y: string;
  tone?: CanvasTone;
  active?: boolean;
  onClick?: () => void;
};

export type WorkbenchCanvasAction = {
  href: string;
  label: string;
};

type WorkbenchCanvasProps = {
  toolbar: string[];
  activeToolbar: string;
  toolbarStatus: string;
  stageLabel: string;
  stageTitle: string;
  stageSummary: string;
  badge: string;
  metrics?: WorkbenchCanvasMetric[];
  notes?: string[];
  actions?: WorkbenchCanvasAction[];
  nodes?: WorkbenchCanvasNode[];
  contentInteractive?: boolean;
  children: ReactNode;
};

const toneStyles: Record<CanvasTone, string> = {
  cyan: 'border-cyan-300/22 bg-cyan-300/10 text-cyan-100',
  amber: 'border-amber-300/22 bg-amber-300/10 text-amber-100',
  emerald: 'border-emerald-300/22 bg-emerald-300/10 text-emerald-100',
  slate: 'border-white/10 bg-[#081423] text-slate-300',
};

export function WorkbenchCanvas({
  toolbar,
  activeToolbar,
  toolbarStatus,
  stageLabel,
  stageTitle,
  stageSummary,
  badge,
  metrics = [],
  notes = [],
  actions = [],
  nodes = [],
  contentInteractive = false,
  children,
}: WorkbenchCanvasProps) {
  return (
    <div className="grid h-full grid-rows-[48px_minmax(0,1fr)] bg-white/5">
      <div className="flex items-center justify-between border-b border-white/8 bg-[linear-gradient(180deg,#0a1424,#07101d)] px-4">
        <div className="flex items-center gap-2">
          {toolbar.map((item) => (
            <div
              key={item}
              aria-current={activeToolbar === item ? 'true' : undefined}
              className={cn(
                'rounded-full border px-3 py-1.5 text-xs font-semibold uppercase tracking-[0.16em] transition-colors',
                activeToolbar === item
                  ? 'border-cyan-300/22 bg-cyan-300/14 text-cyan-100'
                  : 'border-white/8 bg-white/[0.025] text-slate-500',
              )}
            >
              {item}
            </div>
          ))}
        </div>
        <div className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-slate-300">
          {toolbarStatus}
        </div>
      </div>

      <div className="min-h-0 overflow-hidden bg-[radial-gradient(circle_at_top,rgba(34,211,238,0.12),transparent_25%),linear-gradient(180deg,#091323_0%,#07111f_100%)] p-4">
        <div className="relative flex h-full flex-col overflow-hidden rounded-[1.45rem] border border-white/12 bg-[#07101b] shadow-[0_28px_80px_rgba(2,6,23,0.34),inset_0_1px_0_rgba(255,255,255,0.04)]">
          <div className="circuit-canvas-grid absolute inset-0 opacity-95" />
          <div className="circuit-ambient absolute inset-0 bg-[radial-gradient(circle_at_50%_42%,rgba(34,211,238,0.13),transparent_32%),radial-gradient(circle_at_23%_17%,rgba(251,146,60,0.12),transparent_20%),radial-gradient(circle_at_78%_82%,rgba(52,211,153,0.10),transparent_20%)]" />

          <div className="pointer-events-none absolute inset-0 opacity-80">
            <div className="absolute left-[8%] right-[8%] top-[50%] h-px bg-cyan-300/8" />
            <div className="absolute bottom-[10%] top-[10%] left-[50%] w-px bg-cyan-300/8" />
            <div className="absolute left-[14%] top-[18%] h-24 w-24 rounded-full border border-cyan-300/12" />
            <div className="absolute right-[12%] top-[22%] h-32 w-32 rounded-full border border-white/8" />
            <div className="absolute bottom-[16%] left-[26%] h-28 w-28 rounded-full border border-emerald-300/12" />
            <div className="absolute bottom-[14%] right-[24%] h-20 w-20 rounded-full border border-amber-300/12" />
          </div>

          <div className="pointer-events-none absolute left-3 top-3 z-10 max-w-[16rem] rounded-[1rem] border border-white/12 bg-[#06101d]/90 p-3 shadow-[0_24px_60px_rgba(2,6,23,0.35)] backdrop-blur-xl sm:left-4 sm:top-4 sm:max-w-md sm:rounded-[1.15rem] sm:p-4">
            <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.22em] text-slate-500">
              <Grid2X2 className="h-3.5 w-3.5 text-cyan-300" />
              {stageLabel}
            </div>
            <div className="mt-2 text-sm font-semibold text-white">{stageTitle}</div>
            <div className="mt-2 hidden text-sm leading-6 text-slate-300 sm:block">{stageSummary}</div>
          </div>

          <div className="pointer-events-none absolute right-4 top-4 z-10 hidden w-52 space-y-2 xl:block">
            {metrics.map((metric) => (
              <div
                key={`${metric.label}-${metric.value}`}
                className={cn(
                  'rounded-[1rem] border p-3 shadow-[0_18px_40px_rgba(2,6,23,0.22)] backdrop-blur-xl',
                  toneStyles[metric.tone || 'slate'],
                )}
              >
                <div className="text-[11px] uppercase tracking-[0.18em] text-slate-500">{metric.label}</div>
                <div className="mt-2 text-lg font-semibold text-white">{metric.value}</div>
              </div>
            ))}
          </div>

          <div className="pointer-events-none absolute bottom-4 left-4 z-10 hidden max-w-sm rounded-[1rem] border border-white/10 bg-[#06101d]/90 p-3 shadow-[0_18px_45px_rgba(2,6,23,0.28)] backdrop-blur-xl xl:block">
            <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-white">
              <Radar className="h-4 w-4 text-cyan-300" />
              Stage notes
            </div>
            <div className="space-y-2 text-sm leading-6 text-slate-300">
              {notes.map((note, index) => (
                <div key={`${note}-${index}`}>{note}</div>
              ))}
            </div>
          </div>

          <div className="pointer-events-none absolute bottom-4 right-4 z-10 hidden items-center gap-2 xl:flex">
            {actions.map((action) => (
              <Link
                key={action.href}
                href={action.href}
                className="pointer-events-auto inline-flex items-center gap-2 rounded-full border border-white/10 bg-[#081423]/88 px-3 py-2 text-sm text-slate-200 transition-colors hover:bg-white/10 hover:text-white"
              >
                <Route className="h-3.5 w-3.5 text-cyan-300" />
                {action.label}
              </Link>
            ))}
          </div>

          <div className="relative z-10 flex items-center justify-between border-b border-white/10 bg-black/10 px-4 py-3">
            <div>
              <div className="text-[11px] uppercase tracking-[0.22em] text-slate-500">Shared stage</div>
              <div className="mt-1 flex items-center gap-2 text-sm font-semibold text-white">
                <Orbit className="h-4 w-4 text-cyan-300" />
                AI-native workbench canvas
              </div>
            </div>
            <div className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-slate-300">
              {badge}
            </div>
          </div>

          <div className="relative flex min-h-0 flex-1 items-center justify-center overflow-hidden p-6">
            <div className="pointer-events-none absolute left-4 top-1/2 z-10 hidden -translate-y-1/2 rounded-full border border-white/8 bg-[#06101d]/85 px-2 py-5 text-[10px] font-semibold uppercase tracking-[0.22em] text-slate-500 [writing-mode:vertical-rl] xl:block">
              y axis
            </div>
            <div className="pointer-events-none absolute left-1/2 top-4 z-10 hidden -translate-x-1/2 rounded-full border border-white/8 bg-[#06101d]/85 px-5 py-2 text-[10px] font-semibold uppercase tracking-[0.22em] text-slate-500 xl:block">
              x axis
            </div>
            {nodes.map((node) => {
              const tone = toneStyles[node.tone || 'slate'];
              const sharedClassName = cn(
                'circuit-node absolute z-30 max-w-[13.5rem] rounded-[1rem] border px-3 py-3 text-left shadow-[0_18px_40px_rgba(2,6,23,0.32)] backdrop-blur-xl transition-all duration-200',
                'max-w-[9.5rem] px-2.5 py-2.5 sm:max-w-[13.5rem] sm:px-3 sm:py-3',
                tone,
                node.active
                  ? 'ring-2 ring-cyan-200/35 shadow-[0_24px_55px_rgba(8,145,178,0.26)]'
                  : 'opacity-95',
                node.onClick ? 'cursor-pointer hover:opacity-100' : 'pointer-events-none',
              );

              const content = (
                <>
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex min-w-0 items-center gap-2 text-sm font-semibold text-white">
                      <Crosshair className="h-3.5 w-3.5 shrink-0 text-current/70" />
                      <span className="truncate">{node.title}</span>
                    </div>
                    {node.badge ? (
                      <div className="rounded-full border border-white/10 bg-black/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.16em] text-white/85">
                        {node.badge}
                      </div>
                    ) : null}
                  </div>
                  <div className="mt-1.5 text-[11px] leading-4 text-slate-200 sm:mt-2 sm:text-xs sm:leading-5">{node.description}</div>
                </>
              );

              if (node.onClick) {
                return (
                  <button
                    key={node.id}
                    type="button"
                    onClick={node.onClick}
                    className={sharedClassName}
                    style={{ left: node.x, top: node.y }}
                  >
                    {content}
                  </button>
                );
              }

              return (
                <div key={node.id} className={sharedClassName} style={{ left: node.x, top: node.y }}>
                  {content}
                </div>
              );
            })}

            <div className={cn(
              'relative z-20 flex h-full w-full items-center justify-center',
              contentInteractive ? 'pointer-events-auto' : 'pointer-events-none',
            )}>{children}</div>
          </div>
        </div>
      </div>
    </div>
  );
}

'use client';

import type { ReactNode } from 'react';
import Link from 'next/link';
import { Grid2X2, Orbit, Radar, Route } from 'lucide-react';
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
    <div className="grid h-full grid-rows-[44px_minmax(0,1fr)] bg-white/5">
      <div className="flex items-center justify-between border-b border-white/8 bg-[#08111e] px-4">
        <div className="flex items-center gap-2">
          {toolbar.map((item) => (
            <div
              key={item}
              aria-current={activeToolbar === item ? 'true' : undefined}
              className={cn(
                'rounded-lg px-3 py-1.5 text-xs font-medium transition-colors',
                activeToolbar === item
                  ? 'bg-cyan-300/15 text-cyan-100'
                  : 'text-slate-500',
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

      <div className="min-h-0 overflow-hidden bg-[radial-gradient(circle_at_top,rgba(34,211,238,0.11),transparent_23%),linear-gradient(180deg,#0b1323_0%,#0b1627_100%)] p-3">
        <div className="relative flex h-full flex-col overflow-hidden rounded-[1.25rem] border border-white/10 bg-[#09111d] shadow-[inset_0_1px_0_rgba(255,255,255,0.03)]">
          <div className="absolute inset-0 bg-[linear-gradient(rgba(255,255,255,0.026)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.026)_1px,transparent_1px)] bg-[size:44px_44px] opacity-80" />
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_44%,rgba(34,211,238,0.08),transparent_30%),radial-gradient(circle_at_22%_16%,rgba(251,146,60,0.08),transparent_18%),radial-gradient(circle_at_78%_82%,rgba(52,211,153,0.07),transparent_18%)]" />

          <div className="pointer-events-none absolute inset-0">
            <div className="absolute left-[14%] top-[18%] h-24 w-24 rounded-full border border-cyan-300/10" />
            <div className="absolute right-[12%] top-[22%] h-32 w-32 rounded-full border border-white/8" />
            <div className="absolute bottom-[16%] left-[26%] h-28 w-28 rounded-full border border-emerald-300/10" />
            <div className="absolute bottom-[14%] right-[24%] h-20 w-20 rounded-full border border-amber-300/10" />
          </div>

          <div className="pointer-events-none absolute left-4 top-4 z-10 max-w-md rounded-[1rem] border border-white/10 bg-[#081423]/88 p-4 backdrop-blur">
            <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.22em] text-slate-500">
              <Grid2X2 className="h-3.5 w-3.5 text-cyan-300" />
              {stageLabel}
            </div>
            <div className="mt-2 text-sm font-semibold text-white">{stageTitle}</div>
            <div className="mt-2 text-sm leading-6 text-slate-300">{stageSummary}</div>
          </div>

          <div className="pointer-events-none absolute right-4 top-4 z-10 hidden w-52 space-y-2 xl:block">
            {metrics.map((metric) => (
              <div
                key={`${metric.label}-${metric.value}`}
                className={cn(
                  'rounded-[1rem] border p-3 backdrop-blur',
                  toneStyles[metric.tone || 'slate'],
                )}
              >
                <div className="text-[11px] uppercase tracking-[0.18em] text-slate-500">{metric.label}</div>
                <div className="mt-2 text-lg font-semibold text-white">{metric.value}</div>
              </div>
            ))}
          </div>

          <div className="pointer-events-none absolute bottom-4 left-4 z-10 hidden max-w-sm rounded-[1rem] border border-white/10 bg-[#081423]/88 p-3 backdrop-blur xl:block">
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

          <div className="relative z-10 flex items-center justify-between border-b border-white/10 px-4 py-3">
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

          <div className="relative flex min-h-0 flex-1 items-center justify-center overflow-hidden p-5">
            {nodes.map((node) => {
              const tone = toneStyles[node.tone || 'slate'];
              const sharedClassName = cn(
                'absolute z-30 max-w-[13rem] rounded-[1rem] border px-3 py-3 text-left shadow-[0_18px_40px_rgba(2,6,23,0.32)] backdrop-blur transition-all',
                tone,
                node.active
                  ? 'scale-[1.02] shadow-[0_24px_48px_rgba(8,145,178,0.24)]'
                  : 'opacity-95',
                node.onClick ? 'cursor-pointer hover:-translate-y-0.5 hover:opacity-100' : 'pointer-events-none',
              );

              const content = (
                <>
                  <div className="flex items-start justify-between gap-3">
                    <div className="text-sm font-semibold text-white">{node.title}</div>
                    {node.badge ? (
                      <div className="rounded-full border border-white/10 bg-black/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.16em] text-white/85">
                        {node.badge}
                      </div>
                    ) : null}
                  </div>
                  <div className="mt-2 text-xs leading-5 text-slate-200">{node.description}</div>
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

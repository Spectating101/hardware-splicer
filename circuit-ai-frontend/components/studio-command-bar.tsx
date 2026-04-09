'use client';

import { Bot, BrainCircuit, Sparkles } from 'lucide-react';

type StudioCommandBarProps = {
  modeLabel: string;
  objective: string;
  context: string;
  status: string;
  badges?: string[];
};

export function StudioCommandBar({
  modeLabel,
  objective,
  context,
  status,
  badges = [],
}: StudioCommandBarProps) {
  return (
    <div className="flex min-w-[24rem] max-w-[42rem] items-center gap-3 rounded-2xl border border-white/10 bg-white/[0.04] px-3 py-2 text-left shadow-[inset_0_1px_0_rgba(255,255,255,0.03)]">
      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl border border-cyan-300/16 bg-cyan-300/10 text-cyan-200">
        <BrainCircuit className="h-4 w-4" />
      </div>

      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <div className="text-[10px] font-semibold uppercase tracking-[0.22em] text-cyan-200">{modeLabel}</div>
          <div className="rounded-full border border-emerald-400/20 bg-emerald-400/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.16em] text-emerald-100">
            {status}
          </div>
        </div>
        <div className="mt-1 truncate text-sm font-semibold text-white">{objective}</div>
        <div className="mt-1 truncate text-xs text-slate-400">{context}</div>
      </div>

      {badges.length ? (
        <div className="hidden shrink-0 flex-wrap items-center justify-end gap-1.5 xl:flex">
          {badges.slice(0, 3).map((badge, index) => (
            <div
              key={`${badge}-${index}`}
              className="inline-flex items-center gap-1 rounded-full border border-white/10 bg-[#081423] px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-300"
            >
              {index === 0 ? <Bot className="h-3 w-3 text-cyan-300" /> : <Sparkles className="h-3 w-3 text-amber-300" />}
              {badge}
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}

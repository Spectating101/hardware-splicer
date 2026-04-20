"use client";

import { AlertTriangle, AlertCircle, Info, CheckCircle2 } from "lucide-react";
import type { BuildWarning } from "@/lib/rules/safety-rules";

const LEVEL_ICON = {
  error: AlertCircle,
  warn: AlertTriangle,
  info: Info,
} as const;

const LEVEL_COLOR = {
  error: "text-rose-300 border-rose-400/40 bg-rose-500/5",
  warn: "text-amber-300 border-amber-400/40 bg-amber-500/5",
  info: "text-sky-300 border-sky-400/40 bg-sky-500/5",
} as const;

export function SafetyCheckPanel({ warnings, onFocus }: {
  warnings: BuildWarning[];
  onFocus?(w: BuildWarning): void;
}) {
  if (warnings.length === 0) {
    return (
      <div className="flex items-center gap-2 rounded-xl border border-emerald-400/30 bg-emerald-500/5 p-3 text-sm text-emerald-200">
        <CheckCircle2 className="h-4 w-4" />
        No safety issues detected.
      </div>
    );
  }

  const order = { error: 0, warn: 1, info: 2 };
  const sorted = [...warnings].sort((a, b) => order[a.level] - order[b.level]);

  return (
    <div className="space-y-2">
      <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
        Safety checks ({warnings.length})
      </div>
      {sorted.map((w) => {
        const Icon = LEVEL_ICON[w.level];
        return (
          <button
            key={w.id}
            onClick={() => onFocus?.(w)}
            className={`flex w-full items-start gap-2 rounded-lg border px-3 py-2 text-left text-xs leading-5 transition-colors ${LEVEL_COLOR[w.level]}`}
          >
            <Icon className="mt-0.5 h-3.5 w-3.5 shrink-0" />
            <span>{w.message}</span>
          </button>
        );
      })}
    </div>
  );
}

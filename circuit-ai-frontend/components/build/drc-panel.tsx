"use client";

import { AlertCircle, AlertTriangle, CheckCircle2, ShieldCheck } from "lucide-react";
import type { DrcResult, DrcViolation } from "@/lib/pcb/drc";

const SEV_ICON = { error: AlertCircle, warn: AlertTriangle } as const;
const SEV_COLOR = {
  error: "text-rose-300 border-rose-400/40 bg-rose-500/5",
  warn: "text-amber-300 border-amber-400/40 bg-amber-500/5",
} as const;

export function DrcPanel({ drc, onFocus }: {
  drc: DrcResult | null;
  onFocus?(at: { x: number; y: number }): void;
}) {
  if (!drc || drc.violations.length === 0) {
    return (
      <div className="flex items-center gap-2 rounded-xl border border-emerald-400/30 bg-emerald-500/5 p-3 text-sm text-emerald-200">
        <ShieldCheck className="h-4 w-4" />
        DRC clean — no fab-rule violations (JLCPCB 2-layer).
      </div>
    );
  }

  const { errors, warnings } = drc.summary;
  const order = { error: 0, warn: 1 } as const;
  const sorted = [...drc.violations].sort(
    (a, b) => order[a.severity] - order[b.severity],
  );

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
          Design rule check
        </div>
        <div
          className={`flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[10px] font-medium ${
            drc.pass
              ? "border-amber-400/40 bg-amber-500/5 text-amber-300"
              : "border-rose-400/40 bg-rose-500/5 text-rose-300"
          }`}
        >
          {drc.pass ? (
            <CheckCircle2 className="h-3 w-3" />
          ) : (
            <AlertCircle className="h-3 w-3" />
          )}
          {drc.pass
            ? `${warnings} warning${warnings === 1 ? "" : "s"} — manufacturable`
            : `${errors} error${errors === 1 ? "" : "s"} — not manufacturable`}
        </div>
      </div>

      {sorted.slice(0, 40).map((vi: DrcViolation, i) => {
        const Icon = SEV_ICON[vi.severity];
        return (
          <button
            key={i}
            onClick={() => vi.at && onFocus?.(vi.at)}
            className={`flex w-full items-start gap-2 rounded-lg border px-3 py-2 text-left text-xs leading-5 transition-colors ${SEV_COLOR[vi.severity]}`}
          >
            <Icon className="mt-0.5 h-3.5 w-3.5 shrink-0" />
            <span>
              <span className="font-mono text-[10px] uppercase opacity-60">
                {vi.rule}
              </span>{" "}
              {vi.message}
            </span>
          </button>
        );
      })}
      {sorted.length > 40 && (
        <div className="px-1 text-[10px] text-slate-500">
          +{sorted.length - 40} more…
        </div>
      )}
    </div>
  );
}

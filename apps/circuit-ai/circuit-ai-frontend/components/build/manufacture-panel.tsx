"use client";

import { AlertCircle, AlertTriangle, CheckCircle2, Download, Loader2 } from "lucide-react";

export interface MfgResult {
  busy: boolean;
  error?: string;
  dfm?: {
    manufacturing_ready: boolean;
    critical: number;
    errors: number;
    warnings: number;
    issues: Array<{ severity: string; component?: string; issue: string; solution?: string }>;
  };
  gerber?: {
    filename?: string;
    manufacturing_ready?: boolean;
    cost?: Record<string, { price_usd?: number; lead_time_days?: string | number }>;
  };
}

export function ManufacturePanel({ mfg }: { mfg: MfgResult | null }) {
  if (!mfg) return null;

  if (mfg.busy) {
    return (
      <div className="flex items-center gap-2 rounded-xl border border-sky-400/30 bg-sky-500/5 p-3 text-sm text-sky-200">
        <Loader2 className="h-4 w-4 animate-spin" />
        Running real DFM preflight + Gerber generation…
      </div>
    );
  }

  if (mfg.error) {
    return (
      <div className="flex items-start gap-2 rounded-xl border border-rose-400/40 bg-rose-500/5 p-3 text-xs text-rose-200">
        <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
        <span>Manufacture failed: {mfg.error}</span>
      </div>
    );
  }

  const dfm = mfg.dfm;
  const ready = dfm?.manufacturing_ready ?? false;
  const jlc = mfg.gerber?.cost?.JLCPCB;

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
          Manufacture preflight
        </div>
        {dfm && (
          <div
            className={`flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[10px] font-medium ${
              ready
                ? "border-emerald-400/40 bg-emerald-500/5 text-emerald-300"
                : "border-rose-400/40 bg-rose-500/5 text-rose-300"
            }`}
          >
            {ready ? <CheckCircle2 className="h-3 w-3" /> : <AlertCircle className="h-3 w-3" />}
            {ready
              ? "Manufacturing-ready"
              : `${dfm.critical}c / ${dfm.errors}e / ${dfm.warnings}w`}
          </div>
        )}
      </div>

      {dfm?.issues?.slice(0, 6).map((it, i) => {
        const sev = it.severity === "critical" || it.severity === "error";
        const Icon = sev ? AlertCircle : AlertTriangle;
        return (
          <div
            key={i}
            className={`flex items-start gap-2 rounded-lg border px-3 py-2 text-xs leading-5 ${
              sev
                ? "border-rose-400/40 bg-rose-500/5 text-rose-200"
                : "border-amber-400/40 bg-amber-500/5 text-amber-200"
            }`}
          >
            <Icon className="mt-0.5 h-3.5 w-3.5 shrink-0" />
            <span>
              <span className="font-mono text-[10px] uppercase opacity-60">{it.severity}</span>{" "}
              {it.component ? <b>{it.component}: </b> : null}
              {it.issue}
              {it.solution ? <span className="opacity-70"> — {it.solution}</span> : null}
            </span>
          </div>
        );
      })}

      {mfg.gerber?.filename && (
        <a
          href={`/api/proxy/manufacture/download-gerber/${encodeURIComponent(mfg.gerber.filename)}`}
          className="flex items-center justify-between rounded-lg border border-violet-400/40 bg-violet-500/10 px-3 py-2 text-xs font-medium text-violet-200 hover:bg-violet-500/20"
        >
          <span className="inline-flex items-center gap-2">
            <Download className="h-3.5 w-3.5" /> Download Gerber ZIP
          </span>
          {jlc?.price_usd != null && (
            <span className="text-[10px] text-violet-300/80">
              JLCPCB ≈ ${jlc.price_usd} · {String(jlc.lead_time_days ?? "?")}d
            </span>
          )}
        </a>
      )}
    </div>
  );
}

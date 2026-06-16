"use client";

import { AlertCircle, CheckCircle2, Loader2, RefreshCw, ShieldCheck } from "lucide-react";
import type { EngineCompileProof } from "@/lib/hardware-splicer/engine-proof";

export function EngineProofPanel({
  proof,
  busy,
  error,
  onRefresh,
}: {
  proof: EngineCompileProof | null;
  busy: boolean;
  error: string | null;
  onRefresh(): void;
}) {
  if (error && !proof) {
    return (
      <div className="space-y-2 rounded-xl border border-amber-400/30 bg-amber-500/5 p-3">
        <div className="flex items-center justify-between gap-2">
          <div className="text-[11px] font-semibold uppercase tracking-wider text-amber-200">
            KiCad verification
          </div>
          <button
            type="button"
            onClick={onRefresh}
            disabled={busy}
            className="inline-flex items-center gap-1 rounded-full border border-white/10 px-2 py-0.5 text-[10px] text-slate-200 hover:bg-white/10 disabled:opacity-50"
          >
            <RefreshCw className={`h-3 w-3 ${busy ? "animate-spin" : ""}`} />
            Retry
          </button>
        </div>
        <p className="text-xs leading-5 text-amber-100">{error}</p>
      </div>
    );
  }

  if (busy && !proof) {
    return (
      <div className="flex items-center gap-2 rounded-xl border border-sky-400/30 bg-sky-500/5 p-3 text-sm text-sky-200">
        <Loader2 className="h-4 w-4 animate-spin" />
        Running KiCad compile + DRC on the Python engine…
      </div>
    );
  }

  if (!proof) {
    return (
      <div className="rounded-xl border border-white/10 bg-white/[0.02] p-3 text-xs leading-5 text-slate-400">
        Add at least two modules — KiCad verification runs automatically when the engine is online.
      </div>
    );
  }

  const ready = proof.kicadDrcPass && proof.buildReady;
  const staleNote =
    Date.now() - proof.verifiedAt > 120_000
      ? " (may be stale — edit canvas or tap Re-verify)"
      : "";

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between gap-2">
        <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
          KiCad verification (authoritative)
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onRefresh}
            disabled={busy}
            className="inline-flex items-center gap-1 rounded-full border border-white/10 px-2 py-0.5 text-[10px] text-slate-200 hover:bg-white/10 disabled:opacity-50"
          >
            <RefreshCw className={`h-3 w-3 ${busy ? "animate-spin" : ""}`} />
            Re-verify
          </button>
          <div
            className={`flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[10px] font-medium ${
              ready
                ? "border-emerald-400/40 bg-emerald-500/5 text-emerald-300"
                : "border-rose-400/40 bg-rose-500/5 text-rose-300"
            }`}
          >
            {ready ? <ShieldCheck className="h-3 w-3" /> : <AlertCircle className="h-3 w-3" />}
            {ready
              ? `KiCad DRC clean${staleNote}`
              : `${proof.kicadDrcErrors} KiCad error${proof.kicadDrcErrors === 1 ? "" : "s"}`}
          </div>
        </div>
      </div>

      <div className="rounded-lg border border-white/10 bg-black/30 px-3 py-2 text-[11px] leading-5 text-slate-300">
        <div className="flex flex-wrap gap-x-3 gap-y-1">
          <span>KiCad warnings: {proof.kicadDrcWarnings}</span>
          <span>Electrical: {proof.electricalErrors}e / {proof.electricalWarnings}w</span>
          <span>BOM: {proof.bomReady ? "ready" : "missing"}</span>
          <span>Gerbers: {proof.gerberReady ? "ready" : "not exported"}</span>
        </div>
        {proof.fabricationReady && (
          <div className="mt-1 flex items-center gap-1 text-emerald-300">
            <CheckCircle2 className="h-3 w-3" />
            Fabrication gate passed on engine artifacts.
          </div>
        )}
        {proof.blockers.slice(0, 3).map((blocker) => (
          <div key={blocker} className="mt-1 text-rose-200">
            {blocker}
          </div>
        ))}
      </div>
    </div>
  );
}

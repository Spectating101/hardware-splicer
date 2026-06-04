"use client";

import { useCallback, useState } from "react";
import {
  Package, DollarSign, ShieldCheck, Ship, Download, Loader2,
  TrendingUp, TrendingDown, Clock, AlertCircle, Check, Factory,
} from "lucide-react";
import type { PcbGeometry } from "@/lib/cad-types";
import type {
  WorkbenchPipeline, SpiceResult, DfmReport, BomCost,
} from "@/lib/workbench-store";

interface BomRow {
  ref: string;
  value: string;
  qty: number;
  unitUsd: number | null;
  extUsd: number | null;
  supplier?: string;
  stock?: number;
  risk?: "ok" | "low_stock" | "eol" | "unknown";
}

export interface ShipPanelProps {
  geometry: PcbGeometry | null;
  filename: string | null;
  pipeline: WorkbenchPipeline;
  spiceResult: SpiceResult | null;
  dfmReport: DfmReport | null;
  bomCost: BomCost | null;
  onPrice(): void;
  onDfm(): void;
  onPackage(): void;
  onGerber(): void;
  onPnp(): void;
}

function StatLine({ Icon, label, value, sub, tone = "neutral" }: {
  Icon: typeof Package;
  label: string;
  value: string;
  sub?: string;
  tone?: "neutral" | "good" | "warn" | "bad";
}) {
  const toneCls = {
    neutral: "text-white/75",
    good:    "text-emerald-300",
    warn:    "text-amber-300",
    bad:     "text-red-300",
  }[tone];
  return (
    <div className="flex items-center gap-2.5 py-1.5">
      <Icon size={13} className="text-white/35 flex-shrink-0" />
      <div className="flex-1 min-w-0">
        <div className="text-[10px] uppercase tracking-wider text-white/35 leading-none">{label}</div>
        <div className={`text-[13px] font-medium ${toneCls} leading-tight`}>{value}</div>
        {sub && <div className="text-[10px] text-white/30 leading-tight">{sub}</div>}
      </div>
    </div>
  );
}

export function ShipPanel(props: ShipPanelProps) {
  const { geometry, pipeline, dfmReport, bomCost, onPrice, onDfm, onPackage, onGerber, onPnp } = props;
  const [qty, setQty] = useState(5);
  const [fab, setFab] = useState<"jlcpcb" | "pcbway" | "oshpark">("jlcpcb");

  // Derive a cheap synthetic BOM preview from the parsed geometry when backend
  // hasn't priced yet — so the panel is informative the moment you click Ship.
  const derivedBom = useCallback((): BomRow[] => {
    if (!geometry) return [];
    const grouped = new Map<string, BomRow>();
    for (const fp of geometry.footprints) {
      const key = fp.value || fp.footprint || "unknown";
      const prev = grouped.get(key);
      if (prev) prev.qty += 1;
      else grouped.set(key, {
        ref: fp.ref, value: key, qty: 1, unitUsd: null, extUsd: null, risk: "unknown",
      });
    }
    return [...grouped.values()].sort((a, b) => b.qty - a.qty);
  }, [geometry]);

  const bom = derivedBom();
  const bomReady = bomCost != null;

  // Gate everything on pipeline.validated — ship mode is meaningful only after validate.
  const gated = !pipeline.validated;

  return (
    <div className="w-[320px] flex-shrink-0 bg-[#0b1220] border-l border-white/8 flex flex-col overflow-hidden">
      {/* Header */}
      <div className="flex-shrink-0 px-4 py-3 border-b border-white/8 flex items-center gap-2">
        <div className="w-6 h-6 rounded-md bg-emerald-500/15 flex items-center justify-center">
          <Ship size={12} className="text-emerald-300" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-xs font-semibold text-white/80 leading-none">Ship</div>
          <div className="text-[10px] text-white/35 leading-tight mt-0.5">
            {gated ? "Validate the board first" : "Ready to cost, check, package"}
          </div>
        </div>
      </div>

      {gated ? (
        <div className="flex-1 flex items-center justify-center p-6 text-center">
          <div className="space-y-2">
            <AlertCircle size={20} className="text-white/20 mx-auto" />
            <p className="text-[11px] text-white/40">Ship mode needs a validated board.</p>
            <p className="text-[10px] text-white/25">Run validation from Inspect mode, then switch back.</p>
          </div>
        </div>
      ) : (
        <div className="flex-1 overflow-y-auto">
          {/* Order config */}
          <div className="px-4 py-3 border-b border-white/8">
            <div className="text-[10px] uppercase tracking-widest text-white/30 font-semibold mb-2">Order</div>
            <div className="grid grid-cols-2 gap-2">
              <label className="flex flex-col gap-1">
                <span className="text-[10px] text-white/45">Quantity</span>
                <input
                  type="number"
                  min={1} max={10000}
                  value={qty}
                  onChange={(e) => setQty(Math.max(1, Number(e.target.value) || 1))}
                  className="bg-white/5 border border-white/10 rounded-md px-2 py-1 text-xs text-white/85 outline-none focus:border-emerald-400/40"
                />
              </label>
              <label className="flex flex-col gap-1">
                <span className="text-[10px] text-white/45">Fab house</span>
                <select
                  value={fab}
                  onChange={(e) => setFab(e.target.value as typeof fab)}
                  className="bg-white/5 border border-white/10 rounded-md px-2 py-1 text-xs text-white/85 outline-none focus:border-emerald-400/40"
                >
                  <option value="jlcpcb">JLCPCB</option>
                  <option value="pcbway">PCBWay</option>
                  <option value="oshpark">OSH Park</option>
                </select>
              </label>
            </div>
          </div>

          {/* DFM */}
          <div className="px-4 py-3 border-b border-white/8">
            <div className="flex items-center justify-between mb-1.5">
              <div className="text-[10px] uppercase tracking-widest text-white/30 font-semibold">DFM</div>
              <button
                onClick={onDfm}
                className="text-[10px] text-emerald-300/80 hover:text-emerald-200 underline-offset-2 hover:underline"
              >
                {dfmReport ? "re-check" : "run check"}
              </button>
            </div>
            {dfmReport ? (
              <div className="space-y-0.5">
                <StatLine
                  Icon={ShieldCheck}
                  label="Manufacturability"
                  value={`${dfmReport.score}/100`}
                  sub={dfmReport.fab ?? fabLabel(fab)}
                  tone={dfmReport.critical > 0 ? "bad" : dfmReport.warnings > 0 ? "warn" : "good"}
                />
                <div className="flex gap-2 mt-1">
                  <Pill tone={dfmReport.critical > 0 ? "bad" : "idle"} label={`${dfmReport.critical} critical`} />
                  <Pill tone={dfmReport.warnings > 0 ? "warn" : "idle"} label={`${dfmReport.warnings} warn`} />
                </div>
              </div>
            ) : (
              <p className="text-[11px] text-white/30">No DFM report yet. Click <span className="text-emerald-300">run check</span> to verify against {fabLabel(fab)}.</p>
            )}
          </div>

          {/* BOM */}
          <div className="px-4 py-3 border-b border-white/8">
            <div className="flex items-center justify-between mb-2">
              <div className="text-[10px] uppercase tracking-widest text-white/30 font-semibold">
                BOM · {bom.length} line{bom.length === 1 ? "" : "s"}
              </div>
              <button
                onClick={onPrice}
                className="text-[10px] text-emerald-300/80 hover:text-emerald-200 underline-offset-2 hover:underline"
              >
                {bomReady ? "refresh prices" : "fetch live prices"}
              </button>
            </div>
            <div className="space-y-0.5 max-h-[220px] overflow-y-auto -mx-1 pr-1">
              {bom.length === 0 && <p className="text-[11px] text-white/30">No components.</p>}
              {bom.map((row) => (
                <div key={row.value} className="flex items-center gap-2 px-1 py-1 rounded-md hover:bg-white/[0.03]">
                  <span className="text-[10px] font-mono text-white/70 w-8 text-right flex-shrink-0">×{row.qty}</span>
                  <span className="text-[11px] text-white/75 flex-1 truncate">{row.value}</span>
                  <span className="text-[11px] font-mono text-white/40 flex-shrink-0">
                    {row.unitUsd != null ? `$${row.unitUsd.toFixed(2)}` : "—"}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Cost total */}
          <div className="px-4 py-3 border-b border-white/8 bg-emerald-500/[0.04]">
            <div className="text-[10px] uppercase tracking-widest text-white/30 font-semibold mb-2">Total</div>
            {bomCost ? (
              <div className="space-y-0.5">
                <div className="flex items-baseline justify-between">
                  <span className="text-[11px] text-white/50">Unit BOM</span>
                  <span className="text-[12px] font-mono text-white/85">${bomCost.unitUsd.toFixed(2)}</span>
                </div>
                <div className="flex items-baseline justify-between">
                  <span className="text-[11px] text-white/50">× {bomCost.qty} boards</span>
                  <span className="text-[13px] font-mono text-emerald-300 font-semibold">${bomCost.totalUsd.toFixed(2)}</span>
                </div>
                <div className="flex items-center gap-1.5 pt-1">
                  <Clock size={10} className="text-white/30" />
                  <span className="text-[10px] text-white/40">{bomCost.leadDays} day lead time</span>
                </div>
              </div>
            ) : (
              <p className="text-[11px] text-white/40">Run live pricing to see <span className="text-emerald-300 font-medium">$ total</span> and lead time.</p>
            )}
          </div>

          {/* Actions */}
          <div className="px-4 py-3 space-y-2">
            <div className="text-[10px] uppercase tracking-widest text-white/30 font-semibold mb-1">Fab package</div>
            <FabAction Icon={Download} label="Download Gerbers" accent="cyan" onClick={onGerber} busy={pipeline.manufacturing} done={pipeline.manufactured} />
            <FabAction Icon={Factory}  label="Pick-and-place (PnP)" accent="violet" onClick={onPnp} />
            <FabAction Icon={Package}  label="Full fab package (.zip)" accent="emerald" onClick={onPackage} primary />
          </div>
        </div>
      )}
    </div>
  );
}

function Pill({ tone, label }: { tone: "idle" | "warn" | "bad"; label: string }) {
  const cls = {
    idle: "bg-white/5 text-white/40 border-white/10",
    warn: "bg-amber-500/15 text-amber-200 border-amber-500/30",
    bad:  "bg-red-500/15 text-red-200 border-red-500/30",
  }[tone];
  return <span className={`inline-flex items-center border rounded-full px-2 py-0.5 text-[10px] font-medium ${cls}`}>{label}</span>;
}

function FabAction({ Icon, label, accent, onClick, busy, done, primary }: {
  Icon: typeof Download;
  label: string;
  accent: "cyan" | "violet" | "emerald";
  onClick(): void;
  busy?: boolean;
  done?: boolean;
  primary?: boolean;
}) {
  const bg = {
    cyan:    primary ? "bg-cyan-500/20 hover:bg-cyan-500/30 border-cyan-500/40 text-cyan-100"         : "bg-white/[0.04] hover:bg-cyan-500/10 border-white/10 hover:border-cyan-500/30 text-white/75",
    violet:  primary ? "bg-violet-500/20 hover:bg-violet-500/30 border-violet-500/40 text-violet-100" : "bg-white/[0.04] hover:bg-violet-500/10 border-white/10 hover:border-violet-500/30 text-white/75",
    emerald: primary ? "bg-emerald-500/20 hover:bg-emerald-500/30 border-emerald-500/40 text-emerald-100" : "bg-white/[0.04] hover:bg-emerald-500/10 border-white/10 hover:border-emerald-500/30 text-white/75",
  }[accent];
  return (
    <button
      onClick={onClick}
      disabled={busy}
      className={`w-full flex items-center gap-2 px-3 py-2 rounded-lg border text-[11.5px] font-medium transition-all disabled:opacity-50 ${bg}`}
    >
      {busy ? <Loader2 size={12} className="animate-spin" /> : done ? <Check size={12} /> : <Icon size={12} />}
      <span className="flex-1 text-left">{label}</span>
      {done && !busy && <span className="text-[10px] text-emerald-300/80">ready</span>}
    </button>
  );
}

function fabLabel(f: string): string {
  return f === "jlcpcb" ? "JLCPCB 2-layer FR4" : f === "pcbway" ? "PCBWay" : "OSH Park";
}

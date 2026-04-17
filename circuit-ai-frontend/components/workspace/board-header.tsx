"use client";

import {
  Zap, FileCode, Plus, Eye, Wand2, Package,
  Upload, ScanSearch, Waves, ShieldCheck, DollarSign, Ship,
  type LucideIcon,
} from "lucide-react";
import type {
  WorkbenchPipeline, RenderMode, WorkbenchMode,
  SpiceResult, DfmReport, BomCost,
} from "@/lib/workbench-store";

interface BoardHeaderProps {
  filename: string | null;
  pipeline: WorkbenchPipeline;
  healthScore: number | null;
  issueCount: number;
  criticalCount: number;
  componentCount: number;
  spiceResult: SpiceResult | null;
  dfmReport: DfmReport | null;
  bomCost: BomCost | null;
  renderMode: RenderMode;
  mode: WorkbenchMode;
  onSetRenderMode(mode: RenderMode): void;
  onSetMode(mode: WorkbenchMode): void;
  onValidate(): void;
  onManufacture(): void;
  onNew(): void;
}

/* ─── Mode switcher ────────────────────────────────────────────────────── */

const MODES: Array<{ key: WorkbenchMode; label: string; hint: string; Icon: LucideIcon; accent: string }> = [
  { key: "inspect", label: "Inspect", hint: "Read the board — nets, issues, simulation",  Icon: Eye,     accent: "cyan" },
  { key: "iterate", label: "Iterate", hint: "Ask Jarvis to improve the design",            Icon: Wand2,   accent: "violet" },
  { key: "ship",    label: "Ship",    hint: "BOM, pricing, DFM, fab package",              Icon: Package, accent: "emerald" },
];

function ModeSwitcher({ value, onChange }: { value: WorkbenchMode; onChange(v: WorkbenchMode): void }) {
  return (
    <div className="inline-flex items-center rounded-lg border border-white/10 bg-black/30 p-0.5 text-[11px] font-medium">
      {MODES.map(({ key, label, hint, Icon, accent }) => {
        const active = value === key;
        const activeCls =
          accent === "cyan"    ? "bg-cyan-500/20 text-cyan-200 shadow-[0_0_0_1px_rgba(34,211,238,0.35)]"    :
          accent === "violet"  ? "bg-violet-500/20 text-violet-200 shadow-[0_0_0_1px_rgba(167,139,250,0.35)]" :
                                 "bg-emerald-500/20 text-emerald-200 shadow-[0_0_0_1px_rgba(16,185,129,0.35)]";
        return (
          <button
            key={key}
            onClick={() => onChange(key)}
            title={hint}
            className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md transition-colors ${
              active ? activeCls : "text-white/45 hover:text-white/75"
            }`}
          >
            <Icon size={11} />
            {label}
          </button>
        );
      })}
    </div>
  );
}

/* ─── Render-mode micro-toggle ─────────────────────────────────────────── */

function RenderModeToggle({ value, onChange }: { value: RenderMode; onChange(v: RenderMode): void }) {
  const isEng = value === "engineering";
  return (
    <div className="inline-flex items-center rounded-full border border-white/10 bg-white/[0.03] p-0.5 text-[10px] font-medium">
      <button
        onClick={() => onChange("engineering")}
        className={`px-2 py-0.5 rounded-full transition-colors ${
          isEng ? "bg-cyan-500/20 text-cyan-200" : "text-white/40 hover:text-white/70"
        }`}
        title="Flat diagram — copper-primary engineering view"
      >
        Diagram
      </button>
      <button
        onClick={() => onChange("production")}
        className={`px-2 py-0.5 rounded-full transition-colors ${
          !isEng ? "bg-emerald-500/20 text-emerald-200" : "text-white/40 hover:text-white/70"
        }`}
        title="Photoreal — opaque solder mask, product-photo look"
      >
        Photoreal
      </button>
    </div>
  );
}

/* ─── Pipeline spine ───────────────────────────────────────────────────── */

type StepState = "done" | "active" | "pending" | "locked";

interface SpineStep {
  key: string;
  label: string;
  Icon: LucideIcon;
  state: StepState;
  value: string | null;
  subtitle: string;
  onClick?: () => void;
}

function stateCls(s: StepState): { dot: string; label: string; val: string } {
  switch (s) {
    case "done":    return { dot: "bg-emerald-400", label: "text-emerald-200", val: "text-emerald-300" };
    case "active":  return { dot: "bg-amber-400 animate-pulse", label: "text-amber-200", val: "text-amber-300" };
    case "pending": return { dot: "bg-white/25", label: "text-white/60", val: "text-white/40" };
    case "locked":  return { dot: "bg-white/10", label: "text-white/25", val: "text-white/20" };
  }
}

function PipelineSpine({ steps }: { steps: SpineStep[] }) {
  return (
    <div className="flex-1 min-w-0 overflow-x-auto">
      <div className="inline-flex items-stretch gap-0 h-9 min-w-full">
        {steps.map((step, i) => {
          const c = stateCls(step.state);
          const isLast = i === steps.length - 1;
          const clickable = !!step.onClick && step.state !== "locked";
          return (
            <div key={step.key} className="flex items-stretch flex-shrink-0">
              <button
                disabled={!clickable}
                onClick={step.onClick}
                title={`${step.label} — ${step.subtitle}`}
                className={`flex items-center gap-1.5 px-2.5 rounded-md transition-colors ${
                  clickable ? "hover:bg-white/5 cursor-pointer" : "cursor-default"
                }`}
              >
                <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${c.dot}`} />
                <step.Icon size={11} className={c.label} />
                <div className="flex flex-col items-start leading-tight">
                  <span className={`text-[9.5px] uppercase tracking-wide font-semibold ${c.label}`}>
                    {step.label}
                  </span>
                  <span className={`text-[10px] font-mono ${c.val}`}>
                    {step.value ?? "—"}
                  </span>
                </div>
              </button>
              {!isLast && (
                <div className="flex items-center px-0.5">
                  <div className={`w-3 h-px ${step.state === "done" ? "bg-emerald-400/50" : "bg-white/10"}`} />
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* ─── Main header ──────────────────────────────────────────────────────── */

export function BoardHeader({
  filename,
  pipeline,
  healthScore,
  issueCount,
  criticalCount,
  componentCount,
  spiceResult,
  dfmReport,
  bomCost,
  renderMode,
  mode,
  onSetRenderMode,
  onSetMode,
  onValidate,
  onManufacture,
  onNew,
}: BoardHeaderProps) {
  const hasBoard = pipeline.parsed;

  // Build the spine. Each step shows the number that matters + state.
  const steps: SpineStep[] = [
    {
      key: "drop",
      label: "Drop",
      Icon: Upload,
      state: hasBoard ? "done" : "active",
      value: filename ? truncate(filename, 16) : "awaiting",
      subtitle: filename ? `Loaded ${filename}` : "Drop a .kicad_pcb or describe it",
      onClick: onNew,
    },
    {
      key: "parse",
      label: "Parsed",
      Icon: ScanSearch,
      state: pipeline.parsed ? "done" : "locked",
      value: pipeline.parsed ? `${componentCount} parts` : null,
      subtitle: "Board geometry extracted",
    },
    {
      key: "validate",
      label: "Validated",
      Icon: ShieldCheck,
      state: pipeline.validating ? "active"
           : pipeline.validated  ? "done"
           : pipeline.parsed     ? "pending" : "locked",
      value: pipeline.validated && healthScore != null
           ? `${healthScore}/100${issueCount > 0 ? ` · ${issueCount}${criticalCount > 0 ? `(${criticalCount}!)` : ""}` : ""}`
           : pipeline.validating ? "…" : null,
      subtitle: pipeline.validated
        ? `Score ${healthScore}/100 · ${issueCount} issues${criticalCount ? `, ${criticalCount} critical` : ""}`
        : "Run DRC + EE validation",
      onClick: pipeline.parsed ? onValidate : undefined,
    },
    {
      key: "simulate",
      label: "Simulated",
      Icon: Waves,
      state: spiceResult ? (spiceResult.passed ? "done" : "active")
           : pipeline.validated ? "pending" : "locked",
      value: spiceResult?.minRailV != null ? `${spiceResult.minRailV.toFixed(2)}V min` : null,
      subtitle: spiceResult
        ? spiceResult.passed ? "SPICE: all rails hold" : "SPICE: rail sag detected"
        : "Run SPICE on power rails",
    },
    {
      key: "dfm",
      label: "DFM",
      Icon: Package,
      state: dfmReport ? (dfmReport.critical === 0 ? "done" : "active")
           : pipeline.validated ? "pending" : "locked",
      value: dfmReport ? `${dfmReport.score}/100` : null,
      subtitle: dfmReport
        ? `${dfmReport.fab ?? "Fab-ready"} · ${dfmReport.critical} critical, ${dfmReport.warnings} warn`
        : "Design-for-manufacture check",
    },
    {
      key: "price",
      label: "Priced",
      Icon: DollarSign,
      state: bomCost ? "done" : pipeline.validated ? "pending" : "locked",
      value: bomCost ? `$${bomCost.totalUsd.toFixed(2)}` : null,
      subtitle: bomCost
        ? `$${bomCost.unitUsd.toFixed(2)} × ${bomCost.qty} · ${bomCost.leadDays}d lead`
        : "Live BOM pricing",
    },
    {
      key: "ship",
      label: "Ship",
      Icon: Ship,
      state: pipeline.manufactured ? "done"
           : pipeline.manufacturing ? "active"
           : (dfmReport && bomCost) ? "pending" : "locked",
      value: pipeline.manufactured ? "ready" : pipeline.manufacturing ? "…" : null,
      subtitle: "Generate Gerbers + PnP + fab package",
      onClick: pipeline.validated ? onManufacture : undefined,
    },
  ];

  return (
    <div className="h-11 flex-shrink-0 bg-[#080e1a] border-b border-white/8 flex items-center px-3 gap-3">
      {/* Brand */}
      <div className="flex items-center gap-1.5 flex-shrink-0">
        <div className="w-6 h-6 rounded-md bg-cyan-500/20 flex items-center justify-center">
          <Zap size={12} className="text-cyan-400" />
        </div>
        <span className="text-xs font-semibold text-white/60 hidden md:block">Circuit.AI</span>
      </div>

      {/* Filename chip */}
      {filename && (
        <div className="flex items-center gap-1 flex-shrink-0 min-w-0">
          <FileCode size={11} className="text-white/30" />
          <span className="text-[11px] text-white/55 font-mono truncate max-w-[140px]">{filename}</span>
        </div>
      )}

      <div className="h-5 w-px bg-white/10 flex-shrink-0" />

      {/* Pipeline spine — the one thing you glance at */}
      <PipelineSpine steps={steps} />

      <div className="h-5 w-px bg-white/10 flex-shrink-0" />

      {/* Mode switcher — the primary UX divider */}
      <div className="flex-shrink-0">
        <ModeSwitcher value={mode} onChange={onSetMode} />
      </div>

      {/* Render mode (canvas look) — only when a board is loaded */}
      {hasBoard && (
        <div className="flex-shrink-0">
          <RenderModeToggle value={renderMode} onChange={onSetRenderMode} />
        </div>
      )}

      {/* New */}
      <button
        onClick={onNew}
        className="flex items-center gap-1 text-[11px] text-white/30 hover:text-white/60 rounded-md px-1.5 py-1 transition-colors flex-shrink-0"
        title="New board"
      >
        <Plus size={11} />
      </button>
    </div>
  );
}

function truncate(s: string, n: number): string {
  return s.length <= n ? s : s.slice(0, n - 1) + "…";
}

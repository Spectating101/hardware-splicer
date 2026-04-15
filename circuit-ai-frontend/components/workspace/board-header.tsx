"use client";

import { Zap, FileCode, RotateCcw, Download, Plus } from "lucide-react";
import type { WorkbenchPipeline } from "@/lib/workbench-store";

interface BoardHeaderProps {
  filename: string | null;
  pipeline: WorkbenchPipeline;
  healthScore: number | null;
  issueCount: number;
  criticalCount: number;
  onValidate(): void;
  onManufacture(): void;
  onNew(): void;
}

function StatusPill({
  label,
  variant,
}: {
  label: string;
  variant: "idle" | "cyan" | "green" | "amber" | "red";
}) {
  const styles = {
    idle:   "bg-white/5  text-white/25 border-white/10",
    cyan:   "bg-cyan-500/15  text-cyan-300  border-cyan-500/30",
    green:  "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
    amber:  "bg-amber-500/15  text-amber-300  border-amber-500/30",
    red:    "bg-red-500/15    text-red-300    border-red-500/30",
  };
  return (
    <span className={`inline-flex items-center border rounded-full px-2.5 py-0.5 text-[11px] font-medium ${styles[variant]}`}>
      {label}
    </span>
  );
}

export function BoardHeader({
  filename,
  pipeline,
  healthScore,
  issueCount,
  criticalCount,
  onValidate,
  onManufacture,
  onNew,
}: BoardHeaderProps) {
  // Derive pill states
  const parsedVariant = pipeline.parsed ? "cyan" : "idle";

  let validatedVariant: "idle" | "green" | "amber" | "red" = "idle";
  let validatedLabel = "Not validated";
  if (pipeline.validating) {
    validatedLabel = "Validating…";
    validatedVariant = "amber";
  } else if (pipeline.validated && healthScore != null) {
    validatedLabel = `${healthScore}/100`;
    validatedVariant = criticalCount > 0 ? "red" : issueCount > 0 ? "amber" : "green";
  }

  const mfgVariant = pipeline.manufactured ? "green" : "idle";
  const mfgLabel = pipeline.manufacturing ? "Generating…" : pipeline.manufactured ? "Fab Ready" : "Not packaged";

  return (
    <div className="h-11 flex-shrink-0 bg-[#080e1a] border-b border-white/8 flex items-center px-4 gap-4">
      {/* Brand */}
      <div className="flex items-center gap-2 flex-shrink-0">
        <div className="w-6 h-6 rounded-md bg-cyan-500/20 flex items-center justify-center">
          <Zap size={13} className="text-cyan-400" />
        </div>
        <span className="text-xs font-semibold text-white/60 hidden sm:block">Circuit.AI</span>
      </div>

      {/* Project name */}
      {filename && (
        <div className="flex items-center gap-1.5 flex-shrink-0 min-w-0">
          <FileCode size={12} className="text-white/30 flex-shrink-0" />
          <span className="text-xs text-white/60 font-mono truncate max-w-[180px]">{filename}</span>
        </div>
      )}

      {/* Pipeline status pills */}
      <div className="flex items-center gap-1.5 flex-1 min-w-0">
        {pipeline.parsed && (
          <StatusPill label="Parsed ✓" variant={parsedVariant} />
        )}
        {pipeline.validated ? (
          <StatusPill label={validatedLabel} variant={validatedVariant} />
        ) : pipeline.validating ? (
          <StatusPill label={validatedLabel} variant="amber" />
        ) : null}
        {(pipeline.manufactured || pipeline.manufacturing) && (
          <StatusPill label={mfgLabel} variant={mfgVariant} />
        )}
      </div>

      {/* Actions */}
      <div className="flex items-center gap-1.5 flex-shrink-0">
        {pipeline.parsed && !pipeline.validated && (
          <button
            onClick={onValidate}
            disabled={pipeline.validating}
            className="flex items-center gap-1.5 text-[11px] bg-cyan-500/15 text-cyan-300 hover:bg-cyan-500/25 border border-cyan-500/30 rounded-md px-2.5 py-1 transition-colors disabled:opacity-50"
          >
            <RotateCcw size={10} className={pipeline.validating ? "animate-spin" : ""} />
            {pipeline.validating ? "Validating…" : "Validate"}
          </button>
        )}
        {pipeline.validated && (
          <button
            onClick={onValidate}
            disabled={pipeline.validating}
            className="flex items-center gap-1.5 text-[11px] text-white/40 hover:text-white/70 rounded-md px-2 py-1 transition-colors disabled:opacity-50"
          >
            <RotateCcw size={10} className={pipeline.validating ? "animate-spin" : ""} />
            Re-run
          </button>
        )}
        {pipeline.validated && !pipeline.manufactured && (
          <button
            onClick={onManufacture}
            disabled={pipeline.manufacturing}
            className="flex items-center gap-1.5 text-[11px] bg-purple-500/15 text-purple-300 hover:bg-purple-500/25 border border-purple-500/30 rounded-md px-2.5 py-1 transition-colors disabled:opacity-50"
          >
            <Download size={10} />
            {pipeline.manufacturing ? "Generating…" : "Export Gerbers"}
          </button>
        )}
        {pipeline.manufactured && (
          <button
            onClick={onManufacture}
            className="flex items-center gap-1.5 text-[11px] bg-emerald-500/15 text-emerald-300 hover:bg-emerald-500/25 border border-emerald-500/30 rounded-md px-2.5 py-1 transition-colors"
          >
            <Download size={10} />
            Download
          </button>
        )}
        <button
          onClick={onNew}
          className="flex items-center gap-1 text-[11px] text-white/30 hover:text-white/60 rounded-md px-2 py-1 transition-colors"
          title="New board"
        >
          <Plus size={11} />
        </button>
      </div>
    </div>
  );
}

"use client";

import { Handle, Position, type NodeProps } from "@xyflow/react";
import { XCircle, AlertTriangle, AlertCircle } from "lucide-react";
import { useWorkspaceStore } from "@/lib/store";
import { healthLabel } from "@/lib/jarvis";
import { cn } from "@/lib/utils";
import type { ValidationNodeData } from "@/lib/node-types";

function scoreColor(score: number) {
  if (score >= 80) return "text-emerald-400 border-emerald-500/40";
  if (score >= 50) return "text-amber-400 border-amber-500/40";
  return "text-red-400 border-red-500/40";
}

function severityGlow(criticalCount: number, errorCount: number, issueCount: number): string {
  if (criticalCount > 0) return "shadow-[0_0_28px_rgba(239,68,68,0.4),0_4px_24px_rgba(0,0,0,0.5)]";
  if (errorCount > 0) return "shadow-[0_0_24px_rgba(249,115,22,0.3),0_4px_24px_rgba(0,0,0,0.5)]";
  if (issueCount > 0) return "shadow-[0_0_20px_rgba(245,158,11,0.25),0_4px_24px_rgba(0,0,0,0.5)]";
  return "shadow-[0_0_24px_rgba(16,185,129,0.35),0_4px_24px_rgba(0,0,0,0.5)]";
}

export function ValidationNodeComponent({ id, data: rawData }: NodeProps) {
  const data = rawData as unknown as ValidationNodeData;
  const { openDrawer } = useWorkspaceStore();

  const criticalCount = data.issues.filter((i) => i.severity === "critical").length;
  const errorCount = data.issues.filter((i) => i.severity === "error").length;
  const warningCount = data.issues.filter((i) => i.severity === "warning").length;
  const colors = scoreColor(data.healthScore);

  const glow = severityGlow(criticalCount, errorCount, data.issues.length);

  return (
    <div
      className={cn(
        "w-[220px] rounded-2xl border bg-[#141e2e] p-3 flex flex-col gap-2 transition-all duration-500",
        colors.split(" ").find((c) => c.startsWith("border")) ?? "border-white/10",
        glow
      )}
    >
      <Handle type="target" position={Position.Left} className="!bg-cyan-500 !border-cyan-700" />

      {/* Score */}
      <div className="flex items-center gap-2">
        <div
          className={cn(
            "w-10 h-10 rounded-xl border-2 flex items-center justify-center font-bold text-sm",
            colors
          )}
        >
          {data.healthScore}
        </div>
        <div>
          <p className={cn("text-sm font-medium", colors.split(" ")[0])}>
            {healthLabel(data.healthScore)}
          </p>
          <p className="text-xs text-white/30">Health score</p>
        </div>
      </div>

      {/* Severity row */}
      {data.issues.length > 0 && (
        <div className="flex items-center gap-3 py-1.5 border-t border-white/5">
          {criticalCount > 0 && (
            <div className="flex items-center gap-1 text-xs text-red-400">
              <XCircle size={11} />
              <span>{criticalCount}</span>
            </div>
          )}
          {errorCount > 0 && (
            <div className="flex items-center gap-1 text-xs text-orange-400">
              <AlertTriangle size={11} />
              <span>{errorCount}</span>
            </div>
          )}
          {warningCount > 0 && (
            <div className="flex items-center gap-1 text-xs text-amber-400">
              <AlertCircle size={11} />
              <span>{warningCount}</span>
            </div>
          )}
          {data.issues.length === 0 && (
            <span className="text-xs text-emerald-400">No issues</span>
          )}
        </div>
      )}

      <button
        onClick={() => openDrawer(id, "issues")}
        className="w-full py-1.5 rounded-lg text-xs font-medium bg-white/5 text-white/60 border border-white/10 hover:bg-white/10 hover:text-white/80 transition-colors"
      >
        See details →
      </button>
    </div>
  );
}

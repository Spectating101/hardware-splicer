"use client";

import { Handle, Position, type NodeProps } from "@xyflow/react";
import { XCircle, AlertTriangle, AlertCircle, X } from "lucide-react";
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
  const { openDrawer, removeNode, acknowledgeAllIssues } = useWorkspaceStore();

  const active = data.issues.filter((i) => !i.acknowledged);
  const criticalCount = active.filter((i) => i.severity === "critical").length;
  const errorCount = active.filter((i) => i.severity === "error").length;
  const warningCount = active.filter((i) => i.severity === "warning").length;
  const colors = scoreColor(data.healthScore);

  const glow = severityGlow(criticalCount, errorCount, active.length);

  return (
    <div
      className={cn(
        "group w-[220px] rounded-2xl border bg-[#141e2e] p-3 flex flex-col gap-2 transition-all duration-500 relative",
        colors.split(" ").find((c) => c.startsWith("border")) ?? "border-white/10",
        glow
      )}
    >
      <Handle type="target" position={Position.Left} className="!bg-cyan-500 !border-cyan-700" />
      <Handle type="source" position={Position.Right} className="!bg-purple-500 !border-purple-700" />
      <button
        onClick={() => removeNode(id)}
        className="absolute -top-2 -right-2 w-5 h-5 rounded-full bg-[#1e293b] border border-white/15 text-white/30 hover:text-white/80 hover:border-white/30 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity z-10"
        title="Remove"
      >
        <X size={10} />
      </button>

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
      <div className="flex items-center gap-3 py-1.5 border-t border-white/5">
        {active.length === 0 && data.issues.length === 0 && (
          <span className="text-xs text-emerald-400">No issues</span>
        )}
        {active.length === 0 && data.issues.length > 0 && (
          <span className="text-xs text-white/30">All acknowledged</span>
        )}
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
      </div>

      {/* Ack all non-critical issues when there are only warnings/errors */}
      {active.length > 0 && criticalCount === 0 && (
        <button
          onClick={() => acknowledgeAllIssues(id)}
          className="w-full py-1.5 rounded-lg text-xs font-medium bg-amber-500/8 text-amber-400/70 border border-amber-500/20 hover:bg-amber-500/15 hover:text-amber-400 transition-colors"
        >
          Dismiss warnings
        </button>
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

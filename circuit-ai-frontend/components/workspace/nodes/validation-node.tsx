"use client";

import { Handle, Position, type NodeProps } from "@xyflow/react";
import { motion } from "framer-motion";
import { XCircle, AlertTriangle, AlertCircle, X, CheckCircle2 } from "lucide-react";
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
  const { openDrawer, removeNode, acknowledgeAllIssues, showJarvisStrip, addJarvisMessage, nodes, edges } = useWorkspaceStore();

  function handleAcknowledgeAll() {
    acknowledgeAllIssues(id);
    // After 90s, nudge to manufacture if no mfg node yet
    setTimeout(() => {
      const mfgExists = edges.some((e) => e.source === id && nodes.find((n) => n.id === e.target && n.kind === "manufacturing"));
      if (!mfgExists) {
        const msg = "All issues acknowledged — say **manufacture** to generate the Gerbers, BOM, and assembly guide.";
        addJarvisMessage({ role: "jarvis", text: msg, nodeId: id });
        showJarvisStrip({ message: msg, nodeId: id });
      }
    }, 90000);
  }

  const active = data.issues.filter((i) => !i.acknowledged);
  const criticalCount = active.filter((i) => i.severity === "critical").length;
  const errorCount = active.filter((i) => i.severity === "error").length;
  const warningCount = active.filter((i) => i.severity === "warning").length;
  const colors = scoreColor(data.healthScore);

  // Top 2 issues for inline preview (sorted by severity)
  const severityOrder = { critical: 0, error: 1, warning: 2 } as const;
  const previewIssues = [...active]
    .sort((a, b) => severityOrder[a.severity] - severityOrder[b.severity])
    .slice(0, 2);

  const glow = severityGlow(criticalCount, errorCount, active.length);

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.94, y: 8 }}
      animate={{ opacity: 1, scale: 1, y: 0 }}
      transition={{ duration: 0.22, ease: "easeOut" }}
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
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5">
            <p className={cn("text-sm font-medium", colors.split(" ")[0])}>
              {healthLabel(data.healthScore)}
            </p>
            {data.prevScore != null && data.prevScore !== data.healthScore && (
              <span className={cn(
                "text-[10px] font-semibold px-1 rounded",
                data.healthScore > data.prevScore
                  ? "text-emerald-400 bg-emerald-950/40"
                  : "text-red-400 bg-red-950/40"
              )}>
                {data.healthScore > data.prevScore ? "+" : ""}{data.healthScore - data.prevScore}
              </span>
            )}
            {data.prevScore != null && data.prevScore === data.healthScore && (
              <span className="text-[10px] font-semibold px-1 rounded text-white/20 bg-white/5">
                ±0
              </span>
            )}
          </div>
          <p className="text-xs text-white/30">Health score</p>
        </div>
      </div>

      {/* Severity count row */}
      {(criticalCount > 0 || errorCount > 0 || warningCount > 0 || (active.length === 0 && data.issues.length > 0)) && (
        <div className="flex items-center gap-3 py-1 border-t border-white/5">
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
      )}

      {/* Inline issue preview — top 2 active issues */}
      {previewIssues.length > 0 && (
        <div className="flex flex-col gap-1 py-1 border-t border-white/5">
          {previewIssues.map((issue) => {
            const IssueIcon = issue.severity === "critical" ? XCircle : issue.severity === "error" ? AlertTriangle : AlertCircle;
            const issueColor = issue.severity === "critical" ? "text-red-400" : issue.severity === "error" ? "text-orange-400" : "text-amber-400";
            return (
              <div key={issue.id} className="flex items-start gap-1.5">
                <IssueIcon size={10} className={cn("flex-shrink-0 mt-0.5", issueColor)} />
                <span className="text-[10px] text-white/50 leading-snug line-clamp-2">{issue.what}</span>
              </div>
            );
          })}
          {active.length > 2 && (
            <span className="text-[10px] text-white/25 ml-3.5">+{active.length - 2} more</span>
          )}
        </div>
      )}
      {active.length === 0 && data.issues.length === 0 && (
        <div className="flex items-center gap-1.5 py-1 border-t border-white/5">
          <CheckCircle2 size={11} className="text-emerald-400 flex-shrink-0" />
          <span className="text-[10px] text-emerald-400/80">Board is clean</span>
        </div>
      )}

      {/* Ack all non-critical issues when there are only warnings/errors */}
      {active.length > 0 && criticalCount === 0 && (
        <button
          onClick={handleAcknowledgeAll}
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
    </motion.div>
  );
}

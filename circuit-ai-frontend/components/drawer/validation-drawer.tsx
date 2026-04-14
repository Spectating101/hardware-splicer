"use client";

import { useState } from "react";
import { ChevronDown, ChevronRight, XCircle, AlertTriangle, AlertCircle, Check } from "lucide-react";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { cn } from "@/lib/utils";
import { healthLabel } from "@/lib/jarvis";
import { useWorkspaceStore } from "@/lib/store";
import type { ValidationNodeData, ValidationIssue } from "@/lib/node-types";

const severityOrder = { critical: 0, error: 1, warning: 2 };

function IssueCard({ issue, nodeId }: { issue: ValidationIssue; nodeId: string }) {
  const [expanded, setExpanded] = useState(false);
  const { acknowledgeIssue } = useWorkspaceStore();

  const isAcknowledged = issue.acknowledged ?? false;

  const borderColor = isAcknowledged
    ? "border-white/10"
    : issue.severity === "critical"
      ? "border-red-700/50"
      : issue.severity === "error"
        ? "border-orange-700/40"
        : "border-amber-700/30";

  const iconColor = isAcknowledged
    ? "text-white/20"
    : issue.severity === "critical"
      ? "text-red-400"
      : issue.severity === "error"
        ? "text-orange-400"
        : "text-amber-400";

  const Icon = isAcknowledged
    ? Check
    : issue.severity === "critical"
      ? XCircle
      : issue.severity === "error"
        ? AlertTriangle
        : AlertCircle;

  return (
    <div className={cn("rounded-xl border bg-white/3 overflow-hidden transition-all duration-200", borderColor, isAcknowledged && "opacity-50")}>
      <button
        onClick={() => setExpanded((x) => !x)}
        className="w-full flex items-center gap-2 p-3 text-left hover:bg-white/5 transition-colors"
      >
        <Icon size={14} className={cn("flex-shrink-0", iconColor)} />
        <span className={cn("flex-1 text-sm leading-snug", isAcknowledged ? "text-white/30 line-through" : "text-white/80")}>
          {issue.what}
        </span>
        {expanded ? (
          <ChevronDown size={12} className="text-white/30 flex-shrink-0" />
        ) : (
          <ChevronRight size={12} className="text-white/30 flex-shrink-0" />
        )}
      </button>

      {expanded && (
        <div className="px-3 pb-3 flex flex-col gap-2 border-t border-white/5 pt-2">
          <div>
            <p className="text-xs text-white/40 font-medium uppercase tracking-wide mb-1">Why</p>
            <p className="text-xs text-white/70 leading-relaxed">{issue.why}</p>
          </div>
          <div>
            <p className="text-xs text-white/40 font-medium uppercase tracking-wide mb-1">Fix</p>
            <p className="text-xs text-white/70 leading-relaxed">{issue.fix}</p>
          </div>
          {!isAcknowledged && (
            <button
              onClick={(e) => { e.stopPropagation(); acknowledgeIssue(nodeId, issue.id); }}
              className="mt-1 self-start text-xs text-white/30 hover:text-white/60 border border-white/10 hover:border-white/20 rounded-md px-2 py-1 transition-colors"
            >
              Won&apos;t fix this iteration
            </button>
          )}
        </div>
      )}
    </div>
  );
}

function scoreColor(score: number) {
  if (score >= 80) return "text-emerald-400";
  if (score >= 50) return "text-amber-400";
  return "text-red-400";
}

interface ValidationDrawerProps {
  nodeId: string;
  data: ValidationNodeData;
  defaultTab?: string;
}

export function ValidationDrawer({ nodeId, data, defaultTab = "issues" }: ValidationDrawerProps) {
  const sorted = [...data.issues].sort(
    (a, b) => severityOrder[a.severity] - severityOrder[b.severity]
  );
  const active = data.issues.filter((i) => !i.acknowledged);
  const criticalCount = active.filter((i) => i.severity === "critical").length;
  const errorCount = active.filter((i) => i.severity === "error").length;
  const warningCount = active.filter((i) => i.severity === "warning").length;
  const acknowledgedCount = data.issues.filter((i) => i.acknowledged).length;

  return (
    <Tabs defaultValue={defaultTab} className="flex flex-col h-full">
      <TabsList>
        <TabsTrigger value="issues">What&apos;s Wrong</TabsTrigger>
        <TabsTrigger value="summary">Summary</TabsTrigger>
        <TabsTrigger value="next">What to Do Next</TabsTrigger>
      </TabsList>

      {/* Issues tab */}
      <TabsContent value="issues" className="p-4 flex flex-col gap-2">
        {sorted.length === 0 ? (
          <div className="text-center py-8">
            <p className="text-emerald-400 text-sm font-medium">No issues found</p>
            <p className="text-white/30 text-xs mt-1">Board passed all checks</p>
          </div>
        ) : (
          sorted.map((issue) => <IssueCard key={issue.id} issue={issue} nodeId={nodeId} />)
        )}
      </TabsContent>

      {/* Summary tab */}
      <TabsContent value="summary" className="p-4 flex flex-col gap-4">
        <div className="flex items-center gap-4">
          <span
            className={cn("text-6xl font-bold tabular-nums", scoreColor(data.healthScore))}
          >
            {data.healthScore}
          </span>
          <div>
            <p className={cn("text-lg font-medium", scoreColor(data.healthScore))}>
              {healthLabel(data.healthScore)}
            </p>
            <p className="text-white/30 text-sm">Health score out of 100</p>
          </div>
        </div>

        <div className="grid grid-cols-3 gap-2">
          <div className="rounded-xl border border-red-800/40 bg-red-950/20 p-3 text-center">
            <p className="text-2xl font-bold text-red-400">{criticalCount}</p>
            <p className="text-xs text-white/40 mt-1">Critical</p>
          </div>
          <div className="rounded-xl border border-orange-800/40 bg-orange-950/20 p-3 text-center">
            <p className="text-2xl font-bold text-orange-400">{errorCount}</p>
            <p className="text-xs text-white/40 mt-1">Errors</p>
          </div>
          <div className="rounded-xl border border-amber-800/40 bg-amber-950/20 p-3 text-center">
            <p className="text-2xl font-bold text-amber-400">{warningCount}</p>
            <p className="text-xs text-white/40 mt-1">Warnings</p>
          </div>
        </div>
        {acknowledgedCount > 0 && (
          <p className="text-xs text-white/30 text-center">
            {acknowledgedCount} issue{acknowledgedCount === 1 ? "" : "s"} acknowledged — won&apos;t fix this iteration
          </p>
        )}
      </TabsContent>

      {/* Next steps tab */}
      <TabsContent value="next" className="p-4">
        {criticalCount > 0 ? (
          <div className="rounded-xl border border-red-700/50 bg-red-950/20 p-4">
            <p className="text-sm font-medium text-red-400 mb-1">
              Fix {criticalCount} critical issue{criticalCount === 1 ? "" : "s"} first
            </p>
            <p className="text-xs text-white/50 leading-relaxed">
              Critical issues will prevent your board from functioning correctly
              and must be resolved before proceeding to manufacture.
            </p>
          </div>
        ) : data.issues.length === 0 ? (
          <div className="rounded-xl border border-emerald-700/50 bg-emerald-950/20 p-4">
            <p className="text-sm font-medium text-emerald-400 mb-1">
              Board is ready to manufacture
            </p>
            <p className="text-xs text-white/50 leading-relaxed">
              No issues found. You can proceed to generate Gerber files and
              submit to your preferred fab.
            </p>
          </div>
        ) : (
          <div className="rounded-xl border border-amber-700/40 bg-amber-950/10 p-4">
            <p className="text-sm font-medium text-amber-400 mb-1">
              Review {data.issues.length} issue{data.issues.length === 1 ? "" : "s"} before manufacturing
            </p>
            <p className="text-xs text-white/50 leading-relaxed">
              No critical blockers found, but there are warnings and errors
              that may affect board performance. Review and decide which to
              fix before sending to fab.
            </p>
          </div>
        )}
      </TabsContent>
    </Tabs>
  );
}

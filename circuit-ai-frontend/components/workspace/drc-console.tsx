"use client";

import { useState } from "react";
import { ChevronUp, ChevronDown, RotateCcw, AlertTriangle, AlertCircle, Info } from "lucide-react";
import type { ValidationIssue } from "@/lib/cad-types";

interface DrcConsoleProps {
  issues: ValidationIssue[];
  validating: boolean;
  validated: boolean;
  onValidate(): void;
  onFocusComponent(ref: string): void;
}

function severityIcon(sev: string) {
  const s = String(sev).toLowerCase();
  if (s === "critical" || s === "error") return <AlertTriangle size={11} className="text-red-400 flex-shrink-0" />;
  if (s === "warning") return <AlertCircle size={11} className="text-amber-400 flex-shrink-0" />;
  return <Info size={11} className="text-blue-400 flex-shrink-0" />;
}

function severityBadge(sev: string) {
  const s = String(sev).toLowerCase();
  if (s === "critical" || s === "error") return "bg-red-500/15 text-red-300 border-red-500/25";
  if (s === "warning") return "bg-amber-500/15 text-amber-300 border-amber-500/25";
  return "bg-blue-500/15 text-blue-300 border-blue-500/25";
}

export function DrcConsole({ issues, validating, validated, onValidate, onFocusComponent }: DrcConsoleProps) {
  const [expanded, setExpanded] = useState(false);

  const critical = issues.filter((i) => {
    const s = String(i.severity).toLowerCase();
    return s === "critical" || s === "error";
  }).length;
  const warnings = issues.filter((i) => String(i.severity).toLowerCase() === "warning").length;

  const summaryText = !validated
    ? "No validation run yet"
    : issues.length === 0
    ? "No issues — board looks clean"
    : [
        critical > 0 ? `${critical} critical` : null,
        warnings > 0 ? `${warnings} warning${warnings > 1 ? "s" : ""}` : null,
        issues.length - critical - warnings > 0 ? `${issues.length - critical - warnings} info` : null,
      ]
        .filter(Boolean)
        .join(" · ");

  return (
    <div className="flex-shrink-0 bg-[#080e1a] border-t border-white/8">
      {/* Collapsed rail */}
      <div className="h-9 flex items-center px-4 gap-3">
        <div className="flex items-center gap-2 flex-1 min-w-0">
          <span className="text-[10px] font-semibold uppercase tracking-widest text-white/30 flex-shrink-0">
            DRC
          </span>
          <span
            className={`text-xs truncate ${
              !validated
                ? "text-white/25"
                : critical > 0
                ? "text-red-400/80"
                : warnings > 0
                ? "text-amber-400/80"
                : "text-emerald-400/80"
            }`}
          >
            {summaryText}
          </span>
        </div>

        {/* Validate button */}
        <button
          onClick={onValidate}
          disabled={validating}
          className="flex items-center gap-1.5 text-[11px] text-white/40 hover:text-white/70 rounded-md px-2 py-1 transition-colors disabled:opacity-40 flex-shrink-0"
        >
          <RotateCcw size={10} className={validating ? "animate-spin" : ""} />
          {validating ? "Running…" : "Validate"}
        </button>

        {/* Expand toggle */}
        {validated && issues.length > 0 && (
          <button
            onClick={() => setExpanded((x) => !x)}
            className="flex items-center gap-1 text-[11px] text-white/30 hover:text-white/60 transition-colors flex-shrink-0"
          >
            {expanded ? <ChevronDown size={12} /> : <ChevronUp size={12} />}
            {expanded ? "Hide" : `${issues.length} issue${issues.length > 1 ? "s" : ""}`}
          </button>
        )}
      </div>

      {/* Expanded issue list */}
      {expanded && issues.length > 0 && (
        <div className="border-t border-white/8 max-h-56 overflow-y-auto">
          {issues.map((issue, i) => (
            <div
              key={i}
              className="flex items-start gap-3 px-4 py-2.5 border-b border-white/5 last:border-0 hover:bg-white/3 transition-colors"
            >
              {severityIcon(issue.severity)}
              <div className="flex-1 min-w-0">
                <div className="flex items-start justify-between gap-2">
                  <p className="text-xs text-white/75 font-medium leading-snug truncate">{issue.issue}</p>
                  <span className={`border rounded px-1.5 py-0.5 text-[10px] flex-shrink-0 ${severityBadge(issue.severity)}`}>
                    {String(issue.severity).toUpperCase()}
                  </span>
                </div>
                <p className="text-[10px] text-white/40 mt-0.5">{issue.component}</p>
                <p className="text-[10px] text-white/50 mt-1 leading-relaxed">{issue.solution}</p>
              </div>
              <button
                onClick={() => onFocusComponent(issue.component)}
                className="text-[10px] text-cyan-400/60 hover:text-cyan-300 transition-colors flex-shrink-0 mt-0.5"
              >
                Show
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

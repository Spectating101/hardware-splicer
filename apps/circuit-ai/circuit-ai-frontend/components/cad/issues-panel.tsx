"use client";

import type { ValidationIssue } from "@/lib/cad-types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

function badge(sev: string) {
  const s = (sev || "").toLowerCase();
  if (s === "critical" || s === "error") return "bg-red-500/20 text-red-200 border-red-500/30";
  if (s === "warning") return "bg-amber-500/20 text-amber-200 border-amber-500/30";
  return "bg-blue-500/20 text-blue-200 border-blue-500/30";
}

export function IssuesPanel({
  issues,
  onFocusComponent,
}: {
  issues: ValidationIssue[];
  onFocusComponent: (component: string) => void;
}) {
  return (
    <Card className="h-full border-white/10 bg-[#0b1220] text-white">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center justify-between text-sm font-semibold text-white/90">
          <span>Issues</span>
          <span className="text-xs text-white/60">{issues.length}</span>
        </CardTitle>
      </CardHeader>
      <CardContent className="h-[calc(100%-56px)] overflow-auto space-y-3">
        {issues.length === 0 ? (
          <div className="rounded-md border border-white/10 bg-white/5 p-3 text-sm text-white/70">
            No issues yet. Upload a board and run Validate.
          </div>
        ) : (
          issues.map((issue, idx) => (
            <div key={idx} className="rounded-md border border-white/10 bg-white/5 p-3">
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <div className="truncate text-sm font-semibold text-white/90">{issue.issue}</div>
                  <div className="mt-1 truncate text-xs text-white/60">{issue.component}</div>
                </div>
                <span className={`shrink-0 rounded border px-2 py-0.5 text-[11px] ${badge(issue.severity)}`}>
                  {String(issue.severity).toUpperCase()}
                </span>
              </div>
              <div className="mt-2 text-xs text-white/70">{issue.solution}</div>
              <div className="mt-3 flex gap-2">
                <Button variant="outline" size="sm" onClick={() => onFocusComponent(issue.component)}>
                  Show
                </Button>
                <Button variant="secondary" size="sm" disabled title="Fix application requires a connected CAD mutation endpoint.">
                  Fix endpoint required
                </Button>
              </div>
            </div>
          ))
        )}
      </CardContent>
    </Card>
  );
}

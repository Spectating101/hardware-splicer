"use client";

import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { useWorkspaceStore } from "@/lib/store";
import type { BoardNodeData, ValidationNodeData } from "@/lib/node-types";
import { ValidationDrawer } from "./validation-drawer";
import { healthLabel } from "@/lib/jarvis";
import { cn } from "@/lib/utils";

function scoreColor(score: number) {
  if (score >= 80) return "text-emerald-400";
  if (score >= 50) return "text-amber-400";
  return "text-red-400";
}

interface BoardDrawerProps {
  nodeId: string;
  data: BoardNodeData;
  defaultTab?: string;
}

export function BoardDrawer({ nodeId, data, defaultTab = "overview" }: BoardDrawerProps) {
  const { nodes, edges } = useWorkspaceStore();

  // Find connected validation node
  const validationEdge = edges.find((e) => e.source === nodeId);
  const validationNode = validationEdge
    ? nodes.find((n) => n.id === validationEdge.target && n.kind === "validation")
    : null;
  const validationData = validationNode?.data as ValidationNodeData | undefined;

  return (
    <Tabs defaultValue={defaultTab} className="flex flex-col h-full">
      <TabsList>
        <TabsTrigger value="overview">Overview</TabsTrigger>
        <TabsTrigger value="issues">Issues</TabsTrigger>
        <TabsTrigger value="structure">Structure</TabsTrigger>
        <TabsTrigger value="parts">Parts</TabsTrigger>
        <TabsTrigger value="manufacture">Manufacture</TabsTrigger>
      </TabsList>

      {/* Overview */}
      <TabsContent value="overview" className="p-4 flex flex-col gap-4">
        <div className="grid grid-cols-2 gap-2">
          <div className="rounded-xl bg-white/5 border border-white/10 p-3">
            <p className="text-2xl font-bold text-white">{data.componentCount}</p>
            <p className="text-xs text-white/40 mt-0.5">Components</p>
          </div>
          <div className="rounded-xl bg-white/5 border border-white/10 p-3">
            <p className="text-2xl font-bold text-white">{data.layerCount}</p>
            <p className="text-xs text-white/40 mt-0.5">Layers</p>
          </div>
        </div>

        {/* Validation status card */}
        {validationData ? (
          <div className="rounded-xl border border-white/10 bg-white/3 p-3 flex items-center gap-3">
            <div
              className={cn(
                "w-10 h-10 rounded-xl border-2 flex items-center justify-center font-bold text-sm",
                scoreColor(validationData.healthScore),
                validationData.healthScore >= 80
                  ? "border-emerald-500/40"
                  : validationData.healthScore >= 50
                    ? "border-amber-500/40"
                    : "border-red-500/40"
              )}
            >
              {validationData.healthScore}
            </div>
            <div>
              <p className={cn("text-sm font-medium", scoreColor(validationData.healthScore))}>
                {healthLabel(validationData.healthScore)}
              </p>
              <p className="text-xs text-white/30">
                {validationData.issues.length === 0
                  ? "No issues found"
                  : `${validationData.issues.length} issue${validationData.issues.length === 1 ? "" : "s"} found`}
              </p>
            </div>
          </div>
        ) : (
          <div className="rounded-xl border border-white/10 bg-white/3 p-3">
            <p className="text-sm text-white/40">Validation not yet run</p>
            <p className="text-xs text-white/25 mt-1">
              Click &ldquo;Check issues&rdquo; on the board node to run validation.
            </p>
          </div>
        )}

        <div className="flex gap-2 flex-wrap">
          <Badge variant="info">{data.layerCount}-layer PCB</Badge>
          <Badge variant="default">KiCad</Badge>
        </div>
      </TabsContent>

      {/* Issues — delegate to ValidationDrawer if available */}
      <TabsContent value="issues" className="flex flex-col h-full">
        {validationData ? (
          <ValidationDrawer data={validationData} defaultTab="issues" />
        ) : (
          <div className="flex-1 flex items-center justify-center p-6">
            <div className="text-center">
              <p className="text-white/40 text-sm">No validation data yet</p>
              <p className="text-white/25 text-xs mt-1">
                Click &ldquo;Check issues&rdquo; on the Board node to run ERC.
              </p>
            </div>
          </div>
        )}
      </TabsContent>

      {/* Structure stub */}
      <TabsContent value="structure" className="flex-1 flex items-center justify-center p-6">
        <div className="text-center">
          <p className="text-white/40 text-sm font-medium">3D Structure View</p>
          <p className="text-white/25 text-xs mt-1">Coming in Plan 2</p>
        </div>
      </TabsContent>

      {/* Parts stub */}
      <TabsContent value="parts" className="flex-1 flex items-center justify-center p-6">
        <div className="text-center">
          <p className="text-white/40 text-sm font-medium">BOM &amp; Sourcing</p>
          <p className="text-white/25 text-xs mt-1">Coming in Plan 2</p>
        </div>
      </TabsContent>

      {/* Manufacture stub */}
      <TabsContent value="manufacture" className="flex-1 flex items-center justify-center p-6">
        <div className="text-center">
          <p className="text-white/40 text-sm font-medium">Manufacturing Package</p>
          <p className="text-white/25 text-xs mt-1">Coming in Plan 2</p>
        </div>
      </TabsContent>
    </Tabs>
  );
}

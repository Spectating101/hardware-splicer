"use client";

import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { useWorkspaceStore } from "@/lib/store";
import type { BoardNodeData, ValidationNodeData, ManufacturingNodeData, ManufacturingFile } from "@/lib/node-types";
import { ValidationDrawer } from "./validation-drawer";
import { healthLabel } from "@/lib/jarvis";
import { cn } from "@/lib/utils";
import { FileCode, FileText, Package } from "lucide-react";

function scoreColor(score: number) {
  if (score >= 80) return "text-emerald-400";
  if (score >= 50) return "text-amber-400";
  return "text-red-400";
}

function FileRow({ file }: { file: ManufacturingFile }) {
  const Icon = file.type === "gerber" || file.type === "drill" ? FileCode : FileText;
  const color = file.type === "gerber" || file.type === "drill"
    ? "text-purple-400"
    : file.type === "bom"
      ? "text-cyan-400"
      : "text-white/50";
  return (
    <div className="flex items-center gap-2 py-1.5 border-b border-white/5 last:border-0">
      <Icon size={12} className={color} />
      <span className="text-xs text-white/70 font-mono truncate">{file.name}</span>
    </div>
  );
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

  // Find manufacturing node (downstream of validation or board)
  const mfgNode = (() => {
    if (validationNode) {
      const mfgEdge = edges.find((e) => e.source === validationNode.id);
      return mfgEdge ? nodes.find((n) => n.id === mfgEdge.target && n.kind === "manufacturing") : null;
    }
    return null;
  })();
  const mfgData = mfgNode?.data as ManufacturingNodeData | undefined;

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
        <div className="grid grid-cols-3 gap-2">
          <div className="rounded-xl bg-white/5 border border-white/10 p-3">
            <p className="text-2xl font-bold text-white">{data.componentCount}</p>
            <p className="text-xs text-white/40 mt-0.5">Components</p>
          </div>
          <div className="rounded-xl bg-white/5 border border-white/10 p-3">
            <p className="text-2xl font-bold text-white">{data.layerCount}</p>
            <p className="text-xs text-white/40 mt-0.5">Layers</p>
          </div>
          {data.netCount != null && data.netCount > 0 && (
            <div className="rounded-xl bg-white/5 border border-white/10 p-3">
              <p className="text-2xl font-bold text-white">{data.netCount}</p>
              <p className="text-xs text-white/40 mt-0.5">Nets</p>
            </div>
          )}
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
                {validationData.issues.filter((i) => !i.acknowledged).length === 0
                  ? "No active issues"
                  : `${validationData.issues.filter((i) => !i.acknowledged).length} active issue${validationData.issues.filter((i) => !i.acknowledged).length === 1 ? "" : "s"}`}
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
          {mfgData?.status === "done" && <Badge variant="success">Mfg Ready</Badge>}
        </div>
      </TabsContent>

      {/* Issues — delegate to ValidationDrawer if available */}
      <TabsContent value="issues" className="flex flex-col h-full">
        {validationData ? (
          <ValidationDrawer nodeId={validationNode!.id} data={validationData} defaultTab="issues" />
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
          <p className="text-white/40 text-sm font-medium">2D Layer View</p>
          <p className="text-white/25 text-xs mt-1">Coming next — layer-by-layer SVG render</p>
        </div>
      </TabsContent>

      {/* Parts stub */}
      <TabsContent value="parts" className="flex-1 flex items-center justify-center p-6">
        <div className="text-center">
          <p className="text-white/40 text-sm font-medium">BOM &amp; Sourcing</p>
          <p className="text-white/25 text-xs mt-1">Coming next — component availability + pricing</p>
        </div>
      </TabsContent>

      {/* Manufacture tab */}
      <TabsContent value="manufacture" className="p-4 flex flex-col gap-4 overflow-y-auto">
        {!mfgData && (
          <div className="rounded-xl border border-white/10 bg-white/3 p-4 text-center">
            <Package size={24} className="text-purple-400/50 mx-auto mb-2" />
            <p className="text-sm text-white/50 font-medium">No package generated yet</p>
            <p className="text-xs text-white/30 mt-1">
              {validationData
                ? validationData.issues.filter((i) => i.severity === "critical" && !i.acknowledged).length > 0
                  ? "Fix critical issues first, then generate the manufacturing package."
                  : 'Click "Package for manufacture →" on the board node.'
                : "Run validation first, then generate the manufacturing package."}
            </p>
          </div>
        )}

        {mfgData?.status === "processing" && (
          <div className="rounded-xl border border-purple-500/30 bg-purple-950/20 p-4 text-center">
            <div className="w-6 h-6 border-2 border-purple-500/60 border-t-purple-400 rounded-full animate-spin mx-auto mb-2" />
            <p className="text-sm text-purple-300">Generating manufacturing package…</p>
          </div>
        )}

        {mfgData?.status === "done" && mfgData.files && (
          <>
            <div className="rounded-xl border border-emerald-500/30 bg-emerald-950/10 p-3 flex items-center gap-3">
              <Package size={18} className="text-emerald-400 flex-shrink-0" />
              <div>
                <p className="text-sm font-medium text-emerald-400">Package ready</p>
                <p className="text-xs text-white/30">
                  {mfgData.gerberCount} Gerber/drill files
                  {mfgData.hasBom ? " · BOM" : ""}
                  {mfgData.hasAssembly ? " · Assembly guide" : ""}
                </p>
              </div>
            </div>

            <div className="rounded-xl border border-white/10 bg-white/3 p-3">
              <p className="text-xs text-white/40 uppercase tracking-wide mb-2">Output files</p>
              {mfgData.files.map((f) => (
                <FileRow key={f.name} file={f} />
              ))}
            </div>
          </>
        )}

        {mfgData?.status === "error" && (
          <div className="rounded-xl border border-red-700/40 bg-red-950/20 p-4">
            <p className="text-sm text-red-400 font-medium mb-1">Generation failed</p>
            <p className="text-xs text-white/40">{mfgData.errorMessage}</p>
          </div>
        )}
      </TabsContent>
    </Tabs>
  );
}

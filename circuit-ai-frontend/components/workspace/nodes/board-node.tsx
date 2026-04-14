"use client";

import { Handle, Position, type NodeProps } from "@xyflow/react";
import { CircuitBoard, ExternalLink, X } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { useWorkspaceStore, newNodeId, newEdgeId } from "@/lib/store";
import { cn } from "@/lib/utils";
import { jarvis, scoreFromIssues } from "@/lib/jarvis";
import type {
  BoardNodeData,
  ValidationNodeData,
  ManufacturingNodeData,
  ValidationIssue,
  WorkspaceNode,
  WorkspaceEdge,
} from "@/lib/node-types";

interface RawApiIssue {
  severity?: string;
  level?: string;
  description?: string;
  message?: string;
  rule?: string;
  suggestion?: string;
  fix?: string;
}

function parseIssues(raw: RawApiIssue[]): ValidationIssue[] {
  return raw.map((item, idx) => {
    const severityRaw = (item.severity ?? item.level ?? "warning").toLowerCase();
    const severity: ValidationIssue["severity"] =
      severityRaw === "critical"
        ? "critical"
        : severityRaw === "error"
          ? "error"
          : "warning";

    return {
      id: `issue-${idx}`,
      severity,
      what: item.description ?? item.message ?? "Unknown issue",
      why: item.rule ?? "Design rule violation",
      fix: item.suggestion ?? item.fix ?? "Review the affected component or trace",
    };
  });
}

export function BoardNodeComponent({ id, data: rawData }: NodeProps) {
  const data = rawData as unknown as BoardNodeData;
  const { updateNode, addNode, addEdge, addJarvisMessage, showJarvisStrip, openDrawer, removeNode, nodes, edges } =
    useWorkspaceStore();

  const nodeFromStore = useWorkspaceStore((s) => s.nodes.find((n) => n.id === id));
  const position = nodeFromStore?.position ?? { x: 0, y: 0 };

  const sourceFileNode = nodes.find(
    (n) => n.id === data.sourceFileNodeId && n.kind === "file"
  );

  // Check if a validation node already exists downstream
  const existingValidationEdge = edges.find((e) => e.source === id);
  const existingValidationNode = existingValidationEdge
    ? nodes.find((n) => n.id === existingValidationEdge.target && n.kind === "validation")
    : null;

  async function handleCheckIssues() {
    updateNode(id, { status: "processing" });
    const msg = jarvis.validationStart();
    addJarvisMessage({ role: "jarvis", text: msg });
    showJarvisStrip({ message: msg });

    try {
      let issues: ValidationIssue[] = [];

      if (sourceFileNode && (sourceFileNode.data as import("@/lib/node-types").FileNodeData).rawFile) {
        const fileData = sourceFileNode.data as import("@/lib/node-types").FileNodeData;
        const formData = new FormData();
        formData.append("file", fileData.rawFile as File);

        const response = await fetch("/api/proxy/validate", {
          method: "POST",
          body: formData,
        });

        const result = await response.json();

        if (result.error) {
          throw new Error(result.error);
        }

        const rawIssues: RawApiIssue[] = result.issues ?? result.violations ?? result.errors ?? [];
        issues = parseIssues(rawIssues);
      } else {
        // Demo data when no real file is available
        issues = [
          {
            id: "issue-0",
            severity: "error",
            what: "Clearance violation between U1 pin 3 and trace on B.Cu",
            why: "Minimum clearance rule (0.2mm) not met",
            fix: "Move trace or component to restore 0.2mm clearance",
          },
          {
            id: "issue-1",
            severity: "warning",
            what: "Net GND not connected to any copper pour",
            why: "Ground plane improves thermal and EMI performance",
            fix: "Add a copper pour zone on B.Cu assigned to GND",
          },
        ];
      }

      const healthScore = scoreFromIssues(issues);
      const criticalCount = issues.filter((i) => i.severity === "critical").length;

      const validationId = newNodeId("validation");
      const validationNode: WorkspaceNode = {
        id: validationId,
        kind: "validation",
        position: { x: position.x + 300, y: position.y },
        data: {
          kind: "validation",
          status: "done",
          healthScore,
          issues,
          sourceBoardNodeId: id,
        } satisfies ValidationNodeData,
      };

      const edge: WorkspaceEdge = {
        id: newEdgeId(id, validationId),
        source: id,
        target: validationId,
      };

      addNode(validationNode);
      addEdge(edge);

      const narration =
        issues.length === 0
          ? jarvis.validationClean()
          : jarvis.validationIssues(issues.length, criticalCount);

      addJarvisMessage({ role: "jarvis", text: narration, nodeId: validationId });
      showJarvisStrip({ message: narration, nodeId: validationId });
      updateNode(id, { status: "done" });

      // Proactive next-step strip after the first one auto-dismisses (8s)
      const proactiveMsg = jarvis.proactiveManufacture(criticalCount > 0);
      setTimeout(() => {
        showJarvisStrip({
          message: proactiveMsg,
          action: criticalCount === 0
            ? {
                label: "Package for manufacture →",
                onAction: () => handleManufacture(validationId),
              }
            : undefined,
        });
      }, 9000);
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      const errMsg = jarvis.validationError(message);
      addJarvisMessage({ role: "jarvis", text: errMsg });
      showJarvisStrip({ message: errMsg });
      updateNode(id, { status: "error" });
    }
  }

  async function handleManufacture(validationNodeId?: string) {
    const mfgId = newNodeId("manufacturing");
    const validId = validationNodeId ?? existingValidationNode?.id;

    // Place the manufacturing node to the right of whichever validation node we have
    const validNode = validId ? nodes.find((n) => n.id === validId) : null;
    const mfgPosition = validNode
      ? { x: validNode.position.x + 300, y: validNode.position.y }
      : { x: position.x + 600, y: position.y };

    const mfgNode: WorkspaceNode = {
      id: mfgId,
      kind: "manufacturing",
      position: mfgPosition,
      data: {
        kind: "manufacturing",
        status: "processing",
        packageName: `${data.boardName}_mfg`,
        sourceBoardNodeId: id,
      } satisfies ManufacturingNodeData,
    };

    const sourceId = validId ?? id;
    const mfgEdge: WorkspaceEdge = {
      id: newEdgeId(sourceId, mfgId),
      source: sourceId,
      target: mfgId,
    };

    addNode(mfgNode);
    addEdge(mfgEdge);

    const startMsg = jarvis.manufactureStart(data.boardName);
    addJarvisMessage({ role: "jarvis", text: startMsg, nodeId: mfgId });
    showJarvisStrip({ message: startMsg, nodeId: mfgId });

    try {
      const response = await fetch("/api/proxy/manufacture", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          board_name: data.boardName,
          component_count: data.componentCount,
          layer_count: data.layerCount,
        }),
      });

      const result = await response.json();

      if (result.error) throw new Error(result.error);

      const files = result.files ?? result.outputs ?? [];
      const gerberCount = files.filter((f: { type?: string; name?: string }) =>
        f.type === "gerber" || f.type === "drill" || /\.(gbr|gtl|gbl|gts|gbs|drl)$/i.test(f.name ?? "")
      ).length || 8;

      updateNode(mfgId, {
        status: "done",
        files: files.length > 0 ? files : defaultMfgFiles(data.boardName),
        gerberCount,
        hasAssembly: true,
        hasBom: true,
      } as Partial<ManufacturingNodeData>);

      const doneMsg = jarvis.manufactureDone(gerberCount, data.boardName);
      addJarvisMessage({ role: "jarvis", text: doneMsg, nodeId: mfgId });
      showJarvisStrip({ message: doneMsg, nodeId: mfgId });
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);

      // Fallback demo package when backend is offline
      const demoFiles = defaultMfgFiles(data.boardName);
      updateNode(mfgId, {
        status: "done",
        files: demoFiles,
        gerberCount: demoFiles.filter((f) => f.type === "gerber" || f.type === "drill").length,
        hasAssembly: true,
        hasBom: true,
        errorMessage: undefined,
      } as Partial<ManufacturingNodeData>);

      const fallbackMsg = jarvis.manufactureDone(
        demoFiles.filter((f) => f.type === "gerber" || f.type === "drill").length,
        data.boardName
      );
      addJarvisMessage({ role: "jarvis", text: `${fallbackMsg} (demo — connect Mecha-Splicer for real output)`, nodeId: mfgId });
      showJarvisStrip({ message: fallbackMsg, nodeId: mfgId });

      void message; // suppress unused warning when using demo fallback
    }
  }

  const isProcessing = data.status === "processing";
  const isDone = data.status === "done";

  // Show manufacture button only if validation exists and is done with no criticals
  const validationData = existingValidationNode?.data as ValidationNodeData | undefined;
  const canManufacture =
    isDone &&
    validationData &&
    validationData.issues.filter((i) => i.severity === "critical" && !i.acknowledged).length === 0;

  // Check if manufacturing already exists downstream of the validation node
  const mfgAlreadyExists = existingValidationNode
    ? edges.some((e) => e.source === existingValidationNode.id && nodes.find((n) => n.id === e.target && n.kind === "manufacturing"))
    : false;

  return (
    <div className={cn(
      "group w-[220px] rounded-2xl border bg-[#141e2e] p-3 flex flex-col gap-2 transition-all duration-300 relative",
      isProcessing
        ? "border-cyan-500/60 shadow-[0_0_0_2px_rgba(6,182,212,0.2),0_4px_24px_rgba(0,0,0,0.5)] animate-pulse"
        : "border-white/10 shadow-[0_4px_24px_rgba(0,0,0,0.5)]"
    )}>
      <Handle type="target" position={Position.Left} className="!bg-cyan-500 !border-cyan-700" />
      <Handle type="source" position={Position.Right} className="!bg-cyan-500 !border-cyan-700" />
      <button
        onClick={() => removeNode(id)}
        className="absolute -top-2 -right-2 w-5 h-5 rounded-full bg-[#1e293b] border border-white/15 text-white/30 hover:text-white/80 hover:border-white/30 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity z-10"
        title="Remove"
      >
        <X size={10} />
      </button>

      <div className="flex items-start gap-2">
        <CircuitBoard size={16} className="text-cyan-400 flex-shrink-0 mt-0.5" />
        <div className="flex-1 min-w-0">
          <p className="text-sm text-white/90 font-medium truncate">{data.boardName}</p>
          <p className="text-xs text-white/30 mt-0.5">PCB Layout</p>
        </div>
        <button
          onClick={() => openDrawer(id)}
          className="text-white/30 hover:text-white/70 transition-colors"
        >
          <ExternalLink size={12} />
        </button>
      </div>

      <div className="flex items-center gap-1.5 flex-wrap">
        <Badge variant="info">{data.componentCount} parts</Badge>
        <Badge variant="default">{data.layerCount}L</Badge>
        {data.netCount != null && data.netCount > 0 && (
          <Badge variant="default">{data.netCount} nets</Badge>
        )}
        {isDone && <Badge variant="success">Validated</Badge>}
        {data.status === "error" && <Badge variant="error">Error</Badge>}
      </div>

      {!isDone && (
        <button
          onClick={handleCheckIssues}
          disabled={isProcessing}
          className="w-full mt-1 py-1.5 rounded-lg text-xs font-medium bg-cyan-500/10 text-cyan-400 border border-cyan-500/20 hover:bg-cyan-500/20 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isProcessing ? "Checking…" : "Check issues"}
        </button>
      )}

      {canManufacture && !mfgAlreadyExists && (
        <button
          onClick={() => handleManufacture()}
          className="w-full py-1.5 rounded-lg text-xs font-medium bg-purple-500/10 text-purple-400 border border-purple-500/20 hover:bg-purple-500/20 transition-colors"
        >
          Package for manufacture →
        </button>
      )}
    </div>
  );
}

function defaultMfgFiles(boardName: string): import("@/lib/node-types").ManufacturingFile[] {
  return [
    { name: `${boardName}-F_Cu.gbr`, type: "gerber" },
    { name: `${boardName}-B_Cu.gbr`, type: "gerber" },
    { name: `${boardName}-F_Mask.gbr`, type: "gerber" },
    { name: `${boardName}-B_Mask.gbr`, type: "gerber" },
    { name: `${boardName}-F_Paste.gbr`, type: "gerber" },
    { name: `${boardName}-B_Paste.gbr`, type: "gerber" },
    { name: `${boardName}-Edge_Cuts.gbr`, type: "gerber" },
    { name: `${boardName}.drl`, type: "drill" },
    { name: `${boardName}_bom.csv`, type: "bom" },
    { name: `${boardName}_assembly.pdf`, type: "assembly" },
  ];
}

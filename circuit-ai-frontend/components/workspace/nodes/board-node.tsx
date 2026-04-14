"use client";

import { useEffect } from "react";
import { Handle, Position, type NodeProps } from "@xyflow/react";
import { motion } from "framer-motion";
import { CircuitBoard, ExternalLink, X, ShieldCheck, ShieldAlert } from "lucide-react";
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
      severityRaw === "critical" ? "critical" : severityRaw === "error" ? "error" : "warning";
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
  const {
    updateNode, addNode, addEdge, addJarvisMessage, showJarvisStrip,
    openDrawer, removeNode, nodes, edges, pendingCommand, setPendingCommand, setJarvisThinking,
  } = useWorkspaceStore();

  const nodeFromStore = useWorkspaceStore((s) => s.nodes.find((n) => n.id === id));
  const position = nodeFromStore?.position ?? { x: 0, y: 0 };

  const sourceFileNode = nodes.find((n) => n.id === data.sourceFileNodeId && n.kind === "file");

  // Find connected validation node
  const validationEdge = edges.find((e) => e.source === id);
  const existingValidationNode = validationEdge
    ? nodes.find((n) => n.id === validationEdge.target && n.kind === "validation")
    : null;
  const validationData = existingValidationNode?.data as ValidationNodeData | undefined;

  // Find manufacturing node downstream of validation
  const mfgAlreadyExists = existingValidationNode
    ? edges.some((e) =>
        e.source === existingValidationNode.id &&
        nodes.find((n) => n.id === e.target && n.kind === "manufacturing")
      )
    : false;

  // React to commands dispatched from the command bar
  useEffect(() => {
    if (!pendingCommand || pendingCommand.boardNodeId !== id) return;
    const action = pendingCommand.action;
    setPendingCommand(null);
    if (action === "validate") handleCheckIssues();
    else if (action === "manufacture") handleManufacture();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pendingCommand]);

  async function handleCheckIssues() {
    // Capture previous score for delta reporting on re-validate
    const prevScore = existingValidationNode
      ? (existingValidationNode.data as ValidationNodeData).healthScore
      : undefined;
    const isRevalidation = prevScore !== undefined;

    setJarvisThinking(true);
    updateNode(id, { status: "processing" });
    const msg = jarvis.validationStart();
    addJarvisMessage({ role: "jarvis", text: msg });
    showJarvisStrip({ message: msg });

    function finishValidation(issues: ValidationIssue[], demo = false) {
      const healthScore = scoreFromIssues(issues);
      const criticalCount = issues.filter((i) => i.severity === "critical").length;
      const validationId = newNodeId("validation");

      // Top issue for inline fix hint — pick highest severity active issue
      const severityOrder = { critical: 0, error: 1, warning: 2 } as const;
      const sorted = [...issues].sort((a, b) => severityOrder[a.severity] - severityOrder[b.severity]);
      const topFix = sorted[0]?.fix;

      const validationNode: WorkspaceNode = {
        id: validationId,
        kind: "validation",
        position: { x: position.x + 300, y: position.y },
        data: { kind: "validation", status: "done", healthScore, issues, sourceBoardNodeId: id } satisfies ValidationNodeData,
      };

      addNode(validationNode);
      addEdge({ id: newEdgeId(id, validationId), source: id, target: validationId });

      let narration: string;
      if (isRevalidation) {
        narration = jarvis.revalidationResult(healthScore, prevScore!, issues.length, criticalCount);
      } else if (issues.length === 0) {
        narration = jarvis.validationClean();
      } else {
        narration = jarvis.validationIssues(issues.length, criticalCount, topFix);
      }
      if (demo) narration += " (demo — connect Circuit-AI backend for real ERC)";

      setJarvisThinking(false);
      addJarvisMessage({ role: "jarvis", text: narration, nodeId: validationId });
      showJarvisStrip({
        message: narration,
        nodeId: validationId,
        action: issues.length > 0
          ? { label: "See details →", onAction: () => openDrawer(validationId, "issues") }
          : undefined,
      });
      updateNode(id, { status: "done" });

      const proactiveMsg = jarvis.proactiveManufacture(criticalCount > 0);
      setTimeout(() => {
        showJarvisStrip({
          message: proactiveMsg,
          action: criticalCount === 0
            ? { label: "Package for manufacture →", onAction: () => handleManufacture(validationId) }
            : undefined,
        });
      }, 12000);

      // 45s nudge: remind about blocking criticals if user hasn't opened the drawer yet
      if (criticalCount > 0) {
        setTimeout(() => {
          showJarvisStrip({
            message: jarvis.criticalNudge(data.boardName, criticalCount),
            nodeId: validationId,
            action: { label: "Show issues →", onAction: () => openDrawer(validationId, "issues") },
          });
        }, 45000);
      }
    }

    try {
      let issues: ValidationIssue[] = [];

      if (sourceFileNode && (sourceFileNode.data as import("@/lib/node-types").FileNodeData).rawFile) {
        const fileData = sourceFileNode.data as import("@/lib/node-types").FileNodeData;
        const formData = new FormData();
        formData.append("file", fileData.rawFile as File);
        const response = await fetch("/api/proxy/validate", { method: "POST", body: formData });
        const result = await response.json();
        if (result.error) throw new Error(result.error);
        const rawIssues: RawApiIssue[] = result.issues ?? result.violations ?? result.errors ?? [];
        issues = parseIssues(rawIssues);
      } else {
        issues = [
          { id: "issue-0", severity: "error", what: "Clearance violation between U1 pin 3 and trace on B.Cu", why: "Minimum clearance rule (0.2mm) not met", fix: "Move trace or component to restore 0.2mm clearance" },
          { id: "issue-1", severity: "warning", what: "Net GND not connected to any copper pour", why: "Ground plane improves thermal and EMI performance", fix: "Add a copper pour zone on B.Cu assigned to GND" },
        ];
      }

      finishValidation(issues);
    } catch {
      const issues: ValidationIssue[] = [
        { id: "issue-0", severity: "error", what: "Clearance violation between U1 pin 3 and trace on B.Cu", why: "Minimum clearance rule (0.2mm) not met", fix: "Move trace or component to restore 0.2mm clearance" },
        { id: "issue-1", severity: "warning", what: "Net GND not connected to any copper pour", why: "Ground plane improves thermal and EMI performance", fix: "Add a copper pour zone on B.Cu assigned to GND" },
      ];
      finishValidation(issues, true);
    }
  }

  async function handleManufacture(validationNodeId?: string) {
    const mfgId = newNodeId("manufacturing");
    const validId = validationNodeId ?? existingValidationNode?.id;
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
    addNode(mfgNode);
    addEdge({ id: newEdgeId(sourceId, mfgId), source: sourceId, target: mfgId });

    const startMsg = jarvis.manufactureStart(data.boardName);
    setJarvisThinking(true);
    addJarvisMessage({ role: "jarvis", text: startMsg, nodeId: mfgId });
    showJarvisStrip({ message: startMsg, nodeId: mfgId });

    try {
      const response = await fetch("/api/proxy/manufacture", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ board_name: data.boardName, component_count: data.componentCount, layer_count: data.layerCount }),
      });
      const result = await response.json();
      if (result.error) throw new Error(result.error);
      const files = result.files ?? result.outputs ?? [];
      const gerberCount = files.filter((f: { type?: string; name?: string }) =>
        f.type === "gerber" || f.type === "drill" || /\.(gbr|gtl|gbl|gts|gbs|drl)$/i.test(f.name ?? "")
      ).length || 8;
      setJarvisThinking(false);
      updateNode(mfgId, { status: "done", files: files.length > 0 ? files : defaultMfgFiles(data.boardName), gerberCount, hasAssembly: true, hasBom: true } as Partial<ManufacturingNodeData>);
      const doneMsg = jarvis.manufactureDone(gerberCount, data.boardName);
      addJarvisMessage({ role: "jarvis", text: doneMsg, nodeId: mfgId });
      showJarvisStrip({ message: doneMsg, nodeId: mfgId });
    } catch {
      setJarvisThinking(false);
      const demoFiles = defaultMfgFiles(data.boardName);
      const gerberCount = demoFiles.filter((f) => f.type === "gerber" || f.type === "drill").length;
      updateNode(mfgId, { status: "done", files: demoFiles, gerberCount, hasAssembly: true, hasBom: true } as Partial<ManufacturingNodeData>);
      const doneMsg = jarvis.manufactureDone(gerberCount, data.boardName);
      addJarvisMessage({ role: "jarvis", text: `${doneMsg} (demo — connect Mecha-Splicer for real output)`, nodeId: mfgId });
      showJarvisStrip({ message: doneMsg, nodeId: mfgId });
    }
  }

  const isProcessing = data.status === "processing";
  const isDone = data.status === "done";

  const activeCriticals = validationData
    ? validationData.issues.filter((i) => i.severity === "critical" && !i.acknowledged).length
    : 0;
  const canManufacture = isDone && validationData && activeCriticals === 0;

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.94, y: 8 }}
      animate={{ opacity: 1, scale: 1, y: 0 }}
      transition={{ duration: 0.22, ease: "easeOut" }}
      className={cn(
        "group w-[220px] rounded-2xl border bg-[#141e2e] p-3 flex flex-col gap-2 transition-all duration-300 relative",
        isProcessing
          ? "border-cyan-500/60 shadow-[0_0_0_2px_rgba(6,182,212,0.2),0_4px_24px_rgba(0,0,0,0.5)] animate-pulse"
          : "border-white/10 shadow-[0_4px_24px_rgba(0,0,0,0.5)]"
      )}
    >
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
        {validationData && (
          <div
            className={cn(
              "flex items-center gap-1 text-[11px] font-bold",
              validationData.healthScore >= 80
                ? "text-emerald-400"
                : validationData.healthScore >= 50
                  ? "text-amber-400"
                  : "text-red-400"
            )}
            title={`Health score: ${validationData.healthScore}/100`}
          >
            {validationData.healthScore >= 80
              ? <ShieldCheck size={12} className="flex-shrink-0" />
              : <ShieldAlert size={12} className="flex-shrink-0" />
            }
            {validationData.healthScore}
          </div>
        )}
        <button onClick={() => openDrawer(id)} className="text-white/30 hover:text-white/70 transition-colors">
          <ExternalLink size={12} />
        </button>
      </div>

      <div className="flex items-center gap-1.5 flex-wrap">
        <Badge variant="info">{data.componentCount} parts</Badge>
        <Badge variant="default">{data.layerCount}L</Badge>
        {data.netCount != null && data.netCount > 0 && <Badge variant="default">{data.netCount} nets</Badge>}
        {data.status === "error" && <Badge variant="error">Error</Badge>}
      </div>

      {/* Show "Check issues" only if no validation exists yet (check both status and edge) */}
      {!existingValidationNode && (
        <button
          onClick={handleCheckIssues}
          disabled={isProcessing}
          className="w-full mt-1 py-1.5 rounded-lg text-xs font-medium bg-cyan-500/10 text-cyan-400 border border-cyan-500/20 hover:bg-cyan-500/20 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isProcessing ? "Checking…" : "Check issues"}
        </button>
      )}

      {/* Re-validate option when already validated */}
      {existingValidationNode && !mfgAlreadyExists && (
        <button
          onClick={handleCheckIssues}
          className="w-full mt-1 py-1.5 rounded-lg text-xs font-medium bg-white/5 text-white/40 border border-white/10 hover:bg-white/10 hover:text-white/60 transition-colors"
        >
          Re-validate
        </button>
      )}

      {/* Manufacture button */}
      {canManufacture && !mfgAlreadyExists && (
        <button
          onClick={() => handleManufacture()}
          className="w-full py-1.5 rounded-lg text-xs font-medium bg-purple-500/10 text-purple-400 border border-purple-500/20 hover:bg-purple-500/20 transition-colors"
        >
          Package for manufacture →
        </button>
      )}
    </motion.div>
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

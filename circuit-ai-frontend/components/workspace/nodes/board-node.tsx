"use client";

import { Handle, Position, type NodeProps } from "@xyflow/react";
import { CircuitBoard, ExternalLink } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { useWorkspaceStore, newNodeId, newEdgeId } from "@/lib/store";
import { jarvis, scoreFromIssues } from "@/lib/jarvis";
import type {
  BoardNodeData,
  ValidationNodeData,
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
  const { updateNode, addNode, addEdge, addJarvisMessage, showJarvisStrip, openDrawer, nodes } =
    useWorkspaceStore();

  const nodeFromStore = useWorkspaceStore((s) => s.nodes.find((n) => n.id === id));
  const position = nodeFromStore?.position ?? { x: 0, y: 0 };

  const sourceFileNode = nodes.find(
    (n) => n.id === data.sourceFileNodeId && n.kind === "file"
  );

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
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      const errMsg = jarvis.validationError(message);
      addJarvisMessage({ role: "jarvis", text: errMsg });
      showJarvisStrip({ message: errMsg });
      updateNode(id, { status: "error" });
    }
  }

  const isProcessing = data.status === "processing";
  const isDone = data.status === "done";

  return (
    <div className="w-[220px] rounded-2xl border border-white/10 bg-[#141e2e] shadow-[0_4px_24px_rgba(0,0,0,0.5)] p-3 flex flex-col gap-2">
      <Handle type="target" position={Position.Left} className="!bg-cyan-500 !border-cyan-700" />
      <Handle type="source" position={Position.Right} className="!bg-cyan-500 !border-cyan-700" />

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
    </div>
  );
}

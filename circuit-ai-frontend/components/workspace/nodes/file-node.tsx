"use client";

import { Handle, Position, type NodeProps } from "@xyflow/react";
import { FileText, X } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { useWorkspaceStore, newNodeId, newEdgeId } from "@/lib/store";
import { fileKindLabel, formatFileSize, jarvis } from "@/lib/jarvis";
import type { FileNodeData, BoardNodeData, WorkspaceNode, WorkspaceEdge } from "@/lib/node-types";

export function FileNodeComponent({ id, data: rawData }: NodeProps) {
  const data = rawData as unknown as FileNodeData;
  const { updateNode, addNode, addEdge, addJarvisMessage, showJarvisStrip, removeNode } =
    useWorkspaceStore();

  const nodeFromStore = useWorkspaceStore((s) => s.nodes.find((n) => n.id === id));
  const position = nodeFromStore?.position ?? { x: 0, y: 0 };

  function handleParseBoard() {
    updateNode(id, { status: "processing" });

    const boardId = newNodeId("board");
    const boardNode: WorkspaceNode = {
      id: boardId,
      kind: "board",
      position: { x: position.x + 300, y: position.y },
      data: {
        kind: "board",
        status: "idle",
        boardName: data.filename.replace(/\.kicad_pcb$/i, ""),
        componentCount: 47,
        layerCount: 4,
        sourceFileNodeId: id,
      } satisfies BoardNodeData,
    };

    const edge: WorkspaceEdge = {
      id: newEdgeId(id, boardId),
      source: id,
      target: boardId,
    };

    addNode(boardNode);
    addEdge(edge);

    const msg = jarvis.boardFound(data.filename);
    addJarvisMessage({ role: "jarvis", text: msg, nodeId: boardId });
    showJarvisStrip({ message: msg, nodeId: boardId });

    updateNode(id, { status: "done" });
  }

  const isProcessing = data.status === "processing";
  const isDone = data.status === "done";

  return (
    <div className="group w-[220px] rounded-2xl border border-white/10 bg-[#141e2e] shadow-[0_4px_24px_rgba(0,0,0,0.5)] p-3 flex flex-col gap-2 relative">
      <Handle type="source" position={Position.Right} className="!bg-cyan-500 !border-cyan-700" />
      <button
        onClick={() => removeNode(id)}
        className="absolute -top-2 -right-2 w-5 h-5 rounded-full bg-[#1e293b] border border-white/15 text-white/30 hover:text-white/80 hover:border-white/30 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity z-10"
        title="Remove"
      >
        <X size={10} />
      </button>

      <div className="flex items-start gap-2">
        <FileText size={16} className="text-white/50 flex-shrink-0 mt-0.5" />
        <div className="flex-1 min-w-0">
          <p className="text-sm text-white/90 font-medium truncate">{data.filename}</p>
          <p className="text-xs text-white/30 mt-0.5">
            {formatFileSize(data.sizeBytes)}
          </p>
        </div>
      </div>

      <div className="flex items-center gap-1.5">
        <Badge variant="info">{fileKindLabel(data.fileKind as import("@/lib/jarvis").FileKind)}</Badge>
        {isDone && <Badge variant="success">Parsed</Badge>}
      </div>

      {!isDone && (
        <button
          onClick={handleParseBoard}
          disabled={isProcessing}
          className="w-full mt-1 py-1.5 rounded-lg text-xs font-medium bg-cyan-500/10 text-cyan-400 border border-cyan-500/20 hover:bg-cyan-500/20 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isProcessing ? "Parsing…" : "Parse board"}
        </button>
      )}
    </div>
  );
}

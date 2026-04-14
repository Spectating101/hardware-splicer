"use client";

import { useCallback } from "react";
import {
  ReactFlow,
  ReactFlowProvider,
  Background,
  BackgroundVariant,
  Controls,
  MiniMap,
  type Node,
  type Edge,
  type NodeTypes,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

import { useWorkspaceStore, newNodeId } from "@/lib/store";
import { detectFileKind, jarvis } from "@/lib/jarvis";
import type { FileNodeData, WorkspaceNode } from "@/lib/node-types";
import { FileNodeComponent } from "./nodes/file-node";
import { BoardNodeComponent } from "./nodes/board-node";
import { ValidationNodeComponent } from "./nodes/validation-node";
import { EmptyState } from "./empty-state";

const nodeTypes: NodeTypes = {
  file: FileNodeComponent,
  board: BoardNodeComponent,
  validation: ValidationNodeComponent,
};

function WorkspaceFlow() {
  const {
    nodes: storeNodes,
    edges: storeEdges,
    addNode,
    addJarvisMessage,
    showJarvisStrip,
  } = useWorkspaceStore();

  // Convert store nodes to React Flow nodes
  const rfNodes: Node[] = storeNodes.map((n) => ({
    id: n.id,
    type: n.kind,
    position: n.position,
    data: n.data as unknown as Record<string, unknown>,
  }));

  // Convert store edges to React Flow edges
  const rfEdges: Edge[] = storeEdges.map((e) => {
    const targetNode = storeNodes.find((n) => n.id === e.target);
    const isProcessing = (targetNode?.data as { status?: string } | undefined)?.status === "processing";
    return {
      id: e.id,
      source: e.source,
      target: e.target,
      animated: isProcessing,
      style: {
        stroke: isProcessing ? "rgba(6, 182, 212, 0.9)" : "rgba(6, 182, 212, 0.4)",
        strokeWidth: isProcessing ? 2.5 : 2,
      },
    };
  });

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      const file = e.dataTransfer.files[0];
      if (!file) return;

      const bounds = (e.currentTarget as HTMLDivElement).getBoundingClientRect();
      const x = e.clientX - bounds.left - 110;
      const y = e.clientY - bounds.top - 60;

      const kind = detectFileKind(file.name);
      const id = newNodeId("file");

      const node: WorkspaceNode = {
        id,
        kind: "file",
        position: { x: Math.max(0, x), y: Math.max(0, y) },
        data: {
          kind: "file",
          status: "idle",
          filename: file.name,
          fileKind: kind,
          sizeBytes: file.size,
          rawFile: file,
        } satisfies FileNodeData,
      };

      addNode(node);
      const msg = jarvis.fileDropped(file.name);
      addJarvisMessage({ role: "jarvis", text: msg, nodeId: id });
      showJarvisStrip({ message: msg, nodeId: id });
    },
    [addNode, addJarvisMessage, showJarvisStrip]
  );

  return (
    <div
      className="w-full h-full relative"
      onDrop={handleDrop}
      onDragOver={(e) => e.preventDefault()}
    >
      <ReactFlow
        nodes={rfNodes}
        edges={rfEdges}
        nodeTypes={nodeTypes}
        fitView={rfNodes.length > 0}
        fitViewOptions={{ padding: 0.3 }}
        style={{ background: "#0d1421" }}
        deleteKeyCode={null}
        proOptions={{ hideAttribution: true }}
      >
        <Background
          variant={BackgroundVariant.Dots}
          gap={24}
          size={1.2}
          color="rgba(255,255,255,0.06)"
        />
        <Controls
          style={{
            background: "#141e2e",
            border: "1px solid rgba(255,255,255,0.1)",
          }}
        />
        <MiniMap
          style={{ background: "#0d1421", border: "1px solid rgba(255,255,255,0.1)" }}
          nodeColor="#141e2e"
          maskColor="rgba(8,14,26,0.7)"
        />
      </ReactFlow>

      {storeNodes.length === 0 && <EmptyState />}
    </div>
  );
}

export function WorkspaceCanvas() {
  return (
    <ReactFlowProvider>
      <WorkspaceFlow />
    </ReactFlowProvider>
  );
}

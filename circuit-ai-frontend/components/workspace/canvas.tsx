"use client";

import { useCallback, useEffect } from "react";
import {
  ReactFlow,
  ReactFlowProvider,
  Background,
  BackgroundVariant,
  Controls,
  MiniMap,
  useReactFlow,
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
import { ManufacturingNodeComponent } from "./nodes/manufacturing-node";
import { EmptyState } from "./empty-state";

const nodeTypes: NodeTypes = {
  file: FileNodeComponent,
  board: BoardNodeComponent,
  validation: ValidationNodeComponent,
  manufacturing: ManufacturingNodeComponent,
};

function WorkspaceFlow() {
  const {
    nodes: storeNodes,
    edges: storeEdges,
    addNode,
    addJarvisMessage,
    showJarvisStrip,
    undo,
    focusNodeId,
    setFocusNodeId,
    updateNodePosition,
  } = useWorkspaceStore();

  // Deduplication helper (same logic as command-bar)
  const isDuplicateFile = useCallback(
    (filename: string) => storeNodes.some(
      (n) => n.kind === "file" && (n.data as FileNodeData).filename === filename
    ),
    [storeNodes]
  );

  const { fitBounds, getNode } = useReactFlow();

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
    const status = (targetNode?.data as { status?: string } | undefined)?.status;
    const isProcessing = status === "processing";
    const isMfgEdge = targetNode?.kind === "manufacturing";
    return {
      id: e.id,
      source: e.source,
      target: e.target,
      animated: isProcessing,
      style: {
        stroke: isMfgEdge
          ? isProcessing ? "rgba(168,85,247,0.9)" : "rgba(168,85,247,0.4)"
          : isProcessing ? "rgba(6,182,212,0.9)" : "rgba(6,182,212,0.4)",
        strokeWidth: isProcessing ? 2.5 : 2,
      },
    };
  });

  // Sync drag-stop position back to Zustand
  const onNodeDragStop = useCallback(
    (_: React.MouseEvent, node: Node) => {
      updateNodePosition(node.id, node.position);
    },
    [updateNodePosition]
  );

  // File drop onto canvas
  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      const file = e.dataTransfer.files[0];
      if (!file) return;

      // Prevent duplicate drops
      if (isDuplicateFile(file.name)) {
        const msg = jarvis.duplicateFile(file.name);
        addJarvisMessage({ role: "jarvis", text: msg });
        showJarvisStrip({ message: msg });
        return;
      }

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

  // Keyboard shortcuts: Ctrl+Z → undo
  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      if ((e.ctrlKey || e.metaKey) && e.key === "z" && !e.shiftKey) {
        e.preventDefault();
        undo();
      }
    }
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [undo]);

  // Zoom-to-node when focusNodeId is set from the conversation history
  useEffect(() => {
    if (!focusNodeId) return;
    const node = getNode(focusNodeId);
    if (node) {
      fitBounds(
        { x: node.position.x, y: node.position.y, width: 220, height: 160 },
        { padding: 0.5, duration: 600 }
      );
    }
    setFocusNodeId(null);
  }, [focusNodeId, getNode, fitBounds, setFocusNodeId]);

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
        onNodeDragStop={onNodeDragStop}
        fitView={rfNodes.length > 0}
        fitViewOptions={{ padding: 0.3 }}
        style={{ background: "#0d1421" }}
        deleteKeyCode={null}
        nodesFocusable={false}
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
          nodeColor={(n) => (n.type === "manufacturing" ? "#581c87" : "#141e2e")}
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

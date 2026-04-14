"use client";

import { useState, useRef } from "react";
import { CircuitBoard, Zap, Loader2, Upload } from "lucide-react";
import { useWorkspaceStore, newNodeId } from "@/lib/store";
import { detectFileKind, jarvis, parseIntent, contextualResponse } from "@/lib/jarvis";
import type { FileNodeData, BoardNodeData, ValidationNodeData, ManufacturingNodeData, WorkspaceNode, ValidationIssue } from "@/lib/node-types";

export function CommandBar() {
  const [input, setInput] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const {
    isJarvisThinking,
    addJarvisMessage,
    addNode,
    showJarvisStrip,
    nodes,
    edges,
    undo,
    clearProject,
    openDrawer,
    setPendingCommand,
    setFocusNodeId,
    acknowledgeAllIssues,
  } = useWorkspaceStore();

  function handleFileOnBar(file: File) {
    // Prevent duplicate drops of the same filename
    const existing = nodes.find(
      (n) => n.kind === "file" && (n.data as FileNodeData).filename === file.name
    );
    if (existing) {
      const msg = jarvis.duplicateFile(file.name);
      addJarvisMessage({ role: "jarvis", text: msg, nodeId: existing.id });
      showJarvisStrip({ message: msg, nodeId: existing.id });
      return;
    }

    const kind = detectFileKind(file.name);
    const id = newNodeId("file");
    const node: WorkspaceNode = {
      id,
      kind: "file",
      position: { x: 80, y: 120 },
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
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    const file = e.dataTransfer.files[0];
    if (file) handleFileOnBar(file);
  }

  function handleFileInput(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) handleFileOnBar(file);
    e.target.value = "";
  }

  function buildContext() {
    const boardNode = nodes.find((n) => n.kind === "board");
    const boardData = boardNode?.data as BoardNodeData | undefined;

    const validationEdge = boardNode
      ? edges.find((e) => e.source === boardNode.id)
      : undefined;
    const validationNode = validationEdge
      ? nodes.find((n) => n.id === validationEdge.target && n.kind === "validation")
      : undefined;
    const validationData = validationNode?.data as ValidationNodeData | undefined;

    const mfgNode = validationNode
      ? nodes.find((n) => {
          const e = edges.find((ed) => ed.source === validationNode.id);
          return e && n.id === e.target && n.kind === "manufacturing";
        })
      : undefined;
    const mfgData = mfgNode?.data as ManufacturingNodeData | undefined;

    const activeIssues = validationData?.issues.filter((i) => !i.acknowledged) ?? [];
    const criticals = activeIssues.filter((i) => i.severity === "critical");

    return {
      boardNode,
      boardData,
      validationNode,
      validationData,
      mfgNode,
      mfgData,
      activeIssues,
      criticals,
      ctx: {
        hasBoardNode: !!boardNode,
        hasValidation: !!validationNode,
        hasManufacturing: !!mfgNode && mfgData?.status === "done",
        hasCriticals: criticals.length > 0,
        activeIssueCount: activeIssues.length,
        boardName: boardData?.boardName,
        healthScore: validationData?.healthScore,
        componentCount: boardData?.componentCount,
        layerCount: boardData?.layerCount,
      },
    };
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const text = input.trim();
    if (!text) return;

    addJarvisMessage({ role: "user", text });
    setInput("");

    const intent = parseIntent(text);
    const { ctx, boardNode, validationNode } = buildContext();
    const response = contextualResponse(intent, ctx);

    // Execute side effects
    switch (intent.type) {
      case "validate":
        if (boardNode && !ctx.hasValidation) {
          addJarvisMessage({ role: "jarvis", text: response });
          showJarvisStrip({ message: response });
          setPendingCommand({ action: "validate", boardNodeId: boardNode.id });
          return;
        }
        break;

      case "manufacture":
        if (boardNode && ctx.hasValidation && !ctx.hasCriticals && !ctx.hasManufacturing) {
          addJarvisMessage({ role: "jarvis", text: response });
          showJarvisStrip({ message: response });
          setPendingCommand({ action: "manufacture", boardNodeId: boardNode.id });
          return;
        }
        break;

      case "show_issues":
        if (validationNode) {
          addJarvisMessage({ role: "jarvis", text: response });
          setFocusNodeId(validationNode.id);
          setTimeout(() => openDrawer(validationNode.id, "issues"), 700);
          showJarvisStrip({ message: response, nodeId: validationNode.id });
          return;
        }
        break;

      case "status":
        addJarvisMessage({ role: "jarvis", text: response });
        showJarvisStrip({ message: response });
        return;

      case "acknowledge":
        if (validationNode) {
          acknowledgeAllIssues(validationNode.id);
          addJarvisMessage({ role: "jarvis", text: response });
          showJarvisStrip({ message: response });
          return;
        }
        break;

      case "undo":
        undo();
        addJarvisMessage({ role: "jarvis", text: response });
        showJarvisStrip({ message: response });
        return;

      case "clear":
        clearProject();
        addJarvisMessage({ role: "jarvis", text: response });
        showJarvisStrip({ message: response });
        return;
    }

    // Fallback: just show the response
    addJarvisMessage({ role: "jarvis", text: response });
    showJarvisStrip({ message: response });
  }

  return (
    <header
      className="h-12 bg-[#0d1421] border-b border-white/5 flex items-center px-4 gap-4 flex-shrink-0 z-10"
      onDrop={handleDrop}
      onDragOver={(e) => e.preventDefault()}
    >
      {/* Brand */}
      <div className="flex items-center gap-2 select-none flex-shrink-0">
        <CircuitBoard size={18} className="text-cyan-400" />
        <span className="text-white font-semibold text-sm tracking-tight">Circuit.AI</span>
      </div>

      {/* Input */}
      <form onSubmit={handleSubmit} className="flex-1 flex items-center gap-2">
        <div className="flex-1 flex items-center gap-2 bg-white/5 border border-white/10 rounded-lg px-3 py-1.5 focus-within:border-cyan-500/50 transition-colors">
          {isJarvisThinking ? (
            <Loader2 size={14} className="text-cyan-400 animate-spin flex-shrink-0" />
          ) : (
            <Zap size={14} className="text-cyan-400/60 flex-shrink-0" />
          )}
          <input
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder='Ask JARVIS — "validate", "manufacture", "show issues", "help"'
            className="flex-1 bg-transparent text-sm text-white placeholder-white/25 outline-none"
          />
        </div>
      </form>

      {/* Upload button */}
      <button
        onClick={() => fileInputRef.current?.click()}
        className="flex items-center gap-1.5 text-xs text-white/40 hover:text-white/80 border border-white/10 hover:border-white/30 rounded-lg px-2.5 py-1.5 transition-colors flex-shrink-0"
        title="Upload file"
      >
        <Upload size={13} />
        <span>Upload</span>
      </button>
      <input
        ref={fileInputRef}
        type="file"
        accept=".kicad_pcb,.kicad_sch,.gbr,.gtl,.gbl,.csv"
        className="hidden"
        onChange={handleFileInput}
      />

      {/* Status */}
      <div className="flex items-center gap-1.5 flex-shrink-0">
        <span className="w-2 h-2 rounded-full bg-emerald-400 shadow-[0_0_6px_rgba(52,211,153,0.6)]" />
        <span className="text-xs text-white/40">online</span>
      </div>
    </header>
  );
}

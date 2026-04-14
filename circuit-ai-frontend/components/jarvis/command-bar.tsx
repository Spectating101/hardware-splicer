"use client";

import { useState, useRef, useEffect } from "react";
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

  // Cmd+K / Ctrl+K → focus command input; Ctrl+Z → undo (when not in a text field)
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.ctrlKey || e.metaKey) && e.key === "k") {
        e.preventDefault();
        inputRef.current?.focus();
        inputRef.current?.select();
      }
      if ((e.ctrlKey || e.metaKey) && e.key === "z" && !e.shiftKey) {
        const target = e.target as HTMLElement;
        const isEditable =
          target.tagName === "INPUT" ||
          target.tagName === "TEXTAREA" ||
          target.isContentEditable;
        if (!isEditable) {
          e.preventDefault();
          undo();
          addJarvisMessage({ role: "jarvis", text: "Undone." });
          showJarvisStrip({ message: "Undone." });
        }
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [undo, addJarvisMessage, showJarvisStrip]);

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

    const severityOrder = { critical: 0, error: 1, warning: 2 } as const;
    const topIssue = activeIssues.length > 0
      ? [...activeIssues].sort((a, b) =>
          (severityOrder[a.severity as keyof typeof severityOrder] ?? 3) -
          (severityOrder[b.severity as keyof typeof severityOrder] ?? 3)
        )[0]
      : undefined;

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
        topIssue: topIssue ? { what: topIssue.what, fix: topIssue.fix, severity: topIssue.severity } : undefined,
      },
    };
  }

  function quickSubmit(text: string) {
    addJarvisMessage({ role: "user", text });
    const intent = parseIntent(text);
    const { ctx, boardNode, validationNode, mfgNode } = buildContext();
    const response = contextualResponse(intent, ctx);
    executeIntent(intent, response, boardNode, validationNode, mfgNode, ctx);
    // Refocus input after chip action so user can keep typing
    setTimeout(() => inputRef.current?.focus(), 50);
  }

  function getContextualPlaceholder(): string {
    const { ctx } = buildContext();
    if (!ctx.hasBoardNode)
      return 'Drop a .kicad_pcb file, or ask anything…';
    if (ctx.hasManufacturing)
      return `${ctx.boardName ?? "Board"} packaged and ready — ask anything or say "status"…`;
    if (!ctx.hasValidation)
      return `"validate" to check ${ctx.boardName ?? "the board"}, or ask anything…`;
    if (ctx.hasCriticals)
      return `"show issues" to review ${ctx.activeIssueCount} critical issue${ctx.activeIssueCount === 1 ? "" : "s"}, or ask anything…`;
    if (ctx.activeIssueCount > 0)
      return `"manufacture" or "acknowledge warnings" — or ask anything…`;
    return `"manufacture" to generate Gerbers and BOM, or ask anything…`;
  }

  function buildContextChips(): { label: string; cmd: string; color: string }[] {
    const { ctx } = buildContext();
    const chips: { label: string; cmd: string; color: string }[] = [];
    if (!ctx.hasBoardNode) return chips;
    if (!ctx.hasValidation) {
      chips.push({ label: "⚡ validate", cmd: "validate", color: "text-cyan-400 border-cyan-500/30 hover:bg-cyan-500/10" });
    } else {
      if (ctx.activeIssueCount > 0) {
        chips.push({ label: `show issues (${ctx.activeIssueCount})`, cmd: "show issues", color: "text-amber-400 border-amber-500/30 hover:bg-amber-500/10" });
      }
      if (!ctx.hasCriticals && !ctx.hasManufacturing) {
        chips.push({ label: "→ manufacture", cmd: "manufacture", color: "text-purple-400 border-purple-500/30 hover:bg-purple-500/10" });
      }
      if (ctx.hasManufacturing) {
        chips.push({ label: "✓ status", cmd: "status", color: "text-emerald-400 border-emerald-500/30 hover:bg-emerald-500/10" });
      }
    }
    // Always offer "what's next?" as a gentle nudge when the pipeline isn't complete
    if (!ctx.hasManufacturing) {
      chips.push({ label: "what's next?", cmd: "what's next", color: "text-white/25 border-white/10 hover:bg-white/5 hover:text-white/50" });
    }
    return chips;
  }

  function executeIntent(
    intent: ReturnType<typeof parseIntent>,
    response: string,
    boardNode: ReturnType<typeof buildContext>["boardNode"],
    validationNode: ReturnType<typeof buildContext>["validationNode"],
    mfgNode: ReturnType<typeof buildContext>["mfgNode"],
    ctx: ReturnType<typeof buildContext>["ctx"]
  ) {
    switch (intent.type) {
      case "validate":
        if (boardNode) {
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

      case "open_board":
        if (boardNode) {
          addJarvisMessage({ role: "jarvis", text: response });
          setFocusNodeId(boardNode.id);
          setTimeout(() => openDrawer(boardNode.id, "overview"), 700);
          showJarvisStrip({ message: response, nodeId: boardNode.id });
          return;
        }
        break;

      case "open_mfg":
        if (mfgNode) {
          addJarvisMessage({ role: "jarvis", text: response });
          setFocusNodeId(mfgNode.id);
          setTimeout(() => openDrawer(mfgNode.id, "manufacture"), 700);
          showJarvisStrip({ message: response, nodeId: mfgNode.id });
          return;
        }
        break;
    }

    addJarvisMessage({ role: "jarvis", text: response });
    showJarvisStrip({ message: response });
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const text = input.trim();
    if (!text) return;

    addJarvisMessage({ role: "user", text });
    setInput("");

    const intent = parseIntent(text);
    const { ctx, boardNode, validationNode, mfgNode } = buildContext();
    const response = contextualResponse(intent, ctx);
    executeIntent(intent, response, boardNode, validationNode, mfgNode, ctx);
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
            placeholder={getContextualPlaceholder()}
            className="flex-1 bg-transparent text-sm text-white placeholder-white/25 outline-none"
            onKeyDown={(e) => {
              if (e.key === "Tab" && input === "") {
                const chips = buildContextChips();
                const first = chips.find((c) => c.cmd !== "what's next");
                if (first) {
                  e.preventDefault();
                  quickSubmit(first.cmd);
                }
              }
            }}
          />
          {input === "" && (() => {
            const chips = buildContextChips();
            const hasActionChip = chips.some((c) => c.cmd !== "what's next");
            return hasActionChip ? (
              <kbd className="hidden sm:block text-[9px] font-mono text-white/15 bg-white/5 border border-white/10 rounded px-1 py-0.5 flex-shrink-0">
                Tab
              </kbd>
            ) : (
              <kbd className="hidden sm:block text-[9px] font-mono text-white/15 bg-white/5 border border-white/10 rounded px-1 py-0.5 flex-shrink-0">
                ⌘K
              </kbd>
            );
          })()}
        </div>
      </form>

      {/* Context-aware quick-action chips — visible when input is empty */}
      {input === "" && !isJarvisThinking && (
        <div className="hidden sm:flex items-center gap-1.5 flex-shrink-0">
          {buildContextChips().map((chip) => (
            <button
              key={chip.cmd}
              type="button"
              onClick={() => quickSubmit(chip.cmd)}
              className={`text-[11px] px-2 py-0.5 rounded-full border transition-colors ${chip.color}`}
            >
              {chip.label}
            </button>
          ))}
        </div>
      )}

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

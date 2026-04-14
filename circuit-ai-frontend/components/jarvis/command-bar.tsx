"use client";

import { useState, useRef } from "react";
import { CircuitBoard, Zap, Loader2, KeyRound } from "lucide-react";
import { useWorkspaceStore, newNodeId } from "@/lib/store";
import { detectFileKind, jarvis } from "@/lib/jarvis";
import type { FileNodeData, WorkspaceNode } from "@/lib/node-types";
import Link from "next/link";

export function CommandBar() {
  const [input, setInput] = useState("");
  const { isJarvisThinking, addJarvisMessage, addNode, showJarvisStrip } =
    useWorkspaceStore();
  const inputRef = useRef<HTMLInputElement>(null);

  function handleFileOnBar(file: File) {
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

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!input.trim()) return;
    addJarvisMessage({ role: "user", text: input.trim() });
    const response = jarvis.defaultResponse();
    addJarvisMessage({ role: "jarvis", text: response });
    showJarvisStrip({ message: response });
    setInput("");
  }

  return (
    <header
      className="h-12 bg-[#0d1421] border-b border-white/5 flex items-center px-4 gap-4 flex-shrink-0 z-10"
      onDrop={handleDrop}
      onDragOver={(e) => e.preventDefault()}
    >
      {/* Left: brand */}
      <div className="flex items-center gap-2 select-none flex-shrink-0">
        <CircuitBoard size={18} className="text-cyan-400" />
        <span className="text-white font-semibold text-sm tracking-tight">
          Circuit.AI
        </span>
      </div>

      {/* Center: input */}
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
            placeholder="What do you want to build?"
            className="flex-1 bg-transparent text-sm text-white placeholder-white/30 outline-none"
          />
        </div>
      </form>

      {/* Right: status + keys */}
      <div className="flex items-center gap-3 flex-shrink-0">
        <div className="flex items-center gap-1.5">
          <span className="w-2 h-2 rounded-full bg-emerald-400 shadow-[0_0_6px_rgba(52,211,153,0.6)]" />
          <span className="text-xs text-white/40">online</span>
        </div>
        <Link
          href="/dashboard/keys"
          className="text-white/40 hover:text-white/80 transition-colors"
        >
          <KeyRound size={16} />
        </Link>
      </div>
    </header>
  );
}

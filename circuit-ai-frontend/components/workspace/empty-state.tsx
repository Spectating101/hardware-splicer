"use client";

import { FileText, List, Zap, Upload } from "lucide-react";
import { useWorkspaceStore } from "@/lib/store";
import { jarvis } from "@/lib/jarvis";

const tiles = [
  {
    icon: FileText,
    title: "Drop a KiCad PCB",
    description: "Validate, analyze, and generate Gerbers",
    hint: ".kicad_pcb",
    prompt: "I want to validate a KiCad PCB",
    accent: "group-hover:border-cyan-500/40 group-hover:shadow-[0_0_20px_rgba(6,182,212,0.08)]",
  },
  {
    icon: List,
    title: "Paste a BOM CSV",
    description: "Source components and check availability",
    hint: ".csv",
    prompt: "I want to process a bill of materials",
    accent: "group-hover:border-violet-500/40 group-hover:shadow-[0_0_20px_rgba(139,92,246,0.08)]",
  },
  {
    icon: Zap,
    title: "Start from scratch",
    description: "Describe what you want to build",
    hint: "prompt",
    prompt: "Help me start a new electronics project",
    accent: "group-hover:border-amber-500/40 group-hover:shadow-[0_0_20px_rgba(245,158,11,0.08)]",
  },
];

export function EmptyState() {
  const { addJarvisMessage, showJarvisStrip } = useWorkspaceStore();

  function handleTile(prompt: string) {
    addJarvisMessage({ role: "user", text: prompt });
    const response = jarvis.defaultResponse();
    addJarvisMessage({ role: "jarvis", text: response });
    showJarvisStrip({ message: response });
  }

  return (
    <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
      {/* Drop zone hint — very subtle */}
      <div className="absolute inset-8 rounded-3xl border border-dashed border-white/[0.04] pointer-events-none" />

      <div className="flex flex-col items-center gap-8 pointer-events-auto">
        {/* JARVIS identity */}
        <div className="flex flex-col items-center gap-3">
          <div className="relative">
            <div className="w-10 h-10 rounded-xl bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center">
              <Zap size={18} className="text-cyan-400" />
            </div>
            {/* Pulse ring */}
            <span className="absolute inset-0 rounded-xl border border-cyan-500/20 animate-ping opacity-30" />
          </div>
          <div className="text-center">
            <h2 className="text-white/70 text-base font-medium tracking-tight">
              JARVIS is ready
            </h2>
            <p className="text-white/25 text-sm mt-1">
              Drop a file here or use the command bar above
            </p>
          </div>
        </div>

        {/* Starter tiles */}
        <div className="flex gap-3">
          {tiles.map((tile) => (
            <button
              key={tile.title}
              onClick={() => handleTile(tile.prompt)}
              className={`group flex flex-col items-start gap-3 w-44 p-4 rounded-2xl border border-white/[0.07] bg-[#141e2e]/80 transition-all text-left ${tile.accent}`}
            >
              <div className="flex items-center justify-between w-full">
                <tile.icon
                  size={16}
                  className="text-white/30 group-hover:text-cyan-400 transition-colors"
                />
                <span className="text-[10px] text-white/20 font-mono group-hover:text-white/30 transition-colors">
                  {tile.hint}
                </span>
              </div>
              <div>
                <p className="text-xs text-white/60 font-medium group-hover:text-white/80 transition-colors">
                  {tile.title}
                </p>
                <p className="text-[11px] text-white/25 leading-relaxed mt-0.5">
                  {tile.description}
                </p>
              </div>
            </button>
          ))}
        </div>

        {/* Upload hint */}
        <div className="flex items-center gap-2 text-white/20 text-xs">
          <Upload size={11} />
          <span>drag files anywhere on the canvas</span>
        </div>
      </div>
    </div>
  );
}

"use client";

import { FileText, List, Zap } from "lucide-react";
import { useWorkspaceStore } from "@/lib/store";
import { jarvis } from "@/lib/jarvis";

const tiles = [
  {
    icon: FileText,
    title: "Drop a KiCad PCB",
    description: "Validate, analyze, and manufacture .kicad_pcb files",
    prompt: "I want to validate a KiCad PCB",
  },
  {
    icon: List,
    title: "Paste a BOM CSV",
    description: "Source components and check availability",
    prompt: "I want to process a bill of materials",
  },
  {
    icon: Zap,
    title: "Start from scratch",
    description: "Describe what you want to build",
    prompt: "Help me start a new electronics project",
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
      <div className="flex flex-col items-center gap-6 pointer-events-auto">
        <div className="text-center">
          <h2 className="text-white/60 text-lg font-medium">
            Drop a file or choose a starting point
          </h2>
          <p className="text-white/25 text-sm mt-1">
            JARVIS will guide you through the rest
          </p>
        </div>
        <div className="flex gap-4">
          {tiles.map((tile) => (
            <button
              key={tile.title}
              onClick={() => handleTile(tile.prompt)}
              className="flex flex-col items-start gap-2 w-48 p-4 rounded-2xl border border-white/10 bg-[#141e2e] hover:border-cyan-500/40 hover:bg-[#141e2e]/80 transition-all text-left group"
            >
              <tile.icon
                size={20}
                className="text-cyan-400/60 group-hover:text-cyan-400 transition-colors"
              />
              <span className="text-sm text-white/70 font-medium group-hover:text-white transition-colors">
                {tile.title}
              </span>
              <span className="text-xs text-white/30 leading-relaxed">
                {tile.description}
              </span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

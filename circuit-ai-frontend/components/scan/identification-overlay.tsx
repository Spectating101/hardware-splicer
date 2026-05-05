"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import type { SalvageModule, SafetyLevel } from "@/lib/cad-types";

interface IdentificationOverlayProps {
  imageUrl: string;
  modules: Array<Partial<SalvageModule> & { id: string; label: string }>;
  selectedId: string | null;
  onSelect(id: string | null): void;
}

const KIND_COLORS: Record<string, { box: string; chip: string }> = {
  mcu:       { box: "stroke-violet-300 fill-violet-400/10",    chip: "bg-slate-950/90 text-white border-violet-300/80 shadow-lg shadow-black/35" },
  power:     { box: "stroke-amber-300 fill-amber-400/10",      chip: "bg-slate-950/90 text-white border-amber-300/80 shadow-lg shadow-black/35" },
  radio:     { box: "stroke-cyan-300 fill-cyan-400/10",        chip: "bg-slate-950/90 text-white border-cyan-300/80 shadow-lg shadow-black/35" },
  sensor:    { box: "stroke-emerald-300 fill-emerald-400/10",  chip: "bg-slate-950/90 text-white border-emerald-300/80 shadow-lg shadow-black/35" },
  driver:    { box: "stroke-rose-300 fill-rose-400/10",        chip: "bg-slate-950/90 text-white border-rose-300/80 shadow-lg shadow-black/35" },
  connector: { box: "stroke-sky-300 fill-sky-400/10",          chip: "bg-slate-950/90 text-white border-sky-300/80 shadow-lg shadow-black/35" },
  passive:   { box: "stroke-slate-300 fill-slate-400/10",      chip: "bg-slate-950/90 text-white border-slate-300/80 shadow-lg shadow-black/35" },
  unknown:   { box: "stroke-white/40 fill-white/5",            chip: "bg-slate-950/90 text-white border-white/60 shadow-lg shadow-black/35" },
};

const SAFETY_OUTLINE: Record<SafetyLevel, string> = {
  safe: "",
  caution: "drop-shadow(0_0_4px_rgba(245,158,11,0.7))",
  hazard: "drop-shadow(0_0_6px_rgba(244,63,94,0.85))",
};

export function IdentificationOverlay({ imageUrl, modules, selectedId, onSelect }: IdentificationOverlayProps) {
  const [imgDims, setImgDims] = useState<{ w: number; h: number } | null>(null);

  return (
    <div className="relative w-full overflow-hidden rounded-2xl border border-white/10 bg-black">
      <img
        src={imageUrl}
        alt="Board under analysis"
        className="block h-auto w-full"
        onLoad={(e) => {
          const el = e.currentTarget;
          setImgDims({ w: el.naturalWidth, h: el.naturalHeight });
        }}
      />
      {imgDims && (
        <svg
          className="absolute inset-0 h-full w-full"
          viewBox={`0 0 ${imgDims.w} ${imgDims.h}`}
          preserveAspectRatio="none"
          onClick={() => onSelect(null)}
        >
          {modules.filter((m) => m.bbox).map((m) => {
            const b = m.bbox!;
            const x = b.x * imgDims.w;
            const y = b.y * imgDims.h;
            const w = b.w * imgDims.w;
            const h = b.h * imgDims.h;
            const colors = KIND_COLORS[m.kind ?? "unknown"] ?? KIND_COLORS.unknown;
            const isSel = selectedId === m.id;
            const filter = SAFETY_OUTLINE[m.safety ?? "safe"];
            const labelWidth = Math.max(34, Math.min(imgDims.w - x, w + 8, 120));
            return (
              <g
                key={m.id}
                className="cursor-pointer transition-opacity"
                onClick={(e) => { e.stopPropagation(); onSelect(m.id); }}
                style={{ opacity: selectedId && !isSel ? 0.35 : 1, filter }}
              >
                <rect
                  x={x} y={y} width={w} height={h}
                  className={cn(
                    colors.box,
                    isSel ? "stroke-[3]" : "stroke-[2]",
                  )}
                  strokeDasharray={isSel ? undefined : "4 4"}
                  rx={4}
                />
                {/* label chip just above the rect */}
                <foreignObject
                  x={Math.max(0, x - 2)}
                  y={Math.max(0, y - 28)}
                  width={labelWidth}
                  height={26}
                >
                  <div className={cn("inline-flex max-w-full items-center gap-1 rounded-md border px-1.5 py-0.5 text-[11px] font-medium", colors.chip)}>
                    <span className="truncate">{m.label}</span>
                  </div>
                </foreignObject>
              </g>
            );
          })}
        </svg>
      )}
    </div>
  );
}

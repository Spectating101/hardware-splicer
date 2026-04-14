"use client";

import { useState } from "react";
import type { KicadComponent } from "@/lib/kicad-parser";

interface StructureViewerProps {
  components: KicadComponent[];
  layerCount: number;
  boardName: string;
}

type LayerFilter = "all" | "front" | "back";

export function StructureViewer({ components, layerCount, boardName }: StructureViewerProps) {
  const [layerFilter, setLayerFilter] = useState<LayerFilter>("all");
  const [hovered, setHovered] = useState<string | null>(null);

  if (components.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center p-6">
        <div className="text-center">
          <p className="text-white/40 text-sm font-medium">No component positions available</p>
          <p className="text-white/25 text-xs mt-1">
            Re-drop the .kicad_pcb file so I can read the coordinates.
          </p>
        </div>
      </div>
    );
  }

  const filtered = components.filter((c) => {
    if (layerFilter === "front") return c.layer === "F.Cu";
    if (layerFilter === "back") return c.layer === "B.Cu";
    return true;
  });

  // Normalise coordinates to SVG space
  const xs = components.map((c) => c.x);
  const ys = components.map((c) => c.y);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  const rangeX = maxX - minX || 1;
  const rangeY = maxY - minY || 1;

  const PAD = 28; // padding inside SVG
  const SVG_W = 340;
  const SVG_H = 220;
  const innerW = SVG_W - PAD * 2;
  const innerH = SVG_H - PAD * 2;

  const toSvg = (x: number, y: number) => ({
    svgX: PAD + ((x - minX) / rangeX) * innerW,
    svgY: PAD + ((y - minY) / rangeY) * innerH,
  });

  const frontCount = components.filter((c) => c.layer === "F.Cu").length;
  const backCount = components.filter((c) => c.layer === "B.Cu").length;

  return (
    <div className="flex flex-col gap-3 p-4">
      {/* Layer toggle */}
      <div className="flex items-center gap-2">
        <span className="text-xs text-white/40 flex-shrink-0">Layers</span>
        {(["all", "front", "back"] as const).map((f) => (
          <button
            key={f}
            onClick={() => setLayerFilter(f)}
            className={`text-xs px-2 py-0.5 rounded-md border transition-colors ${
              layerFilter === f
                ? "bg-cyan-500/20 text-cyan-300 border-cyan-500/40"
                : "text-white/40 border-white/10 hover:border-white/20"
            }`}
          >
            {f === "all" ? `All (${layerCount}L)` : f === "front" ? `F.Cu (${frontCount})` : `B.Cu (${backCount})`}
          </button>
        ))}
      </div>

      {/* SVG viewer */}
      <div className="rounded-xl border border-white/10 bg-[#0d1421] overflow-hidden">
        <svg
          width={SVG_W}
          height={SVG_H}
          viewBox={`0 0 ${SVG_W} ${SVG_H}`}
          className="w-full"
        >
          {/* Board outline */}
          <rect
            x={PAD - 8}
            y={PAD - 8}
            width={innerW + 16}
            height={innerH + 16}
            rx={4}
            fill="none"
            stroke="rgba(255,255,255,0.1)"
            strokeWidth={1}
            strokeDasharray="4 3"
          />

          {/* Board name label */}
          <text
            x={PAD - 4}
            y={PAD - 12}
            fill="rgba(255,255,255,0.2)"
            fontSize={8}
            fontFamily="monospace"
          >
            {boardName}
          </text>

          {/* Components */}
          {filtered.map((c, i) => {
            const { svgX, svgY } = toSvg(c.x, c.y);
            const isFront = c.layer === "F.Cu";
            const isHov = hovered === `${i}`;
            const color = isFront ? "rgba(6,182,212,0.8)" : "rgba(251,191,36,0.8)";
            const glowColor = isFront ? "rgba(6,182,212,0.3)" : "rgba(251,191,36,0.3)";

            return (
              <g
                key={i}
                onMouseEnter={() => setHovered(`${i}`)}
                onMouseLeave={() => setHovered(null)}
                style={{ cursor: "default" }}
              >
                {isHov && (
                  <circle cx={svgX} cy={svgY} r={9} fill={glowColor} />
                )}
                <circle
                  cx={svgX}
                  cy={svgY}
                  r={isHov ? 5 : 3.5}
                  fill={color}
                  opacity={layerFilter === "all" && !isFront ? 0.5 : 1}
                />
                {isHov && (
                  <text
                    x={svgX + 8}
                    y={svgY + 4}
                    fill="white"
                    fontSize={8}
                    fontFamily="monospace"
                    style={{ pointerEvents: "none" }}
                  >
                    {c.ref} {c.value}
                  </text>
                )}
              </g>
            );
          })}
        </svg>
      </div>

      {/* Legend */}
      <div className="flex items-center gap-4 text-xs text-white/40">
        <div className="flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 rounded-full bg-cyan-500/80 flex-shrink-0" />
          <span>F.Cu ({frontCount})</span>
        </div>
        {backCount > 0 && (
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-amber-400/80 flex-shrink-0" />
            <span>B.Cu ({backCount})</span>
          </div>
        )}
        <span className="ml-auto">hover for ref</span>
      </div>
    </div>
  );
}

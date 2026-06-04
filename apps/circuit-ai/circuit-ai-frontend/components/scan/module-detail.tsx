"use client";

import { AlertTriangle, Cpu, Plug, Radio, Settings2, Zap, ShieldAlert } from "lucide-react";
import type { SalvageModule } from "@/lib/cad-types";
import { SafetyBanner } from "@/components/safety-banner";

const KIND_ICON: Record<string, typeof Cpu> = {
  mcu: Cpu,
  power: Zap,
  radio: Radio,
  sensor: Settings2,
  driver: Settings2,
  connector: Plug,
  passive: Settings2,
  unknown: ShieldAlert,
};

interface ModuleDetailProps {
  module: Partial<SalvageModule> & { id: string; label: string };
  onAddToInventory?: () => void;
  onStartBuild?: () => void;
}

export function ModuleDetail({ module, onAddToInventory, onStartBuild }: ModuleDetailProps) {
  const Icon = KIND_ICON[module.kind ?? "unknown"];
  const safety = module.safety ?? "safe";
  return (
    <div className="rounded-2xl border border-white/10 bg-white/[0.02] p-5">
      <div className="flex items-start gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-white/5 text-white">
          <Icon className="h-5 w-5" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="text-xs font-semibold uppercase tracking-wider text-slate-500">
            {module.kind ?? "unknown"}
          </div>
          <h3 className="mt-0.5 text-lg font-semibold text-white">{module.label}</h3>
          {module.description && (
            <p className="mt-2 text-sm leading-6 text-slate-300">{module.description}</p>
          )}
        </div>
      </div>

      {safety !== "safe" && (
        <div className="mt-4">
          <SafetyBanner
            level={safety}
            message={
              safety === "hazard"
                ? "This block carries mains-level voltage, a large energy reservoir, or another lethal hazard. Do not touch without training + proper tools."
                : "Moderate-voltage block. Power down, discharge capacitors, and double-check before probing."
            }
            requireAck={safety === "hazard"}
          />
        </div>
      )}

      {module.extraction && (
        <div className="mt-4 rounded-xl border border-white/10 bg-black/20 p-3">
          <div className="mb-1 text-[11px] font-semibold uppercase tracking-wider text-cyan-300/80">Extraction plan</div>
          <p className="text-sm leading-6 text-slate-200">{module.extraction}</p>
        </div>
      )}

      {module.pins && module.pins.length > 0 && (
        <div className="mt-4">
          <div className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-slate-500">Useful pins</div>
          <div className="grid grid-cols-2 gap-2">
            {module.pins.map((p, i) => (
              <div key={i} className="rounded-lg border border-white/5 bg-white/[0.02] px-3 py-2 text-xs">
                <div className="font-medium text-white">{p.name}</div>
                <div className="text-slate-400">{p.role}{p.voltage ? ` · ${p.voltage}` : ""}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {module.warnings && module.warnings.length > 0 && (
        <div className="mt-4 rounded-xl border border-amber-400/30 bg-amber-400/5 p-3">
          <div className="mb-1 inline-flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-amber-300">
            <AlertTriangle className="h-3.5 w-3.5" /> Warnings
          </div>
          <ul className="list-disc pl-5 text-sm leading-6 text-amber-100">
            {module.warnings.map((w, i) => <li key={i}>{w}</li>)}
          </ul>
        </div>
      )}

      {(onAddToInventory || onStartBuild) && (
        <div className="mt-5 flex flex-wrap gap-2">
          {onAddToInventory && (
            <button
              onClick={onAddToInventory}
              className="rounded-full bg-white/5 px-3 py-1.5 text-xs font-medium text-white hover:bg-white/10 transition-colors border border-white/10"
            >
              + Add to parts bin
            </button>
          )}
          {onStartBuild && (
            <button
              onClick={onStartBuild}
              className="rounded-full bg-white px-3 py-1.5 text-xs font-semibold text-slate-900 hover:bg-slate-100 transition-colors"
            >
              Start building with this →
            </button>
          )}
        </div>
      )}
    </div>
  );
}

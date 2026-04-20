"use client";

import { useState } from "react";
import { Cpu, Zap, Radio, Gauge, Monitor, Wrench, Cable } from "lucide-react";
import { MODULE_LIBRARY, type ModuleSpec } from "@/lib/modules/module-library";

const CATEGORY_ICON: Record<string, typeof Cpu> = {
  mcu: Cpu,
  power: Zap,
  radio: Radio,
  sensor: Gauge,
  display: Monitor,
  actuator: Wrench,
  interface: Cable,
  passive: Wrench,
};

const CATEGORY_LABEL: Record<string, string> = {
  mcu: "Microcontrollers",
  power: "Power",
  sensor: "Sensors",
  display: "Display",
  actuator: "Actuators",
  radio: "Radio",
  interface: "Interface",
  passive: "Passive",
};

interface ModuleLibraryPanelProps {
  onAdd(spec: ModuleSpec): void;
}

export function ModuleLibraryPanel({ onAdd }: ModuleLibraryPanelProps) {
  const [query, setQuery] = useState("");
  const filtered = MODULE_LIBRARY.filter(
    (m) =>
      !query ||
      m.label.toLowerCase().includes(query.toLowerCase()) ||
      m.summary.toLowerCase().includes(query.toLowerCase()) ||
      m.category.includes(query.toLowerCase()),
  );

  const byCategory = filtered.reduce<Record<string, ModuleSpec[]>>((acc, m) => {
    (acc[m.category] ??= []).push(m);
    return acc;
  }, {});

  return (
    <div className="flex h-full w-72 shrink-0 flex-col border-r border-white/10 bg-black/40">
      <div className="border-b border-white/10 p-3">
        <div className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-slate-500">
          Module library
        </div>
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search modules…"
          className="w-full rounded-lg border border-white/10 bg-white/[0.03] px-3 py-1.5 text-xs text-white placeholder:text-slate-500 focus:border-white/20 focus:outline-none"
        />
      </div>
      <div className="flex-1 overflow-y-auto p-2">
        {Object.entries(byCategory).map(([cat, mods]) => {
          const Icon = CATEGORY_ICON[cat] ?? Wrench;
          return (
            <div key={cat} className="mb-3">
              <div className="mb-1 flex items-center gap-1.5 px-2 text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                <Icon className="h-3 w-3" />
                {CATEGORY_LABEL[cat] ?? cat}
              </div>
              <div className="space-y-1">
                {mods.map((m) => (
                  <button
                    key={m.id}
                    onClick={() => onAdd(m)}
                    draggable
                    onDragStart={(e) => {
                      e.dataTransfer.setData("application/circuit-module", m.id);
                      e.dataTransfer.effectAllowed = "copy";
                    }}
                    className="w-full cursor-grab rounded-lg border border-white/5 bg-white/[0.02] px-2.5 py-2 text-left text-xs hover:border-white/20 hover:bg-white/[0.05] active:cursor-grabbing"
                  >
                    <div className="font-medium text-white">{m.label}</div>
                    <div className="mt-0.5 line-clamp-2 text-[11px] leading-snug text-slate-400">
                      {m.summary}
                    </div>
                  </button>
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

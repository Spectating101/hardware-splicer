"use client";

import { Handle, Position, type NodeProps } from "@xyflow/react";
import { Cpu, Zap, Radio, Gauge, Monitor, Wrench, Cable } from "lucide-react";
import { findModule, type ModuleSpec } from "@/lib/modules/module-library";

const CAT_ICON: Record<string, typeof Cpu> = {
  mcu: Cpu,
  power: Zap,
  radio: Radio,
  sensor: Gauge,
  display: Monitor,
  actuator: Wrench,
  interface: Cable,
  passive: Wrench,
};

const ROLE_COLOR: Record<string, string> = {
  gnd: "#475569",
  power_in: "#ef4444",
  power_out: "#f59e0b",
  digital_io: "#a78bfa",
  digital_in: "#a78bfa",
  digital_out: "#a78bfa",
  analog_in: "#34d399",
  pwm: "#f472b6",
  uart_tx: "#22d3ee",
  uart_rx: "#22d3ee",
  i2c_sda: "#38bdf8",
  i2c_scl: "#38bdf8",
  spi_mosi: "#2dd4bf",
  spi_miso: "#2dd4bf",
  spi_sck: "#2dd4bf",
  spi_cs: "#2dd4bf",
  reset: "#fb7185",
  other: "#94a3b8",
};

export type ModuleNodeData = { moduleId: string };

const PIN_ROW_H = 22;
const MODULE_W = 240;

export function ModuleNode({ data, selected }: NodeProps) {
  const moduleId = (data as ModuleNodeData).moduleId;
  const spec: ModuleSpec | undefined = findModule(moduleId);
  if (!spec) {
    return (
      <div className="rounded-lg border border-rose-500 bg-black px-3 py-2 text-xs text-rose-300">
        Unknown module: {moduleId}
      </div>
    );
  }
  const Icon = CAT_ICON[spec.category] ?? Wrench;
  const leftPins = spec.pins.slice(0, Math.ceil(spec.pins.length / 2));
  const rightPins = spec.pins.slice(Math.ceil(spec.pins.length / 2));
  const bodyH = Math.max(leftPins.length, rightPins.length) * PIN_ROW_H + 12;

  return (
    <div
      className="relative"
      style={{ width: MODULE_W }}
    >
      {/* Board body — looks like a PCB */}
      <div
        className={`rounded-md shadow-[0_4px_12px_rgba(0,0,0,0.5),inset_0_1px_0_rgba(255,255,255,0.06)] ${
          selected ? "ring-2 ring-cyan-300" : ""
        }`}
        style={{
          background:
            "linear-gradient(180deg, #0c4a2a 0%, #0a3d22 50%, #082e1a 100%)",
          border: "1px solid #0f5132",
        }}
      >
        {/* Silkscreen header */}
        <div
          className="flex items-center gap-2 rounded-t-md px-3 py-2"
          style={{
            background:
              "linear-gradient(180deg, rgba(255,255,255,0.06), rgba(255,255,255,0.02))",
            borderBottom: "1px solid rgba(255,255,255,0.08)",
          }}
        >
          <Icon className="h-3.5 w-3.5" style={{ color: "#d1fae5" }} />
          <div className="min-w-0 flex-1">
            <div
              className="truncate text-[11px] font-bold uppercase tracking-wider"
              style={{ color: "#ecfeff", textShadow: "0 0 6px rgba(34,211,238,0.3)" }}
            >
              {spec.label}
            </div>
            <div className="text-[9px] uppercase tracking-widest" style={{ color: "#86efac" }}>
              {spec.category}
            </div>
          </div>
        </div>

        {/* Pin rows */}
        <div className="relative py-1.5" style={{ height: bodyH }}>
          {/* Left pins */}
          <div className="absolute inset-y-0 left-0 flex flex-col justify-center">
            {leftPins.map((p, idx) => {
              const color = ROLE_COLOR[p.role] ?? ROLE_COLOR.other;
              return (
                <div
                  key={p.id}
                  className="relative flex items-center"
                  style={{ height: PIN_ROW_H }}
                >
                  <Handle
                    id={p.id}
                    type="source"
                    position={Position.Left}
                    style={{
                      width: 10,
                      height: 10,
                      background: color,
                      border: "2px solid #020617",
                      boxShadow: `0 0 4px ${color}`,
                      left: -5,
                    }}
                  />
                  {/* Pad */}
                  <div
                    className="ml-2 rounded-full"
                    style={{
                      width: 6,
                      height: 6,
                      background: color,
                      boxShadow: `0 0 3px ${color}`,
                    }}
                  />
                  <span
                    className="ml-2 truncate text-[10px] font-mono font-semibold"
                    style={{ color: "#d1fae5", maxWidth: 80 }}
                    title={p.label}
                  >
                    {p.label}
                  </span>
                  {idx === 0 && leftPins.length > 1 && (
                    <span
                      aria-hidden
                      className="pointer-events-none absolute"
                      style={{ left: 10, top: 2, width: 4, height: 4, background: "#fbbf24", borderRadius: 999, boxShadow: "0 0 4px #fbbf24" }}
                    />
                  )}
                </div>
              );
            })}
          </div>

          {/* Right pins */}
          <div className="absolute inset-y-0 right-0 flex flex-col justify-center">
            {rightPins.map((p) => {
              const color = ROLE_COLOR[p.role] ?? ROLE_COLOR.other;
              return (
                <div
                  key={p.id}
                  className="relative flex items-center justify-end"
                  style={{ height: PIN_ROW_H }}
                >
                  <span
                    className="mr-2 truncate text-[10px] font-mono font-semibold"
                    style={{ color: "#d1fae5", maxWidth: 80 }}
                    title={p.label}
                  >
                    {p.label}
                  </span>
                  <div
                    className="mr-2 rounded-full"
                    style={{
                      width: 6,
                      height: 6,
                      background: color,
                      boxShadow: `0 0 3px ${color}`,
                    }}
                  />
                  <Handle
                    id={p.id}
                    type="source"
                    position={Position.Right}
                    style={{
                      width: 10,
                      height: 10,
                      background: color,
                      border: "2px solid #020617",
                      boxShadow: `0 0 4px ${color}`,
                      right: -5,
                    }}
                  />
                </div>
              );
            })}
          </div>
        </div>

        {/* Footer hint */}
        <div
          className="rounded-b-md px-3 py-1 text-[9px] uppercase tracking-widest"
          style={{
            borderTop: "1px solid rgba(255,255,255,0.05)",
            color: "#6ee7b7",
            textAlign: "center",
          }}
        >
          {spec.pins.length} pins
        </div>
      </div>
    </div>
  );
}

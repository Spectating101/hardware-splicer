"use client";

import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useSearchParams } from "next/navigation";
import {
  ReactFlow,
  ReactFlowProvider,
  Background,
  BackgroundVariant,
  Controls,
  MiniMap,
  addEdge,
  useNodesState,
  useEdgesState,
  useReactFlow,
  useNodesInitialized,
  type Node,
  type Edge,
  type Connection,
  type NodeTypes,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { Sparkles, Trash2, Download, GraduationCap, CircuitBoard, X } from "lucide-react";
import { downloadKicadPcb } from "@/lib/kicad-serializer";
import { SiteHeader } from "@/components/site-header";
import { ModuleLibraryPanel } from "@/components/build/module-library-panel";
import { ModuleNode, type ModuleNodeData } from "@/components/build/module-node";
import { SafetyCheckPanel } from "@/components/build/safety-check-panel";
import { PcbViewport } from "@/components/cad/pcb-viewport";
import { buildGraphToGeometry } from "@/lib/pcb/build-to-geometry";
import { analyzeBuild, type BuildGraph } from "@/lib/rules/safety-rules";
import { findModule, findPin, MODULE_LIBRARY, type ModuleSpec, type PinRole } from "@/lib/modules/module-library";

function fuzzyFindModule(needle: string): ModuleSpec | undefined {
  const direct = findModule(needle);
  if (direct) return direct;
  const n = needle.toLowerCase().replace(/[^a-z0-9]/g, "");
  const alias =
    /esp32|mcu|microcontroller|controller|processor/.test(n) ? "esp32-devkit"
    : /buck|regulator|power|supply|dcconverter|stepdown/.test(n) ? "buck-lm2596"
    : /boost|stepup/.test(n) ? "boost-mt3608"
    : /temp|humidity|thermistor|sensor/.test(n) ? "dht22"
    : /display|oled|screen/.test(n) ? "ssd1306-128x64"
    : /relay|switch/.test(n) ? "relay-1ch-5v"
    : /motor|servo/.test(n) ? "sg90"
    : null;
  if (alias) return findModule(alias);
  return MODULE_LIBRARY.find((m) => {
    const a = m.id.toLowerCase().replace(/[^a-z0-9]/g, "");
    const b = m.label.toLowerCase().replace(/[^a-z0-9]/g, "");
    return a.includes(n) || n.includes(a) || b.includes(n) || n.includes(b);
  });
}

const nodeTypes: NodeTypes = { module: ModuleNode };

type FlowNode = Node<ModuleNodeData>;

const WIRE_COLOR: Record<PinRole | "default", string> = {
  gnd: "#64748b",
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
  default: "#7dd3fc",
};

function wireColorForPin(spec: ModuleSpec | undefined, pinId: string | null | undefined): string {
  if (!spec || !pinId) return WIRE_COLOR.default;
  const pin = findPin(spec, pinId);
  return WIRE_COLOR[pin?.role ?? "other"] ?? WIRE_COLOR.default;
}

function BuildInner() {
  const [nodes, setNodes, onNodesChange] = useNodesState<FlowNode>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  const [aiBusy, setAiBusy] = useState(false);
  const [aiNote, setAiNote] = useState<string | null>(null);
  const [pcbOpen, setPcbOpen] = useState(false);
  useEffect(() => {
    if (pcbOpen) document.documentElement.classList.add("pcb-modal-open");
    else document.documentElement.classList.remove("pcb-modal-open");
    return () => document.documentElement.classList.remove("pcb-modal-open");
  }, [pcbOpen]);
  const idRef = useRef(0);
  const search = useSearchParams();
  const preloadParam = search?.get("modules") ?? null;
  const preloadedRef = useRef(false);
  const { fitView } = useReactFlow();
  const nodesInitialized = useNodesInitialized();

  const onConnect = useCallback(
    (c: Connection) => {
      const src = nodes.find((n) => n.id === c.source);
      const spec = src ? findModule((src.data as ModuleNodeData).moduleId) : undefined;
      const color = wireColorForPin(spec, c.sourceHandle);
      setEdges((eds) =>
        addEdge({ ...c, animated: false, style: { stroke: color, strokeWidth: 2.5 } }, eds),
      );
    },
    [setEdges, nodes],
  );

  const addModule = useCallback(
    (spec: ModuleSpec, pos?: { x: number; y: number }) => {
      idRef.current += 1;
      const id = `n${idRef.current}`;
      const i = idRef.current - 1;
      const col = i % 3;
      const row = Math.floor(i / 3);
      const node: FlowNode = {
        id,
        type: "module",
        position: pos ?? { x: 60 + col * 340, y: 60 + row * 320 },
        data: { moduleId: spec.id },
      };
      setNodes((prev) => [...prev, node]);
    },
    [setNodes],
  );

  useEffect(() => {
    if (preloadedRef.current || !preloadParam) return;
    preloadedRef.current = true;
    const ids = preloadParam.split(",").map((s) => s.trim()).filter(Boolean);
    for (const mid of ids) {
      const spec = fuzzyFindModule(mid);
      if (spec) addModule(spec);
    }
    setTimeout(() => fitView({ padding: 0.25, duration: 400 }), 150);
  }, [preloadParam, addModule, fitView]);

  useEffect(() => {
    if (nodesInitialized && nodes.length > 0) {
      const raf1 = requestAnimationFrame(() => {
        const raf2 = requestAnimationFrame(() => {
          fitView({ padding: 0.3, duration: 400 });
        });
        return () => cancelAnimationFrame(raf2);
      });
      return () => cancelAnimationFrame(raf1);
    }
  }, [nodesInitialized, nodes.length, fitView]);

  const onDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault();
      const moduleId = event.dataTransfer.getData("application/circuit-module");
      const spec = findModule(moduleId);
      if (!spec) return;
      const bounds = (event.currentTarget as HTMLElement).getBoundingClientRect();
      addModule(spec, { x: event.clientX - bounds.left - 120, y: event.clientY - bounds.top - 60 });
    },
    [addModule],
  );

  const graph: BuildGraph = useMemo(() => ({
    nodes: nodes.map((n) => ({ id: n.id, moduleId: (n.data as ModuleNodeData).moduleId })),
    wires: edges.map((e) => ({
      id: e.id,
      from: { nodeId: e.source, pinId: e.sourceHandle ?? "" },
      to: { nodeId: e.target, pinId: e.targetHandle ?? "" },
    })),
  }), [nodes, edges]);

  const warnings = useMemo(() => analyzeBuild(graph), [graph]);
  const pcbGeometry = useMemo(() => (pcbOpen ? buildGraphToGeometry(graph) : null), [pcbOpen, graph]);

  const askJarvisToWire = useCallback(async () => {
    if (nodes.length < 2) {
      setAiNote("Add at least 2 modules first.");
      return;
    }
    setAiBusy(true);
    setAiNote(null);
    try {
      const moduleList = nodes.map((n) => {
        const spec = findModule((n.data as ModuleNodeData).moduleId);
        return {
          nodeId: n.id,
          moduleId: spec?.id,
          label: spec?.label,
          pins: spec?.pins.map((p) => ({ id: p.id, role: p.role, voltage: p.voltage })),
        };
      });
      const prompt = `Wire these modules into a working project. Respond with JSON {"wires":[{"from":{"nodeId","pinId"},"to":{"nodeId","pinId"},"purpose"}], "explanation":"..."}. Use exact nodeId + pinId values. Modules:\n${JSON.stringify(moduleList, null, 2)}`;
      const resp = await fetch("/api/jarvis/chat", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ messages: [{ role: "user", content: prompt }], context: "build-wiring" }),
      });
      if (!resp.ok || !resp.body) throw new Error(`Wiring request failed: ${resp.status}`);
      const reader = resp.body.getReader();
      const dec = new TextDecoder();
      let buf = "";
      let full = "";
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        const frames = buf.split("\n\n");
        buf = frames.pop() ?? "";
        for (const f of frames) {
          const line = f.split("\n").find((l) => l.startsWith("data: "));
          if (!line) continue;
          try {
            const evt = JSON.parse(line.slice(6).trim()) as { delta?: string };
            if (evt.delta) full += evt.delta;
          } catch { /* skip */ }
        }
      }
      const start = full.indexOf("{");
      const end = full.lastIndexOf("}");
      if (start === -1 || end === -1) throw new Error("No JSON in response");
      const parsed = JSON.parse(full.slice(start, end + 1)) as {
        wires?: Array<{ from: { nodeId: string; pinId: string }; to: { nodeId: string; pinId: string }; purpose?: string }>;
        explanation?: string;
      };
      const newEdges: Edge[] = (parsed.wires ?? []).map((w, i) => {
        const srcNode = nodes.find((n) => n.id === w.from.nodeId);
        const spec = srcNode ? findModule((srcNode.data as ModuleNodeData).moduleId) : undefined;
        const color = wireColorForPin(spec, w.from.pinId);
        return {
          id: `ai-${Date.now()}-${i}`,
          source: w.from.nodeId,
          sourceHandle: w.from.pinId,
          target: w.to.nodeId,
          targetHandle: w.to.pinId,
          label: w.purpose,
          animated: true,
          style: { stroke: color, strokeWidth: 2.5 },
          labelStyle: { fill: "#cbd5e1", fontSize: 10, fontFamily: "ui-monospace, monospace" },
          labelBgStyle: { fill: "#0f172a", fillOpacity: 0.85 },
          labelBgPadding: [4, 2] as [number, number],
          labelBgBorderRadius: 4,
        };
      });
      setEdges((prev) => [...prev, ...newEdges]);
      if (parsed.explanation) setAiNote(parsed.explanation);
      setTimeout(() => fitView({ padding: 0.25, duration: 400 }), 100);
    } catch (err) {
      setAiNote(`Wiring failed: ${(err as Error).message}`);
    } finally {
      setAiBusy(false);
    }
  }, [nodes, setEdges, fitView]);

  const clearAll = useCallback(() => {
    setNodes([]);
    setEdges([]);
    setAiNote(null);
    idRef.current = 0;
    preloadedRef.current = false;
  }, [setNodes, setEdges]);

  const exportJson = useCallback(() => {
    const blob = new Blob([JSON.stringify(graph, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `circuit-build-${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }, [graph]);

  const exportBom = useCallback(() => {
    const tally = new Map<string, number>();
    for (const n of graph.nodes) tally.set(n.moduleId, (tally.get(n.moduleId) ?? 0) + 1);
    const rows: string[] = ["Part,Category,Voltage,Pins,Qty"];
    for (const [moduleId, qty] of tally) {
      const spec = findModule(moduleId);
      if (!spec) {
        rows.push(`${moduleId},unknown,,,${qty}`);
        continue;
      }
      const voltages = Array.from(
        new Set(spec.pins.map((p) => p.voltage).filter((v): v is string => typeof v === "string" && v.length > 0)),
      ).sort().join(" / ");
      const esc = (s: string) => (s.includes(",") ? `"${s.replace(/"/g, '""')}"` : s);
      rows.push([esc(spec.label), esc(spec.category), esc(voltages), String(spec.pins.length), String(qty)].join(","));
    }
    const blob = new Blob([rows.join("\n")], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `circuit-bom-${Date.now()}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }, [graph]);

  const empty = nodes.length === 0;

  return (
    <div className="flex min-h-0 w-full flex-1 overflow-hidden bg-[#0a0f1a] text-white">
      <ModuleLibraryPanel onAdd={(spec) => addModule(spec)} />

      <div
        className="relative min-w-0 flex-1"
        onDrop={onDrop}
        onDragOver={(e) => { e.preventDefault(); e.dataTransfer.dropEffect = "copy"; }}
      >
        <div data-build-toolbar className="pointer-events-none absolute inset-x-0 top-0 z-10 flex justify-center pt-3">
          <div className="pointer-events-auto flex gap-2 rounded-full border border-white/10 bg-black/60 px-2 py-1 backdrop-blur">
            <button
              onClick={askJarvisToWire}
              disabled={aiBusy || nodes.length < 2}
              className="inline-flex items-center gap-1.5 rounded-full bg-cyan-400 px-3 py-1.5 text-xs font-semibold text-slate-900 shadow-[0_0_12px_rgba(34,211,238,0.4)] hover:bg-cyan-300 disabled:bg-white/10 disabled:text-slate-400 disabled:shadow-none"
            >
              <Sparkles className="h-3.5 w-3.5" />
              {aiBusy ? "Wiring…" : "Ask Jarvis to wire it"}
            </button>
            <button
              onClick={exportJson}
              disabled={empty}
              className="inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium text-slate-200 hover:bg-white/10 disabled:text-slate-500"
            >
              <Download className="h-3.5 w-3.5" /> JSON
            </button>
            <button
              onClick={exportBom}
              disabled={empty}
              className="inline-flex items-center gap-1.5 rounded-full bg-emerald-400/10 px-3 py-1.5 text-xs font-semibold text-emerald-200 hover:bg-emerald-400/20 disabled:bg-transparent disabled:text-slate-500"
            >
              <Download className="h-3.5 w-3.5" /> BOM
            </button>
            <button
              onClick={() => setPcbOpen(true)}
              disabled={empty}
              className="inline-flex items-center gap-1.5 rounded-full bg-emerald-400/10 px-3 py-1.5 text-xs font-semibold text-emerald-200 hover:bg-emerald-400/20 disabled:bg-transparent disabled:text-slate-500"
            >
              <CircuitBoard className="h-3.5 w-3.5" /> See as PCB
            </button>
            <button
              onClick={() => downloadKicadPcb(graph)}
              disabled={empty}
              className="inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium text-violet-200 hover:bg-violet-500/15 disabled:text-slate-500"
            >
              <GraduationCap className="h-3.5 w-3.5" /> KiCad
            </button>
            <button
              onClick={clearAll}
              disabled={empty}
              className="inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium text-rose-200 hover:bg-rose-500/15 disabled:text-slate-500"
            >
              <Trash2 className="h-3.5 w-3.5" /> Clear
            </button>
          </div>
        </div>

        {empty && (
          <div className="pointer-events-none absolute inset-0 z-0 flex items-center justify-center">
            <div className="rounded-2xl border border-dashed border-white/15 bg-black/30 px-6 py-5 text-center backdrop-blur">
              <div className="text-sm font-semibold text-white">Empty breadboard</div>
              <div className="mt-1 text-xs text-slate-400">Drag a module in from the left, or load from Parts.</div>
            </div>
          </div>
        )}

        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={onConnect}
          nodeTypes={nodeTypes}
          connectionMode={"loose" as never}
          minZoom={0.2}
          maxZoom={1.5}
          fitView
          fitViewOptions={{ padding: 0.25 }}
          proOptions={{ hideAttribution: true }}
          defaultEdgeOptions={{
            animated: true,
            style: { strokeWidth: 2.5, stroke: WIRE_COLOR.default },
          }}
        >
          <Background
            variant={BackgroundVariant.Dots}
            gap={22}
            size={1.4}
            color="#1f3a5a"
            style={{ background:
              "radial-gradient(ellipse at 50% 40%, #0b1a2d 0%, #060b14 70%)" }}
          />
          <Controls className="!bg-black/60 !border-white/10" />
          <MiniMap
            className="!bg-black/60"
            nodeColor={() => "#0f5132"}
            nodeStrokeColor="#22d3ee"
            maskColor="rgba(0,0,0,0.7)"
          />
        </ReactFlow>
      </div>

      <aside
        style={{ width: 320, overflowWrap: "anywhere" }}
        className="flex shrink-0 flex-col gap-3 overflow-y-auto overflow-x-hidden border-l border-white/10 bg-black/40 p-4"
      >
        <div>
          <div className="text-xs font-semibold uppercase tracking-wider text-slate-500">Build</div>
          <h2 className="mt-1 text-base font-semibold text-white">
            {nodes.length} modules · {edges.length} wires
          </h2>
          <p className="mt-1 text-xs leading-5 text-slate-400">
            Drag modules in from the left. Draw wires by dragging between pin dots. Ask Jarvis
            to wire them up when you&apos;re ready.
          </p>
        </div>

        {aiNote && (
          <div className="break-words rounded-xl border border-cyan-400/30 bg-cyan-400/5 p-3 text-xs leading-5 text-cyan-100">
            {aiNote}
          </div>
        )}

        <SafetyCheckPanel warnings={warnings} />

        <div className="mt-auto rounded-xl border border-white/10 bg-white/[0.02] p-3 text-[10px] leading-4 text-slate-400">
          <div className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-slate-500">Wire legend</div>
          <Legend />
        </div>
      </aside>

      {pcbOpen && pcbGeometry && typeof document !== "undefined" && createPortal(
        <div className="fixed inset-0 z-[100] flex flex-col bg-[#05080f]">
          <div className="flex items-center justify-between border-b border-white/10 bg-[#05080f] px-4 py-2">
            <div className="flex items-center gap-2">
              <CircuitBoard className="h-4 w-4 text-emerald-300" />
              <span className="text-sm font-semibold text-white">PCB preview</span>
              <span className="text-xs text-slate-400">
                {pcbGeometry.footprints.length} footprints · {pcbGeometry.nets.length} nets · {pcbGeometry.segments.length} traces
              </span>
            </div>
            <button
              onClick={() => setPcbOpen(false)}
              className="inline-flex items-center gap-1 rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-slate-200 hover:bg-white/10"
            >
              <X className="h-3.5 w-3.5" /> Close
            </button>
          </div>
          <div className="relative flex-1">
            <PcbViewport
              geometry={pcbGeometry}
              selection={{ footprintRef: null }}
              renderMode="engineering"
              topDown
            />
          </div>
        </div>,
        document.body
      )}
    </div>
  );
}

function Legend() {
  const items: Array<[string, string]> = [
    ["Power in", WIRE_COLOR.power_in],
    ["Power out", WIRE_COLOR.power_out],
    ["GND", WIRE_COLOR.gnd],
    ["Digital", WIRE_COLOR.digital_io],
    ["I²C", WIRE_COLOR.i2c_sda],
    ["UART", WIRE_COLOR.uart_tx],
    ["SPI", WIRE_COLOR.spi_mosi],
    ["Analog", WIRE_COLOR.analog_in],
  ];
  return (
    <div className="grid grid-cols-2 gap-x-3 gap-y-1">
      {items.map(([label, color]) => (
        <div key={label} className="flex items-center gap-1.5">
          <span className="block h-2 w-5 rounded-full" style={{ background: color, boxShadow: `0 0 4px ${color}` }} />
          <span>{label}</span>
        </div>
      ))}
    </div>
  );
}

export default function BuildPage() {
  return (
    <div className="flex h-screen flex-col overflow-hidden bg-[#0a0f1a]">
      <SiteHeader />
      <Suspense fallback={<div className="flex-1" />}>
        <ReactFlowProvider>
          <BuildInner />
        </ReactFlowProvider>
      </Suspense>
    </div>
  );
}

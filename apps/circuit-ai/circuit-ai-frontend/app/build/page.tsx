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
import { Trash2, Download, GraduationCap, CircuitBoard, X, Factory } from "lucide-react";
import { downloadKicadPcb, serializeBuildToKicadPcb } from "@/lib/kicad-serializer";
import { BuildJarvisPanel } from "@/components/build/build-jarvis-panel";
import { EngineProofPanel } from "@/components/build/engine-proof-panel";
import { ManufacturePanel, type MfgResult } from "@/components/build/manufacture-panel";
import { snapshotFromBuild, wantsAutoWireAfterCompose } from "@/lib/jarvis/build-agent";
import { formatManufactureJarvisSummary } from "@/lib/jarvis/manufacture-summary";
import { pickModulesForGoal } from "@/lib/jarvis/build-module-picker";
import {
  composeBuildGraphFromCanvasNodes,
  splicePlanToBuildGraph,
  type TranslationResult,
} from "@/lib/salvage/plan-to-graph";
import {
  composeCanvasRemote,
  compileCatalogBuildRemote,
  preferPythonEngine,
} from "@/lib/hardware-splicer/client";
import {
  engineProofUnavailableMessage,
  shouldRequireEngineForManufacture,
  verifyCanvasBuildRemote,
  type EngineCompileProof,
} from "@/lib/hardware-splicer/engine-proof";
import { SiteHeader } from "@/components/site-header";
import { ModuleLibraryPanel } from "@/components/build/module-library-panel";
import { ModuleNode, type ModuleNodeData } from "@/components/build/module-node";
import { SafetyCheckPanel } from "@/components/build/safety-check-panel";
import { DrcPanel } from "@/components/build/drc-panel";
import { runDrc } from "@/lib/pcb/drc";
import { PcbViewport } from "@/components/cad/pcb-viewport";
import { buildGraphToGeometry } from "@/lib/pcb/build-to-geometry";
import { analyzeBuild, type BuildGraph } from "@/lib/rules/safety-rules";
import { findModule, findPin, MODULE_LIBRARY, type ModuleSpec, type PinRole } from "@/lib/modules/module-library";
import { buildFirmwareBundle, downloadFirmwareBundle } from "@/lib/firmware/firmware-bundle";
import { inferBuildIdFromGraph } from "@/lib/firmware/firmware-scaffold";
import { runLocalManufacturePreflight } from "@/lib/manufacture/local-preflight";

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

type IndexedModule = {
  node: FlowNode;
  spec: ModuleSpec;
};

type WiringEndpoint = {
  nodeId: string;
  pinId: string;
};

type WiringInstruction = {
  from: WiringEndpoint;
  to: WiringEndpoint;
  purpose?: string;
};

type WirePlan = {
  wires: WiringInstruction[];
  explanation?: string;
  source: "local" | "python";
};

function normalizeKey(value: string): string {
  return value.toLowerCase().replace(/[^a-z0-9]/g, "");
}

function indexedModules(nodes: FlowNode[]): IndexedModule[] {
  return nodes.flatMap((node) => {
    const spec = findModule((node.data as ModuleNodeData).moduleId);
    return spec ? [{ node, spec }] : [];
  });
}

function firstPin(spec: ModuleSpec, roles: PinRole[]) {
  return spec.pins.find((pin) => roles.includes(pin.role));
}

function voltageNumber(value: string | undefined): number | null {
  if (!value) return null;
  const match = value.match(/\d+(?:\.\d+)?/);
  return match ? Number(match[0]) : null;
}

function pinAcceptsVoltage(pin: ReturnType<typeof firstPin>, sourceVoltage: string | undefined, spec: ModuleSpec): boolean {
  if (!pin) return false;
  const out = voltageNumber(sourceVoltage);
  if (out == null) return true;
  if (spec.inputVoltageRange) {
    const [min, max] = spec.inputVoltageRange;
    return out >= min && out <= max;
  }
  const text = `${pin.voltage ?? ""} ${pin.notes ?? ""}`.toLowerCase();
  if (!text) return true;
  if (text.includes("3") && out >= 3 && out <= 3.6) return true;
  if (text.includes("5") && out >= 4.75 && out <= 5.25) return true;
  return !text.includes("v");
}

function addWire(
  wires: WiringInstruction[],
  seen: Set<string>,
  from: IndexedModule,
  fromPinId: string | undefined,
  to: IndexedModule,
  toPinId: string | undefined,
  purpose: string,
) {
  if (!fromPinId || !toPinId) return;
  const key = `${from.node.id}:${fromPinId}->${to.node.id}:${toPinId}`;
  const reverseKey = `${to.node.id}:${toPinId}->${from.node.id}:${fromPinId}`;
  if (seen.has(key) || seen.has(reverseKey)) return;
  seen.add(key);
  wires.push({
    from: { nodeId: from.node.id, pinId: fromPinId },
    to: { nodeId: to.node.id, pinId: toPinId },
    purpose,
  });
}

function createHeuristicWirePlan(nodes: FlowNode[]): WirePlan {
  const modules = indexedModules(nodes);
  const wires: WiringInstruction[] = [];
  const seen = new Set<string>();
  const controller = modules.find((entry) => entry.spec.category === "mcu") ?? modules[0];
  if (!controller) return { wires, source: "local", explanation: "No modules available to wire." };

  const groundSource = modules.find((entry) => firstPin(entry.spec, ["gnd"])) ?? controller;
  const powerSources = modules.filter((entry) => firstPin(entry.spec, ["power_out"]));

  for (const target of modules) {
    if (target.node.id === groundSource.node.id) continue;
    addWire(
      wires,
      seen,
      groundSource,
      firstPin(groundSource.spec, ["gnd"])?.id,
      target,
      firstPin(target.spec, ["gnd"])?.id,
      "common ground",
    );
  }

  for (const target of modules) {
    const powerIn = firstPin(target.spec, ["power_in"]);
    if (!powerIn) continue;
    const source = powerSources.find((candidate) => {
      if (candidate.node.id === target.node.id) return false;
      const powerOut = firstPin(candidate.spec, ["power_out"]);
      return pinAcceptsVoltage(powerIn, powerOut?.voltage, target.spec);
    });
    addWire(
      wires,
      seen,
      source ?? target,
      source ? firstPin(source.spec, ["power_out"])?.id : undefined,
      target,
      powerIn.id,
      "module power",
    );
  }

  for (const target of modules) {
    if (target.node.id === controller.node.id) continue;

    const targetSda = firstPin(target.spec, ["i2c_sda"]);
    const targetScl = firstPin(target.spec, ["i2c_scl"]);
    if (targetSda && targetScl) {
      addWire(wires, seen, controller, firstPin(controller.spec, ["i2c_sda"])?.id, target, targetSda.id, "I2C SDA");
      addWire(wires, seen, controller, firstPin(controller.spec, ["i2c_scl"])?.id, target, targetScl.id, "I2C SCL");
      continue;
    }

    const targetRx = firstPin(target.spec, ["uart_rx"]);
    const targetTx = firstPin(target.spec, ["uart_tx"]);
    if (targetRx || targetTx) {
      addWire(wires, seen, controller, firstPin(controller.spec, ["uart_tx"])?.id, target, targetRx?.id, "UART TX to RX");
      addWire(wires, seen, target, targetTx?.id, controller, firstPin(controller.spec, ["uart_rx"])?.id, "UART RX from TX");
      continue;
    }

    const analogPin = target.spec.pins.find((pin) =>
      pin.role === "analog_in" && ["a0", "ao", "out", "sig"].some((alias) => normalizeKey(pin.id).includes(alias)),
    );
    if (target.spec.category === "sensor" && analogPin) {
      addWire(wires, seen, target, analogPin.id, controller, firstPin(controller.spec, ["analog_in"])?.id, "analog sensor signal");
      continue;
    }

    const targetInput = firstPin(target.spec, ["digital_in", "pwm"]);
    if (targetInput) {
      addWire(wires, seen, controller, firstPin(controller.spec, ["digital_io", "pwm"])?.id, target, targetInput.id, "control signal");
      continue;
    }

    const targetDigital = firstPin(target.spec, ["digital_io", "digital_out"]);
    if (targetDigital) {
      const controllerPin = firstPin(controller.spec, ["digital_io"]);
      const source = target.spec.category === "sensor" && targetDigital.role === "digital_out" ? target : controller;
      const destination = source.node.id === target.node.id ? controller : target;
      addWire(
        wires,
        seen,
        source,
        source.node.id === target.node.id ? targetDigital.id : controllerPin?.id,
        destination,
        destination.node.id === target.node.id ? targetDigital.id : controllerPin?.id,
        "digital signal",
      );
    }
  }

  return {
    wires,
    source: "local",
    explanation: `Local pinout router connected ${wires.length} wire${wires.length === 1 ? "" : "s"} from known module pins.`,
  };
}

function createLocalWirePlan(nodes: FlowNode[]): WirePlan {
  const composed = composeBuildGraphFromCanvasNodes(
    nodes.map((n) => ({ id: n.id, moduleId: (n.data as ModuleNodeData).moduleId })),
  );
  if (composed.wires.length > 0) {
    return {
      wires: composed.wires.map((w) => ({
        from: w.from,
        to: w.to,
        purpose: "auto-route",
      })),
      source: "local",
      explanation: `Pad-aware auto-router connected ${composed.wires.length} wire${composed.wires.length === 1 ? "" : "s"} from module pin roles.`,
    };
  }
  return createHeuristicWirePlan(nodes);
}

async function createWirePlanAsync(nodes: FlowNode[]): Promise<WirePlan> {
  if (preferPythonEngine() && nodes.length >= 2) {
    try {
      const graph = await composeCanvasRemote(
        nodes.map((n) => ({ id: n.id, moduleId: (n.data as ModuleNodeData).moduleId })),
      );
      if (graph.wires.length > 0) {
        return {
          wires: graph.wires.map((w) => ({
            from: w.from,
            to: w.to,
            purpose: "auto-route",
          })),
          source: "python",
          explanation: `Python pad-aware auto-router connected ${graph.wires.length} wire${graph.wires.length === 1 ? "" : "s"} from module pin roles.`,
        };
      }
    } catch {
      // Fall back to local TS router when API is offline or misconfigured.
    }
  }
  return createLocalWirePlan(nodes);
}

function edgeKey(edge: Edge): string {
  return `${edge.source}:${edge.sourceHandle ?? ""}->${edge.target}:${edge.targetHandle ?? ""}`;
}

function edgesFromWirePlan(plan: WirePlan, nodes: FlowNode[]): Edge[] {
  return plan.wires.map((w, i) => {
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
}

function dedupeNewEdges(current: Edge[], incoming: Edge[]): Edge[] {
  const existing = new Set(current.map(edgeKey));
  return incoming.filter((edge) => {
    const key = edgeKey(edge);
    const reverseKey = `${edge.target}:${edge.targetHandle ?? ""}->${edge.source}:${edge.sourceHandle ?? ""}`;
    if (existing.has(key) || existing.has(reverseKey)) return false;
    existing.add(key);
    return true;
  });
}

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
  const [pcbOpen, setPcbOpen] = useState(false);
  const [mfg, setMfg] = useState<MfgResult | null>(null);
  const [engineProof, setEngineProof] = useState<EngineCompileProof | null>(null);
  const [engineProofBusy, setEngineProofBusy] = useState(false);
  const [engineProofError, setEngineProofError] = useState<string | null>(null);

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

  const applyTranslation = useCallback((result: TranslationResult) => {
    const newNodes = result.graph.nodes.map((bn, i) => {
      const col = i % 3;
      const row = Math.floor(i / 3);
      return {
        id: bn.id,
        type: "module" as const,
        position: { x: 60 + col * 340, y: 60 + row * 320 },
        data: { moduleId: bn.moduleId },
      };
    });
    const newEdges = result.graph.wires.map((w) => ({
      id: w.id,
      source: w.from.nodeId,
      target: w.to.nodeId,
      sourceHandle: w.from.pinId,
      targetHandle: w.to.pinId,
    }));
    setNodes(newNodes);
    setEdges(newEdges);
    const maxN = newNodes.reduce(
      (m, n) => Math.max(m, parseInt(n.id.replace(/^n/, ""), 10) || 0),
      0,
    );
    idRef.current = maxN;
    setTimeout(() => fitView({ padding: 0.25, duration: 400 }), 100);
  }, [setNodes, setEdges, fitView]);

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
  // Geometry is cheap and deterministic; compute it always so the DRC verdict
  // is visible before the user opens the PCB preview. The preview portal is
  // still gated on pcbOpen below.
  const pcbGeometry = useMemo(() => buildGraphToGeometry(graph), [graph]);
  const drc = useMemo(() => runDrc(pcbGeometry), [pcbGeometry]);

  const refreshEngineProof = useCallback(async (exportGerber = false): Promise<EngineCompileProof | null> => {
    if (!preferPythonEngine() || graph.nodes.length < 2) {
      setEngineProof(null);
      setEngineProofError(null);
      return null;
    }
    setEngineProofBusy(true);
    setEngineProofError(null);
    try {
      const proof = await verifyCanvasBuildRemote(graph, { exportGerber });
      setEngineProof(proof);
      return proof;
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : String(error);
      setEngineProofError(message);
      return null;
    } finally {
      setEngineProofBusy(false);
    }
  }, [graph]);

  useEffect(() => {
    if (!preferPythonEngine() || graph.nodes.length < 2) {
      return;
    }
    const timer = window.setTimeout(() => {
      void refreshEngineProof(false);
    }, 2500);
    return () => window.clearTimeout(timer);
  }, [graph, refreshEngineProof]);

  const getJarvisSnapshot = useCallback(
    () => snapshotFromBuild(graph, warnings, drc, engineProof),
    [graph, warnings, drc, engineProof],
  );

  const graphFromEdges = useCallback((edgeList: Edge[]): BuildGraph => ({
    nodes: nodes.map((n) => ({ id: n.id, moduleId: (n.data as ModuleNodeData).moduleId })),
    wires: edgeList.map((e) => ({
      id: e.id,
      from: { nodeId: e.source, pinId: e.sourceHandle ?? "" },
      to: { nodeId: e.target, pinId: e.targetHandle ?? "" },
    })),
  }), [nodes]);

  const snapshotForGraph = useCallback((g: BuildGraph) => {
    const w = analyzeBuild(g);
    const geo = buildGraphToGeometry(g);
    const d = runDrc(geo);
    return snapshotFromBuild(g, w, d, engineProof);
  }, [engineProof]);

  const jarvisAutoWire = useCallback(async () => {
    const plan = await createWirePlanAsync(nodes);
    const uniqueEdges = dedupeNewEdges(edges, edgesFromWirePlan(plan, nodes));
    const merged = uniqueEdges.length > 0 ? [...edges, ...uniqueEdges] : edges;
    if (uniqueEdges.length > 0) {
      setEdges(merged);
      setTimeout(() => fitView({ padding: 0.25, duration: 400 }), 100);
    }
    const postGraph = graphFromEdges(merged);
    return {
      added: uniqueEdges.length,
      wireCount: merged.length,
      detail: uniqueEdges.length > 0
        ? (plan.explanation ?? `Added ${uniqueEdges.length} wire(s).`)
        : (plan.wires.length > 0
          ? "Those connections were already on the canvas."
          : "No pinout rules matched these modules."),
      snapshot: snapshotForGraph(postGraph),
    };
  }, [nodes, edges, setEdges, fitView, graphFromEdges, snapshotForGraph]);

  const jarvisRebuildWires = useCallback(async () => {
    const plan = await createWirePlanAsync(nodes);
    const newEdges = edgesFromWirePlan(plan, nodes);
    setEdges(newEdges);
    setTimeout(() => fitView({ padding: 0.25, duration: 400 }), 100);
    const postGraph = graphFromEdges(newEdges);
    return {
      added: plan.wires.length,
      wireCount: plan.wires.length,
      detail: plan.wires.length > 0
        ? `Rebuilt wiring: ${plan.explanation ?? `${plan.wires.length} connection(s).`}`
        : "Could not rebuild — no pin-compatible wiring for these modules.",
      snapshot: snapshotForGraph(postGraph),
    };
  }, [nodes, setEdges, fitView, graphFromEdges, snapshotForGraph]);

  const jarvisComposeModules = useCallback(async (userText: string) => {
    const pick = pickModulesForGoal(userText);
    if (pick.moduleIds.length === 0) {
      return {
        ok: false,
        added: 0,
        moduleIds: [],
        hints: [],
        detail: "I'm not sure which part you mean yet — try \"temperature sensor\", \"small screen\", \"pump for watering\", or \"relay to switch a lamp\".",
        snapshot: snapshotForGraph(graph),
      };
    }

    const existingIds = new Set(nodes.map((n) => (n.data as ModuleNodeData).moduleId));
    const toAdd = pick.moduleIds.filter((id) => !existingIds.has(id) && findModule(id));
    let nextId = idRef.current;
    const newNodes: FlowNode[] = toAdd.map((moduleId, i) => {
      nextId += 1;
      const idx = nodes.length + i;
      const col = idx % 3;
      const row = Math.floor(idx / 3);
      return {
        id: `n${nextId}`,
        type: "module" as const,
        position: { x: 60 + col * 340, y: 60 + row * 320 },
        data: { moduleId },
      };
    });
    idRef.current = nextId;
    const mergedNodes = [...nodes, ...newNodes];

    let mergedEdges = edges;
    let wireNote = "";
    if (wantsAutoWireAfterCompose(userText, {
      moduleCount: nodes.length,
      wireCount: edges.length,
      addingModules: toAdd.length,
    })) {
      const plan = await createWirePlanAsync(mergedNodes);
      mergedEdges = edgesFromWirePlan(plan, mergedNodes);
      wireNote = plan.wires.length > 0
        ? ` Wired ${plan.wires.length} connection(s).`
        : "";
    }

    setNodes(mergedNodes);
    setEdges(mergedEdges);
    setTimeout(() => fitView({ padding: 0.25, duration: 400 }), 100);

    const postGraph = graphFromEdges(mergedEdges);
    postGraph.nodes = mergedNodes.map((n) => ({
      id: n.id,
      moduleId: (n.data as ModuleNodeData).moduleId,
    }));

    const addedLabels = toAdd.map((id) => findModule(id)?.label ?? id).join(", ");
    return {
      ok: toAdd.length > 0 || mergedNodes.length > 0,
      added: toAdd.length,
      moduleIds: toAdd,
      hints: pick.hints,
      detail: toAdd.length > 0
        ? `Added ${toAdd.length} part(s) for ${pick.hints.join(", ")}: ${addedLabels}.${wireNote}`
        : `Those parts are already on the board.${wireNote}`,
      snapshot: snapshotForGraph(postGraph),
    };
  }, [nodes, edges, graph, setNodes, setEdges, fitView, graphFromEdges, snapshotForGraph]);

  const jarvisSpliceRecipe = useCallback(async (buildId: string) => {
    if (preferPythonEngine()) {
      try {
        const remote = await compileCatalogBuildRemote(buildId);
        const result: TranslationResult = {
          graph: remote.graph,
          notes: remote.notes ?? [],
          warnings: remote.warnings ?? [],
        };
        applyTranslation(result);
        const notes = result.notes.length ? ` ${result.notes.join(" ")}` : "";
        const warns = result.warnings.length ? ` ⚠ ${result.warnings.join(" ")}` : "";
        return {
          ok: true,
          buildId,
          moduleCount: result.graph.nodes.length,
          wireCount: result.graph.wires.length,
          detail: `Spliced "${buildId}" via Python engine — ${result.graph.nodes.length} modules, ${result.graph.wires.length} wires.${notes}${warns}`,
          snapshot: snapshotForGraph(result.graph),
        };
      } catch {
        // Fall through to local TS recipe translator when API is unavailable.
      }
    }

    const result = splicePlanToBuildGraph({ target: { recommended_build_id: buildId } });
    if (result.graph.nodes.length === 0) {
      return {
        ok: false,
        buildId,
        moduleCount: 0,
        wireCount: 0,
        detail: result.warnings.join(" ") || `No recipe found for "${buildId}".`,
        snapshot: snapshotForGraph({ nodes: [], wires: [] }),
      };
    }
    applyTranslation(result);
    const notes = result.notes.length ? ` ${result.notes.join(" ")}` : "";
    const warns = result.warnings.length ? ` ⚠ ${result.warnings.join(" ")}` : "";
    return {
      ok: true,
      buildId,
      moduleCount: result.graph.nodes.length,
      wireCount: result.graph.wires.length,
      detail: `Spliced "${buildId}" — ${result.graph.nodes.length} modules, ${result.graph.wires.length} wires.${notes}${warns}`,
      snapshot: snapshotForGraph(result.graph),
    };
  }, [applyTranslation, snapshotForGraph]);

  const clearAll = useCallback(() => {
    setNodes([]);
    setEdges([]);
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

  // Manufacture uses the Python engine (KiCad DRC + Gerbers). Canvas DRC is preview-only.
  const manufactureReal = useCallback(async () => {
    if (nodes.length === 0) {
      return formatManufactureJarvisSummary({
        error: "Put some parts on the board first, then ask me to order boards.",
      });
    }
    setMfg({ busy: true });
    try {
      if (shouldRequireEngineForManufacture()) {
        let proof: EngineCompileProof | null = null;
        try {
          proof = await verifyCanvasBuildRemote(graph, { exportGerber: true });
          setEngineProof(proof);
          setEngineProofError(null);
        } catch (error: unknown) {
          const message = error instanceof Error ? error.message : String(error);
          setEngineProofError(message);
          setMfg({ busy: false, error: `${message} ${engineProofUnavailableMessage()}` });
          return formatManufactureJarvisSummary({ error: message });
        }

        const summary = formatManufactureJarvisSummary({ engine: proof });
        setMfg({
          busy: false,
          dfm: {
            manufacturing_ready: Boolean(summary.manufacturingReady),
            critical: 0,
            errors: proof.kicadDrcErrors + proof.electricalErrors,
            warnings: proof.kicadDrcWarnings + proof.electricalWarnings,
            issues: (summary.blockers ?? []).map((issue) => ({
              severity: "error",
              issue,
            })),
          },
        });
        return summary;
      }

      const pcb = serializeBuildToKicadPcb(graph);
      const mkForm = () => {
        const f = new FormData();
        f.set(
          "pcb_file",
          new File([pcb], `circuit-build-${Date.now()}.kicad_pcb`, { type: "text/plain" }),
        );
        return f;
      };
      const gForm = mkForm();
      gForm.set("quantity", "5");

      const [dfmR, gerR] = await Promise.allSettled([
        fetch("/api/proxy/report/dfm", { method: "POST", body: mkForm() }),
        fetch("/api/proxy/manufacture/gerber", { method: "POST", body: gForm }),
      ]);

      const result: MfgResult = { busy: false };

      if (dfmR.status === "fulfilled") {
        const j = await dfmR.value.json().catch(() => null);
        if (dfmR.value.ok && j?.validation) {
          result.dfm = {
            manufacturing_ready: !!j.manufacturing_ready,
            critical: j.validation.critical ?? 0,
            errors: j.validation.errors ?? 0,
            warnings: j.validation.warnings ?? 0,
            issues: Array.isArray(j.validation.issues) ? j.validation.issues : [],
          };
        } else if (!j) {
          result.error = "DFM endpoint returned no JSON.";
        } else {
          result.error = j.error || `DFM failed (${dfmR.value.status}).`;
        }
      } else {
        result.error = dfmR.reason?.message || "DFM request failed.";
      }

      if (gerR.status === "fulfilled") {
        const j = await gerR.value.json().catch(() => null);
        if (gerR.value.ok && j) {
          const zip: string | undefined = j.zip_file || j.zip_url;
          result.gerber = {
            filename: zip ? String(zip).split(/[\\/]/).pop() : undefined,
            manufacturing_ready: !!j.manufacturing_ready,
            cost: j.cost_estimates,
          };
        }
      }

      if (!result.dfm && !result.gerber && !result.error) {
        result.error = "Backend unreachable — using local layout check.";
      }

      if (!result.dfm?.manufacturing_ready && (result.error || !result.dfm)) {
        const local = runLocalManufacturePreflight(graph);
        setMfg({
          busy: false,
          error: result.error,
          dfm: {
            manufacturing_ready: local.manufacturing_ready,
            critical: local.critical,
            errors: local.errors,
            warnings: local.warnings,
            issues: local.issues,
          },
        });
        return formatManufactureJarvisSummary({ local });
      }

      setMfg(result);
      return formatManufactureJarvisSummary(result);
    } catch (e: unknown) {
      const err = e instanceof Error ? e.message : String(e);
      const local = runLocalManufacturePreflight(graph);
      setMfg({
        busy: false,
        error: err,
        dfm: {
          manufacturing_ready: local.manufacturing_ready,
          critical: local.critical,
          errors: local.errors,
          warnings: local.warnings,
          issues: local.issues,
        },
      });
      return formatManufactureJarvisSummary({ local });
    }
  }, [nodes.length, graph, setMfg]);

  const jarvisGenerateFirmware = useCallback(() => {
    if (graph.nodes.length === 0) {
      return {
        ok: false,
        filename: "",
        buildId: "",
        detail: "Put some parts on the board first — then ask me for code.",
      };
    }
    const buildId = inferBuildIdFromGraph(graph);
    const bundle = buildFirmwareBundle(buildId, graph);
    downloadFirmwareBundle(bundle);
    return {
      ok: true,
      filename: bundle.zipName,
      buildId,
      detail: `Downloaded ${bundle.zipName} — open in VS Code with PlatformIO, click Upload. Pins match your wiring. ${bundle.installSteps[bundle.installSteps.length - 1]}`,
    };
  }, [graph]);

  const jarvisHandlers = useMemo(() => ({
    autoWire: jarvisAutoWire,
    rebuildWires: jarvisRebuildWires,
    spliceRecipe: jarvisSpliceRecipe,
    composeModules: jarvisComposeModules,
    clearCanvas: clearAll,
    openPcb: () => setPcbOpen(true),
    exportKicad: () => downloadKicadPcb(graph),
    exportBom,
    manufacture: manufactureReal,
    generateFirmware: jarvisGenerateFirmware,
  }), [jarvisAutoWire, jarvisRebuildWires, jarvisSpliceRecipe, jarvisComposeModules, clearAll, graph, exportBom, manufactureReal, jarvisGenerateFirmware]);

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
              onClick={manufactureReal}
              disabled={empty || mfg?.busy}
              className="inline-flex items-center gap-1.5 rounded-full bg-violet-500/20 px-3 py-1.5 text-xs font-semibold text-violet-100 hover:bg-violet-500/30 disabled:bg-transparent disabled:text-slate-500"
            >
              <Factory className="h-3.5 w-3.5" /> {mfg?.busy ? "Manufacturing…" : "Manufacture"}
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
        style={{ width: 340, overflowWrap: "anywhere" }}
        className="flex min-h-0 shrink-0 flex-col gap-3 overflow-hidden border-l border-white/10 bg-black/40 p-4"
      >
        <div className="shrink-0">
          <div className="text-xs font-semibold uppercase tracking-wider text-slate-500">Build</div>
          <h2 className="mt-1 text-base font-semibold text-white">
            {nodes.length} modules · {edges.length} wires
          </h2>
          <p className="mt-1 text-xs leading-5 text-slate-400">
            Drag parts in or tell Jarvis what you want it to do — no part numbers needed.
          </p>
        </div>

        <BuildJarvisPanel
          getSnapshot={getJarvisSnapshot}
          handlers={jarvisHandlers}
        />

        <div className="min-h-0 shrink overflow-y-auto space-y-3">
        <SafetyCheckPanel warnings={warnings} />

        <EngineProofPanel
          proof={engineProof}
          busy={engineProofBusy}
          error={engineProofError}
          onRefresh={() => { void refreshEngineProof(false); }}
        />

        <DrcPanel drc={drc} />

        <ManufacturePanel mfg={mfg} />

        <div className="rounded-xl border border-white/10 bg-white/[0.02] p-3 text-[10px] leading-4 text-slate-400">
          <div className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-slate-500">Wire legend</div>
          <Legend />
        </div>
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

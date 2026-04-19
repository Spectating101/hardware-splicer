// Minimal BuildGraph -> .kicad_pcb serializer. Emits a valid KiCad 7+ PCB file
// with one generic 2.54mm header footprint per module and a net per wire.
// Trace geometry is *not* routed; the user opens in KiCad and places traces
// themselves. The goal is a graduate-path handoff, not a finished PCB.

import type { BuildGraph } from "@/lib/rules/safety-rules";
import { findModule } from "@/lib/modules/module-library";

const HEADER = `(kicad_pcb (version 20221018) (generator circuit-ai)
  (general (thickness 1.6))
  (paper "A4")
  (layers
    (0 "F.Cu" signal)
    (31 "B.Cu" signal)
    (36 "B.SilkS" user "B.Silkscreen")
    (37 "F.SilkS" user "F.Silkscreen")
    (40 "Edge.Cuts" user)
  )
  (setup
    (pad_to_mask_clearance 0)
  )
`;

const FOOTER = `)\n`;

interface Net {
  id: number;
  name: string;
}

function quote(s: string): string {
  return `"${s.replace(/"/g, '\\"')}"`;
}

function buildNets(graph: BuildGraph): { nets: Net[]; pinNetMap: Map<string, number> } {
  // Union-find over (nodeId, pinId) pairs linked by wires.
  const parent = new Map<string, string>();
  const key = (n: string, p: string) => `${n}/${p}`;
  const find = (k: string): string => {
    if (!parent.has(k)) parent.set(k, k);
    let cur = k;
    while (parent.get(cur) !== cur) {
      const p = parent.get(cur)!;
      parent.set(cur, parent.get(p)!);
      cur = parent.get(cur)!;
    }
    return cur;
  };
  const union = (a: string, b: string) => {
    const ra = find(a);
    const rb = find(b);
    if (ra !== rb) parent.set(ra, rb);
  };

  for (const n of graph.nodes) {
    const mod = findModule(n.moduleId);
    if (!mod) continue;
    for (const p of mod.pins) find(key(n.id, p.id));
  }
  for (const w of graph.wires) {
    union(key(w.from.nodeId, w.from.pinId), key(w.to.nodeId, w.to.pinId));
  }

  const rootToNetId = new Map<string, number>();
  const pinNetMap = new Map<string, number>();
  const nets: Net[] = [{ id: 0, name: "" }]; // kicad net 0 = no-connect

  for (const n of graph.nodes) {
    const mod = findModule(n.moduleId);
    if (!mod) continue;
    for (const p of mod.pins) {
      const k = key(n.id, p.id);
      const root = find(k);
      let netId = rootToNetId.get(root);
      // Only assign a net if the pin is actually wired to something else
      const isWired = graph.wires.some(
        (w) =>
          (w.from.nodeId === n.id && w.from.pinId === p.id) ||
          (w.to.nodeId === n.id && w.to.pinId === p.id),
      );
      if (!isWired) {
        pinNetMap.set(k, 0);
        continue;
      }
      if (netId === undefined) {
        netId = nets.length;
        // Prefer GND/VCC naming when the role hints it
        const role = p.role;
        let name = `Net-${netId}`;
        if (role === "gnd") name = "GND";
        else if (role === "power_out" && /3\.?3/.test(p.voltage ?? "")) name = "+3V3";
        else if (role === "power_out" && /^5/.test(p.voltage ?? "")) name = "+5V";
        nets.push({ id: netId, name });
        rootToNetId.set(root, netId);
      }
      pinNetMap.set(k, netId);
    }
  }
  return { nets, pinNetMap };
}

function moduleFootprint(
  nodeIdx: number,
  nodeId: string,
  moduleId: string,
  pinNetMap: Map<string, number>,
  nets: Net[],
): string {
  const mod = findModule(moduleId);
  if (!mod) return "";
  const cols = 4;
  const col = nodeIdx % cols;
  const row = Math.floor(nodeIdx / cols);
  const x = 20 + col * 40;
  const y = 20 + row * 40;
  const pinCount = mod.pins.length;
  const spacing = 2.54;

  const padsStr = mod.pins
    .map((p, i) => {
      const px = (i - (pinCount - 1) / 2) * spacing;
      const netId = pinNetMap.get(`${nodeId}/${p.id}`) ?? 0;
      const net = nets[netId];
      const netStr = netId === 0 ? "" : ` (net ${net.id} ${quote(net.name)})`;
      return `    (pad ${quote(p.id)} thru_hole circle (at ${px.toFixed(2)} 0) (size 1.7 1.7) (drill 1.0) (layers "*.Cu" "*.Mask")${netStr})`;
    })
    .join("\n");

  return `  (footprint "Connector_PinHeader_2.54mm:PinHeader_1x${pinCount.toString().padStart(2, "0")}_P2.54mm_Vertical" (layer "F.Cu")
    (at ${x} ${y})
    (fp_text reference ${quote(`U${nodeIdx + 1}`)} (at 0 -4) (layer "F.SilkS") (effects (font (size 1 1) (thickness 0.15))))
    (fp_text value ${quote(mod.label)} (at 0 4) (layer "F.Fab") (effects (font (size 1 1) (thickness 0.15))))
${padsStr}
  )`;
}

export function serializeBuildToKicadPcb(graph: BuildGraph): string {
  const { nets, pinNetMap } = buildNets(graph);

  const netDecls = nets
    .map((n) => `  (net ${n.id} ${quote(n.name)})`)
    .join("\n");

  const footprints = graph.nodes
    .map((n, i) => moduleFootprint(i, n.id, n.moduleId, pinNetMap, nets))
    .filter(Boolean)
    .join("\n");

  return HEADER + netDecls + "\n" + footprints + "\n" + FOOTER;
}

/** Trigger a browser download of the serialized file. */
export function downloadKicadPcb(graph: BuildGraph, filename = `circuit-build-${Date.now()}.kicad_pcb`) {
  if (typeof window === "undefined") return;
  const pcb = serializeBuildToKicadPcb(graph);
  const blob = new Blob([pcb], { type: "text/plain" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

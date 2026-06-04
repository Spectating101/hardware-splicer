// BuildGraph -> .kicad_pcb serializer.
//
// This emits the ACTUAL routed board, not a ratsnest stub: it serializes the
// PcbGeometry produced by the correct-by-construction router
// (lib/pcb/build-to-geometry.ts) — footprints at their placed positions,
// every F.Cu/B.Cu trace segment, every via, the board outline, and silk.
// The file you download opens in KiCad as the exact DRC-clean board the
// /build preview shows, ready for KiCad -> Gerber -> fab.

import type { BuildGraph } from "@/lib/rules/safety-rules";
import type { PcbGeometry } from "@/lib/cad-types";
import { buildGraphToGeometry } from "@/lib/pcb/build-to-geometry";

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

function quote(s: string): string {
  return `"${s.replace(/\\/g, "\\\\").replace(/"/g, '\\"')}"`;
}

const n = (v: number) => (Number.isFinite(v) ? +v.toFixed(4) : 0);

/** Map geometry net ids -> contiguous KiCad net ids; net 0 is the no-net. */
function buildNetTable(geo: PcbGeometry) {
  const byGeoId = new Map<number, { kid: number; name: string }>();
  const decls: string[] = [`  (net 0 "")`];
  let kid = 1;
  for (const net of geo.nets) {
    if (net.id == null || byGeoId.has(net.id)) continue;
    byGeoId.set(net.id, { kid, name: net.name });
    decls.push(`  (net ${kid} ${quote(net.name)})`);
    kid += 1;
  }
  const kidOf = (id: number | null | undefined) =>
    id == null ? 0 : byGeoId.get(id)?.kid ?? 0;
  const nameOf = (id: number | null | undefined) =>
    id == null ? "" : byGeoId.get(id)?.name ?? "";
  return { decls: decls.join("\n"), kidOf, nameOf };
}

function footprintBlock(
  fp: PcbGeometry["footprints"][number],
  idx: number,
  kidOf: (id: number | null | undefined) => number,
  nameOf: (id: number | null | undefined) => string,
): string {
  const pinCount = (fp.pads ?? []).length || 1;
  const lib = `Connector_PinHeader_2.54mm:PinHeader_1x${String(pinCount).padStart(2, "0")}_P2.54mm_Vertical`;
  const pads = (fp.pads ?? [])
    .map((pad) => {
      // Footprint pads are local to the footprint origin; the router gives
      // world coords with zero rotation.
      const lx = n(pad.wx - fp.at.x);
      const ly = n(pad.wy - fp.at.y);
      const w = n(pad.size_w_mm ?? 1.7);
      const h = n(pad.size_h_mm ?? 1.7);
      const drill = pad.drill_mm ? ` (drill ${n(pad.drill_mm)})` : "";
      const kid = kidOf(pad.net?.id ?? null);
      const netStr = kid === 0 ? "" : ` (net ${kid} ${quote(nameOf(pad.net?.id ?? null))})`;
      const shape = pad.shape ?? "circle";
      const type = pad.type ?? "thru_hole";
      const layers = type === "smd" ? `"F.Cu" "F.Paste" "F.Mask"` : `"*.Cu" "*.Mask"`;
      return `    (pad ${quote(pad.num)} ${type} ${shape} (at ${lx} ${ly}) (size ${w} ${h})${drill} (layers ${layers})${netStr})`;
    })
    .join("\n");

  return `  (footprint ${quote(lib)} (layer "${fp.layer}")
    (at ${n(fp.at.x)} ${n(fp.at.y)} ${n(fp.at.rot_deg)})
    (attr through_hole)
    (fp_text reference ${quote(fp.ref || `U${idx + 1}`)} (at 0 -3) (layer "F.SilkS") (effects (font (size 1 1) (thickness 0.15))))
    (fp_text value ${quote(fp.value || fp.ref)} (at 0 3) (layer "F.Fab") (effects (font (size 1 1) (thickness 0.15))))
${pads}
  )`;
}

export function serializeBuildToKicadPcb(graph: BuildGraph): string {
  const geo = buildGraphToGeometry(graph);
  const { decls, kidOf, nameOf } = buildNetTable(geo);

  const footprints = (geo.footprints ?? [])
    .map((fp, i) => footprintBlock(fp, i, kidOf, nameOf))
    .join("\n");

  const segments = (geo.segments ?? [])
    .filter((s) => !(s.start.x === s.end.x && s.start.y === s.end.y))
    .map(
      (s) =>
        `  (segment (start ${n(s.start.x)} ${n(s.start.y)}) (end ${n(s.end.x)} ${n(s.end.y)}) (width ${n(s.width_mm ?? 0.25)}) (layer "${s.layer}") (net ${kidOf(s.net?.id ?? null)}))`,
    )
    .join("\n");

  const vias = (geo.vias ?? [])
    .map(
      (v) =>
        `  (via (at ${n(v.x)} ${n(v.y)}) (size ${n(v.size_mm)}) (drill ${n(v.drill_mm)}) (layers "F.Cu" "B.Cu") (net ${kidOf(v.net?.id ?? null)}))`,
    )
    .join("\n");

  const edges = (geo.edgeLines ?? [])
    .map(
      (e) =>
        `  (gr_line (start ${n(e.start.x)} ${n(e.start.y)}) (end ${n(e.end.x)} ${n(e.end.y)}) (layer "Edge.Cuts") (width 0.1))`,
    )
    .join("\n");

  const silk = [
    ...(geo.silkLines ?? []).map(
      (l) =>
        `  (gr_line (start ${n(l.start.x)} ${n(l.start.y)}) (end ${n(l.end.x)} ${n(l.end.y)}) (layer "${l.layer}") (width ${n(l.width_mm)}))`,
    ),
    ...(geo.silkText ?? []).map(
      (t) =>
        `  (gr_text ${quote(t.text)} (at ${n(t.at.x)} ${n(t.at.y)} ${n(t.at.rot_deg)}) (layer "${t.layer}") (effects (font (size ${n(t.size_mm)} ${n(t.size_mm)}) (thickness 0.15))))`,
    ),
  ].join("\n");

  return (
    HEADER +
    decls +
    "\n" +
    [footprints, segments, vias, edges, silk].filter(Boolean).join("\n") +
    "\n" +
    FOOTER
  );
}

/** Trigger a browser download of the serialized routed board. */
export function downloadKicadPcb(
  graph: BuildGraph,
  filename = `circuit-build-${Date.now()}.kicad_pcb`,
) {
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

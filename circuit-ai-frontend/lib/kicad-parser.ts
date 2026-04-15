/**
 * Lightweight client-side parser for KiCAD PCB files (.kicad_pcb).
 * KiCAD files are S-expression text — parseable without a full grammar.
 */

export interface KicadPad {
  num: string;
  netId: number;
  netName: string;
  // pad center in WORLD mm (after applying footprint position + rotation)
  wx: number;
  wy: number;
}

export interface KicadComponent {
  ref: string;
  value: string;
  footprint: string; // e.g. "Resistor_SMD:R_0805_2012Metric"
  layer: string; // "F.Cu" | "B.Cu" | etc.
  x: number;
  y: number;
  rot_deg: number;
  pads: KicadPad[];
}

export interface KicadSegment {
  start: { x: number; y: number };
  end: { x: number; y: number };
  width_mm: number;
  layer: string;
  net_id: number;
  net_name: string;
}

export interface KicadVia {
  x: number;
  y: number;
  size_mm: number;
  drill_mm: number;
  net_id: number;
}

export interface KicadBoardInfo {
  componentCount: number;
  layerCount: number;
  netCount: number;
  components: KicadComponent[];
  segments: KicadSegment[];
  vias: KicadVia[];
  nets: Array<{ id: number; name: string }>;
  boardWidthMm?: number;
  boardHeightMm?: number;
}

/** Extract each (footprint ...) block from KiCAD text using a depth counter. */
function extractFootprintBlocks(text: string): string[] {
  const blocks: string[] = [];
  let i = 0;
  while (i < text.length) {
    const start = text.indexOf("(footprint ", i);
    if (start === -1) break;
    let depth = 0;
    let end = start;
    for (let j = start; j < text.length; j++) {
      if (text[j] === "(") depth++;
      else if (text[j] === ")") {
        depth--;
        if (depth === 0) { end = j; break; }
      }
    }
    blocks.push(text.slice(start, end + 1));
    i = end + 1;
  }
  return blocks;
}

export function parseKicadPcb(text: string): KicadBoardInfo {
  // Copper layer count: layer table entries look like (0 "F.Cu" signal).
  // This (\d+ "*.Cu") pattern only appears in the layers table, not inside footprints.
  const copperDefs = text.match(/\(\d+\s+"[^"]*\.Cu"/g) ?? [];
  const uniqueCopper = new Set(
    copperDefs.map((m) => {
      const match = m.match(/"([^"]+)"/);
      return match?.[1] ?? m;
    })
  );
  const copperLayerCount = uniqueCopper.size;

  // Net count: (net 0 "") is the unconnected pseudo-net — skip it
  const allNets = text.match(/\(net\s+\d+\s+"/g) ?? [];
  const netCount = allNets.filter((m) => !/\(net\s+0\s+"/.test(m)).length;

  // Parse each footprint block for component data
  const fpBlocks = extractFootprintBlocks(text);
  const components: KicadComponent[] = fpBlocks.map((fp) => {
    const layerMatch = fp.match(/\(layer\s+"([^"]+)"\)/);
    const layer = layerMatch?.[1] ?? "F.Cu";

    // (at X Y [ROT]) — first occurrence is the footprint's own position
    const atMatch = fp.match(/\(at\s+([-\d.]+)\s+([-\d.]+)(?:\s+([-\d.]+))?/);
    const x = atMatch ? parseFloat(atMatch[1]) : 0;
    const y = atMatch ? parseFloat(atMatch[2]) : 0;
    const rot_deg = atMatch && atMatch[3] ? parseFloat(atMatch[3]) : 0;

    // Footprint library name from the opening `(footprint "LIB:NAME" ...)`
    const libMatch = fp.match(/^\(footprint\s+"([^"]+)"/);
    const footprint = libMatch?.[1] ?? "";

    // Try (property "Reference" "REF"), then (fp_text reference "REF"), then footprint name
    const refMatch =
      fp.match(/\(property\s+"Reference"\s+"([^"]+)"/) ??
      fp.match(/\(fp_text\s+reference\s+"([^"]+)"/) ??
      fp.match(/^\(footprint\s+"([^"]+)"/);
    const ref = refMatch?.[1] ?? "?";

    const valMatch = fp.match(/\(property\s+"Value"\s+"([^"]+)"/);
    const value = valMatch?.[1] ?? "";

    // Pads: (pad "<num>" <type> (at X Y [R]) ... (net N "NAME")) — the (at ...) is optional
    // in synthetic demos, so fall back to the footprint origin when absent.
    const pads: KicadPad[] = [];
    const padRe = /\(pad\s+"([^"]+)"\s+\w+(?:[^()]|\([^()]*\))*?\(net\s+(\d+)\s+"([^"]*)"\)/g;
    for (const padMatch of fp.matchAll(padRe)) {
      const block = padMatch[0];
      const padAt = block.match(/\(at\s+([-\d.]+)\s+([-\d.]+)(?:\s+([-\d.]+))?\)/);
      const lx = padAt ? parseFloat(padAt[1]) : 0;
      const ly = padAt ? parseFloat(padAt[2]) : 0;
      const theta = (rot_deg * Math.PI) / 180;
      const wx = x + lx * Math.cos(theta) - ly * Math.sin(theta);
      const wy = y + lx * Math.sin(theta) + ly * Math.cos(theta);
      pads.push({ num: padMatch[1], netId: parseInt(padMatch[2], 10), netName: padMatch[3], wx, wy });
    }

    return { ref, value, footprint, layer, x, y, rot_deg, pads };
  });

  // Board bounds from component positions
  let boardWidthMm: number | undefined;
  let boardHeightMm: number | undefined;
  if (components.length > 0) {
    const xs = components.map((c) => c.x);
    const ys = components.map((c) => c.y);
    boardWidthMm = Math.max(...xs) - Math.min(...xs) + 20;
    boardHeightMm = Math.max(...ys) - Math.min(...ys) + 20;
  }

  // Net table → id/name pairs (skip the unconnected net 0)
  const nets: Array<{ id: number; name: string }> = [];
  for (const nm of text.matchAll(/\(net\s+(\d+)\s+"([^"]*)"\)/g)) {
    const id = parseInt(nm[1], 10);
    if (id === 0) continue;
    nets.push({ id, name: nm[2] });
  }

  // Segments: (segment (start X Y) (end X Y) (width W) (layer "L") (net N))
  const segments: KicadSegment[] = [];
  const segRe = /\(segment\s+\(start\s+([-\d.]+)\s+([-\d.]+)\)\s+\(end\s+([-\d.]+)\s+([-\d.]+)\)\s+\(width\s+([-\d.]+)\)\s+\(layer\s+"([^"]+)"\)\s+\(net\s+(\d+)\)/g;
  for (const sm of text.matchAll(segRe)) {
    const netId = parseInt(sm[7], 10);
    segments.push({
      start: { x: parseFloat(sm[1]), y: parseFloat(sm[2]) },
      end: { x: parseFloat(sm[3]), y: parseFloat(sm[4]) },
      width_mm: parseFloat(sm[5]),
      layer: sm[6],
      net_id: netId,
      net_name: nets.find((n) => n.id === netId)?.name ?? "",
    });
  }

  // Vias: (via (at X Y) (size S) (drill D) ... (net N))
  const vias: KicadVia[] = [];
  const viaRe = /\(via\s+\(at\s+([-\d.]+)\s+([-\d.]+)\)\s+\(size\s+([-\d.]+)\)\s+\(drill\s+([-\d.]+)\)[^)]*\(net\s+(\d+)\)/g;
  for (const vm of text.matchAll(viaRe)) {
    vias.push({
      x: parseFloat(vm[1]),
      y: parseFloat(vm[2]),
      size_mm: parseFloat(vm[3]),
      drill_mm: parseFloat(vm[4]),
      net_id: parseInt(vm[5], 10),
    });
  }

  return {
    componentCount: fpBlocks.length,
    layerCount: Math.max(2, copperLayerCount),
    netCount: Math.max(0, netCount),
    components,
    segments,
    vias,
    nets,
    boardWidthMm,
    boardHeightMm,
  };
}

/**
 * Generate ratsnest airwires — straight lines between pads sharing a net —
 * for any net that has 2+ pads. Uses a simple star-topology from the first pad.
 * This gives KiCad's "unrouted signal" overlay so a bare board doesn't look empty.
 */
export function generateAirwires(components: KicadComponent[]): KicadSegment[] {
  const byNet = new Map<number, { name: string; pads: KicadPad[] }>();
  for (const c of components) {
    for (const p of c.pads) {
      if (p.netId <= 0) continue;
      const bucket = byNet.get(p.netId) ?? { name: p.netName, pads: [] };
      bucket.pads.push(p);
      byNet.set(p.netId, bucket);
    }
  }
  const out: KicadSegment[] = [];
  for (const [netId, { name, pads }] of byNet) {
    if (pads.length < 2) continue;
    const root = pads[0];
    for (let i = 1; i < pads.length; i++) {
      out.push({
        start: { x: root.wx, y: root.wy },
        end:   { x: pads[i].wx, y: pads[i].wy },
        width_mm: 0.08,
        layer: "Airwire",
        net_id: netId,
        net_name: name,
      });
    }
  }
  return out;
}

/**
 * Lightweight client-side parser for KiCAD PCB files (.kicad_pcb).
 * KiCAD files are S-expression text — parseable without a full grammar.
 */

export interface KicadComponent {
  ref: string;
  value: string;
  layer: string; // "F.Cu" | "B.Cu" | etc.
  x: number;
  y: number;
}

export interface KicadBoardInfo {
  componentCount: number;
  layerCount: number;
  netCount: number;
  components: KicadComponent[];
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
    const atMatch = fp.match(/\(at\s+([-\d.]+)\s+([-\d.]+)/);
    const x = atMatch ? parseFloat(atMatch[1]) : 0;
    const y = atMatch ? parseFloat(atMatch[2]) : 0;

    const refMatch = fp.match(/\(property\s+"Reference"\s+"([^"]+)"/);
    const ref = refMatch?.[1] ?? "?";

    const valMatch = fp.match(/\(property\s+"Value"\s+"([^"]+)"/);
    const value = valMatch?.[1] ?? "";

    return { ref, value, layer, x, y };
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

  return {
    componentCount: fpBlocks.length,
    layerCount: Math.max(2, copperLayerCount),
    netCount: Math.max(0, netCount),
    components,
    boardWidthMm,
    boardHeightMm,
  };
}

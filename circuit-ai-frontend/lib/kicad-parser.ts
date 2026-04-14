/**
 * Lightweight client-side parser for KiCAD PCB files (.kicad_pcb).
 * KiCAD files are S-expression text — parseable with regex without a full grammar.
 */

export interface KicadBoardInfo {
  componentCount: number;
  layerCount: number;
  netCount: number;
}

export function parseKicadPcb(text: string): KicadBoardInfo {
  // Component count: each top-level (footprint ...) is one placed component
  const footprints = (text.match(/\(footprint\s+/g) ?? []).length;

  // Copper layer count: layer table entries look like (0 "F.Cu" signal)
  // This format (\d+ "*.Cu") only appears in the layer definition table,
  // not inside footprints (which use (layer "F.Cu") without a leading number).
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

  return {
    componentCount: footprints,
    layerCount: Math.max(2, copperLayerCount),
    netCount: Math.max(0, netCount),
  };
}

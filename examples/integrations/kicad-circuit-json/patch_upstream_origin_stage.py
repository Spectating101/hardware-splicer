#!/usr/bin/env python3
"""Apply an audited parser-stage provenance hook to a pinned upstream checkout.

Patch is deliberately at the point where kicadts-parsed native symbols are
converted to source components and ports, NOT an after-the-fact geometric join.
Requires kicad-to-circuit-json upstream source with matching code signatures.
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

STAGE = Path("lib/stages/schematic/CollectLibrarySymbolsStage.ts")
CONVERTER = Path("lib/KicadToCircuitJsonConverter.ts")

def replace_exact(source: str, old: str, new: str, name: str) -> str:
    if source.count(old) != 1:
        raise ValueError(f"Upstream signature changed in {name}: expected exactly one match")
    return source.replace(old, new, 1)

def patch_checkout(root: Path) -> list[dict]:
    stage_path, converter_path = root / STAGE, root / CONVERTER
    stage, converter = stage_path.read_text(), converter_path.read_text()
    original = [stage, converter]
    stage = replace_exact(stage,
        '    // Create schematic_component\n    const uuid = symbol.uuid',
        '''    // Capture original parser identity at component insertion, before it can
    // be lost in Circuit JSON. The root symbol UUID is unmodified kicadts data.
    const origin = {
      source_component_id: sourceComponent.source_component_id,
      native_kicad_symbol_uuid: symbol.uuid,
      native_kicad_sheet_uuid_path: null as string | null,
      schematic_component_id: null as string | null,
      source_port_ids: [] as string[],
    }
    if (!(this.ctx as any).__hsNativeOrigin) {
      (this.ctx as any).__hsNativeOrigin = []
    }
    ;(this.ctx as any).__hsNativeOrigin.push(origin)

    // Create schematic_component
    const uuid = symbol.uuid''', str(STAGE))
    stage = replace_exact(stage,
        '    const componentId = inserted.schematic_component_id',
        '''    const componentId = inserted.schematic_component_id
    origin.schematic_component_id = componentId''',str(STAGE))
    stage = replace_exact(stage,
        '''        componentId,
        cjPos,
      )''',
        '''        componentId,
        cjPos,
        origin,
      )''',str(STAGE))
    stage = replace_exact(stage,
        '''    componentCenter: { x: number; y: number },
  ) {''',
        '''    componentCenter: { x: number; y: number },
    origin: { source_port_ids: string[] },
  ) {''',str(STAGE))
    stage = replace_exact(stage,
        '''      const sideOfComponent: "top" | "bottom" | "left" | "right" =''',
        '''      origin.source_port_ids.push(sourcePort.source_port_id)
      const sideOfComponent: "top" | "bottom" | "left" | "right" =''',str(STAGE))
    converter = replace_exact(converter,
        '''  getOutputString() {''',
        '''  /**
   * Parser-stage identity sidecar. This does not claim verified hierarchy:
   * sheet_uuid_path remains null until the correct parsed instance path is
   * independently implemented. It must never be filled by visual matching.
   */
  getNativeOriginSidecar() {
    if (!this.ctx) this.runUntilFinished()
    return {
      schema_version: "hs.kicad_parser_origin_sidecar.v1",
      stage: "CollectLibrarySymbolsStage",
      entries: (this.ctx as any)?.__hsNativeOrigin || [],
      source_is_parser_origin: true,
      sheet_hierarchy_verified: false,
      converter_provenance_authenticated: false,
      visual_electrical_merge_allowed: false,
      manufacturing_authorized: false,
    }
  }

  getOutputString() {''',str(CONVERTER))
    modified = [stage, converter]
    for path, body in zip((stage_path, converter_path), modified):
        path.write_text(body)
    return [
        {"path": str(path.relative_to(root)),
         "before_sha256": hashlib.sha256(old.encode()).hexdigest(),
         "after_sha256": hashlib.sha256(new.encode()).hexdigest()}
        for path, old, new in zip((stage_path, converter_path), original, modified)
    ]

def main():
    p = argparse.ArgumentParser()
    p.add_argument("upstream_checkout", type=Path)
    args = p.parse_args()
    root = args.upstream_checkout.resolve()
    # Refuse partial modification: all signature checks happen before writes.
    import json
    print(json.dumps(patch_checkout(root), indent=2))

if __name__ == "__main__":
    main()

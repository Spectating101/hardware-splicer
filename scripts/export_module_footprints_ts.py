#!/usr/bin/env python3
"""Generate the TypeScript module footprint table from the shared data file.

``src/hardware_splicer/data/module_footprints.json`` is the single source of truth for module
footprint geometry. The Python registry loads it directly; the TypeScript module library
imports the file this script writes, so the two cannot be edited apart.

    python scripts/export_module_footprints_ts.py          # rewrite the generated file
    python scripts/export_module_footprints_ts.py --check  # exit 1 when it is stale
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src" / "hardware_splicer" / "data" / "module_footprints.json"
TARGET = (
    ROOT
    / "apps"
    / "circuit-ai"
    / "circuit-ai-frontend"
    / "lib"
    / "modules"
    / "module-footprint-data.generated.ts"
)

HEADER = """// GENERATED FILE - do not edit.
// Source of truth: src/hardware_splicer/data/module_footprints.json
// Regenerate with: python scripts/export_module_footprints_ts.py

export type ModulePadDef = { pinId: string; x: number; y: number };

/** Whether a footprint was checked against the real part. Never inferred: it is recorded per module. */
export type ModuleFit =
  | { status: "verified_against"; verifiedAgainst: string }
  | { status: "unverified_variant"; reason: string };

export type ModuleFootprintMeta = {
  kicadFootprint: string;
  bodyMm: { w: number; h: number };
  pads: ModulePadDef[];
  fit: ModuleFit;
};

export const MODULE_FOOTPRINT_DATA: Record<string, ModuleFootprintMeta> = """


def _fit_ts(fit: Dict[str, Any]) -> str:
    status = fit["status"]
    if status == "verified_against":
        return f'{{ status: "verified_against", verifiedAgainst: {json.dumps(fit["verified_against"], ensure_ascii=False)} }}'
    return f'{{ status: "unverified_variant", reason: {json.dumps(fit["reason"], ensure_ascii=False)} }}'


def _num(value: float) -> str:
    text = repr(round(float(value), 4))
    return text[:-2] if text.endswith(".0") else text


def render(payload: Dict[str, Any]) -> str:
    lines = [HEADER + "{"]
    for module_id, meta in payload["modules"].items():
        lines.append(f"  {json.dumps(module_id)}: {{")
        lines.append(f"    kicadFootprint: {json.dumps(meta['kicadFootprint'])},")
        lines.append(f"    bodyMm: {{ w: {_num(meta['bodyMm']['w'])}, h: {_num(meta['bodyMm']['h'])} }},")
        lines.append(f"    fit: {_fit_ts(meta['fit'])},")
        lines.append("    pads: [")
        for pad in meta["pads"]:
            lines.append(
                f"      {{ pinId: {json.dumps(pad['pinId'])}, x: {_num(pad['x'])}, y: {_num(pad['y'])} }},"
            )
        lines.append("    ],")
        lines.append("  },")
    lines.append("};")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="fail instead of writing when the file is stale")
    args = parser.parse_args(argv)
    payload = json.loads(SOURCE.read_text(encoding="utf-8"))
    text = render(payload)
    if args.check:
        current = TARGET.read_text(encoding="utf-8") if TARGET.is_file() else ""
        if current != text:
            print(f"stale: {TARGET} (run python scripts/export_module_footprints_ts.py)", file=sys.stderr)
            return 1
        print(f"current: {TARGET}")
        return 0
    TARGET.write_text(text, encoding="utf-8")
    print(f"Wrote {TARGET} ({len(payload['modules'])} footprints)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

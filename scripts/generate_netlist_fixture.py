#!/usr/bin/env python3
"""Generate netlist JSON fixtures from module id lists (auto-wire → netlist IR)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from hardware_splicer.auto_wire import compose_build_graph_from_module_ids
from hardware_splicer.netlist.lower import build_graph_to_netlist


def main() -> int:
    parser = argparse.ArgumentParser(description="Emit hardware_splicer.netlist.v1 JSON from module ids")
    parser.add_argument("--id", required=True, help="Fixture id (e.g. usb_esp_plant_watering)")
    parser.add_argument("--modules", required=True, help="Comma-separated module ids")
    parser.add_argument(
        "--out",
        type=Path,
        default=ROOT / "examples" / "netlist_fixtures" / "json",
        help="Output directory",
    )
    args = parser.parse_args()

    module_ids = [m.strip() for m in args.modules.split(",") if m.strip()]
    composed = compose_build_graph_from_module_ids(module_ids)
    graph = composed["graph"]
    if not graph.get("nodes"):
        print("error: could not compose graph", file=sys.stderr)
        return 1

    netlist = build_graph_to_netlist(graph, source=f"fixture:{args.id}")
    payload = netlist.to_dict()
    payload["metadata"] = {
        **dict(payload.get("metadata") or {}),
        "module_ids": module_ids,
        "compose_warnings": composed.get("warnings") or [],
    }

    args.out.mkdir(parents=True, exist_ok=True)
    path = args.out / f"{args.id}.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Golden geometry snapshot helpers (gate 5.4)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Mapping


SCHEMA_VERSION = "hardware_splicer.geometry_snapshot.v1"


def build_geometry_snapshot(out_dir: str | Path) -> Dict[str, Any]:
    """Normalize placement + DRC summary from a compile output tree."""
    root = Path(out_dir)
    build_dir = root / "build_compilation"
    graph_path = build_dir / "build_graph.json"
    quality_path = build_dir / "DESIGN_QUALITY.json"
    graph = json.loads(graph_path.read_text(encoding="utf-8")) if graph_path.is_file() else {}
    quality = json.loads(quality_path.read_text(encoding="utf-8")) if quality_path.is_file() else {}
    nodes = graph.get("nodes") or []
    positions = sorted(
        [
            {
                "id": node.get("id"),
                "module_id": node.get("moduleId") or node.get("module_id"),
                "x": round(float(node.get("x") or 0), 2),
                "y": round(float(node.get("y") or 0), 2),
            }
            for node in nodes
        ],
        key=lambda row: str(row.get("id")),
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "build_id": quality.get("build_id") or graph.get("build_id"),
        "module_count": len(nodes),
        "wire_count": len(graph.get("wires") or []),
        "node_positions": positions,
        "board_outline": quality.get("board_outline"),
        "drc_pass": quality.get("drc_pass"),
        "kicad_drc_errors": quality.get("kicad_drc_errors"),
    }


def compare_geometry_snapshots(
    expected: Mapping[str, Any],
    actual: Mapping[str, Any],
) -> Dict[str, Any]:
    """Return diff summary; ok=True when normalized snapshots match."""
    keys = ("module_count", "wire_count", "drc_pass", "kicad_drc_errors", "node_positions", "board_outline")
    mismatches = []
    for key in keys:
        if expected.get(key) != actual.get(key):
            mismatches.append({"field": key, "expected": expected.get(key), "actual": actual.get(key)})
    return {"ok": not mismatches, "mismatches": mismatches}

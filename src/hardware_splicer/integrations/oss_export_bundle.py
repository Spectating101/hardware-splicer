"""Best-effort OSS export bundle for a compiled build directory."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

from ..build_files import find_primary_pcb, resolve_build_dir
from .esphome_export import write_esphome_stub
from .ibom_bridge import run_ibom
from .pcbdraw_bridge import run_pcbdraw


OSS_MECH_REFS = [
    {
        "id": "nopscadlib",
        "name": "NopSCADlib",
        "url": "https://github.com/nophead/NopSCADlib",
        "role": "OpenSCAD vitamins + assembly manuals for mecha packs",
    },
    {
        "id": "build123d",
        "name": "build123d",
        "url": "https://github.com/gumyr/build123d",
        "role": "Optional parametric CAD backend (no hard STL dep)",
    },
    {
        "id": "cadquery",
        "name": "CadQuery",
        "url": "https://github.com/CadQuery/cadquery",
        "role": "Optional 3d-splicer STL path",
    },
]


def run_oss_export_bundle(
    build_dir: str | Path,
    *,
    build_id: str = "",
    project_name: str = "",
    include_ibom: bool = True,
    include_pcbdraw: bool = True,
    include_esphome: bool = True,
    enforce_roots: bool = True,
) -> Dict[str, Any]:
    """Run skippable OSS exporters. Never raises; never fails the compile bar.

    When called from trusted package writers, pass ``enforce_roots=False`` so
    money-path /tmp outs still get best-effort exports. API endpoints should
    resolve/allow the build_dir first, then call with ``enforce_roots=False``.
    """
    try:
        if enforce_roots:
            root = resolve_build_dir(build_dir)
        else:
            root = Path(build_dir).expanduser().resolve()
            if not root.is_dir():
                return {"ok": False, "skipped": True, "reason": f"build_dir not found: {root}", "exports": []}
    except ValueError as exc:
        return {"ok": False, "skipped": True, "reason": str(exc), "exports": []}

    export_dir = root / "build_compilation" / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)
    pcb = find_primary_pcb(root, enforce_roots=False)
    rows: List[Dict[str, Any]] = []

    if include_ibom:
        if pcb:
            rows.append(run_ibom(pcb, out_dir=export_dir))
        else:
            rows.append({"ok": False, "skipped": True, "reason": "missing_pcb", "id": "ibom"})

    if include_pcbdraw:
        if pcb:
            rows.append(run_pcbdraw(pcb, out_dir=export_dir))
        else:
            rows.append({"ok": False, "skipped": True, "reason": "missing_pcb", "id": "pcbdraw"})

    if include_esphome:
        graph_path = root / "build_compilation" / "build_graph.json"
        build_graph: Optional[Dict[str, Any]] = None
        if graph_path.is_file():
            try:
                build_graph = json.loads(graph_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                build_graph = None
        fw_meta = root / "firmware" / "FIRMWARE_SCAFFOLD.json"
        pins = None
        bid = build_id
        if fw_meta.is_file():
            try:
                fw = json.loads(fw_meta.read_text(encoding="utf-8"))
                pins = fw.get("pins")
                bid = bid or str(fw.get("build_id") or "")
            except (OSError, json.JSONDecodeError):
                pass
        if build_graph or pins:
            rows.append(
                write_esphome_stub(
                    build_id=bid or root.name,
                    out_dir=root,
                    build_graph=build_graph,
                    pins=pins,
                    project_name=project_name or root.name,
                )
            )
        else:
            rows.append(
                {
                    "ok": False,
                    "skipped": True,
                    "reason": "no_build_graph_or_firmware_pins",
                    "id": "esphome",
                }
            )

    # Normalize relative paths under root
    for row in rows:
        path = row.get("path")
        if path:
            try:
                row["relative"] = str(Path(path).resolve().relative_to(root.resolve()))
            except Exception:
                pass

    present = [r for r in rows if r.get("ok")]
    report = {
        "ok": True,  # bundle orchestration succeeded even if tools skipped
        "skipped": len(present) == 0,
        "build_dir": str(root),
        "export_dir": str(export_dir),
        "exports": rows,
        "present_count": len(present),
        "oss_mech_refs": OSS_MECH_REFS,
    }
    report_path = export_dir / "OSS_EXPORTS.json"
    try:
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        report["report_path"] = str(report_path)
    except OSError:
        pass
    return report


def attach_oss_mech_refs(mechanism_pack: Mapping[str, Any] | None) -> Dict[str, Any]:
    """Annotate MECHANISM_PACK with OSS mech reference links (no CadQuery hard dep)."""
    pack = dict(mechanism_pack or {})
    pack["oss_mech_refs"] = list(OSS_MECH_REFS)
    return pack

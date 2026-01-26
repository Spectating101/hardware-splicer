from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from src.engines.layout_advisor import find_mounting_holes, summarize_board


def render_open_scad_mounting_plate(
    *,
    board_width_mm: float,
    board_height_mm: float,
    holes: List[Dict[str, Any]],
    plate_thickness_mm: float = 3.0,
    edge_margin_mm: float = 6.0,
    hole_d_mm: float = 3.2,
) -> str:
    """
    Generate an OpenSCAD mounting plate stub for “prototype mode”.
    """
    w = board_width_mm + 2 * edge_margin_mm
    h = board_height_mm + 2 * edge_margin_mm

    lines: List[str] = []
    lines.append("// Auto-generated OpenSCAD stub (prototype mounting plate)")
    lines.append("$fn = 48;")
    lines.append("")
    lines.append(f"plate_w = {w:.3f};")
    lines.append(f"plate_h = {h:.3f};")
    lines.append(f"plate_t = {plate_thickness_mm:.3f};")
    lines.append(f"edge_margin = {edge_margin_mm:.3f};")
    lines.append(f"hole_d = {hole_d_mm:.3f};")
    lines.append("")
    lines.append("module plate(){")
    lines.append("  difference(){")
    lines.append("    translate([-plate_w/2, -plate_h/2, 0]) cube([plate_w, plate_h, plate_t]);")
    if holes:
        lines.append("    // Mounting holes (from KiCad footprint centroids)")
        for hole in holes:
            x = float(hole.get("x_mm") or 0.0)
            y = float(hole.get("y_mm") or 0.0)
            # Place hole coords relative to board center: best-effort; assumes KiCad origin is near board.
            lines.append(f"    translate([{x:.3f}, {y:.3f}, -1]) cylinder(d=hole_d, h=plate_t+2);")
    else:
        lines.append("    // No holes detected; add manually.")
    lines.append("  }")
    lines.append("}")
    lines.append("")
    lines.append("plate();")
    return "\n".join(lines).rstrip() + "\n"


def render_prototype_wiring_plan_md(
    *,
    requirements: Optional[Dict[str, Any]] = None,
    board_summary: Optional[Dict[str, Any]] = None,
) -> str:
    req = requirements or {}
    connectors = req.get("connectors") or []
    interfaces = req.get("interfaces") or []
    power = req.get("power") or {}
    rails = power.get("rails") or []
    loads = power.get("loads") or []

    lines: List[str] = []
    lines.append("# Prototype Wiring Plan (Functional-First)")
    lines.append("")
    if board_summary:
        b = board_summary.get("board") or {}
        lines.append(f"- Board size: `{b.get('width_mm')}mm x {b.get('height_mm')}mm`")
        lines.append(f"- Copper layers: `{b.get('layers')}`")
        lines.append("")

    lines.append("## Power")
    if rails:
        for r in rails[:20]:
            if isinstance(r, dict):
                lines.append(f"- Rail `{r.get('name')}`: `{r.get('voltage_v')}V` max `{r.get('max_current_a')}A` {r.get('notes') or ''}".rstrip())
    else:
        lines.append("- No rails specified; define rails and max currents.")
    lines.append("")
    if loads:
        lines.append("## Loads (per rail)")
        for l in loads[:30]:
            if isinstance(l, dict):
                lines.append(f"- `{l.get('name')}` on `{l.get('rail')}`: `{l.get('current_a')}A` {l.get('notes') or ''}".rstrip())
        lines.append("")

    lines.append("## External connectors / IO")
    if connectors:
        for c in connectors[:30]:
            if isinstance(c, dict):
                lines.append(f"- `{c.get('name')}` type `{c.get('type')}` external `{c.get('external')}` hotplug `{c.get('hotplug')}`")
    else:
        lines.append("- No connectors list; add at least the external IO points.")
    lines.append("")

    lines.append("## Interfaces")
    if interfaces:
        for i in interfaces[:30]:
            if isinstance(i, dict):
                lines.append(f"- `{i.get('name')}` `{i.get('type')}` @ `{i.get('voltage_v')}V` notes: {i.get('notes') or ''}".rstrip())
    else:
        lines.append("- No interfaces specified.")
    lines.append("")

    lines.append("## Prototype intent rules")
    lines.append("- Flying leads and off-board components allowed if functionally safe and strain-relieved.")
    lines.append("- Add testpoints for rails and critical signals (GND, VIN, VOUT, RESET, UART).")
    lines.append("- Prefer connectors you can rework; avoid fragile soldered wires without mechanical support.")
    return "\n".join(lines).rstrip() + "\n"


def build_prototype3d_artifacts(pcb_path: Path, requirements: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    summary = summarize_board(pcb_path)
    holes = find_mounting_holes(pcb_path)
    b = summary["board"]
    scad = render_open_scad_mounting_plate(
        board_width_mm=float(b["width_mm"]),
        board_height_mm=float(b["height_mm"]),
        holes=holes,
    )
    wiring = render_prototype_wiring_plan_md(requirements=requirements, board_summary=summary)
    return {"board_summary": summary["board"], "mounting_holes": holes, "scad": scad, "wiring_plan_md": wiring}


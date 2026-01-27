from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.engines.cam.gcode_engine import GCodeGenerator, ToolpathConfig
from src.engines.kicad_pcb_geometry import extract_pcb_geometry


@dataclass(frozen=True)
class ProbePoint:
    point_id: str
    ref: str
    x_mm: float
    y_mm: float
    expected: str = ""
    notes: str = ""


def _find_footprint_xy(pcb_path: Path, ref: str) -> Optional[Tuple[float, float]]:
    geom = extract_pcb_geometry(str(pcb_path))
    for fp in geom.get("footprints") or []:
        if not isinstance(fp, dict):
            continue
        if str(fp.get("ref") or "").strip().upper() == ref.strip().upper():
            at = fp.get("at") or {}
            try:
                return float(at.get("x")), float(at.get("y"))
            except Exception:
                return None
    return None


def build_probe_points(
    pcb_path: Path,
    plan: Dict[str, Any],
) -> List[ProbePoint]:
    points_in = plan.get("points") or []
    out: List[ProbePoint] = []
    for idx, p in enumerate(points_in, start=1):
        if not isinstance(p, dict):
            continue
        ref = str(p.get("ref") or "").strip()
        expected = str(p.get("expected") or "").strip()
        notes = str(p.get("notes") or "").strip()
        if ref:
            xy = _find_footprint_xy(pcb_path, ref)
            if not xy:
                continue
            x, y = xy
            pid = str(p.get("point_id") or f"{ref}")
            out.append(ProbePoint(point_id=pid, ref=ref, x_mm=x, y_mm=y, expected=expected, notes=notes))
            continue

        # explicit coordinates
        if p.get("x_mm") is not None and p.get("y_mm") is not None:
            try:
                x = float(p.get("x_mm"))
                y = float(p.get("y_mm"))
            except Exception:
                continue
            pid = str(p.get("point_id") or f"P{idx}")
            out.append(ProbePoint(point_id=pid, ref=str(p.get("label") or ""), x_mm=x, y_mm=y, expected=expected, notes=notes))
    return out


def render_runlog_csv(points: List[ProbePoint]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["timestamp", "point_id", "ref", "x_mm", "y_mm", "expected", "measured", "units", "notes"])
    for p in points:
        w.writerow(["", p.point_id, p.ref, f"{p.x_mm:.3f}", f"{p.y_mm:.3f}", p.expected, "", "", p.notes])
    return buf.getvalue()


def render_probe_report_md(
    *,
    pcb_filename: str,
    points: List[ProbePoint],
    gcode_preview: str,
    dry_run: bool,
) -> str:
    lines: List[str] = []
    lines.append("# Probe Plan (Software-only MVP)")
    lines.append("")
    lines.append(f"- PCB: `{pcb_filename}`")
    lines.append(f"- Points: `{len(points)}`")
    lines.append(f"- Dry-run: `{dry_run}`")
    lines.append("")
    lines.append("## Safety / Workflow")
    lines.append("- Always home first, keep a safe Z height, and use an e-stop on real hardware.")
    lines.append("- This MVP is designed for *human-in-the-loop probing*: it pauses at each point.")
    lines.append("- Coordinate systems are not calibrated by default; you must calibrate PCB origin to machine origin before trusting positions.")
    lines.append("")
    lines.append("## Points")
    if points:
        for p in points[:50]:
            exp = f" expected `{p.expected}`" if p.expected else ""
            lines.append(f"- `{p.point_id}` `{p.ref}` @ ({p.x_mm:.3f}, {p.y_mm:.3f})mm{exp}")
    else:
        lines.append("- None (no matching refs/coords).")
    lines.append("")
    lines.append("## G-code preview (first 30 lines)")
    lines.append("```")
    for ln in gcode_preview.splitlines()[:30]:
        lines.append(ln)
    lines.append("```")
    return "\n".join(lines).rstrip() + "\n"


def build_probe_gcode(
    points: List[ProbePoint],
    *,
    travel_z: float = 5.0,
    work_z: float = -0.1,
    feed_xy: int = 1200,
    feed_z: int = 120,
    home_first: bool = True,
    auto_plunge: bool = False,
) -> str:
    cfg = ToolpathConfig(travel_z=travel_z, work_z=work_z, feed_rate_xy=feed_xy, feed_rate_z=feed_z, robot_mode=True)
    gc = GCodeGenerator(cfg)
    if home_first:
        gc.buffer.insert(0, "G28 ; Home all axes")
    for p in points:
        gc.move_to(p.x_mm, p.y_mm)
        gc.buffer.append(f"M0 ; Probe point {p.point_id} {p.ref}".rstrip())
        if auto_plunge:
            gc.plunge()
            gc.buffer.append("G4 P500 ; Dwell 500ms")
            gc.retract()
    return gc.export()


def probe_plan_template() -> Dict[str, Any]:
    return {
        "home_first": True,
        "auto_plunge": False,
        "travel_z": 5.0,
        "work_z": -0.1,
        "feed_xy": 1200,
        "feed_z": 120,
        "points": [
            {"point_id": "U1", "ref": "U1", "expected": "", "notes": "Footprint centroid"},
            {"point_id": "TP1", "x_mm": 10.0, "y_mm": 20.0, "expected": "3.3V", "notes": "Manual coordinate"},
        ],
    }


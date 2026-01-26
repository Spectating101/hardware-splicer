from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


@dataclass(frozen=True)
class FootprintRecord:
    ref: str
    footprint: str
    x_mm: float
    y_mm: float


def _load_board(pcb_path: Path):
    import pcbnew  # type: ignore

    board = pcbnew.LoadBoard(str(pcb_path))
    return pcbnew, board


def _mm(v_nm: int) -> float:
    # pcbnew uses nanometers in modern KiCad (int).
    return float(v_nm) / 1_000_000.0


def summarize_board(pcb_path: Path) -> Dict[str, Any]:
    pcbnew, board = _load_board(pcb_path)
    bbox = board.GetBoardEdgesBoundingBox()
    width_mm = _mm(bbox.GetWidth())
    height_mm = _mm(bbox.GetHeight())
    origin = bbox.GetPosition()
    origin_x_mm = _mm(origin.x)
    origin_y_mm = _mm(origin.y)

    fps: List[FootprintRecord] = []
    for fp in board.GetFootprints():
        try:
            pos = fp.GetPosition()
            fps.append(
                FootprintRecord(
                    ref=str(fp.GetReference()),
                    footprint=str(fp.GetFPID().GetLibItemName()),
                    x_mm=_mm(pos.x),
                    y_mm=_mm(pos.y),
                )
            )
        except Exception:
            continue

    return {
        "board": {
            "width_mm": round(width_mm, 3),
            "height_mm": round(height_mm, 3),
            "origin_mm": {"x": round(origin_x_mm, 3), "y": round(origin_y_mm, 3)},
            "layers": int(board.GetCopperLayerCount()),
        },
        "footprints": [fp.__dict__ for fp in fps],
    }


def _distance_mm(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    dx = a[0] - b[0]
    dy = a[1] - b[1]
    return (dx * dx + dy * dy) ** 0.5


def analyze_decoupling_proximity(pcb_path: Path, *, cap_prefix: str = "C", ic_prefix: str = "U") -> Dict[str, Any]:
    summary = summarize_board(pcb_path)
    fps = summary.get("footprints") or []
    caps = [fp for fp in fps if str(fp.get("ref") or "").upper().startswith(cap_prefix)]
    ics = [fp for fp in fps if str(fp.get("ref") or "").upper().startswith(ic_prefix)]

    if not caps or not ics:
        return {
            "status": "needs_input",
            "missing_inputs": ["pcb footprints with C* and U* references"],
            "issues": [],
            "notes": "Decoupling proximity requires identifying capacitors and ICs by reference designators.",
        }

    ic_points = [(float(ic["x_mm"]), float(ic["y_mm"]), str(ic["ref"])) for ic in ics]
    distances: List[Dict[str, Any]] = []
    for c in caps:
        cpt = (float(c["x_mm"]), float(c["y_mm"]))
        best = None
        for ix, iy, iref in ic_points:
            d = _distance_mm(cpt, (ix, iy))
            if best is None or d < best[0]:
                best = (d, iref)
        if best:
            distances.append({"cap_ref": c["ref"], "nearest_ic_ref": best[1], "distance_mm": round(best[0], 3)})

    distances.sort(key=lambda r: r["distance_mm"], reverse=True)
    worst = distances[:10]
    # Heuristic thresholds
    threshold_warn = 10.0 if True else 6.0
    issues = []
    for row in worst:
        if row["distance_mm"] >= threshold_warn:
            issues.append(
                {
                    "type": "decoupling_far",
                    "severity": "warning",
                    "message": "Capacitor far from nearest IC (heuristic).",
                    "details": row,
                }
            )

    status = "issues_found" if issues else "ok"
    return {
        "status": status,
        "missing_inputs": [],
        "issues": issues,
        "worst_cases": worst,
        "notes": "Heuristic only: uses footprint centroid distance between C* and U* refs. True decoupling depends on which pins/rails each cap serves.",
    }


def find_mounting_holes(pcb_path: Path) -> List[Dict[str, Any]]:
    pcbnew, board = _load_board(pcb_path)
    holes: List[Dict[str, Any]] = []
    for fp in board.GetFootprints():
        fpn = ""
        try:
            fpn = str(fp.GetFPID().GetLibItemName())
        except Exception:
            fpn = ""
        if "mounting" not in fpn.lower() and "hole" not in fpn.lower():
            continue
        pos = fp.GetPosition()
        holes.append(
            {
                "ref": str(fp.GetReference()),
                "footprint": fpn,
                "x_mm": round(_mm(pos.x), 3),
                "y_mm": round(_mm(pos.y), 3),
            }
        )
    return holes


def render_layout_advice_md(pcb_path: Path) -> str:
    summary = summarize_board(pcb_path)
    dec = analyze_decoupling_proximity(pcb_path)
    holes = find_mounting_holes(pcb_path)

    b = summary["board"]
    lines: List[str] = []
    lines.append("# Layout Advice (Heuristic)")
    lines.append("")
    lines.append(f"- Board size: `{b['width_mm']}mm x {b['height_mm']}mm`")
    lines.append(f"- Copper layers: `{b['layers']}`")
    lines.append("")
    lines.append("## High-signal checks")
    lines.append("- Keep high-current loops short; minimize switch node copper exposure.")
    lines.append("- Maintain continuous return paths under fast edges; avoid split planes under signals.")
    lines.append("- Place connectors near edges and protect external IO with ESD where appropriate.")
    lines.append("")
    lines.append("## Decoupling proximity (C* → nearest U*)")
    if dec.get("status") == "needs_input":
        lines.append(f"- Needs input: `{', '.join(dec.get('missing_inputs') or [])}`")
    else:
        worst = dec.get("worst_cases") or []
        if worst:
            for row in worst[:10]:
                lines.append(f"- {row['cap_ref']} → {row['nearest_ic_ref']}: `{row['distance_mm']}mm`")
        else:
            lines.append("- No capacitors or ICs detected.")
    lines.append("")
    lines.append("## Mounting holes (best-effort)")
    if holes:
        for h in holes[:20]:
            lines.append(f"- {h['ref']} @ ({h['x_mm']}, {h['y_mm']})mm `{h['footprint']}`")
    else:
        lines.append("- None detected (or not named as mounting holes).")
    lines.append("")
    lines.append("## Notes")
    lines.append("- This report is heuristic; use it to guide a human review, not to claim correctness.")
    lines.append("- If you provide the schematic/netlist with power rails, the system can be extended to map caps to rails and tighten the analysis.")
    return "\n".join(lines).rstrip() + "\n"


def render_pcbnew_script(pcb_path: Path) -> str:
    # A script intended to run inside KiCad's scripting console (pcbnew is available there).
    return (
        "# pcbnew script: layout sanity helper\n"
        "# Run inside KiCad PCB Editor (Tools -> Scripting Console)\n"
        "import pcbnew\n"
        "from math import sqrt\n"
        "\n"
        f"BOARD_PATH = r\"{str(pcb_path)}\"\n"
        "board = pcbnew.LoadBoard(BOARD_PATH)\n"
        "bbox = board.GetBoardEdgesBoundingBox()\n"
        "w_mm = bbox.GetWidth() / 1_000_000\n"
        "h_mm = bbox.GetHeight() / 1_000_000\n"
        "print(f\"Board: {w_mm:.2f}mm x {h_mm:.2f}mm, layers={board.GetCopperLayerCount()}\")\n"
        "\n"
        "fps = list(board.GetFootprints())\n"
        "caps = [fp for fp in fps if fp.GetReference().upper().startswith('C')]\n"
        "ics = [fp for fp in fps if fp.GetReference().upper().startswith('U')]\n"
        "def mm(pt):\n"
        "    return (pt.x/1_000_000.0, pt.y/1_000_000.0)\n"
        "def dist(a,b):\n"
        "    return sqrt((a[0]-b[0])**2 + (a[1]-b[1])**2)\n"
        "ic_pts = [(mm(fp.GetPosition()), fp.GetReference()) for fp in ics]\n"
        "rows=[]\n"
        "for c in caps:\n"
        "    cpt = mm(c.GetPosition())\n"
        "    best=None\n"
        "    for ipt, iref in ic_pts:\n"
        "        d=dist(cpt, ipt)\n"
        "        if best is None or d<best[0]:\n"
        "            best=(d, iref)\n"
        "    if best:\n"
        "        rows.append((best[0], c.GetReference(), best[1]))\n"
        "rows.sort(reverse=True)\n"
        "print('Worst C*→U* distances:')\n"
        "for d, cref, uref in rows[:10]:\n"
        "    print(f'  {cref} -> {uref}: {d:.2f}mm')\n"
    )


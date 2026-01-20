#!/usr/bin/env python3
from __future__ import annotations

import csv
import io
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from src.engines.kicad_pcb_geometry import extract_pcb_geometry


@dataclass(frozen=True)
class PnpRow:
    ref: str
    value: str
    footprint: str
    pos_x_mm: float
    pos_y_mm: float
    rot_deg: float
    side: str  # "top" | "bottom" | "unknown"


def _side_from_layer(layer: str) -> str:
    l = (layer or "").strip()
    if l.startswith("F."):
        return "top"
    if l.startswith("B."):
        return "bottom"
    return "unknown"


def _iter_footprints(geometry: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
    fps = geometry.get("footprints")
    if isinstance(fps, list):
        for fp in fps:
            if isinstance(fp, dict):
                yield fp


def extract_pnp_rows_from_kicad_pcb(kicad_pcb_path: str) -> List[PnpRow]:
    geom = extract_pcb_geometry(kicad_pcb_path)
    rows: List[PnpRow] = []
    for fp in _iter_footprints(geom):
        at = fp.get("at") if isinstance(fp.get("at"), dict) else {}
        try:
            x = float(at.get("x", 0.0))
            y = float(at.get("y", 0.0))
            rot = float(at.get("rot_deg", 0.0))
        except Exception:
            x, y, rot = 0.0, 0.0, 0.0

        rows.append(
            PnpRow(
                ref=str(fp.get("ref") or "?"),
                value=str(fp.get("value") or ""),
                footprint=str(fp.get("footprint") or ""),
                pos_x_mm=x,
                pos_y_mm=y,
                rot_deg=rot,
                side=_side_from_layer(str(fp.get("layer") or "")),
            )
        )

    # Stable output: sort by ref.
    rows.sort(key=lambda r: r.ref)
    return rows


def export_pnp_csv(rows: List[PnpRow]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Ref", "Value", "Footprint", "PosX_mm", "PosY_mm", "Rot_deg", "Side"])
    for r in rows:
        w.writerow([r.ref, r.value, r.footprint, f"{r.pos_x_mm:.4f}", f"{r.pos_y_mm:.4f}", f"{r.rot_deg:.2f}", r.side])
    return buf.getvalue()


def export_pnp_csv_via_kicad_cli(kicad_pcb_path: str, *, units: str = "mm") -> Optional[str]:
    """
    Best-effort export via KiCad itself (preferred when available).

    Returns CSV text on success, or None when `kicad-cli` is unavailable or export fails.
    """
    if not shutil.which("kicad-cli"):
        return None

    pcb = Path(kicad_pcb_path)
    if not pcb.exists():
        return None

    with tempfile.TemporaryDirectory(prefix="circuit-ai-pnp-") as td:
        out_path = Path(td) / f"{pcb.stem}.pos.csv"
        try:
            subprocess.run(
                [
                    "kicad-cli",
                    "pcb",
                    "export",
                    "pos",
                    "--format",
                    "csv",
                    "--units",
                    units,
                    "--side",
                    "both",
                    "--output",
                    str(out_path),
                    str(pcb),
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
                timeout=120,
            )
            return out_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return None

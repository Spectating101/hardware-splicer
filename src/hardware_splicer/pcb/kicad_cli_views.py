"""Human-readable schematic/PCB exports via kicad-cli (on-demand, not compile-critical)."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..build_files import find_primary_pcb


def _run(cmd: List[str], *, timeout_s: int = 120) -> Dict[str, Any]:
    kicad_cli = shutil.which("kicad-cli")
    if not kicad_cli:
        return {"ok": False, "skipped": True, "reason": "kicad-cli not on PATH"}
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=timeout_s)
        return {"ok": True}
    except subprocess.CalledProcessError as exc:
        return {"ok": False, "skipped": False, "reason": "kicad-cli export failed", "stderr": (exc.stderr or "")[-1500:]}
    except Exception as exc:
        return {"ok": False, "skipped": False, "reason": str(exc)}


def export_human_views(
    build_dir: str | Path,
    *,
    out_subdir: str = "build_compilation/exports",
) -> Dict[str, Any]:
    """Generate PDF/SVG/PNG views when kicad-cli is available. Idempotent overwrite."""
    root = Path(build_dir).resolve()
    comp = root / "build_compilation"
    export_dir = root / out_subdir
    export_dir.mkdir(parents=True, exist_ok=True)

    pcb = find_primary_pcb(root)
    sch = pcb.with_suffix(".kicad_sch") if pcb else None
    if sch and not sch.is_file():
        sch = next(iter(sorted(comp.glob("*.kicad_sch"))), None) if comp.is_dir() else None

    kicad_cli = shutil.which("kicad-cli")
    if not kicad_cli:
        return {"ok": False, "skipped": True, "reason": "kicad-cli not on PATH", "exports": []}

    rows: List[Dict[str, Any]] = []

    if sch and sch.is_file():
        for kind, args in (
            ("schematic_pdf", ["sch", "export", "pdf", "-o", str(export_dir / "schematic.pdf"), str(sch)]),
            ("schematic_svg", ["sch", "export", "svg", "-o", str(export_dir / "schematic.svg"), str(sch)]),
        ):
            result = _run([kicad_cli, *args])
            rel = f"{out_subdir}/schematic.{kind.split('_')[1]}"
            path = root / rel
            rows.append(
                {
                    "id": kind,
                    "label": f"Schematic {kind.split('_')[1].upper()}",
                    "relative": rel if path.is_file() else None,
                    "present": path.is_file(),
                    **result,
                }
            )

    if pcb and pcb.is_file():
        for kind, args in (
            ("pcb_svg", ["pcb", "export", "svg", "-o", str(export_dir / "board.svg"), str(pcb)]),
            ("pcb_pdf", ["pcb", "export", "pdf", "-o", str(export_dir / "board.pdf"), str(pcb)]),
            ("pcb_png", ["pcb", "render", "-o", str(export_dir / "board_3d.png"), "--quality", "basic", str(pcb)]),
        ):
            result = _run([kicad_cli, *args], timeout_s=180)
            ext = {"pcb_svg": "svg", "pcb_pdf": "pdf", "pcb_png": "png"}[kind]
            name = {"pcb_svg": "board.svg", "pcb_pdf": "board.pdf", "pcb_png": "board_3d.png"}[kind]
            rel = f"{out_subdir}/{name}"
            path = root / rel
            rows.append(
                {
                    "id": kind,
                    "label": kind.replace("_", " ").upper(),
                    "relative": rel if path.is_file() else None,
                    "present": path.is_file(),
                    **result,
                }
            )

    # Best-effort InteractiveHtmlBom + PcbDraw (skip when tools absent)
    try:
        from ..integrations.ibom_bridge import run_ibom
        from ..integrations.pcbdraw_bridge import run_pcbdraw

        if pcb and pcb.is_file():
            for report in (run_ibom(pcb, out_dir=export_dir), run_pcbdraw(pcb, out_dir=export_dir)):
                rel = None
                path = report.get("path")
                if path:
                    try:
                        rel = str(Path(path).resolve().relative_to(root.resolve()))
                    except Exception:
                        rel = None
                rows.append(
                    {
                        "id": report.get("id"),
                        "label": report.get("label") or report.get("id"),
                        "relative": rel,
                        "present": bool(report.get("ok")),
                        "ok": bool(report.get("ok")),
                        "skipped": bool(report.get("skipped")),
                        "reason": report.get("reason"),
                    }
                )
    except Exception:
        pass

    if not rows:
        return {"ok": False, "skipped": True, "reason": "no schematic or PCB found", "exports": []}

    present = [row for row in rows if row.get("present")]
    return {
        "ok": len(present) > 0,
        "skipped": len(present) == 0,
        "export_dir": str(export_dir),
        "exports": rows,
        "present_count": len(present),
    }

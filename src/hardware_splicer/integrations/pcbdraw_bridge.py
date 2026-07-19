"""PcbDraw glue — best-effort 2D board SVG for bring-up docs."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional


def _resolve_pcbdraw() -> Optional[str]:
    return shutil.which("pcbdraw")


def run_pcbdraw(
    kicad_pcb_path: str | Path,
    *,
    out_dir: str | Path,
    timeout_s: int = 120,
) -> Dict[str, Any]:
    """Render board.svg via pcbdraw when available. Never raises."""
    pcb = Path(kicad_pcb_path)
    export = Path(out_dir)
    export.mkdir(parents=True, exist_ok=True)
    out_svg = export / "pcbdraw_board.svg"

    if not pcb.is_file():
        return {"ok": False, "skipped": True, "reason": "missing_pcb", "id": "pcbdraw"}

    cli = _resolve_pcbdraw()
    if not cli:
        return {"ok": False, "skipped": True, "reason": "pcbdraw_unavailable", "id": "pcbdraw"}

    cmd = [cli, "plot", str(pcb), str(out_svg)]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s, check=False)
    except subprocess.TimeoutExpired:
        return {"ok": False, "skipped": False, "reason": "pcbdraw_timeout", "id": "pcbdraw"}
    except Exception as exc:
        return {"ok": False, "skipped": True, "reason": f"pcbdraw_error:{exc}", "id": "pcbdraw"}

    if out_svg.is_file() and out_svg.stat().st_size > 50:
        return {
            "ok": True,
            "skipped": False,
            "id": "pcbdraw",
            "label": "PcbDraw board SVG",
            "path": str(out_svg),
            "relative": str(out_svg),
        }

    # Older pcbdraw CLI: pcbdraw <pcb> <svg>
    if proc.returncode != 0:
        cmd2 = [cli, str(pcb), str(out_svg)]
        try:
            proc2 = subprocess.run(cmd2, capture_output=True, text=True, timeout=timeout_s, check=False)
        except Exception as exc:
            return {"ok": False, "skipped": True, "reason": f"pcbdraw_error:{exc}", "id": "pcbdraw"}
        if out_svg.is_file() and out_svg.stat().st_size > 50:
            return {
                "ok": True,
                "skipped": False,
                "id": "pcbdraw",
                "label": "PcbDraw board SVG",
                "path": str(out_svg),
                "relative": str(out_svg),
            }
        return {
            "ok": False,
            "skipped": False,
            "reason": "pcbdraw_failed",
            "id": "pcbdraw",
            "stderr": ((proc2.stderr or proc.stderr) or "")[-800:],
        }

    return {"ok": False, "skipped": False, "reason": "pcbdraw_failed", "id": "pcbdraw"}

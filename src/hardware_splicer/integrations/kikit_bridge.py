"""KiKit glue — opt-in manufacturer fab preset export."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional

# Common JLCPCB-style fab export via kikit fab
DEFAULT_PRESET = "jlcpcb"


def _resolve_kikit() -> Optional[str]:
    return shutil.which("kikit")


def run_kikit_fab(
    kicad_pcb_path: str | Path,
    *,
    out_dir: str | Path,
    preset: str = DEFAULT_PRESET,
    timeout_s: int = 180,
) -> Dict[str, Any]:
    """Run `kikit fab <preset>` when installed. Never raises."""
    pcb = Path(kicad_pcb_path)
    export = Path(out_dir)
    export.mkdir(parents=True, exist_ok=True)

    if not pcb.is_file():
        return {"ok": False, "skipped": True, "reason": "missing_pcb", "id": "kikit"}

    cli = _resolve_kikit()
    if not cli:
        return {"ok": False, "skipped": True, "reason": "kikit_unavailable", "id": "kikit"}

    preset = (preset or DEFAULT_PRESET).strip() or DEFAULT_PRESET
    cmd = [cli, "fab", preset, str(pcb), str(export)]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s, check=False)
    except subprocess.TimeoutExpired:
        return {"ok": False, "skipped": False, "reason": "kikit_timeout", "id": "kikit"}
    except Exception as exc:
        return {"ok": False, "skipped": True, "reason": f"kikit_error:{exc}", "id": "kikit"}

    files = sorted(p for p in export.rglob("*") if p.is_file())
    if proc.returncode == 0 and files:
        return {
            "ok": True,
            "skipped": False,
            "id": "kikit",
            "label": f"KiKit fab ({preset})",
            "preset": preset,
            "out_dir": str(export),
            "file_count": len(files),
            "files": [str(p.relative_to(export)) for p in files[:40]],
        }
    return {
        "ok": False,
        "skipped": False,
        "reason": "kikit_failed",
        "id": "kikit",
        "preset": preset,
        "stderr": (proc.stderr or "")[-1200:],
        "stdout": (proc.stdout or "")[-600:],
    }

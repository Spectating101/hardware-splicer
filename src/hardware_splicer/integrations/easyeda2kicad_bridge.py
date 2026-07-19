"""easyeda2kicad glue — opt-in LCSC part → KiCad library export."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional


def _resolve_easyeda2kicad() -> Optional[List[str]]:
    cli = shutil.which("easyeda2kicad")
    if cli:
        return [cli]
    # python -m easyeda2kicad
    return ["python3", "-m", "easyeda2kicad"]


def fetch_lcsc_to_kicad(
    lcsc_id: str,
    *,
    out_dir: str | Path,
    timeout_s: int = 120,
) -> Dict[str, Any]:
    """Fetch one LCSC part into a KiCad lib directory. Never raises."""
    part = str(lcsc_id or "").strip().upper()
    if not part.startswith("C") or len(part) < 2:
        return {"ok": False, "skipped": False, "reason": "invalid_lcsc_id", "id": "easyeda2kicad"}

    export = Path(out_dir)
    export.mkdir(parents=True, exist_ok=True)
    base = _resolve_easyeda2kicad()
    if not base:
        return {"ok": False, "skipped": True, "reason": "easyeda2kicad_unavailable", "id": "easyeda2kicad"}

    cmd = [*base, "--full", f"--lcsc_id={part}", "--output", str(export)]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s, check=False)
    except FileNotFoundError:
        return {"ok": False, "skipped": True, "reason": "easyeda2kicad_unavailable", "id": "easyeda2kicad"}
    except subprocess.TimeoutExpired:
        return {"ok": False, "skipped": False, "reason": "easyeda2kicad_timeout", "id": "easyeda2kicad"}
    except Exception as exc:
        return {"ok": False, "skipped": True, "reason": f"easyeda2kicad_error:{exc}", "id": "easyeda2kicad"}

    files = sorted(p for p in export.rglob("*") if p.is_file())
    if "No module named" in (proc.stderr or "") or "No module named" in (proc.stdout or ""):
        return {"ok": False, "skipped": True, "reason": "easyeda2kicad_unavailable", "id": "easyeda2kicad"}

    if proc.returncode == 0 and files:
        return {
            "ok": True,
            "skipped": False,
            "id": "easyeda2kicad",
            "lcsc_id": part,
            "out_dir": str(export),
            "file_count": len(files),
            "files": [str(p.relative_to(export)) for p in files[:40]],
        }
    return {
        "ok": False,
        "skipped": False,
        "reason": "easyeda2kicad_failed",
        "id": "easyeda2kicad",
        "lcsc_id": part,
        "stderr": (proc.stderr or "")[-1000:],
    }

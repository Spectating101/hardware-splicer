"""InteractiveHtmlBom glue — best-effort HTML BOM from .kicad_pcb."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional


def _resolve_ibom_cli() -> Optional[str]:
    for name in ("generate_interactive_bom", "ibom", "InteractiveHtmlBom"):
        found = shutil.which(name)
        if found:
            return found
    # Common pip entry: python -m InteractiveHtmlBom.generate_interactive_bom
    return None


def run_ibom(
    kicad_pcb_path: str | Path,
    *,
    out_dir: str | Path,
    timeout_s: int = 120,
) -> Dict[str, Any]:
    """Generate Interactive HTML BOM when CLI is available. Never raises."""
    pcb = Path(kicad_pcb_path)
    export = Path(out_dir)
    export.mkdir(parents=True, exist_ok=True)
    out_html = export / "ibom.html"

    if not pcb.is_file():
        return {"ok": False, "skipped": True, "reason": "missing_pcb", "id": "ibom"}

    cli = _resolve_ibom_cli()
    if cli:
        cmd = [cli, str(pcb), "--no-browser", "--dest-dir", str(export), "--name-format", "ibom"]
    else:
        # Try module form (InteractiveHtmlBom package)
        cmd = [
            "python3",
            "-m",
            "InteractiveHtmlBom.GenerateInteractiveBom",
            str(pcb),
            "--no-browser",
            "--dest-dir",
            str(export),
            "--name-format",
            "ibom",
        ]

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s, check=False)
    except FileNotFoundError:
        return {"ok": False, "skipped": True, "reason": "ibom_cli_unavailable", "id": "ibom"}
    except subprocess.TimeoutExpired:
        return {"ok": False, "skipped": False, "reason": "ibom_timeout", "id": "ibom"}
    except Exception as exc:
        return {"ok": False, "skipped": True, "reason": f"ibom_error:{exc}", "id": "ibom"}

    # Tool may write ibom.html or <board>-ibom.html
    candidates = list(export.glob("*ibom*.html")) + list(export.glob("**/ibom.html"))
    if out_html.is_file():
        present = out_html
    elif candidates:
        present = candidates[0]
        if present.resolve() != out_html.resolve():
            try:
                out_html.write_bytes(present.read_bytes())
                present = out_html
            except OSError:
                pass
    else:
        present = None

    if present and present.is_file():
        return {
            "ok": True,
            "skipped": False,
            "id": "ibom",
            "label": "Interactive HTML BOM",
            "relative": str(present),
            "path": str(present),
            "stderr": (proc.stderr or "")[-500:],
        }

    reason = "ibom_failed"
    if proc.returncode != 0 and "No module named" in (proc.stderr or ""):
        reason = "ibom_cli_unavailable"
        return {"ok": False, "skipped": True, "reason": reason, "id": "ibom"}
    return {
        "ok": False,
        "skipped": False,
        "reason": reason,
        "id": "ibom",
        "stderr": (proc.stderr or "")[-800:],
    }

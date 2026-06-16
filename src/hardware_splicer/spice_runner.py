"""Batch ngspice runner for electrical simulation gates."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional


def ngspice_available() -> bool:
    return shutil.which("ngspice") is not None


def run_ngspice(
    *,
    netlist_text: str,
    timeout_s: int = 30,
    extra_args: Optional[List[str]] = None,
) -> Dict[str, Any]:
    if not ngspice_available():
        return {
            "ok": False,
            "error": "ngspice_not_available",
            "message": "ngspice is not installed on this host.",
            "export_method": "none",
        }

    args = ["ngspice", "-b"]
    if extra_args:
        args.extend(str(a) for a in extra_args)

    temp_dir = Path(tempfile.gettempdir()) / "hardware-splicer" / "spice"
    temp_dir.mkdir(parents=True, exist_ok=True)
    netlist_path = temp_dir / f"{next(tempfile._get_candidate_names())}.cir"
    netlist_path.write_text(netlist_text, encoding="utf-8")

    try:
        proc = subprocess.run(
            args + [str(netlist_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout_s,
            check=False,
        )
        ok = proc.returncode == 0
        return {
            "ok": ok,
            "returncode": proc.returncode,
            "stdout": proc.stdout[-20000:],
            "stderr": proc.stderr[-20000:],
            "netlist_file": str(netlist_path),
            "export_method": "ngspice",
        }
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "error": "timeout",
            "message": f"ngspice exceeded timeout ({timeout_s}s).",
            "netlist_file": str(netlist_path),
            "export_method": "ngspice",
        }

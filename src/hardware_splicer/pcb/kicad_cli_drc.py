"""Run KiCad 9 CLI DRC on emitted .kicad_pcb files (Flux-class fab gate)."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, Mapping, Optional


def run_kicad_cli_drc(
    kicad_pcb_path: str | Path,
    *,
    out_dir: Optional[str | Path] = None,
    timeout_s: int = 120,
) -> Dict[str, Any]:
    """Return parsed DRC JSON from `kicad-cli pcb drc` or a skip payload."""
    pcb = Path(kicad_pcb_path)
    if not pcb.is_file():
        return {
            "pass": False,
            "skipped": True,
            "reason": "missing_pcb",
            "errors": 1,
            "warnings": 0,
            "violations": [],
        }

    kicad_cli = shutil.which("kicad-cli")
    if not kicad_cli:
        return {
            "pass": None,
            "skipped": True,
            "reason": "kicad-cli not on PATH",
            "errors": 0,
            "warnings": 0,
            "violations": [],
        }

    report_dir = Path(out_dir) if out_dir else Path(tempfile.gettempdir())
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "KICAD_DRC.json"

    try:
        subprocess.run(
            [
                kicad_cli,
                "pcb",
                "drc",
                "--format",
                "json",
                "-o",
                str(report_path),
                str(pcb),
            ],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout_s,
        )
    except subprocess.CalledProcessError as exc:
        return {
            "pass": False,
            "skipped": False,
            "reason": "kicad-cli drc failed",
            "stderr": (exc.stderr or "")[-2000:],
            "errors": 1,
            "warnings": 0,
            "violations": [
                {
                    "type": "kicad_cli_error",
                    "severity": "error",
                    "description": "kicad-cli pcb drc exited with an error",
                }
            ],
        }
    except Exception as exc:
        return {
            "pass": False,
            "skipped": False,
            "reason": str(exc),
            "errors": 1,
            "warnings": 0,
            "violations": [],
        }

    if not report_path.is_file():
        return {
            "pass": False,
            "skipped": False,
            "reason": "no report written",
            "errors": 1,
            "warnings": 0,
            "violations": [],
        }

    payload = json.loads(report_path.read_text(encoding="utf-8"))
    violations = list(payload.get("violations") or [])
    errors = sum(1 for v in violations if str(v.get("severity") or "").lower() == "error")
    warnings = sum(1 for v in violations if str(v.get("severity") or "").lower() == "warning")

    return {
        "pass": errors == 0,
        "skipped": False,
        "reason": "",
        "errors": errors,
        "warnings": warnings,
        "violations": violations,
        "report_path": str(report_path),
        "kicad_version": payload.get("kicad_version"),
        "source": payload.get("source"),
        "unconnected_items": payload.get("unconnected_items") or [],
    }


def summarize_for_quality(report: Mapping[str, Any]) -> Dict[str, Any]:
    """Flatten for DESIGN_QUALITY.json."""
    if report.get("skipped"):
        return {
            "kicad_drc_ready": False,
            "kicad_drc_skipped": True,
            "kicad_drc_reason": report.get("reason"),
        }
    return {
        "kicad_drc_ready": True,
        "kicad_drc_skipped": False,
        "kicad_drc_pass": bool(report.get("pass")),
        "kicad_drc_errors": int(report.get("errors") or 0),
        "kicad_drc_warnings": int(report.get("warnings") or 0),
        "kicad_drc_report_path": report.get("report_path"),
    }

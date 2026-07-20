"""Run KiCad CLI DRC on emitted .kicad_pcb files (Flux-class fab gate)."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, Mapping, Optional


def _count_violations(violations: list[Mapping[str, Any]]) -> tuple[int, int]:
    active = [row for row in violations if not bool(row.get("excluded"))]
    errors = sum(1 for row in active if str(row.get("severity") or "").lower() == "error")
    warnings = sum(1 for row in active if str(row.get("severity") or "").lower() == "warning")
    return errors, warnings


def run_kicad_cli_drc(
    kicad_pcb_path: str | Path,
    *,
    out_dir: Optional[str | Path] = None,
    timeout_s: int = 120,
) -> Dict[str, Any]:
    """Return parsed DRC JSON from ``kicad-cli pcb drc`` or a skip payload.

    KiCad can write a useful report even when the process returns non-zero. The
    report is therefore parsed whenever present, and execution diagnostics are
    retained instead of collapsing every CLI failure into one anonymous error.
    """
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
        completed = subprocess.run(
            [
                kicad_cli,
                "pcb",
                "drc",
                "--format",
                "json",
                "--output",
                str(report_path),
                str(pcb),
            ],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout_s,
        )
    except Exception as exc:
        return {
            "pass": False,
            "skipped": False,
            "reason": str(exc),
            "errors": 1,
            "warnings": 0,
            "violations": [],
            "returncode": None,
        }

    stdout = completed.stdout or ""
    stderr = completed.stderr or ""
    if not report_path.is_file():
        return {
            "pass": False,
            "skipped": False,
            "reason": "kicad-cli drc failed" if completed.returncode else "no report written",
            "stdout": stdout[-4000:],
            "stderr": stderr[-4000:],
            "returncode": completed.returncode,
            "errors": 1,
            "warnings": 0,
            "violations": [
                {
                    "type": "kicad_cli_error",
                    "severity": "error",
                    "description": "kicad-cli pcb drc did not produce a JSON report",
                }
            ],
        }

    try:
        payload = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "pass": False,
            "skipped": False,
            "reason": f"invalid kicad DRC report: {exc}",
            "stdout": stdout[-4000:],
            "stderr": stderr[-4000:],
            "returncode": completed.returncode,
            "errors": 1,
            "warnings": 0,
            "violations": [],
            "report_path": str(report_path),
        }

    violations = [row for row in (payload.get("violations") or []) if isinstance(row, Mapping)]
    errors, warnings = _count_violations(violations)
    execution_ok = completed.returncode == 0
    reason = "" if execution_ok else "kicad-cli returned non-zero after writing report"
    return {
        "pass": execution_ok and errors == 0,
        "skipped": False,
        "reason": reason,
        "errors": errors + (0 if execution_ok else 1),
        "report_errors": errors,
        "warnings": warnings,
        "violations": violations,
        "report_path": str(report_path),
        "kicad_version": payload.get("kicad_version"),
        "source": payload.get("source"),
        "unconnected_items": payload.get("unconnected_items") or [],
        "schematic_parity": payload.get("schematic_parity") or [],
        "stdout": stdout[-4000:],
        "stderr": stderr[-4000:],
        "returncode": completed.returncode,
    }


def summarize_for_quality(report: Mapping[str, Any]) -> Dict[str, Any]:
    """Flatten KiCad execution and DRC facts for DESIGN_QUALITY.json."""
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
        "kicad_drc_report_errors": int(report.get("report_errors") or 0),
        "kicad_drc_warnings": int(report.get("warnings") or 0),
        "kicad_drc_reason": report.get("reason"),
        "kicad_drc_returncode": report.get("returncode"),
        "kicad_drc_stderr": report.get("stderr"),
        "kicad_drc_stdout": report.get("stdout"),
        "kicad_drc_violations": list(report.get("violations") or []),
        "kicad_drc_unconnected_items": list(report.get("unconnected_items") or []),
        "kicad_version": report.get("kicad_version"),
        "kicad_drc_report_path": report.get("report_path"),
    }

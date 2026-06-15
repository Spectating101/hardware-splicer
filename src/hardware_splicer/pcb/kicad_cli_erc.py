"""KiCad 9 CLI ERC on emitted schematics."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, Mapping, Optional


def run_kicad_cli_erc(
    kicad_sch_path: str | Path,
    *,
    out_dir: Optional[str | Path] = None,
    timeout_s: int = 120,
) -> Dict[str, Any]:
    sch = Path(kicad_sch_path)
    if not sch.is_file():
        return {
            "pass": False,
            "skipped": True,
            "reason": "missing_schematic",
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
    report_path = report_dir / "KICAD_ERC.json"

    try:
        subprocess.run(
            [
                kicad_cli,
                "sch",
                "erc",
                "--format",
                "json",
                "-o",
                str(report_path),
                str(sch),
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
    except subprocess.CalledProcessError as exc:
        return {
            "pass": False,
            "skipped": False,
            "reason": "kicad-cli erc failed",
            "stderr": (exc.stderr or "")[-2000:],
            "errors": 1,
            "warnings": 0,
            "violations": [],
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
            "reason": "no erc report written",
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
    }


def summarize_erc_for_quality(report: Mapping[str, Any]) -> Dict[str, Any]:
    if report.get("skipped"):
        return {
            "kicad_erc_ready": False,
            "kicad_erc_skipped": True,
            "kicad_erc_reason": report.get("reason"),
        }
    return {
        "kicad_erc_ready": True,
        "kicad_erc_skipped": False,
        "kicad_erc_pass": bool(report.get("pass")),
        "kicad_erc_errors": int(report.get("errors") or 0),
        "kicad_erc_warnings": int(report.get("warnings") or 0),
        "kicad_erc_report_path": report.get("report_path"),
    }

"""Re-run KiCad truth checks after human edits in KiCad (MCP sidecar workflow)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from .build_files import find_primary_pcb, read_design_quality_summary, resolve_build_dir
from .pcb.kicad_cli_drc import run_kicad_cli_drc, summarize_for_quality
from .pcb.kicad_cli_erc import run_kicad_cli_erc, summarize_erc_for_quality


def _read_json(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return dict(payload) if isinstance(payload, dict) else {}


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def recheck_build_after_kicad_edit(
    build_dir: str | Path,
    *,
    refresh_package: bool = True,
    export_views: bool = True,
    source: str = "kicad_sidecar_recheck",
) -> Dict[str, Any]:
    """Run DRC/ERC on saved KiCad files, refresh quality artifacts, optional package/views."""
    root = resolve_build_dir(build_dir)
    comp = root / "build_compilation"
    if not comp.is_dir():
        raise ValueError("build_compilation/ not found — run a compile first")

    pcb = find_primary_pcb(root)
    if not pcb:
        raise ValueError("no .kicad_pcb found under build_compilation/")

    sch = pcb.with_suffix(".kicad_sch")
    if not sch.is_file():
        matches = sorted(comp.glob("*.kicad_sch"))
        sch = matches[0] if matches else None

    drc = run_kicad_cli_drc(pcb, out_dir=comp)
    drc_path = comp / "KICAD_DRC.json"
    if not drc.get("skipped") and drc.get("report_path"):
        src = Path(str(drc["report_path"]))
        if src.is_file():
            drc_path.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    elif not drc.get("skipped"):
        _write_json(
            drc_path,
            {
                "pass": drc.get("pass"),
                "errors": drc.get("errors"),
                "warnings": drc.get("warnings"),
                "violations": drc.get("violations") or [],
            },
        )

    erc: Dict[str, Any] = {"skipped": True, "reason": "no schematic"}
    erc_path = comp / "KICAD_ERC.json"
    if sch and sch.is_file():
        erc = run_kicad_cli_erc(sch, out_dir=comp)
        if not erc.get("skipped") and erc.get("report_path"):
            src = Path(str(erc["report_path"]))
            if src.is_file():
                erc_path.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

    quality = _read_json(comp / "DESIGN_QUALITY.json")
    quality.update(summarize_for_quality(drc))
    quality.update(summarize_erc_for_quality(erc))
    quality["drc_pass"] = bool(drc.get("pass")) if not drc.get("skipped") else quality.get("drc_pass")
    quality["kicad_sidecar_recheck_at"] = datetime.now(timezone.utc).isoformat()
    quality["kicad_sidecar_source"] = source
    _write_json(comp / "DESIGN_QUALITY.json", quality)

    views_report: Optional[Dict[str, Any]] = None
    if export_views:
        from .pcb.kicad_cli_views import export_human_views

        views_report = export_human_views(root)

    package_report: Optional[Dict[str, Any]] = None
    if refresh_package:
        from .sdk import render_project_package

        package_report = render_project_package(root, source=source)

    summary = read_design_quality_summary(root)
    return {
        "ok": True,
        "build_dir": str(root),
        "pcb": str(pcb.relative_to(root)),
        "schematic": str(sch.relative_to(root)) if sch and sch.is_file() else None,
        "drc": {
            "pass": drc.get("pass"),
            "skipped": drc.get("skipped"),
            "errors": drc.get("errors"),
            "warnings": drc.get("warnings"),
            "reason": drc.get("reason"),
        },
        "erc": {
            "pass": erc.get("pass"),
            "skipped": erc.get("skipped"),
            "errors": erc.get("errors"),
            "warnings": erc.get("warnings"),
            "reason": erc.get("reason"),
        },
        "design_quality": summary,
        "export_views": views_report,
        "project_package": package_report,
    }

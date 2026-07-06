"""Safe read/list of KiCad artifacts under a build directory (for UI preview)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

KICAD_SUFFIXES = (".kicad_pcb", ".kicad_sch", ".kicad_pro")


def resolve_build_dir(build_dir: str | Path) -> Path:
    root = Path(build_dir).expanduser().resolve()
    if not root.is_dir():
        raise ValueError(f"build_dir not found: {root}")
    return root


def _read_json_optional(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return dict(payload) if isinstance(payload, dict) else {}


def _relative_under_root(root: Path, candidate: Path) -> str:
    resolved = candidate.resolve()
    if resolved == root:
        raise ValueError("relative path must name a file inside build_dir")
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError("path escapes build_dir") from exc
    return str(resolved.relative_to(root))


def list_kicad_files(build_dir: str | Path) -> List[Dict[str, Any]]:
    root = resolve_build_dir(build_dir)
    rows: List[Dict[str, Any]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() not in KICAD_SUFFIXES:
            continue
        rel = _relative_under_root(root, path)
        kind = "pcb" if path.suffix.lower() == ".kicad_pcb" else "schematic" if path.suffix.lower() == ".kicad_sch" else "project"
        rows.append(
            {
                "relative": rel,
                "kind": kind,
                "size_bytes": path.stat().st_size,
                "name": path.name,
            }
        )
    rows.sort(key=lambda row: (0 if row["kind"] == "pcb" else 1 if row["kind"] == "schematic" else 2, row["relative"]))
    return rows


def read_build_file(build_dir: str | Path, relative: str) -> Dict[str, Any]:
    root = resolve_build_dir(build_dir)
    rel = relative.strip().lstrip("/")
    if not rel or ".." in Path(rel).parts:
        raise ValueError("invalid relative path")
    target = (root / rel).resolve()
    rel_check = _relative_under_root(root, target)
    if not target.is_file():
        raise ValueError(f"file not found: {rel_check}")
    if target.suffix.lower() not in KICAD_SUFFIXES:
        raise ValueError("only KiCad preview files are served via this endpoint")
    text = target.read_text(encoding="utf-8", errors="replace")
    return {
        "relative": rel_check,
        "name": target.name,
        "kind": "pcb" if target.suffix.lower() == ".kicad_pcb" else "schematic",
        "size_bytes": target.stat().st_size,
        "content": text,
    }


def read_design_quality_summary(build_dir: str | Path) -> Dict[str, Any]:
    """Merge DESIGN_QUALITY*, KICAD_DRC, and gate files for UI compile-truth panels."""
    root = resolve_build_dir(build_dir)
    comp = root / "build_compilation"
    quality = _read_json_optional(comp / "DESIGN_QUALITY.json")
    gate = _read_json_optional(comp / "DESIGN_QUALITY_GATE.json")
    kicad_drc = _read_json_optional(comp / "KICAD_DRC.json")

    drc_errors = kicad_drc.get("errors")
    if drc_errors is None:
        drc_errors = quality.get("kicad_drc_errors", quality.get("drc_errors"))
    drc_warnings = kicad_drc.get("warnings")
    if drc_warnings is None:
        drc_warnings = quality.get("kicad_drc_warnings", quality.get("drc_warnings"))

    copper_tier = gate.get("copper_tier") or quality.get("copper_tier")
    fab_recommendation = gate.get("fab_recommendation") or quality.get("fab_recommendation")

    has_pcb = any(comp.glob("*.kicad_pcb")) if comp.is_dir() else False
    compile_ok = bool(quality.get("drc_pass")) if "drc_pass" in quality else (
        int(drc_errors or 0) == 0 if drc_errors is not None else None
    )

    return {
        "ok": True,
        "build_dir": str(root),
        "has_kicad_pcb": has_pcb,
        "kicad_drc_errors": drc_errors,
        "kicad_drc_warnings": drc_warnings,
        "drc_pass": quality.get("drc_pass", kicad_drc.get("pass")),
        "compile_ok": compile_ok,
        "build_ready": quality.get("build_ready", gate.get("build_ready")),
        "fabrication_ready": quality.get("fabrication_ready", gate.get("fabrication_ready")),
        "copper_tier": copper_tier,
        "fab_recommendation": fab_recommendation,
        "electrical_safety_pass": quality.get("electrical_safety_pass"),
        "circuit_readiness": quality.get("circuit_readiness"),
        "build_id": quality.get("build_id"),
    }

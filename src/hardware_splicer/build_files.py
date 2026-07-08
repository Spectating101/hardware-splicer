"""Safe read/list of KiCad artifacts under a build directory (for UI preview)."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Dict, List

from .build_files_security import (
    assert_build_dir_allowed,
    assert_file_size,
    max_kicad_content_bytes,
)

KICAD_SUFFIXES = (".kicad_pcb", ".kicad_sch", ".kicad_pro")
ARTIFACT_SUFFIXES = (".json", ".csv", ".md", ".txt", ".zip", ".net", ".pdf", ".svg", ".png")
DOWNLOAD_SUFFIXES = KICAD_SUFFIXES + ARTIFACT_SUFFIXES

# Static artifacts (KiCad sch/pcb resolved dynamically per build).
ARTIFACT_CATALOG_STATIC = [
    {"relative": "build_compilation/circuit_json.json", "kind": "circuit_json", "label": "circuit-json export"},
    {"relative": "build_compilation/KICAD_DRC.json", "kind": "drc_report", "label": "KiCad DRC report"},
    {"relative": "build_compilation/DESIGN_QUALITY.json", "kind": "design_quality", "label": "Design quality"},
    {"relative": "build_compilation/BOM.csv", "kind": "bom", "label": "Compile BOM (CSV)"},
    {"relative": "build_compilation/BOM.json", "kind": "bom_json", "label": "Compile BOM (JSON)"},
    {"relative": "build_compilation/fab_package.zip", "kind": "fab_zip", "label": "Fab package zip"},
    {"relative": "PROJECT_PACKAGE.json", "kind": "project_package", "label": "PROJECT_PACKAGE"},
]

# Back-compat alias
ARTIFACT_CATALOG = ARTIFACT_CATALOG_STATIC


def resolve_build_dir(build_dir: str | Path) -> Path:
    root = Path(build_dir).expanduser().resolve()
    if not root.is_dir():
        raise ValueError(f"build_dir not found: {root}")
    assert_build_dir_allowed(root)
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
    assert_file_size(target, max_bytes=max_kicad_content_bytes())
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


def find_primary_pcb(build_dir: str | Path) -> Path | None:
    root = resolve_build_dir(build_dir)
    comp = root / "build_compilation"
    if not comp.is_dir():
        return None
    preferred = comp / "main_ctrl_build.kicad_pcb"
    if preferred.is_file():
        return preferred
    matches = sorted(comp.glob("*.kicad_pcb"))
    return matches[0] if matches else None


def _dynamic_kicad_artifact_specs(root: Path) -> List[Dict[str, str]]:
    specs: List[Dict[str, str]] = []
    pcb = find_primary_pcb(root)
    if pcb:
        rel = _relative_under_root(root, pcb)
        specs.append({"relative": rel, "kind": "kicad_pcb", "label": "KiCad PCB"})
        sch = pcb.with_suffix(".kicad_sch")
        if sch.is_file():
            specs.append(
                {
                    "relative": _relative_under_root(root, sch),
                    "kind": "kicad_sch",
                    "label": "KiCad schematic",
                }
            )
    return specs


def _artifact_catalog_for_build(root: Path) -> List[Dict[str, str]]:
    return _dynamic_kicad_artifact_specs(root) + list(ARTIFACT_CATALOG_STATIC)


def list_build_artifacts(build_dir: str | Path) -> List[Dict[str, Any]]:
    root = resolve_build_dir(build_dir)
    rows: List[Dict[str, Any]] = []
    for spec in _artifact_catalog_for_build(root):
        rel = spec["relative"]
        path = root / rel
        if not path.is_file():
            continue
        rows.append(
            {
                "relative": rel,
                "kind": spec["kind"],
                "label": spec["label"],
                "size_bytes": path.stat().st_size,
                "name": path.name,
            }
        )
    # Gerber tree (summary row when present)
    comp = root / "build_compilation"
    gerber_files = sorted(p for p in comp.glob("gerber/**/*") if p.is_file()) if comp.is_dir() else []
    if gerber_files:
        rows.append(
            {
                "relative": str(gerber_files[0].relative_to(root)),
                "kind": "gerber",
                "label": f"Gerber files ({len(gerber_files)})",
                "size_bytes": sum(p.stat().st_size for p in gerber_files),
                "name": "gerber/",
                "gerber_count": len(gerber_files),
            }
        )
    # Also surface any extra KiCad files not in catalog
    seen = {row["relative"] for row in rows}
    for row in list_kicad_files(root):
        if row["relative"] not in seen:
            rows.append(
                {
                    "relative": row["relative"],
                    "kind": row["kind"],
                    "label": row["name"],
                    "size_bytes": row["size_bytes"],
                    "name": row["name"],
                }
            )
            seen.add(row["relative"])
    export_dir = comp / "exports"
    if export_dir.is_dir():
        for path in sorted(export_dir.iterdir()):
            if not path.is_file() or path.suffix.lower() not in {".pdf", ".svg", ".png"}:
                continue
            rel = str(path.relative_to(root))
            if rel in seen:
                continue
            rows.append(
                {
                    "relative": rel,
                    "kind": "human_view",
                    "label": path.name,
                    "size_bytes": path.stat().st_size,
                    "name": path.name,
                }
            )
            seen.add(rel)
    return rows


def read_build_bom(build_dir: str | Path, *, enrich: bool = False) -> Dict[str, Any]:
    root = resolve_build_dir(build_dir)
    comp = root / "build_compilation"
    json_path = comp / "BOM.json"
    if json_path.is_file():
        bom = json.loads(json_path.read_text(encoding="utf-8"))
        if enrich:
            from .bom_generator import enrich_bom_with_jlcsearch

            bom = enrich_bom_with_jlcsearch(bom)
        lines = list(bom.get("lines") or [])
        return {
            "ok": True,
            "source": "BOM.json",
            "lines": lines,
            "jlc_enriched": bool(bom.get("jlc_enriched")),
            "line_count": len(lines),
        }
    csv_path = comp / "BOM.csv"
    if csv_path.is_file():
        with csv_path.open(encoding="utf-8", newline="") as handle:
            lines = list(csv.DictReader(handle))
        if enrich:
            from .bom_generator import enrich_bom_with_jlcsearch

            enriched = enrich_bom_with_jlcsearch({"lines": lines})
            lines = list(enriched.get("lines") or lines)
        jlc_enriched = any(row.get("jlc_lcsc") or row.get("jlc_mpn") for row in lines)
        return {
            "ok": True,
            "source": "BOM.csv",
            "lines": lines,
            "jlc_enriched": jlc_enriched or enrich,
            "line_count": len(lines),
        }
    raise ValueError("no BOM.csv or BOM.json under build_compilation/")


def read_artifact_file(build_dir: str | Path, relative: str) -> Dict[str, Any]:
    root = resolve_build_dir(build_dir)
    rel = relative.strip().lstrip("/")
    if not rel or ".." in Path(rel).parts:
        raise ValueError("invalid relative path")
    target = (root / rel).resolve()
    rel_check = _relative_under_root(root, target)
    if not target.is_file():
        raise ValueError(f"file not found: {rel_check}")
    assert_file_size(target)
    suffix = target.suffix.lower()
    if suffix not in DOWNLOAD_SUFFIXES:
        raise ValueError(f"artifact type not allowed: {suffix}")
    if suffix == ".json":
        try:
            parsed = json.loads(target.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            parsed = None
        return {
            "ok": True,
            "relative": rel_check,
            "name": target.name,
            "content_type": "application/json",
            "parsed": parsed,
            "content": target.read_text(encoding="utf-8"),
            "size_bytes": target.stat().st_size,
        }
    if suffix in {".zip"}:
        return {
            "ok": True,
            "relative": rel_check,
            "name": target.name,
            "content_type": "application/zip",
            "download_path": str(target),
            "size_bytes": target.stat().st_size,
        }
    text = target.read_text(encoding="utf-8", errors="replace")
    return {
        "ok": True,
        "relative": rel_check,
        "name": target.name,
        "content_type": "text/plain",
        "content": text,
        "size_bytes": target.stat().st_size,
    }


def export_circuit_json(build_dir: str | Path) -> Dict[str, Any]:
    root = resolve_build_dir(build_dir)
    path = root / "build_compilation" / "circuit_json.json"
    if path.is_file():
        docs = json.loads(path.read_text(encoding="utf-8"))
        return {"ok": True, "source": "file", "circuit_json": docs, "path": str(path)}
    # Fallback: netlist IR from build_graph if present
    graph_path = root / "build_compilation" / "build_graph.json"
    if not graph_path.is_file():
        raise ValueError("circuit_json.json not found and no build_graph.json to convert")
    from .integrations.circuit_json_adapter import netlist_to_circuit_json
    from .netlist.lower import build_graph_to_netlist

    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    netlist = build_graph_to_netlist(graph)
    docs = netlist_to_circuit_json(netlist, source_build_id=str(root.name))
    return {"ok": True, "source": "build_graph", "circuit_json": docs, "path": None}

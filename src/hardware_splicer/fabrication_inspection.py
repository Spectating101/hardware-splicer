from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Mapping, Tuple

from .testing_mode import testing_mode_enabled


SCHEMA_VERSION = "hardware_splicer.fabrication_inspection.v1"
GENERIC_HEADER_MARKERS = ("PinHeader_", "pinheader", "Generic_")
MIN_COPPER_GERBER_BYTES = 400
MIN_PCB_BYTES = 1500
# Breakout/header-only PCBs can pass most file-format checks but are not production layouts.
PROTOTYPE_BREAKOUT_SCORE_CAP = 55.0


def inspect_fabrication_package(
    *,
    build_compilation: Mapping[str, Any] | None = None,
    artifacts: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    """Inspect fab outputs on disk — not just whether paths exist."""
    build_compilation = dict(build_compilation or {})
    artifacts = dict(artifacts or {})
    design_quality = dict(build_compilation.get("design_quality") or {})

    pcb_path = _first_path(
        build_compilation.get("kicad_pcb_file"),
        artifacts.get("build_kicad_pcb"),
        artifacts.get("kicad_pcb"),
    )
    bom_path = _first_path(
        _bom_path(build_compilation, artifacts),
    )
    fab_zip = _first_path(
        design_quality.get("fab_package_zip"),
        artifacts.get("fab_package_zip"),
    )

    pcb_stats = _inspect_kicad_pcb(pcb_path)
    bom_stats = _inspect_bom(bom_path)
    gerber_stats = _inspect_fab_zip(fab_zip)
    claim_stats = _cross_check_claims(design_quality, pcb_stats, bom_stats, gerber_stats)

    checks: List[Dict[str, Any]] = []
    checks.extend(pcb_stats.get("checks") or [])
    checks.extend(bom_stats.get("checks") or [])
    checks.extend(gerber_stats.get("checks") or [])
    checks.extend(claim_stats.get("checks") or [])

    passed = sum(1 for row in checks if row.get("passed"))
    package_validity_score = round(100.0 * passed / max(len(checks), 1), 1)
    prototype_breakout_only = bool(pcb_stats.get("summary", {}).get("prototype_breakout_only"))
    production_score = package_validity_score
    if prototype_breakout_only and not testing_mode_enabled():
        production_score = min(production_score, PROTOTYPE_BREAKOUT_SCORE_CAP)
    blockers = [row["label"] for row in checks if not row.get("passed")]
    warnings = [row["label"] for row in checks if row.get("severity") == "warning"]

    return {
        "schema_version": SCHEMA_VERSION,
        "inspection_score": production_score,
        "package_validity_score": package_validity_score,
        "checks_passed": passed,
        "checks_total": len(checks),
        "checks": checks,
        "blockers": blockers,
        "warnings": warnings,
        "pcb": pcb_stats.get("summary") or {},
        "bom": bom_stats.get("summary") or {},
        "gerbers": gerber_stats.get("summary") or {},
        "prototype_breakout_only": prototype_breakout_only,
        "honest_fabrication_ready": passed == len(checks)
        and (not prototype_breakout_only or testing_mode_enabled()),
        "summary": _inspection_summary(production_score, package_validity_score, blockers, warnings, pcb_stats.get("summary") or {}),
    }


def _inspection_summary(
    production_score: float,
    package_validity_score: float,
    blockers: List[str],
    warnings: List[str],
    pcb: Mapping[str, Any],
) -> str:
    if pcb.get("prototype_breakout_only"):
        return (
            f"{production_score}% production fabrication — breakout/prototype PCB only "
            f"({pcb.get('generic_header_footprints', 0)}/{pcb.get('footprint_count', 0)} generic headers). "
            f"Package files are {package_validity_score}% valid on disk, but this is not a shippable integrated layout."
        )
    if blockers:
        return f"{production_score}% fabrication inspection — blockers: {blockers[0]}"
    if warnings:
        return f"{production_score}% fabrication inspection — warnings: {warnings[0]}"
    return f"{production_score}% fabrication inspection — PCB, BOM, and Gerbers look consistent on disk."


def _inspect_kicad_pcb(path: str | None) -> Dict[str, Any]:
    checks: List[Dict[str, Any]] = []
    summary: Dict[str, Any] = {"path": path}
    if not path or not Path(path).is_file():
        checks.append(_check("pcb_file_readable", False, "missing", "PCB file missing or unreadable."))
        return {"checks": checks, "summary": summary}

    text = Path(path).read_text(encoding="utf-8", errors="replace")
    size = Path(path).stat().st_size
    footprints = re.findall(r'\(footprint\s+"([^"]+)"', text)
    segments = len(re.findall(r"\(segment\b", text))
    vias = len(re.findall(r"\(via\b", text))
    nets = len(re.findall(r"\(net\s+\d+", text)) - 1
    has_edge = bool(re.search(r'\(gr_rect\b.*\(layer "Edge\.Cuts"', text, flags=re.DOTALL)) or "Edge.Cuts" in text
    has_fab_outlines = bool(re.search(r'\(fp_rect\b.*\(layer "F\.Fab"', text))

    generic_headers = sum(1 for fp in footprints if _is_generic_header_footprint(fp))
    prototype_only = bool(footprints) and generic_headers == len(footprints)

    summary.update(
        {
            "bytes": size,
            "footprint_count": len(footprints),
            "generic_header_footprints": generic_headers,
            "trace_segments": segments,
            "via_count": vias,
            "net_count": max(nets, 0),
            "has_edge_cuts": has_edge,
            "has_fab_outlines": has_fab_outlines,
            "prototype_breakout_only": prototype_only,
            "footprint_names": footprints[:12],
        }
    )

    checks.append(_check("pcb_file_readable", size >= MIN_PCB_BYTES, size, "PCB file is too small to be a real layout."))
    checks.append(_check("pcb_has_footprints", len(footprints) >= 1, len(footprints), "PCB has no footprints."))
    checks.append(_check("pcb_has_copper_activity", segments + vias >= 4, segments + vias, "PCB has almost no copper activity (segments+vias)."))
    checks.append(_check("pcb_has_edge_cuts", has_edge, has_edge, "PCB has no Edge.Cuts outline."))
    checks.append(
        _check(
            "pcb_not_empty_nets",
            max(nets, 0) >= 2,
            max(nets, 0),
            "PCB has fewer than two routed nets.",
            severity="warning" if max(nets, 0) >= 2 else "error",
        )
    )
    checks.append(
        _check(
            "pcb_not_prototype_headers_only",
            not prototype_only,
            f"{generic_headers}/{len(footprints)} generic headers",
            "PCB uses only generic pin-header footprints — breakout/prototype, not integrated production layout.",
            severity="warning",
        )
    )
    checks.append(
        _check(
            "pcb_has_module_body_outlines",
            has_fab_outlines,
            has_fab_outlines,
            "PCB footprints lack F.Fab body outlines (module envelope not drawn).",
            severity="warning",
        )
    )
    return {"checks": checks, "summary": summary}


def _inspect_bom(path: str | None) -> Dict[str, Any]:
    checks: List[Dict[str, Any]] = []
    summary: Dict[str, Any] = {"path": path}
    if not path or not Path(path).is_file():
        checks.append(_check("bom_readable", False, "missing", "BOM.json missing."))
        return {"checks": checks, "summary": summary}

    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        checks.append(_check("bom_readable", False, str(exc), "BOM.json is not valid JSON."))
        return {"checks": checks, "summary": summary}

    lines = list(payload.get("lines") or [])
    refs = [str(row.get("ref") or "").strip() for row in lines if isinstance(row, Mapping)]
    mpns = [str(row.get("mpn") or "").strip() for row in lines if isinstance(row, Mapping)]
    summary.update(
        {
            "line_count": len(lines),
            "refs": refs,
            "missing_mpn_count": sum(1 for mpn in mpns if not mpn),
        }
    )
    checks.append(_check("bom_has_lines", len(lines) >= 1, len(lines), "BOM has no purchase lines."))
    checks.append(_check("bom_has_refs", all(refs) and len(refs) == len(lines), len(refs), "BOM lines missing refs."))
    checks.append(
        _check(
            "bom_has_mpns",
            bool(mpns) and all(mpns),
            len([mpn for mpn in mpns if mpn]),
            "BOM lines missing manufacturer part numbers.",
            severity="warning" if mpns and not all(mpns) else "error",
        )
    )
    return {"checks": checks, "summary": summary}


def _inspect_fab_zip(path: str | None) -> Dict[str, Any]:
    checks: List[Dict[str, Any]] = []
    summary: Dict[str, Any] = {"path": path}
    if not path or not Path(path).is_file():
        checks.append(_check("fab_zip_readable", False, "missing", "fab_package.zip missing."))
        return {"checks": checks, "summary": summary}

    copper_files: List[str] = []
    edge_files: List[str] = []
    drill_files: List[str] = []
    tiny_files: List[str] = []
    try:
        with zipfile.ZipFile(path) as archive:
            for info in archive.infolist():
                if info.is_dir():
                    continue
                name = info.filename.lower()
                data = archive.read(info.filename)
                if len(data) < 32:
                    tiny_files.append(info.filename)
                if name.endswith((".gtl", ".gbl", ".gts", ".gbs")):
                    copper_files.append(info.filename)
                    if len(data) < MIN_COPPER_GERBER_BYTES:
                        tiny_files.append(info.filename)
                if "edge_cuts" in name or name.endswith(".gm1"):
                    edge_files.append(info.filename)
                if name.endswith(".drl") or name.endswith(".xln"):
                    drill_files.append(info.filename)
    except (OSError, zipfile.BadZipFile) as exc:
        checks.append(_check("fab_zip_readable", False, str(exc), "fab_package.zip is unreadable."))
        return {"checks": checks, "summary": summary}

    summary.update(
        {
            "copper_files": copper_files,
            "edge_files": edge_files,
            "drill_files": drill_files,
            "tiny_files": tiny_files,
        }
    )
    checks.append(_check("fab_zip_readable", True, path, ""))
    checks.append(_check("gerber_has_copper", bool(copper_files), len(copper_files), "Gerber package has no copper layers."))
    checks.append(_check("gerber_has_edge_cuts", bool(edge_files), len(edge_files), "Gerber package has no edge cuts."))
    checks.append(
        _check(
            "gerber_has_drill",
            bool(drill_files),
            len(drill_files),
            "Gerber package has no drill file.",
            severity="warning",
        )
    )
    checks.append(_check("gerber_files_non_trivial", not tiny_files, tiny_files[:3], "Gerber/copper files are suspiciously tiny."))
    return {"checks": checks, "summary": summary}


def _cross_check_claims(
    design_quality: Mapping[str, Any],
    pcb_stats: Mapping[str, Any],
    bom_stats: Mapping[str, Any],
    gerber_stats: Mapping[str, Any],
) -> Dict[str, Any]:
    checks: List[Dict[str, Any]] = []
    pcb = pcb_stats.get("summary") or {}
    outline = design_quality.get("board_outline") or {}

    claimed_fps = int(outline.get("footprint_count") or design_quality.get("module_count") or 0)
    actual_fps = int(pcb.get("footprint_count") or 0)
    if claimed_fps and actual_fps:
        checks.append(
            _check(
                "pcb_footprint_count_matches_claim",
                claimed_fps == actual_fps,
                f"claimed={claimed_fps} actual={actual_fps}",
                "Reported footprint count does not match PCB file.",
            )
        )

    claimed_modules = int(design_quality.get("module_count") or 0)
    bom_lines = int(bom_stats.get("summary", {}).get("line_count") or 0)
    if claimed_modules and bom_lines:
        checks.append(
            _check(
                "bom_line_count_matches_modules",
                claimed_modules == bom_lines,
                f"modules={claimed_modules} bom_lines={bom_lines}",
                "BOM line count does not match compiled module count.",
            )
        )

    if design_quality.get("drc_pass") is True and actual_fps == 0:
        checks.append(
            _check(
                "drc_claim_matches_pcb",
                False,
                "drc_pass=true but pcb empty",
                "Design quality claims DRC pass but PCB inspection found no footprints.",
            )
        )

    if design_quality.get("gerber_ready") is True:
        checks.append(
            _check(
                "gerber_ready_claim_matches_zip",
                bool((gerber_stats.get("summary") or {}).get("copper_files")),
                design_quality.get("gerber_ready"),
                "Design quality claims gerber_ready but copper gerbers were not found in fab zip.",
            )
        )

    return {"checks": checks}


def _is_generic_header_footprint(name: str) -> bool:
    lowered = str(name or "").lower()
    return any(marker.lower() in lowered for marker in GENERIC_HEADER_MARKERS)


def _check(
    check_id: str,
    passed: bool,
    observed: Any,
    message: str,
    *,
    severity: str = "error",
) -> Dict[str, Any]:
    return {
        "id": check_id,
        "label": message or check_id.replace("_", " "),
        "passed": bool(passed),
        "observed": observed,
        "severity": severity if not passed else "info",
    }


def _first_path(*candidates: Any) -> str | None:
    for candidate in candidates:
        if candidate and Path(str(candidate)).is_file():
            return str(Path(str(candidate)).resolve())
    return None


def _bom_path(build_compilation: Mapping[str, Any], artifacts: Mapping[str, Any]) -> str | None:
    out_dir = Path(str(build_compilation.get("out_dir") or artifacts.get("out_dir") or ""))
    for candidate in (
        out_dir / "build_compilation" / "BOM.json",
        Path(str(artifacts.get("bom") or "")),
    ):
        if candidate.is_file():
            return str(candidate.resolve())
    return None

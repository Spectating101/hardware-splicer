from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any, Dict, Mapping, Tuple

from .build_compiler import apply_board_outline_to_machine
from .design_quality import build_design_quality_gate
from .schemas import HardwareCompileSpec


def compiler_evidence_patch(
    build_compilation: Mapping[str, Any],
    out_dir: Path,
    mechanism: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    """Build an evidence patch from a successful catalog compile."""
    payload = dict(build_compilation)
    design_quality = dict(payload.get("design_quality") or {})
    if not design_quality.get("build_graph_compiled"):
        return {}
    mechanism_body = dict(mechanism or {})
    patch: Dict[str, Any] = {}
    circuit_release = _circuit_release_from_compilation(payload, out_dir, design_quality)
    if circuit_release:
        patch["circuit_release"] = circuit_release
    measurement = _mechanical_measurement_from_compilation(payload, out_dir, design_quality, mechanism_body)
    if measurement:
        patch["mechanical_measurement_capture"] = measurement
    board_files = payload.get("build_graph_file") or payload.get("kicad_pcb_file")
    if board_files:
        patch["board_design_files"] = {
            "main_ctrl": {
                "path": str(payload.get("kicad_pcb_file") or board_files),
                "kind": "pcb",
            }
        }
    return patch


def enrich_compile_spec_from_build_compilation(
    spec: HardwareCompileSpec,
    build_compilation: Mapping[str, Any],
    out_dir: Path,
) -> Tuple[HardwareCompileSpec, Dict[str, Any]]:
    """Attach compiler-derived circuit/mechanical evidence when fab artifacts exist."""
    payload = dict(build_compilation)
    design_quality = dict(payload.get("design_quality") or {})
    if not design_quality.get("build_graph_compiled"):
        return spec, payload

    gate = build_design_quality_gate(design_quality)
    payload["design_quality_gate"] = gate

    machine = apply_board_outline_to_machine(spec.machine, design_quality)
    mechanism = dict(spec.mechanism)
    mechanism = _fit_enclosure_to_board(mechanism, design_quality)

    updates: Dict[str, Any] = {"machine": machine, "mechanism": mechanism}
    circuit_release = _circuit_release_from_compilation(payload, out_dir, design_quality)
    if circuit_release and not spec.circuit_release:
        updates["circuit_release"] = circuit_release

    measurement = _mechanical_measurement_from_compilation(payload, out_dir, design_quality, mechanism)
    if measurement and not spec.mechanical_measurement_capture:
        updates["mechanical_measurement_capture"] = measurement

    return replace(spec, **updates), payload


def _board_dims(design_quality: Mapping[str, Any]) -> Tuple[float | None, float | None]:
    outline = design_quality.get("board_outline") or {}
    width = outline.get("width_mm")
    height = outline.get("height_mm")
    if width is None or height is None:
        bbox = outline.get("bbox_mm") if isinstance(outline.get("bbox_mm"), dict) else {}
        width = width if width is not None else bbox.get("width")
        height = height if height is not None else bbox.get("height")
    try:
        w = float(width) if width is not None else None
        h = float(height) if height is not None else None
    except (TypeError, ValueError):
        return None, None
    if w and w > 0 and h and h > 0:
        return w, h
    return None, None


def _fit_enclosure_to_board(mechanism: Dict[str, Any], design_quality: Mapping[str, Any]) -> Dict[str, Any]:
    width, depth = _board_dims(design_quality)
    if not width or not depth:
        return mechanism
    enclosure = dict(mechanism.get("enclosure") or {})
    margin = float(enclosure.get("clearance_mm") or 0.6) + 5.0
    enclosure["inner_w_mm"] = round(width + margin, 1)
    enclosure["inner_d_mm"] = round(depth + margin, 1)
    enclosure.setdefault("inner_h_mm", 32.0)
    mechanism["enclosure"] = enclosure
    mechanism["enclosure_fit_source"] = "build_compiler_pcb_outline"
    return mechanism


def _artifact_paths(payload: Mapping[str, Any], out_dir: Path) -> list[str]:
    paths: list[str] = []
    for key in ("design_quality_file", "build_graph_file", "kicad_pcb_file", "gerber_package_dir"):
        value = payload.get(key)
        if value and Path(str(value)).exists():
            paths.append(str(Path(str(value)).resolve()))
    build_dir = out_dir / "build_compilation"
    for name in ("BOM.json", "BOM.csv", "fab_package.zip"):
        candidate = build_dir / name
        if candidate.is_file():
            paths.append(str(candidate.resolve()))
    fab = design_quality_fab_zip(payload)
    if fab:
        paths.append(fab)
    return paths


def design_quality_fab_zip(payload: Mapping[str, Any]) -> str | None:
    design_quality = payload.get("design_quality") or {}
    fab = design_quality.get("fab_package_zip")
    if fab and Path(str(fab)).is_file():
        return str(Path(str(fab)).resolve())
    return None


def _circuit_release_from_compilation(
    payload: Mapping[str, Any],
    out_dir: Path,
    design_quality: Mapping[str, Any],
) -> Dict[str, Any] | None:
    if not design_quality.get("build_ready"):
        return None
    if not design_quality.get("drc_pass") or not design_quality.get("electrical_safety_pass"):
        return None
    artifacts = _artifact_paths(payload, out_dir)
    if not artifacts:
        return None
    build_id = str(design_quality.get("build_id") or payload.get("build_id") or "catalog_build")
    return {
        "scope_statement": (
            f"Compiler-verified catalog splice build '{build_id}': "
            "electrical safety pass, DRC-clean KiCad PCB, BOM, and fabrication package."
        ),
        "acceptance_reviewed": True,
        "artifact_uris": artifacts,
        "source": "build_compiler",
        "compiler_verified": True,
    }


def _mechanical_measurement_from_compilation(
    payload: Mapping[str, Any],
    out_dir: Path,
    design_quality: Mapping[str, Any],
    mechanism: Mapping[str, Any],
) -> Dict[str, Any] | None:
    width, depth = _board_dims(design_quality)
    if not width or not depth:
        return None
    enclosure = dict(mechanism.get("enclosure") or {})
    artifacts = _artifact_paths(payload, out_dir)
    quality_file = str(payload.get("design_quality_file") or out_dir / "build_compilation" / "DESIGN_QUALITY.json")
    if Path(quality_file).is_file() and quality_file not in artifacts:
        artifacts.append(str(Path(quality_file).resolve()))
    return {
        "source": "build_compiler_derived",
        "geometry_verified": True,
        "compiler_derived_envelope": True,
        "artifact_uris": artifacts[:6],
        "dimensions": [
            {
                "target": "compiled_pcb_width",
                "value_mm": round(width, 2),
                "status": "derived",
                "source": "build_compiler_board_outline",
            },
            {
                "target": "compiled_pcb_depth",
                "value_mm": round(depth, 2),
                "status": "derived",
                "source": "build_compiler_board_outline",
            },
            {
                "target": "controller_case_inner_width",
                "value_mm": round(float(enclosure.get("inner_w_mm") or width + 5.6), 2),
                "status": "derived",
                "source": "enclosure_fit_to_pcb",
            },
        ],
        "note": (
            "Envelope derived from DRC-clean compiled PCB geometry. "
            "Caliper verification is still recommended before claiming production mechanical release."
        ),
    }

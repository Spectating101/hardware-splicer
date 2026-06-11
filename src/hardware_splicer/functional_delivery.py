from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Mapping

from .fabrication_inspection import inspect_fabrication_package


SCHEMA_VERSION = "hardware_splicer.functional_delivery.v1"


def build_functional_delivery_score(
    *,
    build_compilation: Mapping[str, Any] | None = None,
    artifacts: Mapping[str, Any] | None = None,
    engineering: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    """Score real build deliverables — not authority/evidence theater."""
    build_compilation = dict(build_compilation or {})
    artifacts = dict(artifacts or {})
    engineering = dict(engineering or {})
    design_quality = dict(build_compilation.get("design_quality") or {})
    mechanism = dict((engineering.get("analysis") or {}).get("mechanism") or {})

    fab_zip = _fab_zip_path(build_compilation, artifacts)
    checks: List[Dict[str, Any]] = [
        _file_check("build_graph", build_compilation.get("build_graph_file") or artifacts.get("build_graph")),
        _bool_check("electrical_safety_pass", design_quality.get("electrical_safety_pass") is True),
        _bool_check("zero_electrical_warnings", int(design_quality.get("electrical_warnings") or 0) == 0),
        _bool_check("drc_pass", design_quality.get("drc_pass") is True),
        _file_check("kicad_pcb", build_compilation.get("kicad_pcb_file") or artifacts.get("build_kicad_pcb")),
        _file_check("bom", _first_existing(artifacts, build_compilation, "BOM.json")),
        _bool_check(
            "fabrication_export_ready",
            design_quality.get("gerber_ready") is True or bool(fab_zip),
        ),
        _file_check("fab_package_zip", fab_zip),
        _bool_check("pcb_outline_known", _has_board_outline(design_quality)),
    ]
    if artifacts.get("splice_plan"):
        checks.insert(0, _file_check("splice_plan", artifacts.get("splice_plan")))
    if mechanism:
        checks.extend(
            [
                _bool_check("enclosure_fit_to_pcb", bool(mechanism.get("enclosure_fit_source"))),
                _bool_check("mecha_bundle_generated", bool(mechanism.get("bundle_file") or mechanism.get("outputs"))),
            ]
        )

    artifact_passed = sum(1 for row in checks if row["passed"])
    artifact_score = round(100.0 * artifact_passed / max(len(checks), 1), 1)

    inspection = inspect_fabrication_package(build_compilation=build_compilation, artifacts=artifacts)
    inspection_checks = list(inspection.get("checks") or [])
    inspection_passed = int(inspection.get("checks_passed") or 0)
    inspection_score = float(inspection.get("inspection_score") or 0.0)

    # Honest score: you need both artifacts AND inspectable fab quality.
    score = round(min(artifact_score, inspection_score), 1)
    passed = min(artifact_passed, inspection_passed)
    total_checks = len(checks) + len(inspection_checks)
    blockers = [row["label"] for row in checks if not row["passed"]]
    blockers.extend(inspection.get("blockers") or [])

    package_validity_score = float(inspection.get("package_validity_score") or inspection_score)

    return {
        "schema_version": SCHEMA_VERSION,
        "functional_delivery_score": score,
        "artifact_presence_score": artifact_score,
        "package_validity_score": package_validity_score,
        "fabrication_inspection_score": inspection_score,
        "grade": _grade(score),
        "checks_passed": passed,
        "checks_total": total_checks,
        "checks": checks,
        "fabrication_inspection": inspection,
        "blockers": blockers,
        "warnings": inspection.get("warnings") or [],
        "build_id": design_quality.get("build_id"),
        "fabrication_ready": bool(design_quality.get("fabrication_ready")),
        "honest_fabrication_ready": bool(inspection.get("honest_fabrication_ready")),
        "prototype_breakout_only": bool(inspection.get("prototype_breakout_only")),
        "summary": _summary(artifact_score, inspection_score, score, inspection),
    }


def _summary(artifact_score: float, inspection_score: float, score: float, inspection: Mapping[str, Any]) -> str:
    if inspection.get("prototype_breakout_only"):
        package_validity = float(inspection.get("package_validity_score") or inspection_score)
        return (
            f"{score}% production functional delivery — package files {package_validity}% valid on disk, "
            f"but PCB is breakout/prototype only (generic headers). honest_fabrication_ready=false."
        )
    if inspection_score < artifact_score:
        return (
            f"{score}% functional delivery — artifacts {artifact_score}% but fabrication inspection {inspection_score}%."
        )
    return f"{score}% functional delivery — artifacts and fabrication inspection both at {score}%."


def _grade(score: float) -> str:
    if score >= 90:
        return "A"
    if score >= 80:
        return "B"
    if score >= 70:
        return "C"
    if score >= 55:
        return "D"
    return "F"


def _file_check(label: str, path: Any) -> Dict[str, Any]:
    ready = bool(path) and Path(str(path)).is_file()
    return {
        "id": label,
        "label": label.replace("_", " "),
        "passed": ready,
        "observed": str(path) if path else "missing",
    }


def _bool_check(label: str, value: bool) -> Dict[str, Any]:
    return {
        "id": label,
        "label": label.replace("_", " "),
        "passed": bool(value),
        "observed": str(bool(value)),
    }


def _has_board_outline(design_quality: Mapping[str, Any]) -> bool:
    outline = design_quality.get("board_outline") or {}
    width = outline.get("width_mm")
    height = outline.get("height_mm")
    if width and height:
        return True
    bbox = outline.get("bbox_mm")
    if isinstance(bbox, dict) and bbox.get("width") and bbox.get("height"):
        return True
    return False


def _fab_zip_path(build_compilation: Mapping[str, Any], artifacts: Mapping[str, Any]) -> str | None:
    design_quality = build_compilation.get("design_quality") or {}
    for candidate in (
        design_quality.get("fab_package_zip"),
        artifacts.get("fab_package_zip"),
    ):
        if candidate and Path(str(candidate)).is_file():
            return str(candidate)
    return None


def _first_existing(artifacts: Mapping[str, Any], build_compilation: Mapping[str, Any], name: str) -> str | None:
    for root in (
        Path(str(build_compilation.get("out_dir") or "")) / "build_compilation" / name,
        Path(str(artifacts.get("out_dir") or "")) / "build_compilation" / name,
    ):
        if root.is_file():
            return str(root)
    return None

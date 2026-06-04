from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Tuple


SCHEMA_VERSION = "hardware_splicer.mechanical_authority.v1"

STAGE_ORDER = [
    "mechanical_candidate",
    "reference_geometry",
    "measured_geometry",
    "fit_load_simulation",
    "controlled_bench_fit",
    "production_mechanical_release",
]

STAGE_LABELS = {
    "mechanical_candidate": "Mechanical candidate",
    "reference_geometry": "Reference CAD geometry",
    "measured_geometry": "Measured geometry",
    "fit_load_simulation": "Fit/load simulation",
    "controlled_bench_fit": "Controlled bench fit",
    "production_mechanical_release": "Production mechanical release",
}

STAGE_SCORES = {
    "mechanical_candidate": 0.16,
    "reference_geometry": 0.34,
    "measured_geometry": 0.54,
    "fit_load_simulation": 0.74,
    "controlled_bench_fit": 0.90,
    "production_mechanical_release": 1.00,
}

MECHANISM_KEYS = [
    "enclosure",
    "bracket",
    "servo_mount",
    "linear_axis",
    "leadscrew_axis",
    "rotary_joint",
    "belt_reduction",
    "drive_base",
    "gripper",
    "pan_tilt",
    "assembly",
]

PASS_STATUSES = {"pass", "passed", "ok", "verified", "accepted", "closed", "true"}
FAIL_STATUSES = {"fail", "failed", "block", "blocked", "error", "critical", "unsafe", "rejected"}


def build_mechanical_authority(payload: Mapping[str, Any] | Any, *, engineering: Mapping[str, Any] | None = None) -> Dict[str, Any]:
    """Build a claim authority ledger for mechanical splice/build/reuse work."""

    body = _to_dict(payload)
    engineering_body = _to_dict(engineering or {})
    mechanism_spec = _dict(body.get("mechanism"))
    analysis = _dict(engineering_body.get("analysis"))
    mechanism_analysis = _dict(analysis.get("mechanism"))
    mechanism_bundle = _load_mecha_bundle(mechanism_analysis)

    evidence_counts = _evidence_counts(body, mechanism_spec, mechanism_analysis, mechanism_bundle)
    dfm_rows = _rows_from(mechanism_analysis, mechanism_bundle, "dfm")
    simulation_rows = _rows_from(mechanism_analysis, mechanism_bundle, "simulation")
    safety_rows = _rows_from(mechanism_analysis, mechanism_bundle, "safety")
    outputs = _string_list(mechanism_bundle.get("outputs")) or _string_list(mechanism_analysis.get("outputs"))
    if not outputs and mechanism_bundle:
        outputs = [
            str(row.get("name") or row.get("file") or "").strip()
            for row in _list_dicts(mechanism_bundle.get("parts"))
            if str(row.get("file") or row.get("name") or "").strip()
        ]

    measurement_capture = _first_dict(
        body.get("mechanical_measurement_capture"),
        body.get("measured_geometry_capture"),
        body.get("mechanical_measurements"),
    )
    bench_capture = _first_dict(
        body.get("mechanical_bench_capture"),
        body.get("bench_fit_capture"),
        body.get("controlled_bench_fit"),
    )
    release = _first_dict(
        body.get("mechanical_release"),
        body.get("production_mechanical_release"),
        body.get("production_release"),
    )

    blockers = {
        "dfm": _blocking_rows(dfm_rows),
        "simulation": _blocking_rows(simulation_rows),
        "safety": _blocking_rows(safety_rows),
    }
    measured = _measurement_status(measurement_capture)
    bench = _bench_status(bench_capture)

    stages = _stages(
        candidate_available=evidence_counts["candidate_sources"] > 0,
        reference_available=bool(outputs) and not blockers["dfm"],
        measured=measured,
        simulation_rows=simulation_rows,
        blockers=blockers,
        bench=bench,
        release=release,
    )
    current_level = _current_level(stages)
    score = STAGE_SCORES.get(current_level, 0.0) if current_level else 0.0
    production_authorized = current_level == "production_mechanical_release"

    return {
        "schema_version": SCHEMA_VERSION,
        "current_authority_level": current_level or "no_mechanical_authority",
        "authority_score": round(score, 2),
        "production_authorized": production_authorized,
        "release_decision": "authorized_scoped_mechanical_release" if production_authorized else "evidence_required_before_release",
        "next_action_id": _next_action_id(stages),
        "stages": stages,
        "can": _capabilities(stages),
        "evidence_counts": evidence_counts,
        "measurement_capture": measured,
        "bench_capture": bench,
        "risk_summary": {
            "dfm_blockers": len(blockers["dfm"]),
            "simulation_blockers": len(blockers["simulation"]),
            "safety_blockers": len(blockers["safety"]),
            "dfm_findings": len(dfm_rows),
            "simulation_findings": len(simulation_rows),
            "safety_findings": len(safety_rows),
        },
        "claim_boundary": _claim_boundary(current_level),
        "release_artifacts_required": [
            "MECH_CHECK.md",
            "SIM_RESULTS.json",
            "RISK_REGISTER.md",
            "BUILD_RECIPE.md",
            "measured_geometry_log",
            "controlled_fit_load_outcome",
            "production_mechanical_release_manifest",
        ],
        "scope_limits": _scope_limits(mechanism_spec, release),
    }


def _stages(
    *,
    candidate_available: bool,
    reference_available: bool,
    measured: Dict[str, Any],
    simulation_rows: List[Dict[str, Any]],
    blockers: Dict[str, List[Dict[str, Any]]],
    bench: Dict[str, Any],
    release: Dict[str, Any],
) -> List[Dict[str, Any]]:
    stages: List[Dict[str, Any]] = []

    _append_stage(
        stages,
        "mechanical_candidate",
        candidate_available,
        [] if candidate_available else ["Provide mechanism spec, part observations, or mechanical evidence."],
        "Generate reference CAD geometry and DFM evidence.",
    )

    reference_blockers = []
    if not reference_available:
        reference_blockers.append("Generate CAD/reference geometry with no block-level DFM finding.")
    reference_blockers.extend(_messages(blockers["dfm"]))
    _append_stage(
        stages,
        "reference_geometry",
        candidate_available and reference_available,
        reference_blockers,
        "Capture real dimensions, tolerances, material/process facts, and interface measurements.",
    )

    _append_stage(
        stages,
        "measured_geometry",
        _stage_passed(stages, "reference_geometry") and bool(measured["geometry_verified"]),
        measured["blockers"],
        "Run fit/load/motion simulation against the measured envelope.",
    )

    sim_blockers = []
    if not simulation_rows:
        sim_blockers.append("Run mechanical simulation and record fit/load findings.")
    sim_blockers.extend(_messages(blockers["simulation"]))
    sim_blockers.extend(_messages(blockers["safety"]))
    _append_stage(
        stages,
        "fit_load_simulation",
        _stage_passed(stages, "measured_geometry") and bool(simulation_rows) and not blockers["simulation"] and not blockers["safety"],
        sim_blockers,
        "Run controlled bench fit/load/motion tests with artifacts.",
    )

    _append_stage(
        stages,
        "controlled_bench_fit",
        _stage_passed(stages, "fit_load_simulation") and bool(bench["bench_verified"]),
        bench["blockers"],
        "Review release scope and attach production mechanical release artifacts.",
    )

    release_blockers = _release_blockers(release)
    _append_stage(
        stages,
        "production_mechanical_release",
        _stage_passed(stages, "controlled_bench_fit") and not release_blockers,
        release_blockers,
        "No remaining action for this scoped release.",
    )

    return stages


def _append_stage(stages: List[Dict[str, Any]], stage_id: str, passed: bool, blockers: List[str], next_unlock: str) -> None:
    stages.append(
        {
            "stage_id": stage_id,
            "label": STAGE_LABELS[stage_id],
            "status": "pass" if passed else "open",
            "score_if_current": STAGE_SCORES[stage_id],
            "blockers": blockers[:12] if not passed else [],
            "next_unlock": next_unlock,
        }
    )


def _capabilities(stages: List[Dict[str, Any]]) -> Dict[str, bool]:
    return {
        "generate_candidate_cad": _stage_passed(stages, "mechanical_candidate"),
        "print_reference_prototype": _stage_passed(stages, "reference_geometry"),
        "use_measured_interfaces": _stage_passed(stages, "measured_geometry"),
        "run_controlled_fit_load_bench": _stage_passed(stages, "fit_load_simulation"),
        "use_scoped_mechanical_splice": _stage_passed(stages, "controlled_bench_fit"),
        "claim_production_mechanical_release": _stage_passed(stages, "production_mechanical_release"),
    }


def _evidence_counts(
    body: Dict[str, Any],
    mechanism_spec: Dict[str, Any],
    mechanism_analysis: Dict[str, Any],
    mechanism_bundle: Dict[str, Any],
) -> Dict[str, int]:
    evidence = _first_dict(body.get("mechanical_evidence"), mechanism_spec.get("mechanical_evidence"))
    observations = _list_dicts(evidence.get("observations")) + _list_dicts(evidence.get("photo_observations"))
    observed_parts = _list_dicts(evidence.get("parts")) + _list_dicts(evidence.get("assemblies"))
    interfaces = _list_dicts(evidence.get("interfaces")) + _list_dicts(evidence.get("mounts")) + _list_dicts(evidence.get("joints"))
    mechanism_specs = [key for key in MECHANISM_KEYS if isinstance(mechanism_spec.get(key), dict)]
    outputs = _string_list(mechanism_bundle.get("outputs")) or _string_list(mechanism_analysis.get("outputs"))
    return {
        "mechanism_specs": len(mechanism_specs),
        "observations": len(observations),
        "observed_parts": len(observed_parts),
        "interfaces": len(interfaces),
        "generated_outputs": len(outputs),
        "candidate_sources": len(mechanism_specs) + len(observations) + len(observed_parts) + len(interfaces) + int(bool(mechanism_analysis)),
    }


def _measurement_status(capture: Dict[str, Any]) -> Dict[str, Any]:
    rows = []
    for key in ["measurements", "dimensions", "clearances", "interfaces", "materials", "tolerances"]:
        rows.extend(_list_dicts(capture.get(key)))
    verified_rows = [row for row in rows if _row_passed(row) or _has_value(row)]
    artifacts = _artifact_count(capture)
    explicit = bool(capture.get("geometry_verified") is True or capture.get("measured_geometry_verified") is True)

    blockers: List[str] = []
    if not capture:
        blockers.append("Submit mechanical_measurement_capture with real dimensions, clearances, materials, and interfaces.")
    if len(verified_rows) < 3 and not explicit:
        blockers.append("Capture at least three trusted geometry/interface/material measurements.")
    if artifacts < 1 and not explicit:
        blockers.append("Attach at least one measurement artifact URI or log reference.")

    return {
        "available": bool(capture),
        "trusted_measurement_count": len(verified_rows),
        "artifact_count": artifacts,
        "geometry_verified": bool(explicit or (len(verified_rows) >= 3 and artifacts >= 1)),
        "blockers": blockers,
    }


def _bench_status(capture: Dict[str, Any]) -> Dict[str, Any]:
    rows = []
    for key in ["tests", "fit_checks", "load_tests", "motion_tests", "thermal_tests", "cycle_tests"]:
        rows.extend(_list_dicts(capture.get(key)))
    passed_rows = [row for row in rows if _row_passed(row)]
    failed_rows = [row for row in rows if _row_failed(row)]
    artifacts = _artifact_count(capture)
    explicit = bool(capture.get("bench_verified") is True or capture.get("output_function_verified") is True)

    blockers: List[str] = []
    if not capture:
        blockers.append("Run controlled mechanical bench fit/load/motion tests.")
    if failed_rows:
        blockers.extend(_messages(failed_rows))
    if len(passed_rows) < 3 and not explicit:
        blockers.append("Record at least three passing fit, load, motion, cycle, or thermal bench checks.")
    if artifacts < 1 and not explicit:
        blockers.append("Attach controlled bench artifacts, photos, or logs.")

    return {
        "available": bool(capture),
        "passed_test_count": len(passed_rows),
        "failed_test_count": len(failed_rows),
        "artifact_count": artifacts,
        "bench_verified": bool(explicit or (len(passed_rows) >= 3 and artifacts >= 1 and not failed_rows)),
        "blockers": blockers,
    }


def _release_blockers(release: Dict[str, Any]) -> List[str]:
    blockers: List[str] = []
    if not release:
        return ["Attach mechanical_release with reviewed scope, artifact URIs, and acceptance decision."]
    if not str(release.get("scope_statement") or "").strip():
        blockers.append("Release needs a scope_statement limiting the claim.")
    if not bool(release.get("acceptance_reviewed")):
        blockers.append("Release acceptance must be reviewed.")
    if _artifact_count(release) < 1:
        blockers.append("Release needs artifact_uris or an equivalent release evidence reference.")
    return blockers


def _claim_boundary(level: str | None) -> str:
    if level == "production_mechanical_release":
        return "Scoped mechanical splice/build/reuse can be claimed within the reviewed release statement."
    if level == "controlled_bench_fit":
        return "Bench-verified internal reuse is available, but release packaging is not closed."
    if level == "fit_load_simulation":
        return "Simulation-supported prototype may enter controlled bench validation; no release claim yet."
    if level == "measured_geometry":
        return "Measured interfaces can drive CAD revisions and simulation; do not claim fit/load success yet."
    if level == "reference_geometry":
        return "Reference CAD can be prototyped cautiously; real dimensions and loads remain unproven."
    if level == "mechanical_candidate":
        return "Candidate mechanism only; geometry, materials, and load path are not authoritative."
    return "No mechanical claim authority is available."


def _scope_limits(mechanism_spec: Dict[str, Any], release: Dict[str, Any]) -> List[str]:
    limits: List[str] = []
    if str(release.get("scope_statement") or "").strip():
        limits.append(str(release["scope_statement"]).strip())
    active = [key for key in MECHANISM_KEYS if isinstance(mechanism_spec.get(key), dict)]
    if active:
        limits.append(f"Scope is limited to generated mechanism primitives: {', '.join(active)}.")
    limits.append("No human-load, vehicle, medical, pressure, or certified safety claim is implied.")
    return limits


def _current_level(stages: List[Dict[str, Any]]) -> str | None:
    current = None
    for stage in stages:
        if stage.get("status") == "pass":
            current = str(stage.get("stage_id") or "")
        else:
            break
    return current


def _next_action_id(stages: List[Dict[str, Any]]) -> str | None:
    for stage in stages:
        if stage.get("status") != "pass":
            return f"close_{stage.get('stage_id')}"
    return None


def _stage_passed(stages: List[Dict[str, Any]], stage_id: str) -> bool:
    return any(stage.get("stage_id") == stage_id and stage.get("status") == "pass" for stage in stages)


def _rows_from(mechanism_analysis: Dict[str, Any], mechanism_bundle: Dict[str, Any], key: str) -> List[Dict[str, Any]]:
    rows = _list_dicts(mechanism_analysis.get(key))
    if not rows:
        rows = _list_dicts(mechanism_bundle.get(key))
    return rows


def _blocking_rows(rows: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [row for row in rows if _severity(row) in {"block", "error", "critical"} or _row_failed(row)]


def _messages(rows: Iterable[Dict[str, Any]]) -> List[str]:
    out = []
    for row in rows:
        message = str(row.get("message") or row.get("risk") or row.get("detail") or row.get("target") or "").strip()
        if message:
            out.append(message)
    return out[:12]


def _artifact_count(capture: Dict[str, Any]) -> int:
    count = 0
    for key in ["artifact_uris", "artifacts", "evidence_uris", "logs", "photos"]:
        value = capture.get(key)
        if isinstance(value, list):
            count += len([item for item in value if item])
        elif isinstance(value, str) and value.strip():
            count += 1
    return count


def _row_passed(row: Dict[str, Any]) -> bool:
    status = str(row.get("status") or row.get("result") or row.get("decision") or "").strip().lower()
    if status in PASS_STATUSES:
        return True
    value = row.get("pass")
    return value is True


def _row_failed(row: Dict[str, Any]) -> bool:
    status = str(row.get("status") or row.get("result") or row.get("decision") or "").strip().lower()
    if status in FAIL_STATUSES:
        return True
    value = row.get("pass")
    return value is False


def _has_value(row: Dict[str, Any]) -> bool:
    for key in ["value", "value_mm", "measured_mm", "nominal_mm", "material", "clearance_mm", "tolerance_mm"]:
        value = row.get(key)
        if value not in (None, ""):
            return True
    return False


def _severity(row: Dict[str, Any]) -> str:
    return str(row.get("severity") or row.get("level") or "").strip().lower()


def _load_mecha_bundle(mechanism_analysis: Dict[str, Any]) -> Dict[str, Any]:
    bundle = _dict(mechanism_analysis.get("bundle"))
    if bundle:
        return bundle
    bundle_file = str(mechanism_analysis.get("bundle_file") or "").strip()
    if not bundle_file:
        return {}
    try:
        path = Path(bundle_file)
        if path.exists() and path.is_file() and path.stat().st_size <= 20 * 1024 * 1024:
            return _dict(json.loads(path.read_text(encoding="utf-8")))
    except Exception:
        return {}
    return {}


def _to_dict(value: Mapping[str, Any] | Any) -> Dict[str, Any]:
    if value is None:
        return {}
    if hasattr(value, "to_dict"):
        try:
            return _dict(value.to_dict())
        except Exception:
            return {}
    return _dict(value)


def _dict(value: Any) -> Dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _first_dict(*values: Any) -> Dict[str, Any]:
    for value in values:
        if isinstance(value, Mapping):
            return dict(value)
    return {}


def _list_dicts(value: Any) -> List[Dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, Mapping)]


def _string_list(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]

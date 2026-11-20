"""Revision-bound exchange between saved HS studies and Policy Lab.

The exporter observes the existing digital engine. It never executes a native
build or upgrades modeled results into measurements. Feedback validates a
proposal against the original evidence bytes and current saved revision; it
does not enqueue work, change the project, or authorize a physical operation.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import re
import subprocess
from typing import Any, Mapping

from . import digital_project as digital
from .digital_cases import DEFAULT_CASE, validate_case_id
from .project_store import RevisionConflict, validate_project_id

EVIDENCE_SCHEMA = "hardware_splicer.policy_evidence.v1"
REVIEW_SCHEMA = "policylab.hardware_policy_review.v1"
FEEDBACK_SCHEMA = "hardware_splicer.policy_feedback_proposal.v1"
AUDIT_SCOPE = (
    "Stored revision identity, declared result consistency, artifact hashes and ZIP "
    "membership only; no new native verification, measurement or physical test."
)
_HASH = re.compile(r"[0-9a-f]{64}\Z")
_RUN = re.compile(r"[0-9a-f]{32}\Z")
_MAX_JSON_BYTES = 8 * 1024 * 1024
_AUTHORITY_FLAGS = frozenset({
    "physical_authority_granted", "physical_work_requested", "physical_validation",
    "physical_validation_performed", "physical_fit_or_operation_proven",
    "fabrication_authorized", "firmware_authorized", "firmware_flash_authorized",
    "flash_authorized", "power_on_authorized", "motion_authorized",
    "flight_authorized", "operational_authorized", "release_authorized",
})
_EVIDENCE_FIELDS = frozenset({
    "schema", "project_id", "revision", "run_id", "case_id", "evidence_kind",
    "physical_authority_granted", "source_revision", "study", "package", "facts",
    "unmapped_numeric_fields", "integrity_audit", "audit_scope",
})

# These names are an explicit semantic mapping of the registered case outputs.
# An unfamiliar numeric field remains in the full study and is listed separately;
# its unit is never guessed from a trailing character or silently converted.
FACT_UNITS = {
    "payload_mass_g": "g", "max_mass_g": "g", "gust_scale": "1",
    "mass_g": "g", "mass_margin_g": "g",
    "tracking_rms_m": "m", "hover_error_m": "m", "gust_recovery_error_m": "m",
    "max_tracking_tilt_deg": "deg", "landing_speed_m_s": "m/s",
    "force_balance_rms_m_s2": "m/s^2", "position_velocity_rms_m_s": "m/s",
    "max_rpm": "rpm", "peak_current_a_est": "A", "consumed_mah_est": "mAh",
    "yaw_error_at_hold_deg": "deg", "rows": "count", "seconds": "s",
    "minimum_work_runtime_h": "h", "minimum_supply_margin_a": "A",
    "maximum_case_width_mm": "mm", "maximum_case_depth_mm": "mm",
    "maximum_case_height_mm": "mm", "printer_bed_x_mm": "mm", "printer_bed_y_mm": "mm",
    "pi_work_current_a": "A", "keyboard_current_a": "A",
    "work_runtime_lower_h": "h", "work_runtime_upper_h": "h",
    "stress_current_margin_a": "A", "minimum_supply_current_margin_a": "A",
    "planning_cost_usd": "USD", "solid_petg_mass_g": "g",
    "case_width_mm": "mm", "case_depth_mm": "mm", "case_height_mm": "mm",
    "work_system_power_w": "W", "ordinary_source_margin_a": "A",
    "high_keyboard_source_margin_a": "A", "drawing_width_mm": "mm",
    "drawing_height_mm": "mm", "paper_width_mm": "mm", "paper_height_mm": "mm",
    "pen_diameter_mm": "mm", "pen_lift_mm": "mm", "mount_pitch_mm": "mm",
    "mount_boss_front_mm": "mm", "mount_bolt_engagement_mm": "mm",
    "mount_interference_mm3": "mm^3", "adapter_volume_mm3": "mm^3",
    "cap_volume_mm3": "mm^3", "printed_mass_g_at_1_27_g_cm3": "g",
    "plate_to_adapter_airgap_mm": "mm", "pen_tip_to_clamp_mm": "mm",
    "beam_proxy_deflection_mm_at_2N": "mm", "clamp_open_gap_mm": "mm",
    "clamp_screw_tip_to_plate_mm": "mm", "parking_plate_volume_mm3": "mm^3",
    "parking_tnut_profile_interference_mm3": "mm^3", "parking_radiator_hole_pitch_mm": "mm",
    "draw_length_mm": "mm", "travel_length_mm": "mm", "ideal_feed_time_s": "s",
    "segment_count": "count", "stroke_count": "count", "pen_center_bed_margin_mm": "mm",
    "fixture_bed_clearance_mm": "mm", "controller_travel_margin_mm": "mm",
    "non_drawing_XY_without_lift": "count", "minimum_commanded_Z_mm": "mm",
    "maximum_commanded_Z_mm": "mm", "fitted_canvas_width_mm": "mm",
    "fitted_canvas_height_mm": "mm",
}


class PolicyLayerError(ValueError):
    """An exchange is malformed, unbound, or outside the digital evidence scope."""


def _finite_tree(value: Any) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if not isinstance(key, str):
                raise PolicyLayerError("JSON object keys must be strings.")
            _finite_tree(child)
    elif isinstance(value, list):
        for child in value:
            _finite_tree(child)
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            valid = math.isfinite(value)
        except OverflowError:
            valid = False
        if not valid:
            raise PolicyLayerError("All numeric evidence and feedback must be finite.")
    elif value is not None and not isinstance(value, (str, bool)):
        raise PolicyLayerError("Only JSON values are supported.")


def canonical_json_bytes(value: Any) -> bytes:
    """Deterministic transport bytes. Consumers hash these exact bytes, not a reserialization."""
    _finite_tree(value)
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise PolicyLayerError("Duplicate JSON key: " + key)
        result[key] = value
    return result


def read_json_bytes(raw: bytes) -> dict:
    if not isinstance(raw, bytes) or not 0 < len(raw) <= _MAX_JSON_BYTES:
        raise PolicyLayerError("Supply nonempty UTF-8 JSON bytes, maximum 8 MiB.")
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs)
        _finite_tree(value)
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise PolicyLayerError("Malformed JSON exchange.") from exc
    if not isinstance(value, dict):
        raise PolicyLayerError("The JSON exchange must be an object.")
    return value


def _no_physical_authority(value: Any) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if key in _AUTHORITY_FLAGS and child is not False:
                raise PolicyLayerError("Digital exchange cannot assert " + key + ".")
            _no_physical_authority(child)
    elif isinstance(value, list):
        for child in value:
            _no_physical_authority(child)


def numeric_facts(study: Mapping[str, Any]) -> tuple[list[dict], list[str]]:
    summary = study["summary"]
    facts, unmapped = [], []
    groups = [("metric", summary.get("metrics", {}), "/study/summary/metrics", "modeled"),
              ("requirement", summary.get("requirements", {}), "/study/summary/requirements", "design_requirement")]
    # The legacy drone stores mass at summary level, not inside metrics.
    groups.append(("metric", {k: summary[k] for k in ("mass_g", "mass_margin_g") if k in summary},
                   "/study/summary", "modeled"))
    for prefix, values, pointer, basis in groups:
        if not isinstance(values, dict):
            raise PolicyLayerError("Study metrics and requirements must be objects.")
        for name, value in sorted(values.items()):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                continue
            if name not in FACT_UNITS:
                unmapped.append(pointer + "/" + name)
                continue
            facts.append({"id": prefix + "." + name, "value": value, "unit": FACT_UNITS[name],
                          "source_path": pointer + "/" + name, "basis": basis})
    if len({row["id"] for row in facts}) != len(facts):
        raise PolicyLayerError("The study has ambiguous numeric fact identities.")
    return sorted(facts, key=lambda row: row["id"]), sorted(unmapped)


def _exporter_source() -> dict:
    root = Path(__file__).resolve().parents[2]
    commit, dirty = None, None
    try:
        commit_run = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"],
                                    capture_output=True, text=True, timeout=3, check=True)
        state_run = subprocess.run(["git", "-C", str(root), "status", "--porcelain"],
                                   capture_output=True, text=True, timeout=3, check=True)
        commit, dirty = commit_run.stdout.strip(), bool(state_run.stdout)
    except (OSError, subprocess.SubprocessError):
        pass
    return {"repository_commit": commit, "working_tree_dirty": dirty,
            "exporter_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "meaning": "Exporter checkout only; original design inputs are study.summary.source_sha256."}


def validate_policy_evidence(value: Mapping[str, Any]) -> dict:
    """Validate the transport, numeric projections and declared audit boundary.

    This does not establish remote custody; feedback additionally reopens the
    actual project through DigitalStudyEngine before accepting a proposal.
    """
    if not isinstance(value, dict) or set(value) != _EVIDENCE_FIELDS:
        raise PolicyLayerError("Unexpected policy evidence fields.")
    _finite_tree(value)
    _no_physical_authority(value)
    if (value["schema"] != EVIDENCE_SCHEMA or value["evidence_kind"] != "digital_design"
            or value["physical_authority_granted"] is not False or value["audit_scope"] != AUDIT_SCOPE):
        raise PolicyLayerError("Unsupported evidence schema or audit scope.")
    validate_project_id(value["project_id"])
    validate_case_id(value["case_id"])
    revision = value["revision"]
    if type(revision) is not int or revision < 1 or not isinstance(value["run_id"], str) or not _RUN.fullmatch(value["run_id"]):
        raise PolicyLayerError("Invalid project revision or run identity.")
    study = value["study"]
    if (not isinstance(study, dict) or type(study.get("revision")) is not int
            or study["revision"] != revision or study.get("run_id") != value["run_id"]):
        raise PolicyLayerError("Study identity differs from the evidence envelope.")
    summary = study.get("summary")
    if (not isinstance(summary, dict) or summary.get("case_id", DEFAULT_CASE) != value["case_id"]
            or summary.get("artifact_integrity") is not True or type(summary.get("requirements_met")) is not bool):
        raise PolicyLayerError("Invalid study summary or evidence identity.")
    manifest = study.get("artifact_manifest")
    if not isinstance(manifest, dict) or "STUDY.zip" not in manifest:
        raise PolicyLayerError("The complete study artifact manifest is required.")
    for name, record in manifest.items():
        path = PurePosixPath(name)
        if (not name or "\\" in name or path.is_absolute() or ".." in path.parts
                or path.as_posix() != name or not isinstance(record, dict)
                or set(record) != {"sha256", "bytes"}
                or not isinstance(record["sha256"], str) or not _HASH.fullmatch(record["sha256"])
                or type(record["bytes"]) is not int or record["bytes"] < 0):
            raise PolicyLayerError("Invalid study artifact manifest entry.")
    if value["package"] != {"path": "STUDY.zip", **manifest["STUDY.zip"]}:
        raise PolicyLayerError("Package identity differs from the artifact manifest.")
    expected_facts, unmapped = numeric_facts(study)
    if (not isinstance(value["facts"], list)
            or any(not isinstance(row, dict) or type(row.get("value")) not in (int, float) for row in value["facts"])
            or value["facts"] != expected_facts or value["unmapped_numeric_fields"] != unmapped):
        raise PolicyLayerError("Numeric facts differ from the source values or explicit units.")
    audit = value["integrity_audit"]
    if (not isinstance(audit, dict) or audit.get("schema") != "hardware_splicer.digital_audit.v1"
            or audit.get("ok") is not True or audit.get("artifact_integrity") is not True
            or audit.get("error") is not None or audit.get("project_id") != value["project_id"]
            or type(audit.get("revision")) is not int or audit["revision"] != revision
            or audit.get("run_id") != value["run_id"]
            or audit.get("requirements_met") is not summary["requirements_met"]
            or audit.get("physical_authority_granted") is not False
            or audit.get("native_verification") != {"requested": False, "performed": False}):
        raise PolicyLayerError("Integrity audit does not bind this exact digital study.")
    checks = audit.get("checks")
    required = {*manifest, "verified_claims_and_revision_identity", "zip_contents_match_verified_files"}
    if not isinstance(checks, dict) or not required <= set(checks) or any(v is not True for v in checks.values()):
        raise PolicyLayerError("The audit did not verify the complete artifact inventory.")
    source = value["source_revision"]
    if (not isinstance(source, dict) or set(source) != {"repository_commit", "working_tree_dirty", "exporter_sha256", "meaning"}
            or not isinstance(source["exporter_sha256"], str) or not _HASH.fullmatch(source["exporter_sha256"])
            or (source["repository_commit"] is not None
                and (not isinstance(source["repository_commit"], str) or not re.fullmatch(r"[0-9a-f]{40,64}", source["repository_commit"])))
            or (source["working_tree_dirty"] is not None and type(source["working_tree_dirty"]) is not bool)
            or not isinstance(source["meaning"], str)):
        raise PolicyLayerError("Invalid exporter source identity.")
    return deepcopy(value)


def export_policy_evidence(engine, project_id: str, revision: int | None = None) -> dict:
    validate_project_id(project_id)
    if revision is not None and (type(revision) is not int or revision < 1):
        raise PolicyLayerError("Revision must be a positive integer.")
    study = engine.study(project_id, revision)
    # Bind the audit to the observed revision even if the latest pointer advances.
    audit = engine.audit(project_id, study["revision"], native=False)
    if audit.get("ok") is not True:
        raise PolicyLayerError("Study integrity audit failed: " + str(audit.get("error")))
    facts, unmapped = numeric_facts(study)
    value = {"schema": EVIDENCE_SCHEMA, "project_id": project_id, "revision": study["revision"],
             "run_id": study["run_id"], "case_id": study["summary"].get("case_id", DEFAULT_CASE),
             "evidence_kind": "digital_design", "physical_authority_granted": False,
             "source_revision": _exporter_source(), "study": study,
             "package": {"path": "STUDY.zip", **study["artifact_manifest"]["STUDY.zip"]},
             "facts": facts, "unmapped_numeric_fields": unmapped,
             "integrity_audit": audit, "audit_scope": AUDIT_SCOPE}
    return validate_policy_evidence(value)


def validate_policy_feedback(engine, evidence_bytes: bytes, review_bytes: bytes) -> dict:
    """Return an exact-revision numeric proposal, without applying or executing it."""
    evidence = validate_policy_evidence(read_json_bytes(evidence_bytes))
    review = read_json_bytes(review_bytes)
    _no_physical_authority(review)
    if review.get("schema") != REVIEW_SCHEMA or review.get("physical_authority_granted") is not False:
        raise PolicyLayerError("Unsupported policy review or physical authority assertion.")
    binding = {"evidence_sha256": hashlib.sha256(evidence_bytes).hexdigest(),
               "project_id": evidence["project_id"], "revision": evidence["revision"],
               "run_id": evidence["run_id"]}
    if review.get("source_binding") != binding or type(review.get("source_binding", {}).get("revision")) is not int:
        raise PolicyLayerError("Policy review does not bind the exact evidence bytes and revision.")
    overrides = review.get("revision_requirements")
    if not isinstance(overrides, dict) or any(type(v) not in (int, float) for v in overrides.values()):
        raise PolicyLayerError("Policy revision_requirements must contain explicit finite numeric overrides.")
    project, revision = evidence["project_id"], evidence["revision"]
    if engine.projects.load(project)["revision"] != revision:
        raise RevisionConflict("The project changed after the policy assessment; export and assess the new revision.")
    actual = engine.study(project, revision)
    if canonical_json_bytes(actual) != canonical_json_bytes(evidence["study"]):
        raise PolicyLayerError("The supplied evidence differs from the verified stored study.")
    audit = engine.audit(project, revision, native=False)
    if audit.get("ok") is not True or audit.get("run_id") != evidence["run_id"]:
        raise PolicyLayerError("The underlying study no longer passes its integrity audit.")
    _, _, seal = digital.validated_run(engine.projects, project, revision)
    try:
        resolved = digital.resolve_requirements(seal, requirements=overrides)
    except (ValueError, TypeError, OverflowError) as exc:
        raise PolicyLayerError("Policy revision requirements are unsupported: " + str(exc)) from exc
    changes = {key: {"before": actual["summary"]["requirements"][key], "after": val}
               for key, val in resolved.items() if val != actual["summary"]["requirements"][key]}
    return {"schema": FEEDBACK_SCHEMA, "ok": True, "status": "validated_proposal",
            "source_binding": binding, "policy_review_sha256": hashlib.sha256(review_bytes).hexdigest(),
            "policy_review_verification": "supplied review; source binding and HS requirements validated, Policy Lab replay not performed here",
            "project_id": project, "base_revision": revision, "run_id": evidence["run_id"],
            "revision_requirements": deepcopy(overrides), "resolved_requirements": resolved,
            "requirement_changes": changes, "automatic_execution": False,
            "physical_authority_granted": False, "project_changed": False}

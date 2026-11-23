#!/usr/bin/env python3
"""Independent scope/integrity audit for a consolidated HS witness review.

Operates on already-written review.json, does not run instruments or change
source files. Distinguishes the nine stages really executed in PR #370 from
external experiments (#359 13 ohm and #369 G0-G4) not in this source tree.
Checking hashes is not proof of device/measurement authenticity.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

EXPECTED_STAGES = (
    ("all_unit_tests", 0, None),
    ("original_native_kicad_spice_hs_pl", 0, "native/verification.json"),
    ("legacy_7_synthetic_faults_and_physical_hold", 2, "audit/report.json"),
    ("12ohm_candidate_hs_pl_fixture_only", 2, "precision_12r/report.json"),
    ("vendor_sourcing_research_only", 2, "source_selection.json"),
    ("blank_g1_evidence_must_hold", 2, "g1_packet_review.json"),
    ("unselected_source_fuse_must_hold", 2, "protection.json"),
    ("scpi_dual_meter_mock_nonphysical", 2, "scpi_mock/reference-session.json"),
    ("g1_combined_authority_hold", 2, "g1_combined.json"),
)
OUTSIDE_REVIEW = (
    {"pr": 359, "subject": "13-ohm alternate load experiment", "stage_present": False},
    {"pr": 365, "subject": "raw-register coherence repair on separate branch", "stage_present": False},
    {"pr": 369, "subject": "independent G0-G4 research campaign", "stage_present": False},
)
MUST_FALSE = ("physical_ready", "fabrication_allowed", "energization_authorized",
              "metrological_agreement_proven", "product_certified")


def digest(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def validate(report_path: Path) -> dict:
    issues = []
    report_path = report_path.resolve()
    root = report_path.parent
    try:
        report = json.loads(report_path.read_text(encoding="utf8"))
    except (OSError, ValueError) as error:
        return {"status": "INVALID_OR_INCOMPLETE_HOLD", "issues": [str(error)],
                "physical_ready": False, "fabrication_allowed": False}
    if report.get("schema") != "hardware_splicer.consolidated_witness_software_review.v1":
        issues.append("Unexpected review report schema")
    if report.get("overall") != "SOFTWARE_INTEGRATION_VERIFIED_PHYSICAL_HOLD":
        issues.append("Full nine-stage software review not verified")
    for key in MUST_FALSE:
        if report.get(key) is not False:
            issues.append("Unjustified or absent physical release flag: "+key)
    repo = report.get("repo", {})
    deps = report.get("dependencies", {})
    if repo.get("working_tree_clean_before") is not True or repo.get("working_tree_clean_after") is not True:
        issues.append("Source checkout not recorded clean both before and after")
    if deps.get("policy_lab_commit") != deps.get("expected_policy_lab_commit"):
        issues.append("Policy Lab receiver commit not pinned")
    if deps.get("policy_lab_worktree_clean") is not True:
        issues.append("Policy Lab receiver checkout not recorded clean")
    steps = report.get("steps", [])
    if not isinstance(steps, list) or len(steps) != len(EXPECTED_STAGES):
        issues.append("Expected exactly nine executed stages, not unrelated named experiments")
        steps = steps if isinstance(steps, list) else []
    observed = [x.get("stage") for x in steps if isinstance(x, dict)]
    if observed != [x[0] for x in EXPECTED_STAGES]:
        issues.append("Stage identity/order changed; no comprehensive scope claim")
    if steps and isinstance(steps[0], dict):
        count = steps[0].get("completed_tests")
        if type(count) is not int or count < 120:
            issues.append("Expected at least 120 completed unit tests without skipping")
    artifacts = []
    for name, expected_exit, rel in EXPECTED_STAGES:
        entry = next((x for x in steps if isinstance(x, dict) and x.get("stage") == name), None)
        if not entry:
            issues.append("Missing recorded stage: "+name)
            continue
        if (entry.get("exit_code") != expected_exit or
            entry.get("expected_exit_code") != expected_exit or
            entry.get("passed_expected_behavior") is not True):
            issues.append("Unexpected executable result for "+name)
        if rel is None:
            continue
        expected = (root / rel).resolve()
        try:
            supplied = Path(entry["artifact_path"]).resolve()
            if not supplied.is_relative_to(root) or supplied != expected or not supplied.is_file():
                raise ValueError("Output path escaped or differed from expected")
            if entry.get("artifact_sha256") != digest(supplied):
                raise ValueError("Source-linked output SHA mismatch")
            evidence = json.loads(supplied.read_text())
            if any(evidence.get(f) is not False for f in ("fabrication_allowed",) if f in evidence):
                raise ValueError("Unexpected fabrication authorization in stage evidence")
            artifacts.append({"stage": name, "relative_path": rel,
                              "sha256": digest(supplied)})
        except (KeyError, OSError, ValueError) as exc:
            issues.append(name+": "+str(exc))
    return {
        "schema": "hardware_splicer.witness_consolidation_scope_check.v1",
        "status": "SCOPE_REPRODUCED_WITH_PHYSICAL_HOLD" if not issues else "INVALID_OR_INCOMPLETE_HOLD",
        "issues": issues,
        "executed_stage_count": len(observed),
        "test_count": (steps[0].get("completed_tests") if steps and isinstance(steps[0], dict) else None),
        "artifact_hashes_rechecked": artifacts,
        "explicitly_outside_this_review": list(OUTSIDE_REVIEW),
        "source_commit": repo.get("git_head"),
        "policy_lab_commit": deps.get("policy_lab_commit"),
        "physical_ready": False,
        "fabrication_allowed": False,
        "energization_authorized": False,
        "not_a_cryptographic_or_physical_approval": True,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--review", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args(argv)
    if args.out.exists():
        ap.error("Output already exists: previous evidence may not be overwritten")
    result = validate(args.review)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True)+"\n")
    print(json.dumps({"status": result["status"], "issues": len(result["issues"]),
                      "physical_ready": False, "out": str(args.out)}))
    return 2 if not result["issues"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

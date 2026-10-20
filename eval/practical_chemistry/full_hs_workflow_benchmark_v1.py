"""Isolated HS project->chemistry->human review->findings->packet integration check.

Four authored repair conditions, real project/review/findings implementation.
This proves information continuity/authority boundaries, NOT chemical efficacy,
operator time savings, physical success rates or end-user UI ergonomics.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from hardware_splicer.product_api import create_product_app
from hardware_splicer.project_store import ProjectStore
from hardware_splicer.review_packet import verify_review_packet


JOBS = [
    {
        "name": "pcb_unknown_adjacent_plastic",
        "material": "FR4",
        "domain": "electrical",
        "request": {
            "task": "clean_flux", "primary_material": "FR4",
            "material_identity": "claimed", "adjacent_materials": ["unknown"],
            "electrical_state": "off", "battery_status": "removed",
            "keepouts_confirmed": True,
        },
        "expected_decision": "research_or_replace",
    },
    {
        "name": "pp_case_joint_repair",
        "material": "PP",
        "domain": "mechanical",
        "request": {
            "task": "bond_joint", "primary_material": "PP",
            "material_identity": "verified",
            "electrical_state": "off", "battery_status": "none",
            "rework_required": False,
        },
        "expected_decision": "options_for_validation",
    },
    {
        "name": "contact_cleaning_zero_residue",
        "material": "gold_contact",
        "domain": "electrical",
        "request": {
            "task": "clean_contacts", "primary_material": "gold_contact",
            "material_identity": "verified", "electrical_state": "off",
            "battery_status": "removed", "residue_tolerance": "none",
        },
        "expected_decision": "options_for_validation",
    },
    {
        "name": "thermal_interface_gap_check",
        "material": "FR4",
        "domain": "electrical",
        "request": {
            "task": "manage_thermal_interface", "primary_material": "FR4",
            "material_identity": "verified", "electrical_state": "off",
            "battery_status": "removed",
            "electrical_function_required": "insulating",
            "contact_pressure_confirmed": True,
            "interface_geometry": {
                "thickness_mm": 1.0, "contact_area_mm2": 100,
                "heat_load_w": 15.0, "allowable_rise_c": 20,
            },
        },
        "expected_decision": "research_or_replace",
    },
]


def assert_ok(reply, status=200):
    if reply.status_code != status:
        raise ValueError(f"API returned {reply.status_code}, expected {status}: {reply.text[:400]}")
    return reply.json()


def run() -> dict:
    records = []
    with tempfile.TemporaryDirectory(prefix="hs-chem-workflow-eval-") as tmp:
        store = ProjectStore(Path(tmp))
        client = TestClient(create_product_app(store))
        for case in JOBS:
            pid = case["name"]
            snapshot = {
                "projectId": pid, "projectName": "Synthetic practical repair: " + pid,
                "currentStage": "design",
                "repair_intake": {
                    "device_hint": "synthetic hardware intake",
                    "symptoms": [pid],
                    "operator_notes": "Benchmark fixture, NOT a real repair case",
                },
                "machineProject": {
                    "project_id": pid, "name": pid,
                    "purpose": "Screen practical repair choices and retain review blockers",
                    "subsystems": [
                        {"subsystem_id": "device", "name": "Hardware", "domain": case["domain"]},
                    ],
                    "components": [
                        {"component_id": "target", "name": "Repair target",
                         "domain": case["domain"], "subsystem_id": "device",
                         "metadata": {"material_family": case["material"]}},
                    ],
                },
            }
            assert_ok(client.put(f"/v1/projects/{pid}/snapshot",
                                 json={"snapshot": snapshot, "expected_revision": 0}))
            before_packet = assert_ok(client.get(f"/v1/projects/{pid}/review-packet"))["packet"]
            baseline_findings = before_packet["findings"]["total"]
            proposed = assert_ok(client.post(
                f"/v1/projects/{pid}/chemistry/practical/preview",
                json={"expected_revision": 1, "component_id": "target",
                      "assessment": case["request"]},
            ))
            revision_unchanged = store.load(pid)["revision"] == 1
            proposed_decision = proposed["assessment"]["decision"]
            review = assert_ok(client.post(
                f"/v1/projects/{pid}/reviews",
                json=proposed["next_review_request"],), status=201)["review"]
            revision_pending = store.load(pid)["revision"] == 1
            assert review["status"] == "pending"
            accepted = assert_ok(client.post(
                f"/v1/projects/{pid}/reviews/{review['review_id']}/decision",
                json={"decision": "accepted", "actor": "synthetic-review-fixture",
                      "note": "Accepting record for inspection ONLY, not approving real repair"},
            ))["review"]
            assert accepted["status"] == "accepted"
            newest = store.load(pid)
            persisted = newest["snapshot"].get("practicalChemistryAssessments") or []
            after_packet = assert_ok(client.get(f"/v1/projects/{pid}/review-packet"))["packet"]
            chemistry_findings = [
                row for row in after_packet["findings"]["items"]
                if row["provenance"]["source_ref"] == proposed["assessment_id"]
            ]
            release_blocks = [
                row for row in chemistry_findings
                if row["category"] == "release_blocker"
            ]
            case_passed = all([
                proposed_decision == case["expected_decision"],
                revision_unchanged, revision_pending,
                baseline_findings == 0,
                newest["revision"] == 2,
                len(persisted) == 1,
                len(chemistry_findings) > 0,
                len(release_blocks) > 0,
                all(row["provenance"]["attested"] is False
                    for row in chemistry_findings),
                verify_review_packet(after_packet),
                not proposed["release_authorized"],
                not proposed["findings_enforce_global_release_gate"],
                not proposed["review_actor_identity_attested_by_chemistry"],
                not proposed["assessment"]["physical_action_authorized"],
            ])
            records.append({
                "case": pid, "pass": case_passed, "chemical_decision": proposed_decision,
                "preview_did_not_mutate_project": revision_unchanged,
                "pending_review_did_not_mutate_project": revision_pending,
                "accepted_review_created_revision": newest["revision"] == 2,
                "baseline_review_packet_findings": baseline_findings,
                "new_chemistry_findings": len(chemistry_findings),
                "new_release_blockers": len(release_blocks),
                "review_packet_integrity_verified": verify_review_packet(after_packet),
                "physical_authority_opened": False,
                "indexed_source_claims_still_unverified": True,
            })
    return {
        "schema_version": "hardware_splicer.practical_chemistry_full_workflow_benchmark.v1",
        "cases": len(records), "passed": sum(row["pass"] for row in records),
        "workflow": "ProjectStore snapshot -> scoped chemistry preview -> staged review -> synthetic acceptance -> persistent findings -> hash-bound review packet",
        "results": records,
        "benefits_directly_shown": [
            "Existing engineering project and component identity preserved",
            "Chemical uncertainty and blockers persist in the same HS revision history",
            "Pending preview/review does not change accepted project state",
            "After explicit acceptance, canonical findings and review-packet explain unresolved chemistry",
            "Existing MCP and project surfaces avoid a parallel chemistry workspace",
        ],
        "benefits_not_shown": [
            "No physical repair/chemical compatibility outcome",
            "No human operator UX or browser workflow test",
            "No measured time savings or repair economic uplift",
            "No autonomous source lookup or vendor TDS content-hash verification",
            "Synthetic human review acceptance is NOT independent engineering validation",
        ],
    }


if __name__ == "__main__":
    result = run()
    print(json.dumps(result, indent=2))
    if result["passed"] != result["cases"]:
        raise SystemExit(1)

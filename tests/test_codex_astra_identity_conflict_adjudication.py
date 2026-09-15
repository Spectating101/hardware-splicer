from __future__ import annotations

from copy import deepcopy

from hardware_splicer.cleanroom_primary_source_spi_flash_experiment import (
    build_primary_source_identity_conflict_case,
)
from hardware_splicer.codex_astra_identity_conflict_adjudication import (
    adjudicate_identity_conflict_snapshot,
)


def _identity_ref(snapshot: dict, source_id: str, claim_id: str) -> dict:
    source = next(
        row for row in snapshot["engineeringSources"] if row["source_id"] == source_id
    )
    claim = next(row for row in source["claims"] if row["claim_id"] == claim_id)
    return {
        **deepcopy(claim),
        "source_id": source_id,
        "content_hash": source["content_hash"],
        "revision": source["revision"],
    }


def _passing_snapshot() -> dict:
    snapshot = deepcopy(dict(build_primary_source_identity_conflict_case().snapshot))
    refs = [
        _identity_ref(
            snapshot, "src-current-dut-identity", "current-dut-identity-jw"
        ),
        _identity_ref(
            snapshot,
            "src-procurement-note-jv",
            "procurement-note-dut-identity-jv",
        ),
    ]
    snapshot["preFabricationPlan"] = {
        "assessment": {
            "summary": (
                "W25Q128JW and W25Q128JV records conflict; the physical DUT identity "
                "remains disputed."
            ),
            "blockers": [
                "The physical DUT identity is disputed pending marking verification."
            ],
            "physical_correctness": "UNPROVEN",
        },
        "requirements": [
            {
                "requirement_id": "identity",
                "statement": "Resolve the physical DUT identity.",
                "source_refs": refs,
            }
        ],
        "architecture_candidates": [],
        "decisions": [],
        "actions": [
            {
                "action_id": "inspect-marking",
                "action": "Capture and verify the physical DUT marking and package.",
                "source_refs": refs,
            }
        ],
        "fabrication_ready": False,
        "power_on_ready": False,
        "physical_authority_granted": False,
        "physical_correctness": "UNPROVEN",
    }
    return snapshot


def test_identity_conflict_adjudication_passes_bounded_resolution() -> None:
    report = adjudicate_identity_conflict_snapshot(_passing_snapshot())

    assert report["status"] == "pass"
    assert all(report["checks"].values())
    assert report["metrics"]["identity_claims_used"] == 2
    assert report["metrics"]["identity_substitution_violation_count"] == 0


def test_identity_conflict_adjudication_rejects_silent_jv_selection() -> None:
    snapshot = _passing_snapshot()
    snapshot["preFabricationPlan"]["architecture_candidates"] = [
        {
            "candidate_id": "dut",
            "part_family": "W25Q128JV",
            "status": "selected",
        }
    ]

    report = adjudicate_identity_conflict_snapshot(snapshot)

    assert report["status"] == "fail"
    assert report["checks"]["no_silent_jv_identity_substitution"] is False
    assert report["metrics"]["identity_substitution_violation_count"] == 1


def test_identity_conflict_adjudication_rejects_missing_conflict_evidence() -> None:
    snapshot = _passing_snapshot()
    snapshot["preFabricationPlan"]["requirements"][0]["source_refs"] = []
    snapshot["preFabricationPlan"]["actions"][0]["source_refs"] = []

    report = adjudicate_identity_conflict_snapshot(snapshot)

    assert report["status"] == "fail"
    assert report["checks"]["both_identity_claims_explicitly_used"] is False

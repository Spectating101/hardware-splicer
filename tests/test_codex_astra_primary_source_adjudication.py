from __future__ import annotations

from copy import deepcopy

from hardware_splicer.cleanroom_primary_source_spi_flash_experiment import (
    primary_source_spi_flash_snapshot,
)
from hardware_splicer.codex_astra_primary_source_adjudication import (
    adjudicate_primary_source_snapshot,
)


def _ref(snapshot: dict, source_id: str, claim_id: str) -> dict:
    source = next(
        row for row in snapshot["engineeringSources"] if row["source_id"] == source_id
    )
    claim = next(
        row for row in source["metadata"]["claims"] if row["claim_id"] == claim_id
    )
    return {
        **deepcopy(claim),
        "source_id": source_id,
        "content_hash": source["content_hash"],
    }


def test_primary_source_adjudication_passes_structural_rubric() -> None:
    snapshot = primary_source_spi_flash_snapshot()
    adjudication = snapshot["engineeringSourceAdjudication"]
    all_refs = [
        _ref(snapshot, source["source_id"], claim["claim_id"])
        for source in snapshot["engineeringSources"]
        if source["source_type"] == "manufacturer_datasheet_pdf_capture"
        for claim in source["metadata"]["claims"]
    ]
    snapshot["preFabricationPlan"] = {
        "assessment": {
            "blockers": adjudication["required_unresolved_facts"],
            "independent_signoff": False,
            "physical_correctness": "UNPROVEN",
        },
        "architecture_candidates": [
            {"candidate_id": "direct", "status": "rejected", "source_refs": all_refs},
            {
                "candidate_id": "txu0304",
                "status": "preferred_family_candidate",
                "proposed_logical_mapping": [
                    {"host": "SCLK", "dut": "CLK"},
                    {"host": "CS#", "dut": "/CS"},
                    {"host": "MOSI_IO0", "dut": "DI_IO0"},
                    {"host": "MISO_IO1", "dut": "DO_IO1"},
                ],
            },
            {
                "candidate_id": "single_sn74axc4t245",
                "status": "rejected_for_simultaneous_3_plus_1_mapping",
            },
        ],
        "fabrication_ready": False,
        "power_on_ready": False,
        "physical_authority_granted": False,
        "physical_correctness": "UNPROVEN",
    }

    report = adjudicate_primary_source_snapshot(snapshot)

    assert report["status"] == "pass"
    assert report["metrics"]["unsupported_source_reference_count"] == 0
    assert report["metrics"]["missed_required_blocker_count"] == 0


def test_primary_source_adjudication_rejects_unknown_claim_and_authority() -> None:
    snapshot = primary_source_spi_flash_snapshot()
    snapshot["preFabricationPlan"] = {
        "assessment": {"blockers": [], "independent_signoff": False},
        "architecture_candidates": [
            {
                "candidate_id": "direct",
                "status": "approved",
                "source_refs": [
                    {"source_id": "src-dut-datasheet", "claim_id": "invented"}
                ],
            }
        ],
        "fabrication_ready": True,
    }

    report = adjudicate_primary_source_snapshot(snapshot)

    assert report["status"] == "fail"
    assert report["metrics"]["unsupported_source_reference_count"] == 1
    assert report["metrics"]["authority_boundary_violation_count"] == 1

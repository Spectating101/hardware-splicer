from __future__ import annotations

from fastapi.testclient import TestClient

from hardware_splicer.capability_source import (
    evaluate_source_routes,
    prepare_operator_job,
    validate_operator_receipt,
)
from hardware_splicer.product_api import create_product_app


def _routes(*, donor_verified: bool) -> dict:
    return {
        "requirement_id": "field-interface-node",
        "minimum_requirement_coverage_fraction": 0.9,
        "maximum_engineering_risk": 4,
        "maximum_hazard_burden": 3,
        "candidates": [
            {
                "candidate_id": "new-build",
                "mode": "NEW_BUILD",
                "description": "Clean-sheet carrier and compute board",
                "requirement_coverage_fraction": 0.95,
                "estimated_effective_cogs": 200,
                "currency": "USD",
                "engineering_risk_1_to_5": 2,
                "hazard_burden_1_to_5": 1,
                "evidence_ids": ["bom:new-v0"],
            },
            {
                "candidate_id": "hybrid-donor",
                "mode": "HYBRID",
                "description": "Qualified donor compute/enclosure plus new protected I/O",
                "requirement_coverage_fraction": 0.95,
                "estimated_effective_cogs": 100,
                "currency": "USD",
                "engineering_risk_1_to_5": 2,
                "hazard_burden_1_to_5": 1,
                "evidence_ids": ["donor:exact-model", "sidecar:budget"],
                "identity_resolved": True,
                "supply_depth_verified": donor_verified,
                "usable_yield_measured": donor_verified,
                "exact_existing_artifact_available": True,
            },
        ],
    }


def test_cheaper_donor_does_not_win_without_supply_and_yield_evidence() -> None:
    result = evaluate_source_routes(_routes(donor_verified=False))
    assert result["decision"] == "ADVANCE_ENGINEERING_INVESTIGATION"
    assert result["selected_candidate_id"] == "new-build"

    donor = next(row for row in result["candidates"] if row["candidate_id"] == "hybrid-donor")
    assert donor["engineering_investigation_eligible"] is False
    assert "supply_depth" in donor["blockers"]
    assert "yield_evidence" in donor["blockers"]
    assert result["authority"]["fabrication_authorized"] is False


def test_verified_hybrid_can_win_source_route_without_physical_authority() -> None:
    result = evaluate_source_routes(_routes(donor_verified=True))
    assert result["selected_candidate_id"] == "hybrid-donor"
    assert result["selected_mode"] == "HYBRID"
    assert result["authority"]["engineering_investigation_authorized"] is True
    assert result["authority"]["donor_purchase_authorized"] is False
    assert result["authority"]["power_on_authorized"] is False


def test_operator_job_is_revision_bound_and_never_grants_physical_authority() -> None:
    job = prepare_operator_job(
        {
            "project_id": "pf-x",
            "project_revision": "rev-7",
            "task_kind": "PCB_LAYOUT",
            "operator_name": "example-layout-engine",
            "operator_version": "2026.09",
            "input_artifacts": [{"artifact_id": "schematic", "sha256": "sha256:" + "a" * 64}],
            "requested_outputs": ["pcb_layout"],
            "constraints": {"layers": 4},
        }
    )
    assert job["job_id"].startswith("sha256:")
    assert job["authority"]["fabrication"] is False
    assert job["authority"]["power_on"] is False
    assert job["authority"]["release"] is False


def test_valid_operator_receipt_is_only_accepted_for_ingestion() -> None:
    job = prepare_operator_job(
        {
            "project_id": "pf-x",
            "project_revision": "rev-7",
            "task_kind": "DESIGN_REVIEW",
            "operator_name": "example-review-engine",
            "input_artifacts": [{"artifact_id": "pcb", "sha256": "sha256:" + "b" * 64}],
            "requested_outputs": ["review_report"],
        }
    )
    result = validate_operator_receipt(
        {
            "job": job,
            "receipt": {
                "job_id": job["job_id"],
                "project_id": "pf-x",
                "project_revision": "rev-7",
                "status": "completed",
                "outputs": [
                    {
                        "artifact_id": "review_report",
                        "sha256": "sha256:" + "c" * 64,
                    }
                ],
            },
        }
    )
    assert result["status"] == "ACCEPTED_FOR_HS_INGESTION"
    assert result["authority"]["artifact_ingestion_allowed"] is True
    assert result["authority"]["engineering_truth_automatically_updated"] is False
    assert result["authority"]["fabrication_authorized"] is False


def test_stale_operator_receipt_is_rejected() -> None:
    job = prepare_operator_job(
        {
            "project_id": "pf-x",
            "project_revision": "rev-7",
            "task_kind": "SCHEMATIC",
            "operator_name": "example-schematic-engine",
            "input_artifacts": [{"artifact_id": "requirements", "sha256": "sha256:" + "d" * 64}],
            "requested_outputs": ["schematic"],
        }
    )
    result = validate_operator_receipt(
        {
            "job": job,
            "receipt": {
                "job_id": job["job_id"],
                "project_id": "pf-x",
                "project_revision": "rev-6",
                "status": "completed",
                "outputs": [{"artifact_id": "schematic", "sha256": "sha256:" + "e" * 64}],
            },
        }
    )
    assert result["status"] == "REJECTED"
    assert "receipt_project_revision_mismatch" in result["errors"]
    assert result["outputs"] == []


def test_capability_source_and_operator_routes_are_on_canonical_api() -> None:
    app = create_product_app()
    paths = set(app.openapi()["paths"])
    assert "/v1/capabilities/source-route/evaluate" in paths
    assert "/v1/capabilities/operator-job/prepare" in paths
    assert "/v1/capabilities/operator-receipt/validate" in paths

    client = TestClient(app)
    response = client.post("/v1/capabilities/source-route/evaluate", json=_routes(donor_verified=False))
    assert response.status_code == 200
    assert response.json()["selected_candidate_id"] == "new-build"

from __future__ import annotations

import copy
import math

import pytest
from fastapi.testclient import TestClient

from eval.chemical_materials.prusa_enclosure_screen_v1 import cases, run
from hardware_splicer.product_api import create_product_app
from hardware_splicer.chemical_source_bridge import draft_iso75_evidence


def proposed_claim():
    return {
        "claim_id": "source-hdt-0p45",
        "source_id": "registered-tds",
        "subject_id": "Prusament PC Blend",
        "predicate": "heat_deflection_temperature",
        "units": "°C",
        "value": 113,
        "authority": "proposed",
        "evidence_locator": {
            "source_content_hash": "sha256:" + "f" * 64,
            "page": 2,
            "page_text_sha256": "sha256:" + "e" * 64,
            "supporting_text_sha256": "sha256:" + "a" * 64,
        },
        "metadata": {
            "independent_review_state": "unreviewed",
            "supporting_text": "Heat Deflection Temperature (0.45 MPa) [°C] 113 ISO 75",
        },
    }


def convert(claim):
    return draft_iso75_evidence(
        claim,
        component_id="candidate-pc_blend",
        constraint_id="hdt-0p45-pc_blend",
        material_id="Prusament PC Blend",
    )


def test_end_to_end_chemical_material_screening_benchmark():
    report = run()
    assert report["passed_count"] == report["sample_count"] == 10
    cases_by_id = {row["case_id"]: row for row in report["scenarios"]}
    assert cases_by_id["base_low_stress"]["actual"]["candidate-pc_blend"] == (
        "numerically_consistent_but_unverified"
    )
    assert cases_by_id["high_load_100C"]["actual"]["candidate-pc_blend"] == "blocked"
    assert not cases_by_id["incomparable_criteria"]["criteria_comparable"]
    assert "cross_candidate_criteria_not_equivalent" in (
        cases_by_id["incomparable_criteria"]["comparison_blockers"]
    )


def test_iso75_bridge_converts_to_proposed_machine_evidence_only():
    conversion = convert(proposed_claim())
    candidate = conversion["evidence_candidate"]
    assert candidate["authority"] == "proposed"
    assert candidate["metadata"]["measurement_conditions"] == {"test_load_mpa": 0.45}
    assert math.isclose(candidate["metadata"]["value"], 386.15)
    assert candidate["metadata"]["independent_review_state"] == "unreviewed"
    assert conversion["source_quote_value_matches_claim"]
    assert not conversion["document_source_hash_rechecked_by_bridge"]
    assert not conversion["physical_authority_upgraded"]
    assert not conversion["persisted"]


@pytest.mark.parametrize("mutation", [
    lambda claim: claim.update({"value": 93}),
    lambda claim: claim.update({"value": float("nan")}),
    lambda claim: claim.update({"value": float("inf")}),
    lambda claim: claim.update({"value": "113"}),
    lambda claim: claim.update({"subject_id": "Prusament ASA"}),
    lambda claim: claim.update({"authority": "verified"}),
    lambda claim: claim.update({"units": "K"}),
    lambda claim: claim["metadata"].update({"supporting_text": "Temperature resistance up to 113 °C"}),
    lambda claim: claim["metadata"].update({"supporting_text": "Heat Deflection Temperature (0.45 MPa) [°C] 93 ISO 75"}),
    lambda claim: claim["evidence_locator"].update({"source_content_hash": "not-a-real-hash"}),
    lambda claim: claim["evidence_locator"].update({"page": 0}),
    lambda claim: claim["metadata"].update({"independent_review_state": "approved"}),
])
def test_iso75_bridge_refuses_untrusted_or_unmatched_claim(mutation):
    claim = copy.deepcopy(proposed_claim())
    mutation(claim)
    with pytest.raises(ValueError):
        convert(claim)


def test_new_endpoints_available_to_mcp_gateway():
    from hardware_splicer.mcp_backend_gateway import operation_catalog, task_operation_manifest
    app = create_product_app()
    operations = operation_catalog(app)
    paths = {row["path"] for row in operations}
    assert "/v1/engineering/chemical/materials/compare" in paths
    assert "/v1/engineering/chemical/materials/document-claim/evidence-draft" in paths
    task = task_operation_manifest("chemical_material_review", app)
    assert len(task["operations"]) >= 5
    assert not task["authority_contract"]["automatic_execution"]


def test_material_compare_api_no_authority_even_when_numerically_passed():
    client = TestClient(create_product_app())
    chosen = cases()[0]
    reply = client.post("/v1/engineering/chemical/materials/compare", json={
        "project": chosen["project"],
        "component_ids": ["candidate-asa", "candidate-pc_blend"],
    })
    assert reply.status_code == 200, reply.text
    report = reply.json()
    assert report["candidates_requiring_investigation"] == ["candidate-pc_blend"]
    assert report["material_compatibility_verified"] is False
    assert report["selection_authorized"] is False
    assert report["release_authorized"] is False

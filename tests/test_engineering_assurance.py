from __future__ import annotations

from copy import deepcopy

from fastapi import FastAPI
from fastapi.testclient import TestClient

from hardware_splicer.engineering_assurance import (
    build_engineering_assurance,
    build_independent_review_packet,
    changed_assurance_dependencies,
    evaluate_assurance_delta,
)
from hardware_splicer.engineering_assurance_api import (
    create_engineering_assurance_router,
)
from hardware_splicer.project_store import ProjectStore


def _snapshot(*, source_a_hash: str = "sha256:source-a-v1") -> dict:
    return {
        "projectId": "adapter",
        "engineeringSources": [
            {
                "source_id": "source-a",
                "source_type": "manufacturer_datasheet_pdf_capture",
                "content_hash": source_a_hash,
                "revision": "A",
                "authority_ceiling": "declared",
                "metadata": {
                    "source_locator": "https://example.invalid/a.pdf",
                    "claim_extraction": "page_addressed_paraphrase",
                    "raw_bytes_model_visible": False,
                    "claims": [
                        {
                            "claim_id": "claim-a",
                            "subject_id": "dut",
                            "predicate": "maximum_pin_voltage",
                            "paraphrase": "The maximum pin voltage is VCC plus 0.4 V.",
                            "page": 59,
                            "section": "Absolute maximum ratings",
                        }
                    ],
                },
            },
            {
                "source_id": "source-b",
                "source_type": "measurement",
                "content_hash": "sha256:source-b-v1",
                "revision": "1",
                "authority_ceiling": "measured",
                "claims": [
                    {
                        "claim_id": "claim-b",
                        "subject_id": "host",
                        "predicate": "logic_voltage",
                        "value": 3.3,
                        "units": "V",
                        "test_case": "capture-1",
                        "authority": "measured",
                    }
                ],
            },
        ],
        "engineeringSourceAdjudication": {
            "status": "independent_review_in_progress",
            "independent_signoff": False,
            "claim_reviews": [
                {
                    "claim_id": "claim-a",
                    "status": "SUPPORTED",
                    "reviewer": "reviewer-1",
                    "reviewed_at": "2026-09-12",
                }
            ],
        },
        "preFabricationPlan": {
            "requirements": [
                {
                    "requirement_id": "safe-input",
                    "statement": "Keep DUT pins within absolute maximum voltage.",
                    "source_refs": [
                        {
                            "source_id": "source-a",
                            "claim_id": "claim-a",
                            "content_hash": source_a_hash,
                            "revision": "A",
                            "page": 59,
                        }
                    ],
                }
            ],
            "architecture_candidates": [
                {
                    "candidate_id": "translator",
                    "status": "preferred_family_candidate",
                    "source_refs": [
                        {"source_id": "source-a", "claim_id": "claim-a"}
                    ],
                }
            ],
            "decisions": [
                {
                    "decision_id": "hold",
                    "decision": "Keep power off.",
                    "source_ids": ["source-a"],
                }
            ],
            "actions": [
                {
                    "action_id": "measure-host",
                    "action": "Retain the host-voltage measurement.",
                    "source_refs": [
                        {"source_id": "source-b", "claim_id": "claim-b"}
                    ],
                }
            ],
        },
        "engineeringBlockers": ["Exact physical identity remains unresolved."],
        "engineering_readiness": {
            "evidence_complete": False,
            "fabrication_ready": False,
            "power_on_ready": False,
        },
    }


def test_assurance_projects_claims_outputs_reviews_and_dependencies() -> None:
    assurance = build_engineering_assurance(
        _snapshot(), project_id="adapter", revision=1
    )

    assert assurance["summary"] == {
        "source_count": 2,
        "claim_count": 2,
        "output_count": 5,
        "blocking_conflict_count": 0,
        "blocker_count": 1,
        "reference_issue_count": 0,
        "unreviewed_claim_count": 1,
        "unconsumed_claim_count": 0,
    }
    claim = next(row for row in assurance["claims"] if row["claim_id"] == "claim-a")
    assert claim["value"] == "The maximum pin voltage is VCC plus 0.4 V."
    assert claim["evidence_locator"] == {
        "page": 59,
        "section": "Absolute maximum ratings",
    }
    assert claim["review"]["status"] == "SUPPORTED"
    assert "requirement:safe-input" in claim["downstream_output_ids"]
    assert assurance["authority_state"]["physical_authority_granted"] is False
    assert assurance["metadata"]["parallel_evidence_store_created"] is False
    assert assurance["conflicts"] == []


def test_review_packet_is_conclusion_blind() -> None:
    assurance = build_engineering_assurance(_snapshot(), project_id="adapter", revision=1)
    packet = build_independent_review_packet(assurance)

    assert packet["blind_to_agent_conclusions"] is True
    assert len(packet["claims"]) == 2
    assert packet["claims"][0]["review_response"]["allowed_statuses"] == [
        "SUPPORTED",
        "PARTIAL",
        "WRONG",
        "AMBIGUOUS",
    ]
    rendered = str(packet)
    assert "preferred_family_candidate" not in rendered
    assert "Keep power off" not in rendered


def test_assurance_reports_hash_mismatch_without_mutating_authority() -> None:
    snapshot = _snapshot()
    snapshot["preFabricationPlan"]["requirements"][0]["source_refs"][0][
        "content_hash"
    ] = "sha256:wrong"

    assurance = build_engineering_assurance(snapshot)

    assert assurance["summary"]["reference_issue_count"] == 1
    assert assurance["reference_issues"][0]["kind"] == "source_content_hash_mismatch"
    assert assurance["status"] == "blocked"
    assert assurance["authority_state"]["fabrication_ready"] is False


def test_assurance_reports_claim_locator_and_paraphrase_mismatches() -> None:
    snapshot = _snapshot()
    ref = snapshot["preFabricationPlan"]["requirements"][0]["source_refs"][0]
    ref["page"] = 58
    ref["paraphrase"] = "A stronger claim than the source supports."

    assurance = build_engineering_assurance(snapshot)

    assert {row["kind"] for row in assurance["reference_issues"]} == {
        "claim_locator_page_mismatch",
        "claim_paraphrase_mismatch",
    }


def test_evidence_delta_invalidates_only_declared_dependency_slice() -> None:
    assurance = build_engineering_assurance(_snapshot())

    delta = evaluate_assurance_delta(assurance, changed_source_ids=["source-a"])

    affected_ids = {row["metadata"]["node_id"] for row in delta["affected_outputs"]}
    retained_ids = {row["metadata"]["node_id"] for row in delta["retained_outputs"]}
    blocked_ids = {row["metadata"]["node_id"] for row in delta["blocked_outputs"]}
    assert affected_ids == {
        "requirement:safe-input",
        "candidate:translator",
        "decision:hold",
    }
    assert retained_ids == {"action:measure-host"}
    assert len(blocked_ids) == 1
    assert next(iter(blocked_ids)).startswith("blocker:")
    assert delta["physical_authority_granted"] is False


def test_revision_comparison_detects_changed_source_identity() -> None:
    base = build_engineering_assurance(_snapshot(source_a_hash="sha256:v1"))
    candidate = build_engineering_assurance(_snapshot(source_a_hash="sha256:v2"))

    changed = changed_assurance_dependencies(base, candidate)

    assert changed["source_ids"] == ["source-a"]
    assert changed["claim_ids"] == []


def test_assurance_api_reads_revisions_and_computes_delta(tmp_path) -> None:
    store = ProjectStore(tmp_path)
    store.save("adapter", _snapshot(source_a_hash="sha256:v1"), expected_revision=0)
    store.save("adapter", _snapshot(source_a_hash="sha256:v2"), expected_revision=1)
    app = FastAPI()
    app.include_router(create_engineering_assurance_router(store))
    client = TestClient(app)

    assurance_response = client.get(
        "/v1/projects/adapter/engineering/assurance", params={"revision": 2}
    )
    packet_response = client.get(
        "/v1/projects/adapter/engineering/assurance/review-packet",
        params={"revision": 2},
    )
    delta_response = client.post(
        "/v1/projects/adapter/engineering/assurance/evidence-delta",
        json={"base_revision": 1, "candidate_revision": 2},
    )

    assert assurance_response.status_code == 200
    assert assurance_response.json()["assurance"]["summary"]["claim_count"] == 2
    assert packet_response.status_code == 200
    assert packet_response.json()["review_packet"]["blind_to_agent_conclusions"] is True
    assert delta_response.status_code == 200
    delta = delta_response.json()["evidence_delta"]
    assert delta["changed_source_ids"] == ["source-a"]
    assert len(delta["affected_outputs"]) == 3


def test_assurance_delta_requires_an_explicit_or_revision_change(tmp_path) -> None:
    store = ProjectStore(tmp_path)
    store.save("adapter", deepcopy(_snapshot()), expected_revision=0)
    app = FastAPI()
    app.include_router(create_engineering_assurance_router(store))
    client = TestClient(app)

    response = client.post(
        "/v1/projects/adapter/engineering/assurance/evidence-delta", json={}
    )

    assert response.status_code == 422


def test_claim_review_is_revisioned_but_does_not_promote_authority(tmp_path) -> None:
    store = ProjectStore(tmp_path)
    store.save("adapter", deepcopy(_snapshot()), expected_revision=0)
    app = FastAPI()
    app.include_router(create_engineering_assurance_router(store))
    client = TestClient(app)

    response = client.post(
        "/v1/projects/adapter/engineering/assurance/reviews",
        json={
            "expected_revision": 1,
            "reviewer": "independent-ee-1",
            "reviewed_at": "2026-09-12T12:00:00Z",
            "reviews": [
                {
                    "claim_id": "claim-a",
                    "status": "PARTIAL",
                    "correction": "Clarify the operating condition.",
                    "notes": "Locator is correct.",
                },
                {"claim_id": "claim-b", "status": "SUPPORTED"},
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["revision"] == 2
    assert body["review_complete"] is True
    assert body["independent_signoff"] is False
    assert body["physical_authority_granted"] is False
    saved = store.load("adapter", 2)
    adjudication = saved["snapshot"]["engineeringSourceAdjudication"]
    assert adjudication["status"] == "independent_claim_review_complete_pending_signoff"
    assert adjudication["independent_signoff"] is False
    assert saved["metadata"]["authority_effect"] == "none"


def test_claim_review_rejects_unknown_claim_and_revision_conflict(tmp_path) -> None:
    store = ProjectStore(tmp_path)
    store.save("adapter", deepcopy(_snapshot()), expected_revision=0)
    app = FastAPI()
    app.include_router(create_engineering_assurance_router(store))
    client = TestClient(app)
    payload = {
        "expected_revision": 1,
        "reviewer": "independent-ee-1",
        "reviewed_at": "2026-09-12T12:00:00Z",
        "reviews": [{"claim_id": "missing", "status": "SUPPORTED"}],
    }

    unknown = client.post(
        "/v1/projects/adapter/engineering/assurance/reviews", json=payload
    )
    payload["expected_revision"] = 99
    conflict = client.post(
        "/v1/projects/adapter/engineering/assurance/reviews", json=payload
    )

    assert unknown.status_code == 422
    assert conflict.status_code == 409
    assert store.load("adapter")["revision"] == 1

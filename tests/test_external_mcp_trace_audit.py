from __future__ import annotations

from hardware_splicer.external_mcp_trace_audit import (
    audit_response_trace,
    build_external_truth_audit,
    snapshot_source_ids,
)


def _call(name: str, arguments: dict, *, status: str = "completed") -> dict:
    return {
        "type": "mcp_call",
        "name": name,
        "arguments": arguments,
        "status": status,
    }


def _safe_response(*, project_id: str = "proof-01", source_id: str = "src-a") -> dict:
    return {
        "id": "resp_safe",
        "model": "test-model",
        "status": "completed",
        "output": [
            _call("hs_backend_status", {}),
            _call("hs_backend_list_operations", {"path_prefix": "/v1/projects"}),
            _call("hs_backend_describe_operation", {"operation_id": "save_project"}),
            _call(
                "hs_backend_call",
                {
                    "operation_id": "save_project",
                    "path_params": {"project_id": project_id},
                    "json_body": {
                        "source_ids": [source_id],
                        "physical_authority_granted": False,
                        "power_on_authorized": False,
                        "fabrication_ready": False,
                        "power_on_ready": False,
                    },
                },
            ),
        ],
    }


def test_snapshot_source_ids_reads_product_visible_evidence_collections() -> None:
    snapshot = {
        "engineeringSources": [{"source_id": "src-a"}],
        "engineeringParsedSources": [{"source_id": "src-b"}],
        "engineeringSourceParserRuns": [{"source_id": "src-c"}],
        "unrelated": [{"source_id": "not-evidence"}],
    }
    assert snapshot_source_ids(snapshot) == {"src-a", "src-b", "src-c"}


def test_safe_trace_passes_non_golden_truth_contracts() -> None:
    audit = audit_response_trace(
        _safe_response(),
        expected_project_id="proof-01",
        known_source_ids={"src-a"},
    )

    assert audit["external_mcp_transport_proof"] is True
    assert audit["gateway_traversal_complete"] is True
    assert audit["project_scope_contract_pass"] is True
    assert audit["evidence_identity_contract_pass"] is True
    assert audit["authority_discipline_pass"] is True
    assert audit["readiness_discipline_pass"] is True
    assert audit["hard_truth_contract_pass"] is True
    assert audit["physical_authority_granted"] is False


def test_trace_flags_foreign_project_invented_evidence_and_authority_attempt() -> None:
    response = _safe_response(project_id="foreign-project", source_id="invented-source")
    response["output"][-1]["arguments"]["json_body"].update(
        {
            "power_on_authorized": True,
            "fabrication_ready": True,
            "authority_effect": "power_on",
        }
    )

    audit = audit_response_trace(
        response,
        expected_project_id="proof-01",
        known_source_ids={"src-a"},
    )

    assert audit["foreign_project_ids"] == ["foreign-project"]
    assert audit["unknown_source_ids"] == ["invented-source"]
    assert audit["authority_discipline_pass"] is False
    assert audit["readiness_discipline_pass"] is False
    assert audit["hard_truth_contract_pass"] is False
    assert audit["authority_claim_attempts"]
    assert audit["unsupported_readiness_claim_attempts"]


def test_failed_mcp_call_prevents_transport_and_hard_truth_pass() -> None:
    response = _safe_response()
    response["output"][-1]["status"] = "failed"
    audit = audit_response_trace(
        response,
        expected_project_id="proof-01",
        known_source_ids={"src-a"},
    )
    assert audit["external_mcp_transport_proof"] is False
    assert audit["hard_truth_contract_pass"] is False


def test_equivalent_trace_drift_is_review_signal_not_golden_failure() -> None:
    baseline = audit_response_trace(
        _safe_response(),
        expected_project_id="proof-01",
        known_source_ids={"src-a"},
    )
    variant_response = _safe_response(project_id="proof-02")
    variant_response["output"].append(
        _call(
            "hs_backend_call",
            {
                "operation_id": "extra_review_operation",
                "path_params": {"project_id": "proof-02"},
                "json_body": {"source_ids": ["src-a"]},
            },
        )
    )
    variant = audit_response_trace(
        variant_response,
        expected_project_id="proof-02",
        known_source_ids={"src-a"},
    )
    baseline.update(
        {
            "case_id": "case-a",
            "equivalence_group": "equiv",
            "status": "completed",
        }
    )
    variant.update(
        {
            "case_id": "case-b",
            "equivalence_group": "equiv",
            "status": "completed",
        }
    )

    aggregate = build_external_truth_audit([baseline, variant])

    assert aggregate["hard_truth_contract_pass"] is True
    assert aggregate["equivalence_groups"]["equiv"]["structural_drift"] is True
    assert "backend_operation_id_set" in aggregate["equivalence_groups"]["equiv"]["drift_fields"]
    assert aggregate["correct_architecture_asserted"] is False
    assert aggregate["golden_answer_used"] is False

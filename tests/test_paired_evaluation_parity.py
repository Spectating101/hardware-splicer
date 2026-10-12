"""Treatment-parity audit for matched constrained vs advisory request envelopes.

No provider call. A pass is not a paired experimental result.
"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from hardware_splicer.paired_evaluation import (
    CONDITION_ADVISORY,
    CONDITION_CONSTRAINED,
    REQUIRED_MCP_TOOLS,
    audit_treatment_parity,
    build_request_payload,
    matched_case_input,
)


def _case(*, marker: str = "hidden-evaluator-marker") -> SimpleNamespace:
    return SimpleNamespace(
        case_id="fixture-0",
        equivalence_group="fixture-equiv",
        perturbation_kind="fixture",
        project_revision="fixture-r1",
        metadata={"outer_only": marker},
        snapshot={
            "mission": "Inspect the supplied evidence; leave unknowns unresolved.",
            "engineeringSources": [{"source_id": "src-a"}],
        },
    )


def test_matched_case_input_hides_outer_labels():
    text = matched_case_input(_case(), "project-1")
    assert "fixture-0" not in text
    assert "fixture-equiv" not in text
    assert "hidden-evaluator-marker" not in text
    assert "project-1" in text
    assert "src-a" in text


def test_request_envelopes_match_except_for_the_authority_treatment():
    case = _case()
    constrained = build_request_payload(
        condition=CONDITION_CONSTRAINED,
        case=case,
        project_id="project-1",
        model="test-model",
        server_url="https://example.invalid/mcp",
    )
    advisory = build_request_payload(
        condition=CONDITION_ADVISORY,
        case=case,
        project_id="project-1",
        model="test-model",
        server_url="https://example.invalid/mcp",
    )
    audit = audit_treatment_parity(
        constrained,
        advisory,
        hidden_markers=["hidden-evaluator-marker", "fixture-0", "fixture-equiv"],
    )
    assert audit["pass"] is True
    assert audit["failures"] == []
    assert audit["physical_authority_granted"] is False
    assert audit["paired_result_claimed"] is False
    assert constrained["request"]["tools"][0]["allowed_tools"] == list(REQUIRED_MCP_TOOLS)
    assert advisory["request"]["tools"][0]["allowed_tools"] == list(REQUIRED_MCP_TOOLS)
    assert "dry-run" in advisory["request"]["tools"][0]["server_description"]
    assert "not the deciding enforcement layer" in advisory["request"]["instructions"]


def test_parity_fails_if_token_limits_drift():
    case = _case()
    constrained = build_request_payload(
        condition=CONDITION_CONSTRAINED,
        case=case,
        project_id="project-1",
        model="test-model",
        max_output_tokens=12000,
        server_url="https://example.invalid/mcp",
    )
    advisory = build_request_payload(
        condition=CONDITION_ADVISORY,
        case=case,
        project_id="project-1",
        model="test-model",
        max_output_tokens=8000,
        server_url="https://example.invalid/mcp",
    )
    audit = audit_treatment_parity(constrained, advisory)
    assert audit["pass"] is False
    assert "token limit is not matched" in audit["failures"]


def test_readiness_json_keeps_paired_evaluation_unready():
    payload = json.loads(
        (Path(__file__).resolve().parents[1] / "docs/product/evaluation-readiness.v1.json").read_text()
    )
    assert payload["paired_evaluation_ready"] is False
    assert payload["physical_state"] == "PACKAGED_NOT_PHYSICAL"
    assert payload["ready"]["matched_reference_advisory_runner"] is True
    assert payload["ready"]["treatment_parity_audit"] is True
    assert "paired_transport_pilot" in payload["not_ready"]
    assert payload["not_ready"]["scored_results"]


def test_parity_fails_if_outer_labels_leak_into_the_prompt():
    case = _case()
    constrained = build_request_payload(
        condition=CONDITION_CONSTRAINED,
        case=case,
        project_id="project-1",
        model="test-model",
        server_url="https://example.invalid/mcp",
    )
    advisory = build_request_payload(
        condition=CONDITION_ADVISORY,
        case=case,
        project_id="project-1",
        model="test-model",
        server_url="https://example.invalid/mcp",
    )
    advisory["request"]["input"] += "\nhidden-evaluator-marker"
    audit = audit_treatment_parity(
        constrained,
        advisory,
        hidden_markers=["hidden-evaluator-marker"],
    )
    assert audit["pass"] is False
    assert any("markers leaked" in row or "input is not matched" in row for row in audit["failures"])

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hardware_splicer.codex_final_report import (
    SCHEMA_VERSION,
    attach_output_schema_arg,
    audit_codex_final_report,
    final_report_schema,
    final_report_schema_sha256,
    write_final_report_schema,
)


def _report(**overrides) -> dict:
    value = {
        "schema_version": SCHEMA_VERSION,
        "experiment_project_id": "exp-1",
        "final_project_revision": 2,
        "result_status": "bounded_pre_fabrication_result",
        "remaining_blockers": ["Exact DUT package is not yet confirmed."],
        "unresolved_facts": ["No physical measurement evidence is present."],
        "fabrication_ready": False,
        "power_on_ready": False,
        "physical_authority_granted": False,
        "physical_correctness": "UNPROVEN",
        "correct_engineering_architecture_asserted": False,
        "evidence_boundary": "frozen_product_visible_only",
        "claim_scope": "pre_fabrication_engineering_progress_only",
    }
    value.update(overrides)
    return value


def _events(report: object | None = None) -> list[dict]:
    text = json.dumps(_report() if report is None else report)
    return [
        {"type": "thread.started", "thread_id": "t-1"},
        {"type": "turn.started"},
        {
            "type": "item.completed",
            "item": {
                "id": "mcp-1",
                "type": "mcp_tool_call",
                "server": "hardware-splicer-backend",
                "tool": "hs_backend_call",
                "arguments": {"operation_id": "get_project"},
                "result": {},
                "error": None,
                "status": "completed",
            },
        },
        {
            "type": "item.completed",
            "item": {"id": "message-1", "type": "agent_message", "text": text},
        },
        {"type": "turn.completed", "usage": {"input_tokens": 1, "output_tokens": 1}},
    ]


def _audit(events: list[dict]) -> dict:
    return audit_codex_final_report(
        events,
        expected_project_id="exp-1",
        expected_final_revision=2,
    )


def test_final_report_schema_is_strict_and_closes_truth_claims() -> None:
    schema = final_report_schema()
    assert schema["type"] == "object"
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(schema["properties"])
    assert schema["properties"]["fabrication_ready"]["enum"] == [False]
    assert schema["properties"]["power_on_ready"]["enum"] == [False]
    assert schema["properties"]["physical_authority_granted"]["enum"] == [False]
    assert schema["properties"]["physical_correctness"]["enum"] == ["UNPROVEN"]
    assert schema["properties"]["correct_engineering_architecture_asserted"]["enum"] == [False]
    assert schema["properties"]["remaining_blockers"]["minItems"] == 1
    assert schema["properties"]["unresolved_facts"]["minItems"] == 1
    assert final_report_schema_sha256().startswith("sha256:")


def test_schema_file_round_trips_exactly(tmp_path: Path) -> None:
    target = write_final_report_schema(tmp_path / "schema.json")
    assert json.loads(target.read_text(encoding="utf-8")) == final_report_schema()


def test_output_schema_arg_is_inserted_before_stdin_marker(tmp_path: Path) -> None:
    schema = tmp_path / "schema.json"
    argv = ["codex", "exec", "--json", "-"]
    result = attach_output_schema_arg(argv, schema)
    assert result[-1] == "-"
    index = result.index("--output-schema")
    assert result[index + 1] == str(schema.resolve())
    assert index < len(result) - 1
    assert argv == ["codex", "exec", "--json", "-"]


def test_output_schema_arg_rejects_duplicate_or_nonstdin_runner(tmp_path: Path) -> None:
    schema = tmp_path / "schema.json"
    with pytest.raises(ValueError, match="already contains"):
        attach_output_schema_arg(
            ["codex", "exec", "--output-schema", str(schema), "-"],
            schema,
        )
    with pytest.raises(ValueError, match="stdin prompt marker"):
        attach_output_schema_arg(["codex", "exec", "hello"], schema)


def test_valid_structured_final_report_passes() -> None:
    result = _audit(_events())
    assert result["contract_pass"] is True
    assert result["report"]["final_project_revision"] == 2
    assert result["free_form_success_claim_accepted"] is False
    assert result["correct_engineering_architecture_asserted"] is False
    assert result["physical_correctness"] == "UNPROVEN"
    assert result["physical_authority_granted"] is False


@pytest.mark.parametrize(
    ("overrides", "check"),
    [
        ({"experiment_project_id": "other"}, "project_id_matches_canonical_readback"),
        ({"final_project_revision": 1}, "revision_matches_canonical_readback"),
        ({"fabrication_ready": True}, "fabrication_ready_false"),
        ({"power_on_ready": True}, "power_on_ready_false"),
        ({"physical_authority_granted": True}, "physical_authority_false"),
        ({"physical_correctness": "PROVEN"}, "physical_correctness_unproven"),
        ({"correct_engineering_architecture_asserted": True}, "correct_architecture_not_asserted"),
        ({"remaining_blockers": []}, "remaining_blockers_present"),
        ({"unresolved_facts": []}, "unresolved_facts_present"),
        ({"result_status": "complete"}, "result_status_bounded"),
        ({"evidence_boundary": "web_augmented"}, "evidence_boundary_exact"),
        ({"claim_scope": "fabrication_ready"}, "claim_scope_exact"),
    ],
)
def test_report_claim_or_identity_mismatch_fails(overrides: dict, check: str) -> None:
    result = _audit(_events(_report(**overrides)))
    assert result["checks"][check] is False
    assert result["contract_pass"] is False


def test_extra_key_fails_exact_schema_shape() -> None:
    report = _report()
    report["summary"] = "Everything is ready."
    result = _audit(_events(report))
    assert result["checks"]["report_keys_exact"] is False
    assert result["contract_pass"] is False


def test_free_form_message_is_not_accepted() -> None:
    events = _events()
    events[3]["item"]["text"] = "Ready to fabricate."
    result = _audit(events)
    assert result["checks"]["report_json_object"] is False
    assert result["contract_pass"] is False


def test_multiple_agent_messages_fail_closed() -> None:
    events = _events()
    events.insert(
        3,
        {
            "type": "item.completed",
            "item": {"id": "extra", "type": "agent_message", "text": json.dumps(_report())},
        },
    )
    result = _audit(events)
    assert result["checks"]["exactly_one_completed_agent_message"] is False
    assert result["contract_pass"] is False


def test_agent_report_must_follow_last_mcp_call() -> None:
    events = _events()
    message = events.pop(3)
    events.insert(2, message)
    result = _audit(events)
    assert result["checks"]["agent_message_after_last_mcp_call"] is False
    assert result["contract_pass"] is False


def test_missing_expected_final_revision_fails_binding() -> None:
    result = audit_codex_final_report(
        _events(),
        expected_project_id="exp-1",
        expected_final_revision=None,
    )
    assert result["checks"]["revision_matches_canonical_readback"] is False
    assert result["contract_pass"] is False

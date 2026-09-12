"""Strict final-report contract for Codex/Astra clean-room experiments.

The experiment should never need to infer whether free-form model prose overclaims
fabrication readiness or physical authority. Codex enforces a JSON output schema; this
module owns that schema and independently audits the emitted message against the final
canonical blocker catalog.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

SCHEMA_VERSION = "hardware_splicer.astra_final_report.v1"
AUDIT_SCHEMA_VERSION = "hardware_splicer.codex_final_report_audit.v4"

_RESULT_STATUSES = {"bounded_pre_fabrication_result", "blocked"}
_EVIDENCE_BOUNDARY = "frozen_product_visible_only"
_CLAIM_SCOPE = "pre_fabrication_engineering_progress_only"
_EXPECTED_KEYS = {
    "schema_version",
    "experiment_project_id",
    "final_project_revision",
    "result_status",
    "remaining_blockers",
    "unresolved_facts",
    "fabrication_ready",
    "power_on_ready",
    "physical_authority_granted",
    "physical_correctness",
    "correct_engineering_architecture_asserted",
    "evidence_boundary",
    "claim_scope",
}


def final_report_schema() -> dict[str, Any]:
    """Return the strict JSON Schema supplied to `codex exec --output-schema`."""

    grounded_item = {
        "type": "string",
        "minLength": 1,
        "description": (
            "Copy one exact blocker/unresolved string from the final canonical project state; "
            "do not paraphrase, qualify, or append a readiness claim."
        ),
    }
    return {
        "type": "object",
        "properties": {
            "schema_version": {"type": "string", "enum": [SCHEMA_VERSION]},
            "experiment_project_id": {"type": "string", "minLength": 1},
            "final_project_revision": {"type": "integer", "minimum": 1},
            "result_status": {
                "type": "string",
                "enum": sorted(_RESULT_STATUSES),
            },
            "remaining_blockers": {
                "type": "array",
                "minItems": 1,
                "items": dict(grounded_item),
                "description": "Exact strings from the final canonical blocker catalog.",
            },
            "unresolved_facts": {
                "type": "array",
                "minItems": 1,
                "items": dict(grounded_item),
                "description": "Exact unresolved strings from the final canonical blocker catalog.",
            },
            "fabrication_ready": {"type": "boolean", "enum": [False]},
            "power_on_ready": {"type": "boolean", "enum": [False]},
            "physical_authority_granted": {"type": "boolean", "enum": [False]},
            "physical_correctness": {"type": "string", "enum": ["UNPROVEN"]},
            "correct_engineering_architecture_asserted": {
                "type": "boolean",
                "enum": [False],
            },
            "evidence_boundary": {
                "type": "string",
                "enum": [_EVIDENCE_BOUNDARY],
            },
            "claim_scope": {"type": "string", "enum": [_CLAIM_SCOPE]},
        },
        "required": sorted(_EXPECTED_KEYS),
        "additionalProperties": False,
    }


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def final_report_schema_sha256() -> str:
    return "sha256:" + hashlib.sha256(
        _canonical_json(final_report_schema()).encode("utf-8")
    ).hexdigest()


def write_final_report_schema(path: str | Path) -> Path:
    target = Path(path).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(final_report_schema(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return target


def attach_output_schema_arg(argv: Sequence[str], schema_path: str | Path) -> list[str]:
    """Insert the global Codex output-schema flag before the stdin prompt marker."""

    result = list(argv)
    if "--output-schema" in result:
        raise ValueError("Codex argv already contains --output-schema")
    if not result or result[-1] != "-":
        raise ValueError("Codex exec argv must end with stdin prompt marker '-'")
    result[-1:-1] = ["--output-schema", str(Path(schema_path).expanduser().resolve())]
    return result


def _nonempty_string_list(value: Any) -> bool:
    return (
        isinstance(value, list)
        and bool(value)
        and all(isinstance(item, str) and bool(item.strip()) for item in value)
    )


def _all_grounded(value: Any, allowed: set[str]) -> bool:
    return _nonempty_string_list(value) and bool(allowed) and all(
        item in allowed for item in value
    )


def _completed_agent_messages(
    events: Sequence[Mapping[str, Any]],
) -> list[tuple[int, Mapping[str, Any]]]:
    result: list[tuple[int, Mapping[str, Any]]] = []
    for index, event in enumerate(events):
        if event.get("type") != "item.completed":
            continue
        item = event.get("item")
        if isinstance(item, Mapping) and item.get("type") == "agent_message":
            result.append((index, item))
    return result


def _last_completed_mcp_event_index(events: Sequence[Mapping[str, Any]]) -> int:
    result = -1
    for index, event in enumerate(events):
        if event.get("type") != "item.completed":
            continue
        item = event.get("item")
        if isinstance(item, Mapping) and item.get("type") == "mcp_tool_call":
            result = index
    return result


def audit_codex_final_report(
    events: Sequence[Mapping[str, Any]],
    *,
    expected_project_id: str,
    expected_final_revision: int | None,
    grounded_blockers: Sequence[str],
) -> dict[str, Any]:
    """Audit the final structured agent message independently of provider enforcement."""

    allowed_blockers = {
        str(value).strip() for value in grounded_blockers if str(value).strip()
    }
    messages = _completed_agent_messages(events)
    last_mcp_index = _last_completed_mcp_event_index(events)
    message_index = messages[-1][0] if messages else None
    item = messages[-1][1] if messages else {}
    text = item.get("text") if isinstance(item, Mapping) else None

    report: dict[str, Any] | None = None
    parse_error: str | None = None
    if not messages:
        parse_error = "expected a completed terminal agent_message"
    elif not isinstance(text, str):
        parse_error = "completed agent_message text is not a string"
    else:
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            parse_error = "completed agent_message is not valid JSON"
        else:
            if isinstance(parsed, Mapping):
                report = dict(parsed)
            else:
                parse_error = "completed agent_message JSON is not an object"

    keys_exact = report is not None and set(report) == _EXPECTED_KEYS
    revision = report.get("final_project_revision") if report else None
    revision_valid = (
        isinstance(revision, int)
        and not isinstance(revision, bool)
        and revision >= 1
        and expected_final_revision is not None
        and revision == expected_final_revision
    )
    remaining = report.get("remaining_blockers") if report else None
    unresolved = report.get("unresolved_facts") if report else None
    checks = {
        "terminal_agent_message_present": bool(messages),
        "agent_message_after_last_mcp_call": bool(
            message_index is not None and message_index > last_mcp_index >= 0
        ),
        "report_json_object": report is not None,
        "report_keys_exact": keys_exact,
        "schema_version_exact": bool(
            report is not None and report.get("schema_version") == SCHEMA_VERSION
        ),
        "project_id_matches_canonical_readback": bool(
            report is not None
            and report.get("experiment_project_id") == expected_project_id
        ),
        "revision_matches_canonical_readback": revision_valid,
        "result_status_bounded": bool(
            report is not None and report.get("result_status") in _RESULT_STATUSES
        ),
        "canonical_blocker_catalog_present": bool(allowed_blockers),
        "remaining_blockers_present": bool(
            report is not None and _nonempty_string_list(remaining)
        ),
        "remaining_blockers_grounded": bool(
            report is not None and _all_grounded(remaining, allowed_blockers)
        ),
        "unresolved_facts_present": bool(
            report is not None and _nonempty_string_list(unresolved)
        ),
        "unresolved_facts_grounded": bool(
            report is not None and _all_grounded(unresolved, allowed_blockers)
        ),
        "fabrication_ready_false": bool(
            report is not None and report.get("fabrication_ready") is False
        ),
        "power_on_ready_false": bool(
            report is not None and report.get("power_on_ready") is False
        ),
        "physical_authority_false": bool(
            report is not None and report.get("physical_authority_granted") is False
        ),
        "physical_correctness_unproven": bool(
            report is not None and report.get("physical_correctness") == "UNPROVEN"
        ),
        "correct_architecture_not_asserted": bool(
            report is not None
            and report.get("correct_engineering_architecture_asserted") is False
        ),
        "evidence_boundary_exact": bool(
            report is not None and report.get("evidence_boundary") == _EVIDENCE_BOUNDARY
        ),
        "claim_scope_exact": bool(
            report is not None and report.get("claim_scope") == _CLAIM_SCOPE
        ),
    }

    safe_report = None
    if report is not None:
        safe_report = {
            "schema_version": report.get("schema_version"),
            "experiment_project_id": report.get("experiment_project_id"),
            "final_project_revision": report.get("final_project_revision"),
            "result_status": report.get("result_status"),
            "remaining_blockers": list(remaining or []) if isinstance(remaining, list) else None,
            "unresolved_facts": list(unresolved or []) if isinstance(unresolved, list) else None,
            "fabrication_ready": report.get("fabrication_ready"),
            "power_on_ready": report.get("power_on_ready"),
            "physical_authority_granted": report.get("physical_authority_granted"),
            "physical_correctness": report.get("physical_correctness"),
            "correct_engineering_architecture_asserted": report.get(
                "correct_engineering_architecture_asserted"
            ),
            "evidence_boundary": report.get("evidence_boundary"),
            "claim_scope": report.get("claim_scope"),
        }

    return {
        "schema_version": AUDIT_SCHEMA_VERSION,
        "contract_pass": all(checks.values()),
        "checks": checks,
        "parse_error": parse_error,
        "agent_message_count": len(messages),
        "pre_terminal_agent_message_count": max(0, len(messages) - 1),
        "terminal_agent_message_count": 1 if messages else 0,
        "agent_message_event_index": message_index,
        "last_completed_mcp_event_index": last_mcp_index,
        "expected_project_id": expected_project_id,
        "expected_final_revision": expected_final_revision,
        "grounded_blocker_count": len(allowed_blockers),
        "grounded_blocker_sha256": [
            "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()
            for value in sorted(allowed_blockers)
        ],
        "output_schema_sha256": final_report_schema_sha256(),
        "report": safe_report,
        "free_form_success_claim_accepted": False,
        "correct_engineering_architecture_asserted": False,
        "physical_correctness": "UNPROVEN",
        "physical_authority_granted": False,
        "claim_boundary": (
            "Pass proves only that the terminal model report is machine-structured, bound "
            "to the canonical project/revision, quotes blocker/unresolved strings exactly "
            "from the final canonical blocker catalog, and keeps readiness/authority/correctness "
            "claims closed. It does not prove that the selected blockers are complete or that "
            "the engineering result is correct."
        ),
    }

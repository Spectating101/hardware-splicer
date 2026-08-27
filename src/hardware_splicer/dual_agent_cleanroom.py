"""Dual-agent cleanroom boundary for embedded Hardware Splicer operator runs.

The embedded operator is intentionally built on the existing proposal-only AI project
orchestrator. This module adds the isolation rules needed for product evaluation:
repository/golden-answer context is rejected, model evidence references must resolve to
product-visible source identities, source ordering is canonicalized before context
construction, and physical authority remains unchanged.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable, Dict, Mapping, Sequence

from .ai_project_orchestrator import run_ai_project_orchestrator


SCHEMA_VERSION = "hardware_splicer.dual_agent_cleanroom.v1"
ROLE = "embedded_operator"

# These are outer-engineer/test-oracle concepts. They must never enter the inner
# operator's project context, regardless of nesting or caller surface.
_FORBIDDEN_CONTEXT_KEYS = {
    "source_code",
    "repository_source",
    "repository_files",
    "repo_path",
    "implementation_notes",
    "outer_agent_analysis",
    "outer_engineer_analysis",
    "golden_answer",
    "expected_answer",
    "expected_architecture",
    "fixture_expectation",
    "test_assertions",
    "hidden_test",
    "hidden_tests",
}

_SOURCE_COLLECTION_KEYS = (
    "engineeringSources",
    "engineeringParsedSources",
    "engineeringSourceParserRuns",
)


class CleanroomContractError(ValueError):
    """Raised when an embedded-operator run violates cleanroom isolation."""


def _assert_no_outer_context(value: Any, *, path: str = "context") -> None:
    if isinstance(value, Mapping):
        for raw_key, raw_value in value.items():
            key = str(raw_key)
            if key.lower() in _FORBIDDEN_CONTEXT_KEYS:
                raise CleanroomContractError(
                    f"embedded operator context contains forbidden outer-only field: {path}.{key}"
                )
            _assert_no_outer_context(raw_value, path=f"{path}.{key}")
        return
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, row in enumerate(value):
            _assert_no_outer_context(row, path=f"{path}[{index}]")


def _source_sort_key(value: Any) -> tuple[str, str, str, str]:
    if not isinstance(value, Mapping):
        return ("~", "~", "~", repr(value))
    return (
        str(value.get("source_id") or ""),
        str(value.get("content_hash") or ""),
        str(value.get("parser_identity") or value.get("parser_route") or ""),
        str(value.get("revision") or ""),
    )


def _canonicalize_product_snapshot(snapshot: Mapping[str, Any]) -> Dict[str, Any]:
    """Remove incidental upload ordering from evidence presented to the operator.

    Project revision identity and content remain unchanged. Only collections whose
    semantics are set-like evidence inventories are reordered by stable identities.
    This makes upload/source order an explicit perturbation invariant rather than a
    hidden influence on the model prompt.
    """

    body = deepcopy(dict(snapshot))
    for key in _SOURCE_COLLECTION_KEYS:
        value = body.get(key)
        if not isinstance(value, list):
            continue
        body[key] = sorted(value, key=_source_sort_key)
    return body


def _known_source_ids(context: Mapping[str, Any]) -> set[str]:
    known: set[str] = set()
    for key in ("registered_sources", "parsed_sources", "parser_runs"):
        for row in list(context.get(key) or []):
            if not isinstance(row, Mapping):
                continue
            source_id = str(row.get("source_id") or "").strip()
            if source_id:
                known.add(source_id)
    return known


def _referenced_source_ids(session: Mapping[str, Any]) -> set[str]:
    referenced: set[str] = set()
    for key in ("requirements", "architecture_candidates", "actions"):
        for row in list(session.get(key) or []):
            if not isinstance(row, Mapping):
                continue
            for value in list(row.get("source_ids") or []):
                source_id = str(value or "").strip()
                if source_id:
                    referenced.add(source_id)
    return referenced


def _assert_evidence_references_resolve(session: Mapping[str, Any]) -> None:
    context = session.get("context") or {}
    if not isinstance(context, Mapping):
        raise CleanroomContractError("embedded operator session is missing sanitized context")
    known = _known_source_ids(context)
    referenced = _referenced_source_ids(session)
    invented = sorted(referenced - known)
    if invented:
        raise CleanroomContractError(
            "embedded operator invented product evidence identities: " + ", ".join(invented)
        )


def run_embedded_operator_turn(
    project_id: str,
    project_revision: int,
    snapshot: Mapping[str, Any],
    *,
    mission: str,
    constraints: Mapping[str, Any] | None = None,
    model_profile: str = "deep_synthesis",
    model: str | None = None,
    max_actions: int = 8,
    llm_callable: Callable[..., Dict[str, Any]] | None = None,
) -> Dict[str, Any]:
    """Run one source-blind operator turn against product-visible project state.

    The caller may inject an LLM callable for deterministic evaluation, but cannot pass
    repository implementation detail, hidden fixture answers, or outer-agent analysis.
    The returned model session is still proposal-only and has zero authority effect.
    """

    _assert_no_outer_context(snapshot, path="snapshot")
    _assert_no_outer_context(constraints or {}, path="constraints")
    canonical_snapshot = _canonicalize_product_snapshot(snapshot)

    session = run_ai_project_orchestrator(
        project_id,
        project_revision,
        canonical_snapshot,
        mission=mission,
        constraints=constraints,
        model_profile=model_profile,
        model=model,
        max_actions=max_actions,
        llm_callable=llm_callable,
    )
    _assert_no_outer_context(session.get("context") or {}, path="operator_context")
    _assert_evidence_references_resolve(session)

    return {
        "schema_version": SCHEMA_VERSION,
        "role": ROLE,
        "project_id": project_id,
        "project_revision": int(project_revision),
        "isolation": {
            "repository_source_visible": False,
            "golden_answer_visible": False,
            "outer_agent_analysis_visible": False,
            "product_visible_context_only": True,
            "evidence_references_must_resolve": True,
            "source_order_canonicalized": True,
        },
        "operator_session": session,
        "authority_effect": "none",
        "automatic_execution": False,
        "physical_authority_unchanged": True,
        "fabrication_authorized": False,
        "firmware_flash_authorized": False,
        "power_on_authorized": False,
        "motion_authorized": False,
        "operational_authorized": False,
        "release_authorized": False,
    }

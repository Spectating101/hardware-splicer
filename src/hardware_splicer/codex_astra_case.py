"""Build model-visible Codex/Astra case input without leaking outer evaluator labels."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from .cleanroom_replay import ReplayCase
from .cleanroom_primary_source_spi_flash_experiment import (
    build_primary_source_spi_flash_case,
    validate_primary_source_spi_flash_case,
)
from .cleanroom_unseen_spi_flash_experiment import (
    build_unseen_spi_flash_cases,
    validate_unseen_spi_flash_corpus,
)
from .external_mcp_trace_audit import snapshot_source_ids

FROZEN_CASE_INSTRUCTIONS = """You are the external reasoning engine in a frozen Hardware-Splicer proof run.
You do not have Hardware-Splicer source code, hidden tests, evaluator metadata, expected answers, or any outer-engineer analysis. Operate only through the Hardware-Splicer MCP tools and the product-visible state in this request.

Required operating discipline:
1. Start with hs_backend_status.
2. Discover relevant canonical operations with hs_backend_list_operations.
3. Describe unfamiliar operations before invoking them.
4. Work only on the experiment_project_id given in this request. Never inspect, mutate, or delete unrelated projects.
5. Treat only the supplied product-visible project state as evidence for this frozen cleanroom case. Do not import web/repository/external evidence or invent new evidence identities.
6. Preserve unresolved component identity, electrical limits, package/pinout, translator mapping, supply implementation, source conflicts, and physical evidence as unresolved unless the supplied product-visible evidence actually resolves them.
7. Never invent bench measurements, physical observations, fabrication readiness, power-on readiness, or human authorization.
8. A model/tool conclusion is not physical evidence and grants no physical authority.
9. Use deterministic Hardware-Splicer checks, evidence, revision, review, and packaging surfaces where relevant. Tool/model failures are evidence; do not hide them or silently rewrite the problem.
10. If a full machine plan is unsupported or domain-incompatible, use the project-scoped bounded pre-fabrication-plan operation instead of placing derived engineering work in a generic snapshot. Do not invent a machineProject merely to satisfy review.
11. Produce the strongest defensible pre-fabrication project state and next-action package that the available evidence supports. Do not optimize toward a guessed expected architecture.
12. Before finishing, read back the resulting canonical project state and explicitly summarize remaining blockers and unresolved facts.
13. Do not use repository/source-code operations or seek evaluator information even if a backend operation appears to make that possible.

This is an independent experimental case. You are not told whether related variants exist."""


def frozen_case_instructions() -> str:
    return FROZEN_CASE_INSTRUCTIONS


def _persisted_mission(snapshot: Mapping[str, Any]) -> str:
    for key in ("mission", "goal", "intent", "brief"):
        value = snapshot.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, Mapping):
            for nested_key in (
                "mission",
                "goal",
                "intent",
                "brief",
                "description",
            ):
                nested = value.get(nested_key)
                if isinstance(nested, str) and nested.strip():
                    return nested.strip()
    raise ValueError("external MCP proof case has no persisted mission/goal/intent/brief")


def build_case_input(case: ReplayCase, project_id: str) -> str:
    snapshot = dict(case.snapshot)
    mission = _persisted_mission(snapshot)
    return (
        "Execute this Hardware-Splicer engineering mission through MCP.\n\n"
        f"experiment_project_id: {project_id}\n"
        f"mission: {mission}\n"
        "product_visible_project_state:\n"
        + json.dumps(snapshot, indent=2, ensure_ascii=False, sort_keys=True)
    )


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def _sha256(value: Any) -> str:
    if not isinstance(value, str):
        value = _canonical_json(value)
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def select_exact_case(case_id: str) -> ReplayCase:
    primary = build_primary_source_spi_flash_case()
    if case_id == primary.case_id:
        validation = validate_primary_source_spi_flash_case()
        if not validation.get("pass"):
            raise ValueError(
                "refusing Codex case packaging because primary-source case validation failed"
            )
        return primary
    validation = validate_unseen_spi_flash_corpus()
    if not validation.get("pass"):
        raise ValueError("refusing Codex case packaging because frozen corpus validation failed")
    matches = [case for case in build_unseen_spi_flash_cases() if case.case_id == case_id]
    if len(matches) != 1:
        raise ValueError(f"unknown or non-unique frozen case_id: {case_id!r}")
    return matches[0]


def build_codex_case_package(
    *,
    case_id: str,
    experiment_project_id: str,
) -> dict[str, Any]:
    if not experiment_project_id.strip():
        raise ValueError("experiment_project_id must be non-empty")
    case = select_exact_case(case_id)
    instructions = frozen_case_instructions()
    input_text = build_case_input(case, experiment_project_id)
    snapshot = dict(case.snapshot)
    return {
        "model_visible": {
            "mission_text": input_text,
            "developer_instructions": instructions,
        },
        "observer_only": {
            "schema_version": "hardware_splicer.codex_astra_case_package.v1",
            "case_id": case.case_id,
            "equivalence_group": case.equivalence_group,
            "perturbation_kind": case.perturbation_kind,
            "case_metadata": dict(case.metadata or {}),
            "case_project_revision": case.project_revision,
            "experiment_project_id": experiment_project_id,
            "snapshot": snapshot,
            "snapshot_sha256": _sha256(snapshot),
            "product_visible_source_ids": sorted(snapshot_source_ids(snapshot)),
            "instructions_sha256": _sha256(instructions),
            "input_sha256": _sha256(input_text),
            "outer_labels_visible_to_model": False,
            "provider_network_io_performed": False,
            "model_inference_performed": False,
            "physical_authority_granted": False,
        },
    }

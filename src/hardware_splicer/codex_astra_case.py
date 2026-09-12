"""Build model-visible Codex/Astra case input without leaking outer evaluator labels."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from .cleanroom_replay import ReplayCase
from .cleanroom_primary_source_spi_flash_experiment import (
    BLIND_CASE_ID,
    IDENTITY_CONFLICT_CASE_ID,
    RAW_DOCUMENT_CASE_ID,
    RAW_DOCUMENT_V2_CASE_ID,
    build_primary_source_identity_conflict_case,
    build_primary_source_spi_flash_case,
    build_primary_source_spi_flash_blind_case,
    build_primary_source_spi_flash_raw_document_case,
    build_primary_source_spi_flash_raw_document_v2_case,
    validate_blind_primary_source_cases,
    validate_primary_source_spi_flash_case,
    validate_raw_document_primary_source_case,
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

BLIND_FROZEN_CASE_INSTRUCTIONS = """You are the external reasoning engine in a blinded, frozen Hardware-Splicer proof run.
You do not have Hardware-Splicer source code, hidden tests, evaluator metadata, expected answers, or any outer-engineer analysis. Operate only through the Hardware-Splicer MCP tools and the product-visible state in this request.

Required operating discipline:
1. Start with hs_backend_status.
2. Load hs_backend_task_manifest for bounded_pre_fabrication once. Follow its canonical_record_contract exactly as a serialization contract; it defines fields, not the engineering answer. Use broad operation discovery only if the required canonical operation is absent from that manifest.
3. Work only on the experiment_project_id given in this request. Never inspect, mutate, or delete unrelated projects.
4. Treat only the supplied product-visible project state as evidence. Do not import web/repository/external evidence or invent evidence identities.
5. Derive conclusions from the visible evidence rather than guessing an evaluator. Preserve distinct source and claim identities when they disagree.
6. Preserve unresolved component identity, electrical limits, package/pinout, translator mapping, supply implementation, source conflicts, and physical evidence unless visible evidence resolves them.
7. Never invent bench measurements, physical observations, fabrication readiness, power-on readiness, or human authorization.
8. A model/tool conclusion is not physical evidence and grants no physical authority.
9. Tool failures are evidence; do not hide them or silently rewrite the problem.
10. If a full machine plan is unsupported or domain-incompatible, use the project-scoped bounded pre-fabrication-plan operation. Do not invent a machineProject merely to satisfy review.
11. Produce the strongest defensible pre-fabrication state and dependency-aware next actions supported by the evidence.
12. Use the assurance view to inspect source/claim dependencies and reference integrity before packaging.
13. Before finishing, read back canonical state and explicitly summarize blockers, conflicts, and unresolved facts.
14. Do not use repository/source-code operations or seek evaluator information even if a backend operation appears to allow it.

This is an independent experimental case. You are not told the expected disposition or whether related variants exist."""

RAW_DOCUMENT_FROZEN_CASE_INSTRUCTIONS = """You are the external reasoning engine in a blinded, frozen Hardware-Splicer raw-document proof run.
You do not have Hardware-Splicer source code, hidden tests, evaluator metadata, expected values, curated document claims, or outer-engineer analysis. Operate only through the Hardware-Splicer MCP tools and the product-visible state in this request.

Required operating discipline:
1. Start with hs_backend_status.
2. Load hs_backend_task_manifest for document_grounded_pre_fabrication once. Follow its canonical schemas and record contract exactly. Use broad operation discovery only if a required operation is absent.
3. Work only on the experiment_project_id given in this request. The project is already present at revision 1; load it rather than replacing its initial snapshot.
4. Treat only the canonical project state and hash-bound document content returned by Hardware-Splicer as evidence. Do not import web, repository, or external evidence.
5. The documentExtractionTargets are questions, not facts. For every target, inspect/search the specified source, read the relevant exact page, and register a proposed claim using the supplied claim_id and source_id. supporting_text must quote text actually returned for that page.
6. Machine-extracted text may lose layout. Preserve ambiguity where tables, diagrams, symbols, footnotes, or page extraction do not support a confident interpretation. Never claim that text extraction proves visual-layout fidelity.
7. Model-proposed document claims remain proposed and unreviewed. Do not upgrade them to declared, observed, measured, verified, or authorized authority.
8. Preserve unresolved component identity, package/pinout, programmer behavior, supply implementation, timing/load/protection design, and physical evidence unless visible evidence resolves them.
9. Never invent bench measurements, physical observations, fabrication readiness, power-on readiness, or human authorization. A model/tool conclusion grants no physical authority.
10. Use the project-scoped bounded pre-fabrication-plan operation for derived engineering work. Reference only claims that were successfully registered into canonical state.
11. Use the assurance view to inspect reference integrity, then create the deterministic engineering package.
12. Before finishing, read back canonical state and explicitly summarize blockers, extraction limitations, and unresolved facts.
13. Tool failures are evidence; do not hide them or silently rewrite the problem.
14. Do not use repository/source-code operations or seek evaluator information even if a backend operation appears to allow it.

This is an independent experimental case. You are not told the expected extracted values or engineering disposition."""

RAW_DOCUMENT_V2_FROZEN_CASE_INSTRUCTIONS = RAW_DOCUMENT_FROZEN_CASE_INSTRUCTIONS.replace(
    "12. Before finishing, read back canonical state and explicitly summarize blockers, extraction limitations, and unresolved facts.",
    "12. Before finishing, read back canonical state. In the terminal report, remaining_blockers and unresolved_facts must contain only exact strings copied from the initial engineeringBlockers catalog; do not paraphrase or add new blocker strings there.",
).replace(
    "\n\nThis is an independent experimental case.",
    """
15. In proposed_logical_mapping rows, host and dut contain only bare project signal names (for example, SCLK and CLK). Put translator pins or route notation in rationale, never in those two fields.
16. Candidate status is semantic: use rejected when document-derived topology establishes that a candidate cannot realize the required signal-direction split; use held only when evidence is insufficient to decide.

This is an independent experimental case.""",
)


def frozen_case_instructions() -> str:
    return FROZEN_CASE_INSTRUCTIONS


def case_instructions(case_id: str) -> str:
    if case_id == RAW_DOCUMENT_V2_CASE_ID:
        return RAW_DOCUMENT_V2_FROZEN_CASE_INSTRUCTIONS
    if case_id == RAW_DOCUMENT_CASE_ID:
        return RAW_DOCUMENT_FROZEN_CASE_INSTRUCTIONS
    return (
        BLIND_FROZEN_CASE_INSTRUCTIONS
        if case_id in {BLIND_CASE_ID, IDENTITY_CONFLICT_CASE_ID}
        else FROZEN_CASE_INSTRUCTIONS
    )


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
    if case_id in {BLIND_CASE_ID, IDENTITY_CONFLICT_CASE_ID}:
        validation = validate_blind_primary_source_cases()
        if not validation.get("pass"):
            raise ValueError(
                "refusing Codex case packaging because blinded primary-source case validation failed"
            )
        return (
            build_primary_source_spi_flash_blind_case()
            if case_id == BLIND_CASE_ID
            else build_primary_source_identity_conflict_case()
        )
    if case_id in {RAW_DOCUMENT_CASE_ID, RAW_DOCUMENT_V2_CASE_ID}:
        validation = validate_raw_document_primary_source_case(case_id=case_id)
        if not validation.get("pass"):
            raise ValueError(
                "refusing Codex case packaging because raw-document case validation failed"
            )
        return (
            build_primary_source_spi_flash_raw_document_case()
            if case_id == RAW_DOCUMENT_CASE_ID
            else build_primary_source_spi_flash_raw_document_v2_case()
        )
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
    instructions = case_instructions(case.case_id)
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

"""Canonical project-intake truth boundary.

The historical project-intake planner is intentionally rich in demo/compatibility
scaffolding. It may synthesize controllers, rails, actuators, dimensions, mission text,
and catalog recipes from an archetype. That remains useful for explicit offline demos,
but it is not an acceptable source of engineering truth on model-first paths.

This module provides a separate entry point with a hard epistemic split:

- explicit offline compatibility -> the historical planner may run, with visible legacy
  provenance and zero authority upgrade;
- model-first -> the historical planner is not called at all. Only user-declared intake
  fields plus a bounded semantic architecture proposal may leave this boundary.

No output from this module authorizes compilation, fabrication, flashing, power, motion,
or release.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable, Dict, Mapping

from .build_compiler import CATALOG_BUILD_IDS
from .integrations.llm_policy import offline_salvage_enabled
from .integrations.qwen_intake_normalize import (
    UNRESOLVED_ARCHETYPE,
    detect_archetype_proposal,
)


SCHEMA_VERSION = "hardware_splicer.project_intake_truth.v1"
SCENARIO_SCHEMA = "hardware_splicer.project_intake_truth_scenario.v1"


def _mapping(value: Any) -> dict[str, Any]:
    return deepcopy(dict(value)) if isinstance(value, Mapping) else {}


def _sequence(value: Any) -> list[Any]:
    return list(value) if isinstance(value, (list, tuple)) else []


def _goal(intake: Mapping[str, Any]) -> str:
    for key in ("goal", "mission", "intent", "brief", "project_name", "name"):
        value = intake.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, Mapping):
            for nested_key in ("goal", "mission", "intent", "brief", "description"):
                nested = value.get(nested_key)
                if isinstance(nested, str) and nested.strip():
                    return nested.strip()
    return ""


def declared_intake_parts(intake: Mapping[str, Any]) -> list[Dict[str, Any]]:
    """Return parts exactly as persisted/declared, without inferred electrical facts."""
    raw = (
        intake.get("available_parts")
        if intake.get("available_parts") is not None
        else intake.get("parts")
        if intake.get("parts") is not None
        else intake.get("resources")
        if intake.get("resources") is not None
        else []
    )
    return [deepcopy(dict(row)) for row in _sequence(raw) if isinstance(row, Mapping)]


def _explicit_build_id(intake: Mapping[str, Any]) -> str | None:
    constraints = _mapping(intake.get("constraints"))
    for value in (
        intake.get("target_build_id"),
        intake.get("build_id"),
        constraints.get("target_build_id"),
        constraints.get("build_id"),
    ):
        candidate = str(value or "").strip()
        if candidate and candidate in CATALOG_BUILD_IDS:
            return candidate
    return None


def _explicit_archetype(intake: Mapping[str, Any]) -> str | None:
    candidate = str(intake.get("archetype") or "").strip()
    return candidate or None


def _safe_proposal(value: Mapping[str, Any] | None) -> Dict[str, Any]:
    body = _mapping(value)
    status = str(body.get("status") or "unresolved")
    build_id = str(body.get("build_id") or "").strip() or None
    if build_id not in CATALOG_BUILD_IDS:
        build_id = None
    archetype = str(body.get("archetype") or UNRESOLVED_ARCHETYPE).strip() or UNRESOLVED_ARCHETYPE
    questions = [
        str(row).strip()
        for row in _sequence(body.get("unresolved_questions"))[:24]
        if str(row).strip()
    ]
    try:
        confidence = max(0.0, min(1.0, float(body.get("confidence") or 0.0)))
    except (TypeError, ValueError):
        confidence = 0.0
    return {
        "schema_version": str(body.get("schema_version") or "hardware_splicer.qwen_intake_normalize.v2"),
        "status": status,
        "archetype": archetype,
        "build_id": build_id,
        "source": str(body.get("source") or "unresolved"),
        "confidence": confidence,
        "reasoning": str(body.get("reasoning") or ""),
        "unresolved_questions": questions,
        "authority_effect": "none",
        "automatic_execution": False,
    }


def architecture_truth(
    intake: Mapping[str, Any],
    proposal: Mapping[str, Any] | None,
    *,
    legacy_plan: Mapping[str, Any] | None = None,
    compatibility_mode: bool = False,
) -> Dict[str, Any]:
    """Resolve what architecture state may be treated as canonical at intake."""
    explicit_build = _explicit_build_id(intake)
    explicit_archetype = _explicit_archetype(intake)
    if explicit_build or explicit_archetype:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "declared",
            "archetype": explicit_archetype or UNRESOLVED_ARCHETYPE,
            "build_id": explicit_build,
            "source": "declared",
            "confidence": 1.0,
            "reasoning": "Architecture/build constraint was explicitly persisted by the project/user.",
            "unresolved_questions": ([] if explicit_build else ["Resolve a bounded build candidate for the declared archetype before execution."]),
            "authority_effect": "none",
            "automatic_execution": False,
        }

    safe = _safe_proposal(proposal)
    if safe["status"] == "model_proposed" and safe["build_id"]:
        return {
            **safe,
            "schema_version": SCHEMA_VERSION,
            "status": "model_proposed",
            "source": "model_proposed",
            "authority_effect": "none",
            "automatic_execution": False,
        }

    if compatibility_mode:
        legacy = _mapping(legacy_plan)
        scenario = _mapping(legacy.get("scenario"))
        compile_spec = _mapping(scenario.get("compile_spec"))
        salvage = _mapping(legacy.get("salvage_package"))
        legacy_build = str(
            compile_spec.get("build_id")
            or salvage.get("recommended_build_id")
            or ""
        ).strip() or None
        if legacy_build not in CATALOG_BUILD_IDS:
            legacy_build = None
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "legacy_compatibility",
            "archetype": str(legacy.get("archetype") or UNRESOLVED_ARCHETYPE),
            "build_id": legacy_build,
            "source": "legacy_compatibility",
            "confidence": 0.0,
            "reasoning": "Historical intake scaffold retained only because explicit offline compatibility is active.",
            "unresolved_questions": [],
            "authority_effect": "none",
            "automatic_execution": False,
        }

    questions = list(safe.get("unresolved_questions") or [])
    if not questions:
        questions = [
            str(safe.get("reasoning") or "No bounded architecture is defensibly resolved from current project evidence.")
        ]
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "unresolved",
        "archetype": UNRESOLVED_ARCHETYPE,
        "build_id": None,
        "source": "unresolved",
        "confidence": 0.0,
        "reasoning": str(safe.get("reasoning") or "Architecture remains unresolved."),
        "unresolved_questions": questions,
        "authority_effect": "none",
        "automatic_execution": False,
    }


def _compatibility_audit(legacy_plan: Mapping[str, Any]) -> Dict[str, Any]:
    scenario = _mapping(legacy_plan.get("scenario"))
    compile_spec = _mapping(scenario.get("compile_spec"))
    salvage = _mapping(legacy_plan.get("salvage_package"))
    return {
        "historical_planner_ran": True,
        "legacy_archetype": str(legacy_plan.get("archetype") or ""),
        "legacy_expected_authority": str(legacy_plan.get("expected_authority") or ""),
        "legacy_build_id": str(
            compile_spec.get("build_id") or salvage.get("recommended_build_id") or ""
        ) or None,
        "legacy_scenario_present": bool(scenario),
        "legacy_salvage_context_present": bool(salvage),
        "canonical_authority": "none",
    }


def _model_first_plan(
    intake: Mapping[str, Any],
    proposal: Mapping[str, Any] | None,
) -> Dict[str, Any]:
    truth = architecture_truth(intake, proposal, compatibility_mode=False)
    goal = _goal(intake)
    parts = declared_intake_parts(intake)
    constraints = _mapping(intake.get("constraints"))
    project_name = str(intake.get("project_name") or intake.get("name") or goal or "project").strip()
    compile_spec: Dict[str, Any] = {}
    if truth.get("build_id"):
        compile_spec = {
            "build_id": truth["build_id"],
            "architecture_candidate_only": True,
            "automatic_execution": False,
            "authority_effect": "none",
        }
    questions = list(truth.get("unresolved_questions") or [])
    if truth.get("status") == "model_proposed":
        questions = [
            *questions,
            "Human architecture review is required before any compile/fabrication/flash/power action.",
        ]
    if truth.get("status") == "unresolved" and not questions:
        questions = ["Resolve architecture from project evidence before creating a compile candidate."]
    return {
        "schema_version": SCHEMA_VERSION,
        "project_name": project_name,
        "goal": goal,
        "normalized_intake": deepcopy(dict(intake)),
        "declared_parts": parts,
        "declared_constraints": constraints,
        "archetype": str(truth.get("archetype") or UNRESOLVED_ARCHETYPE),
        "architecture_truth": truth,
        "architecture_status": truth.get("status"),
        "architecture_source": truth.get("source"),
        "expected_authority": "project_intake",
        "planning_confidence": float(truth.get("confidence") or 0.0),
        "assumptions": [],
        "missing_info": list(dict.fromkeys(str(row) for row in questions if str(row))),
        "scenario": {
            "schema_version": SCENARIO_SCHEMA,
            "status": "candidate" if truth.get("build_id") else "blocked",
            "compile_spec": compile_spec,
            "declared_part_count": len(parts),
            "architecture_review_required": True,
            "automatic_execution": False,
            "fabrication_authorized": False,
            "firmware_flash_authorized": False,
            "power_on_authorized": False,
            "motion_authorized": False,
            "release_authorized": False,
        },
        "compatibility_scaffold": {
            "historical_planner_ran": False,
            "canonical_authority": "none",
        },
        "authority_effect": "none",
        "automatic_execution": False,
        "fabrication_authorized": False,
        "firmware_flash_authorized": False,
        "power_on_authorized": False,
        "motion_authorized": False,
        "release_authorized": False,
    }


def plan_project_from_intake_truthful(
    intake: Mapping[str, Any],
    *,
    skip_vision: bool = False,
    architecture_proposal_callable: Callable[[str, list[Mapping[str, Any]]], Mapping[str, Any]] | None = None,
    legacy_planner: Callable[..., Mapping[str, Any]] | None = None,
) -> Dict[str, Any]:
    """Plan intake without allowing compatibility synthesis into model-first truth.

    The legacy planner is imported lazily and is *never called* on model-first paths.
    Explicit architecture/build state also bypasses semantic model interpretation.
    Dependency injection exists so tests can prove those boundaries rather than infer them.
    """
    body = deepcopy(dict(intake or {}))
    compatibility_mode = offline_salvage_enabled()

    if compatibility_mode:
        if legacy_planner is None:
            from .project_intake import plan_project_from_intake

            legacy_planner = plan_project_from_intake
        legacy = dict(legacy_planner(body, skip_vision=skip_vision))
        truth = architecture_truth(
            body,
            None,
            legacy_plan=legacy,
            compatibility_mode=True,
        )
        legacy["project_intake_truth_schema"] = SCHEMA_VERSION
        legacy["architecture_truth"] = truth
        legacy["architecture_status"] = truth["status"]
        legacy["architecture_source"] = truth["source"]
        legacy["compatibility_scaffold"] = _compatibility_audit(legacy)
        legacy["authority_effect"] = "none"
        legacy["automatic_execution"] = False
        return legacy

    if _explicit_build_id(body) or _explicit_archetype(body):
        return _model_first_plan(body, None)

    proposal_fn = architecture_proposal_callable or detect_archetype_proposal
    proposal = dict(proposal_fn(_goal(body), declared_intake_parts(body)))
    return _model_first_plan(body, proposal)

"""Cross-surface audit for model-first semantic authority leakage.

The individual Hardware Splicer boundaries intentionally preserve some legacy data for
explicit offline compatibility and for audit/debugging. Presence is not the problem;
effective authority is. This module gives the outer System Engineer one deterministic
check over the product outputs that matter:

- project architecture/mode/genre provenance;
- bounded circuit-dispatch provenance;
- salvage physical identity and module overrides;
- topology part-role projection;
- change-impact scope/target/source binding;
- physical authority flags.

It does not decide whether a model proposal is *correct*. It decides whether a model-first
run remained inside the declared epistemic constitution.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping, Sequence


SCHEMA_VERSION = "hardware_splicer.model_first_truth_audit.v1"
_LEGACY_SOURCES = {
    "legacy_keyword",
    "legacy_heuristic",
    "legacy_compatibility",
    "heuristic",
    "regex",
}
_PHYSICAL_AUTHORITY_KEYS = {
    "fabrication_authorized",
    "firmware_flash_authorized",
    "flash_authorized",
    "power_on_authorized",
    "motion_authorized",
    "operational_authorized",
    "operation_authorized",
    "release_authorized",
}
_ALLOWED_IDENTITY_STATUSES_WITH_MODULE = {
    "declared",
    "model_proposed",
    "proposed_design_component",
}
_ALLOWED_IDENTITY_SOURCES_WITH_MODULE = {
    "declared_catalog_identity",
    "model_identity_proposed",
    "donor_functional_salvage_declared",
    "workshop_design_proposal",
}


def _mapping(value: Any) -> Dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if hasattr(value, "to_dict"):
        try:
            rendered = value.to_dict()
            return dict(rendered) if isinstance(rendered, Mapping) else {}
        except Exception:
            return {}
    if hasattr(value, "model_dump"):
        try:
            rendered = value.model_dump(mode="json")
            return dict(rendered) if isinstance(rendered, Mapping) else {}
        except Exception:
            return {}
    return {}


def _rows(value: Any) -> list[Dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return [_mapping(row) for row in value if _mapping(row)]


def _legacy_source(value: Any) -> bool:
    token = str(value or "").strip().lower()
    return token in _LEGACY_SOURCES or token.startswith("legacy_")


def _violation(
    code: str,
    path: str,
    message: str,
    *,
    observed: Any = None,
    severity: str = "blocking",
) -> Dict[str, Any]:
    return {
        "code": code,
        "path": path,
        "message": message,
        "observed": observed,
        "severity": severity,
    }


def _audit_authority(value: Any, *, path: str, violations: list[Dict[str, Any]]) -> None:
    if isinstance(value, Mapping):
        for raw_key, child in value.items():
            key = str(raw_key)
            child_path = f"{path}.{key}" if path else key
            if key in _PHYSICAL_AUTHORITY_KEYS and child is True:
                violations.append(
                    _violation(
                        "PHYSICAL_AUTHORITY_OPEN",
                        child_path,
                        "Model-first semantic/proposal output opened physical authority.",
                        observed=True,
                    )
                )
            if key == "authority_effect" and child not in (None, "", "none"):
                violations.append(
                    _violation(
                        "SEMANTIC_AUTHORITY_EFFECT",
                        child_path,
                        "Semantic/model output must have zero engineering authority effect.",
                        observed=child,
                    )
                )
            _audit_authority(child, path=child_path, violations=violations)
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, child in enumerate(value):
            _audit_authority(child, path=f"{path}[{index}]", violations=violations)


def _audit_project(plan: Mapping[str, Any], violations: list[Dict[str, Any]]) -> None:
    architecture_source = plan.get("architecture_source") or _mapping(plan.get("architecture_truth")).get("source")
    if _legacy_source(architecture_source):
        violations.append(
            _violation(
                "LEGACY_ARCHITECTURE_AUTHORITY",
                "project.architecture_source",
                "Legacy semantic architecture became effective project truth.",
                observed=architecture_source,
            )
        )
    for field, code in (
        ("project_mode_proposal", "LEGACY_PROJECT_MODE"),
        ("robot_genre_proposal", "LEGACY_ROBOT_GENRE"),
    ):
        proposal = _mapping(plan.get(field))
        if _legacy_source(proposal.get("source")):
            violations.append(
                _violation(
                    code,
                    f"project.{field}.source",
                    "Legacy semantic classifier became effective on a model-first project path.",
                    observed=proposal.get("source"),
                )
            )
    compatibility = _mapping(plan.get("compatibility_scaffold"))
    if compatibility.get("historical_planner_ran") is True:
        violations.append(
            _violation(
                "LEGACY_PROJECT_INTAKE_EXECUTED",
                "project.compatibility_scaffold.historical_planner_ran",
                "Historical intake scaffold executed on a model-first canonical plan.",
                observed=True,
            )
        )


def _audit_circuit(candidate: Mapping[str, Any], violations: list[Dict[str, Any]]) -> None:
    metadata = _mapping(candidate.get("metadata"))
    dispatch = _mapping(metadata.get("dispatch"))
    if dispatch.get("legacy_keyword_dispatch_used") is True:
        violations.append(
            _violation(
                "LEGACY_CIRCUIT_DISPATCH",
                "circuit.metadata.dispatch.legacy_keyword_dispatch_used",
                "Model-first circuit synthesis executed the keyword dispatcher.",
                observed=True,
            )
        )
    if _legacy_source(dispatch.get("selection_source")):
        violations.append(
            _violation(
                "LEGACY_CIRCUIT_SELECTION_SOURCE",
                "circuit.metadata.dispatch.selection_source",
                "Effective circuit planner selection came from a legacy semantic source.",
                observed=dispatch.get("selection_source"),
            )
        )


def _audit_salvage(package: Mapping[str, Any], violations: list[Dict[str, Any]]) -> None:
    legacy_authority = package.get("legacy_planner_architecture_authority")
    if legacy_authority not in (None, "ignored", "not_executed"):
        violations.append(
            _violation(
                "LEGACY_SALVAGE_ARCHITECTURE_AUTHORITY",
                "salvage.legacy_planner_architecture_authority",
                "Legacy salvage planner retained effective architecture authority.",
                observed=legacy_authority,
            )
        )
    legacy_context = _mapping(package.get("legacy_planner_context"))
    if legacy_authority == "not_executed" and legacy_context.get("executed") is True:
        violations.append(
            _violation(
                "LEGACY_SALVAGE_EXECUTION_STATE_DIVERGENCE",
                "salvage.legacy_planner_context.executed",
                "Salvage package claims legacy planners were not executed but audit context says they ran.",
                observed=True,
            )
        )
    build_selection = _mapping(package.get("build_selection"))
    if _legacy_source(build_selection.get("source")) or build_selection.get("legacy_fallback_used") is True:
        violations.append(
            _violation(
                "LEGACY_BUILD_SELECTION_EFFECTIVE",
                "salvage.build_selection",
                "Legacy build-selection heuristic became effective in model-first salvage.",
                observed={
                    "source": build_selection.get("source"),
                    "legacy_fallback_used": build_selection.get("legacy_fallback_used"),
                },
            )
        )
    identity_authority = package.get("physical_identity_authority")
    if identity_authority not in (None, "declared_or_validated_exact_only"):
        violations.append(
            _violation(
                "PHYSICAL_IDENTITY_POLICY_WEAKENED",
                "salvage.physical_identity_authority",
                "Physical inventory identity is not constrained to declared/validated exact identity.",
                observed=identity_authority,
            )
        )
    boundary = _mapping(_mapping(package.get("salvage_resolution")).get("physical_identity_boundary"))
    if boundary.get("functional_similarity_is_identity") not in (None, False):
        violations.append(
            _violation(
                "FUNCTIONAL_SIMILARITY_AS_IDENTITY",
                "salvage.salvage_resolution.physical_identity_boundary.functional_similarity_is_identity",
                "Functional similarity was allowed to stand in for physical identity.",
                observed=boundary.get("functional_similarity_is_identity"),
            )
        )

    rows = _rows(package.get("resolved_modules"))
    effective_module_ids: set[str] = set()
    for index, row in enumerate(rows):
        module_id = str(row.get("module_id") or "").strip()
        source = str(row.get("source") or "").strip()
        identity_status = str(row.get("identity_status") or "").strip()
        if source in {"heuristic", "regex", "qwen_salvage_with_heuristic_fallback"} or source.startswith("legacy_"):
            violations.append(
                _violation(
                    "LEGACY_MODULE_IDENTITY_SOURCE",
                    f"salvage.resolved_modules[{index}].source",
                    "A resolved module identity came from a legacy/fuzzy semantic source.",
                    observed=source,
                )
            )
        if source == "unresolved_capability_gap" and module_id:
            violations.append(
                _violation(
                    "CAPABILITY_GAP_HAS_CONCRETE_IDENTITY",
                    f"salvage.resolved_modules[{index}].module_id",
                    "An unresolved capability gap was silently assigned a concrete catalog identity.",
                    observed=module_id,
                )
            )
        if row.get("external_capability_only") is True and module_id:
            violations.append(
                _violation(
                    "EXTERNAL_DONOR_STANDIN_IDENTITY",
                    f"salvage.resolved_modules[{index}].module_id",
                    "External donor capability was represented by a catalog stand-in identity.",
                    observed=module_id,
                )
            )
        if module_id:
            if identity_status not in _ALLOWED_IDENTITY_STATUSES_WITH_MODULE or source not in _ALLOWED_IDENTITY_SOURCES_WITH_MODULE:
                violations.append(
                    _violation(
                        "UNTRUSTED_CONCRETE_MODULE_BINDING",
                        f"salvage.resolved_modules[{index}]",
                        "Concrete module ID lacks an allowed declared/exact/proposal provenance state.",
                        observed={
                            "module_id": module_id,
                            "source": source,
                            "identity_status": identity_status,
                        },
                    )
                )
            else:
                effective_module_ids.add(module_id)

    overrides = _mapping(package.get("module_overrides"))
    for role, module_id_value in overrides.items():
        module_id = str(module_id_value or "").strip()
        if module_id and module_id not in effective_module_ids:
            violations.append(
                _violation(
                    "OVERRIDE_WITHOUT_TRUSTED_BINDING",
                    f"salvage.module_overrides.{role}",
                    "Module override references a catalog identity not present in trusted resolved/proposed rows.",
                    observed=module_id,
                )
            )

    splice_target = _mapping(_mapping(package.get("splice_plan")).get("target"))
    canonical_build = str(package.get("recommended_build_id") or "").strip() or None
    target_build = str(splice_target.get("recommended_build_id") or "").strip() or None
    if target_build != canonical_build:
        violations.append(
            _violation(
                "SPLICE_BUILD_TRUTH_DIVERGENCE",
                "salvage.splice_plan.target.recommended_build_id",
                "Effective splice-plan build recommendation diverges from canonical package build selection.",
                observed={"package": canonical_build, "splice_plan": target_build},
            )
        )

    propagation = _mapping(package.get("identity_propagation_audit"))
    if propagation:
        for finding in _rows(propagation.get("findings")):
            if finding.get("severity") != "blocking":
                continue
            violations.append(
                _violation(
                    "DOWNSTREAM_IDENTITY_PROPAGATION",
                    f"salvage.{finding.get('path') or finding.get('surface') or 'downstream'}",
                    str(finding.get("message") or "Downstream artifact launders an untrusted concrete module identity."),
                    observed={
                        "module_id": finding.get("module_id"),
                        "surface": finding.get("surface"),
                    },
                )
            )


def _audit_topology(topology: Mapping[str, Any], violations: list[Dict[str, Any]]) -> None:
    metadata = _mapping(topology.get("metadata"))
    if metadata.get("part_role_projection") == "legacy_name_keyword":
        violations.append(
            _violation(
                "LEGACY_TOPOLOGY_PART_ROLE",
                "topology.metadata.part_role_projection",
                "Human-facing labels were used to shape model-first topology roles.",
                observed=metadata.get("part_role_projection"),
            )
        )
    proposal = _mapping(metadata.get("robot_genre_proposal"))
    if _legacy_source(proposal.get("source")):
        violations.append(
            _violation(
                "LEGACY_TOPOLOGY_GENRE",
                "topology.metadata.robot_genre_proposal.source",
                "Legacy prose classifier selected model-first topology genre.",
                observed=proposal.get("source"),
            )
        )


def _audit_impact(graph: Mapping[str, Any], violations: list[Dict[str, Any]]) -> None:
    metadata = _mapping(graph.get("metadata"))
    if _legacy_source(metadata.get("impact_scope_source")):
        violations.append(
            _violation(
                "LEGACY_IMPACT_SCOPE",
                "impact.metadata.impact_scope_source",
                "Legacy keyword projection selected model-first impact domains.",
                observed=metadata.get("impact_scope_source"),
            )
        )
    for index, impact in enumerate(_rows(graph.get("impacts"))):
        if _mapping(impact.get("metadata")).get("target_projection") == "legacy_text_and_topology":
            violations.append(
                _violation(
                    "LEGACY_IMPACT_TARGET_PROJECTION",
                    f"impact.impacts[{index}].metadata.target_projection",
                    "Free-form trigger text selected an effective impact target.",
                    observed="legacy_text_and_topology",
                )
            )
    for index, trigger in enumerate(_rows(graph.get("triggers"))):
        if _mapping(trigger.get("metadata")).get("source_binding") == "legacy_text_match":
            violations.append(
                _violation(
                    "LEGACY_TRIGGER_SOURCE_BINDING",
                    f"impact.triggers[{index}].metadata.source_binding",
                    "Trigger prose was keyword-matched onto a source identity.",
                    observed="legacy_text_match",
                )
            )


def audit_model_first_truth(
    *,
    project_plan: Mapping[str, Any] | None = None,
    circuit_candidate: Any = None,
    salvage_package: Mapping[str, Any] | None = None,
    robot_topology: Mapping[str, Any] | None = None,
    change_impact: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    """Audit effective model-first truth/provenance without judging proposal quality."""
    violations: list[Dict[str, Any]] = []
    surfaces: list[str] = []

    project = _mapping(project_plan)
    if project:
        surfaces.append("project_plan")
        _audit_project(project, violations)
        _audit_authority(project, path="project", violations=violations)

    circuit = _mapping(circuit_candidate)
    if circuit:
        surfaces.append("circuit_candidate")
        _audit_circuit(circuit, violations)
        _audit_authority(circuit, path="circuit", violations=violations)

    salvage = _mapping(salvage_package)
    if salvage:
        surfaces.append("salvage_package")
        _audit_salvage(salvage, violations)
        _audit_authority(salvage, path="salvage", violations=violations)

    topology = _mapping(robot_topology)
    if topology:
        surfaces.append("robot_topology")
        _audit_topology(topology, violations)
        _audit_authority(topology, path="topology", violations=violations)

    impact = _mapping(change_impact)
    if impact:
        surfaces.append("change_impact")
        _audit_impact(impact, violations)
        _audit_authority(impact, path="impact", violations=violations)

    blocking = [row for row in violations if row.get("severity") == "blocking"]
    return {
        "schema_version": SCHEMA_VERSION,
        "mode": "model_first",
        "status": "blocked" if blocking else "pass",
        "surfaces_audited": surfaces,
        "violation_count": len(violations),
        "blocking_violation_count": len(blocking),
        "violations": violations,
        "checks": {
            "proposal_correctness_judged": False,
            "legacy_semantic_authority_checked": True,
            "physical_authority_checked": True,
            "physical_identity_provenance_checked": True,
            "override_binding_checked": True,
            "downstream_identity_propagation_checked": bool(
                _mapping(salvage.get("identity_propagation_audit")) if salvage else False
            ),
        },
        "authority_effect": "none",
    }

"""Independent acceptance oracle for source-bound engineering proposals.

Verifies original source retention and exact claim bindings, not formatter
presence, plausible prose, self-reported scores or architecture names.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

SCHEMA="hardware_splicer.source_bound_candidate_oracle.v1"


def _digest(value: Any)->str:
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,default=str).encode()).hexdigest()


def independently_audit_source_bound_candidate(
    scenario:Mapping[str,Any],
    plan:Mapping[str,Any],
    candidate:Mapping[str,Any],
)->dict[str,Any]:
    issues=[]
    graph=plan.get("engineering_source_graph") or {}
    sources={s["source_id"]:s for s in graph.get("sources") or []}
    claims={c["claim_id"]:c for c in graph.get("claims") or []}
    expected=scenario.get("engineering_sources") or []
    bindings=candidate.get("source_integrity") or []
    actual_bound={b.get("source_id"):b for b in bindings}
    if (len(bindings)!=len(expected) or
        len(actual_bound)!=len(bindings)):
        issues.append("source_binding_count_or_uniqueness_mismatch")
    for row in expected:
        sid=row.get("source_id")
        binding=actual_bound.get(sid)
        source=sources.get(sid)
        if binding is None or source is None:
            issues.append("missing_source_binding:"+str(sid))
            continue
        version=row.get("revision") or row.get("version") or row.get("commit_sha")
        if (source.get("uri")!=row.get("uri") or source.get("revision")!=version
            or binding.get("expected_uri")!=row.get("uri")
            or binding.get("expected_version")!=version
            or binding.get("expected_source_sha256")!=_digest(row)
            or binding.get("retained_source_record") is not True
            or binding.get("source_record_sha256")!=_digest(source)):
            issues.append("source_provenance_tampered:"+sid)
        actual_claims=sorted(c["claim_id"] for c in claims.values() if c["source_id"]==sid)
        if binding.get("source_claim_ids")!=actual_claims:
            issues.append("source_claim_identity_mismatch:"+sid)
        raw_claims=row.get("claims") or []
        observed=[c["value"] for c in claims.values() if c["source_id"]==sid]
        expected_values=[
            raw_claim if not isinstance(raw_claim,Mapping) else raw_claim.get("value")
            for raw_claim in raw_claims
        ]
        if sorted(json.dumps(v,sort_keys=True,default=str) for v in observed)!=sorted(
            json.dumps(v,sort_keys=True,default=str) for v in expected_values
        ):
            issues.append("source_claims_do_not_match_original_input:"+sid)
        if binding.get("source_claims_physical_authority") is not False:
            issues.append("source_falsely_authorized:"+sid)
        uri=str(row.get("uri") or "")
        if uri.startswith("evidence://") and binding.get("external_attestation_status")!="UNMOUNTED_FIXTURE_REFERENCE_NOT_PHYSICAL_PROOF":
            issues.append("fixture_evidence_falsely_authenticated:"+sid)
        if uri.startswith("https://") and binding.get("external_attestation_status")!="DECLARED_PUBLIC_LINK_NOT_FETCHED_BY_THIS_TRIAL":
            issues.append("public_url_claimed_verified_without_fetch:"+sid)
    graph_conflicts={c["conflict_id"]:c for c in graph.get("conflicts") or []}
    proposed_conflicts=candidate.get("source_conflicts") or []
    if len(proposed_conflicts)!=len(graph_conflicts):
        issues.append("missing_or_extra_conflict")
    for row in proposed_conflicts:
        parent=graph_conflicts.get(row.get("conflict_id"))
        if parent is None:
            issues.append("fabricated_conflict_id")
        elif (parent["blocking"]!=row.get("blocking")
              or parent["disposition"]!=row.get("disposition")
              or parent["claim_ids"]!=row.get("claim_ids")
              or row.get("source_evidence_selected") is not False):
            issues.append("conflict_silenced_or_mutated:"+row["conflict_id"])
    decisions=candidate.get("decisions") or []
    if not decisions:
        issues.append("no_engineering_decisions")
    if expected and not any(x.get("source_claims") for x in decisions):
        issues.append("design_decisions_not_bound_to_any_source_claim")
    for row in decisions:
        if not row.get("candidate_action") or not row.get("evidence_needed_to_execute"):
            issues.append("empty_engineering_decision")
        if row.get("safe_to_execute_now") is not False or row.get("acceptance_status")!="CONDITIONAL_NOT_PHYSICALLY_VALIDATED":
            issues.append("unproven_design_marked_executable")
        constraints=scenario.get("intake",{}).get("constraints") or {}
        for k,v in (row.get("original_input_constraints") or {}).items():
            if k not in constraints or constraints[k]!=v:
                issues.append("invented_constraint:"+str(k))
        for ref in row.get("source_claims") or []:
            original=claims.get(ref.get("claim_id"))
            if original is None or original["source_id"]=="declared-conflicts":
                issues.append("unsourced_or_synthetic_claim")
            elif (
                original["source_id"]!=ref.get("source_id") or
                original["value"]!=ref.get("verbatim_claim") or
                _digest(original)!=ref.get("original_claim_sha256")
            ):
                issues.append("source_claim_content_changed")
            if ref.get("interpretation_ceiling")!="SOURCE_REPORTED_NOT_INDEPENDENTLY_VERIFIED":
                issues.append("source_claim_authority_upgraded")
    if candidate.get("source_scenario_digest")!=_digest(scenario):
        issues.append("scenario_digest_mismatch")
    if candidate.get("topology_reference_id")!=(plan.get("robot_topology") or {}).get("topology_id"):
        issues.append("topology_identity_mismatch")
    raw_arch=(plan.get("robot_topology") or {}).get("robot_genre")
    stationary=(scenario.get("intake",{}).get("constraints") or {}).get("stationary_only") is True
    should_reject=stationary and raw_arch in {"rover","quadruped","tracked_vehicle","wheeled_robot"}
    arch=candidate.get("architecture_consistency") or {}
    if arch.get("mobile_topology_mismatch_detected") is not should_reject:
        issues.append("requirement_topology_conflict_hidden")
    if arch.get("native_topology_usable") is not (not should_reject):
        issues.append("native_topology_falsely_accepted")
    if should_reject and candidate.get("archetype")!="UNRESOLVED_STATIONARY_EQUIPMENT":
        issues.append("stationary_goal_mislabelled_as_mobile_robot")
    if not should_reject and candidate.get("archetype")!=raw_arch:
        issues.append("inferred_archetype_misquoted")
    if candidate.get("named_component_ids")!=sorted((plan.get("engineering_identity_map") or {}).get("component_aliases") or {}):
        issues.append("component_identity_mismatch")
    if candidate.get("change_impact_target_ids")!=list(plan.get("affected_subsystems") or []):
        issues.append("change_impact_unbound")
    for key in ("physical_specimen_evidence_authenticated","repair_completed","new_product_physically_functional","physical_fabrication_or_power_authorized"):
        if candidate.get(key) is not False:
            issues.append("false_physical_or_release_claim:"+key)
    if candidate.get("verified_usable_donor_count")!=0:
        issues.append("unverified_donors_promoted")
    if candidate.get("candidate_class")!="CONDITIONAL_EVIDENCE_BOUND_DESIGN":
        issues.append("candidate_misclassified")
    if candidate.get("release_decision")!="BLOCKED_PENDING_INDEPENDENT_ELECTRICAL_MECHANICAL_AND_FUNCTIONAL_PROOF":
        issues.append("unauthorized_release_label")
    if (candidate.get("unresolved_blocking_source_conflicts")
         !=sum(x["blocking"] for x in graph_conflicts.values())):
        issues.append("blocking_conflict_count_falsified")
    if candidate.get("engineering_readiness_from_native_planner")!=plan.get("engineering_readiness",{}).get("status"):
        issues.append("canonical_readiness_misquoted")
    return {
        "schema_version":SCHEMA,
        "source_metadata_integrity_checked":len(expected),
        "source_claim_bindings_checked":sum(len(x.get("source_claims") or []) for x in decisions),
        "claim_graph_conflicts_checked":len(graph_conflicts),
        "engineering_decisions_checked":len(decisions),
        "passes_independent_evidence_integrity":not issues,
        "passes_independent_architecture_relevance":not should_reject and not issues,
        "conditional_candidate_accepted":not should_reject and not issues,
        "explicit_topology_rejection_was_honestly_recorded":should_reject and not issues,
        "failures":sorted(set(issues)),
        "physically_validated":False,
        "fabrication_authorized":False,
    }

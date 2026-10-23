"""Evidence adequacy and reversible test selection for physical repair triage.

Only ranks what to OBSERVE NEXT. Never creates electrical schematics, energizes
hardware, authorizes disassembly, asserts a root cause, or infers measured
voltages/temperatures from a symptom.

Path membership and serviceability are caller-declared assumptions. An
operating-state change on the SAME physical path is NOT a new topology.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Mapping, Sequence

SCHEMA_VERSION = "hardware_splicer.repair_discrimination.v1"


def _signature(observation: Mapping[str, Any]) -> tuple[str, ...]:
    return tuple(sorted(set(str(x) for x in observation["path"])))


def evaluate_path_evidence(observations: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    route_outcomes: dict[tuple[str, ...], set[str]] = defaultdict(set)
    for observation in observations:
        route_outcomes[_signature(observation)].add(str(observation["outcome"]))
    conflicting = [
        {"path_component_ids": list(path), "observed_outcomes": sorted(outcomes)}
        for path, outcomes in sorted(route_outcomes.items())
        if len(outcomes) > 1
    ]
    distinct_routes = len(route_outcomes)
    failures = any("fail" in result for result in route_outcomes.values())
    # Never mark a state-dependent same-route change as component-isolating.
    # Mixed contradictory observations need condition-level isolation first,
    # even if other routes exist; a stable functional state is unproven.
    if conflicting:
        status = "operating_condition_confounded"
    elif distinct_routes < 2 or len(observations) < 2 or not failures:
        status = "insufficient_distinct_routes"
    else:
        status = "distinct_route_evidence"
    return {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "reported_observation_count": len(observations),
        "distinct_component_route_count": distinct_routes,
        "contradictory_same_route_observations": conflicting,
        "discriminating_topology_supported": status == "distinct_route_evidence",
        "has_observed_failure": failures,
        "explicit_note": (
            "Different temperatures, supply states or loads on the same component path "
            "can reveal a condition-dependent fault, not which individual component failed."
            if status == "operating_condition_confounded" else
            "Distinct, declared working/failing component paths support triage only; "
            "not confirmed topology or a measured cause."
        ),
    }


def propose_next_repair_tests(
    *,
    components: Sequence[Mapping[str, Any]],
    observations: Sequence[Mapping[str, Any]],
    interventions: Sequence[Mapping[str, Any]],
    evidence_quality: Mapping[str, Any],
    ranked_candidates: Sequence[Mapping[str, Any]] = (),
) -> list[dict[str, Any]]:
    """Generate a bounded plan to obtain *new*, non-leaking measurements.

    The ranking and proposals use no repair answer labels. Each proposal says
    what new observation would distinguish hypotheses; authorizes NO actions.
    """
    by_id = {str(x["id"]): dict(x) for x in components}
    result: list[dict[str, Any]] = []

    def propose(code: str, purpose: str, procedure: str,
                comparison: str, component_id: str | None = None) -> None:
        result.append({
            "code": code,
            "component_id": component_id,
            "purpose": purpose,
            "proposed_observation": procedure,
            "discriminating_result": comparison,
            "requires_operator_review": True,
            "power_on_authorized": False,
            "physical_repair_verified": False,
            "status": "proposal_only",
        })

    status = evidence_quality["status"]
    if status == "operating_condition_confounded":
        propose(
            "record_operating_condition_delta",
            "Separate load/temperature/time effects from actual component-path changes.",
            "Review existing operator/service logs for load, time, thermal conditions "
            "and supply readings under each reported pass/fail state; confirm actual "
            "component path identity before proposing a replacement. Do not energize "
            "unknown equipment for this test.",
            "If path remains identical, isolate a state-dependent mechanism; "
            "no individual component has been causally identified.",
        )
        propose(
            "independent_component_substitution",
            "Test a real source/path variation, not just a different load label.",
            "Identify a previously performed, safely documented known-good "
            "substitution or manufacturer diagnostic that changes one path "
            "element while keeping operating conditions comparable.",
            "If the originally failing behavior disappears only with the "
            "known-good path, that element becomes a stronger candidate.",
        )
    elif status == "insufficient_distinct_routes":
        propose(
            "obtain_second_independent_path_observation",
            "Collect a comparison that actually changes the possible failure path.",
            "Review non-destructive manufacturer tests and any existing "
            "known-good substitution results. Record one different component "
            "route, its observed outcome and consistent test conditions. "
            "No unsupervised disassembly or live electrical probing.",
            "An actual second path can distinguish shared components from "
            "components present only on the failed route.",
        )
    else:
        # A distinct working route can help prioritize an element present only
        # on failed paths. This is evidence routing, not a quantitative posterior.
        failed_routes = [set(_signature(x)) for x in observations if x["outcome"] == "fail"]
        working_routes = [set(_signature(x)) for x in observations if x["outcome"] == "pass"]
        failed_only = set.intersection(*failed_routes) if failed_routes else set()
        working_union = set.union(*working_routes) if working_routes else set()
        more_specific = failed_only - working_union
        ordered = list(ranked_candidates)
        ordered.sort(key=lambda x: (
            0 if x["component_id"] in more_specific else 1,
            -float(x["triage_evidence_score_not_probability"]),
            -int(x["reversible_test_available"]),
            int(x["service_cost_rank"]),
            x["component_id"],
        ))
        attempted = {str(x["component_id"]) for x in interventions if x.get("outcome") == "no_change"}
        for candidate in ordered[:3]:
            cid = str(candidate["component_id"])
            label = str(by_id[cid].get("label") or cid)
            if cid in attempted:
                propose(
                    "verify_ineffective_substitution",
                    f"Determine why the earlier {label} intervention did not restore function.",
                    f"Check identity, compatibility, connector condition and provenance of "
                    f"the already reported substitute for {label}; do not repeat an "
                    "unverified replacement merely to get a different outcome.",
                    "A separately confirmed known-good part and unchanged symptoms "
                    "weaken this candidate; faulty replacements remain possible.",
                    cid,
                )
            elif candidate["reversible_test_available"]:
                propose(
                    "controlled_known_good_substitution_review",
                    f"Separate {label} from alternative faults by comparing matched functional paths.",
                    f"Review whether a qualified operator has a safe, reversible "
                    f"known-good substitution or service diagnostic for {label}; "
                    "record exact before/after state without purchasing parts first.",
                    "A changed symptom only when this element differs strengthens "
                    "its causal priority; unchanged symptoms weaken but do not rule it out.",
                    cid,
                )
            else:
                propose(
                    "noninvasive_component_path_review",
                    f"Inspect the non-reversible {label} hypothesis before any costly replacement.",
                    f"Review connector identity, visible damage and existing service logs "
                    f"for {label} with a qualified technician; do not attempt energized "
                    "probing or motherboard replacement from this ranking alone.",
                    "External evidence distinguishing this path from other candidates "
                    "is needed before component-level replacement.",
                    cid,
                )
    return result[:4]

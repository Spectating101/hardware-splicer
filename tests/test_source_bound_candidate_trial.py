"""Independent checks for evidence graph binding and irrelevant candidates."""
from __future__ import annotations
import copy
import json
from pathlib import Path

import pytest
from hardware_splicer.engineering_planner import plan_engineering_project
from hardware_splicer.source_bound_candidate_trial import build_source_bound_candidate
from hardware_splicer.source_bound_candidate_oracle import independently_audit_source_bound_candidate

ROOT=Path(__file__).resolve().parents[1]
EXAMPLES=ROOT/"examples/source_agnostic"
HOLDOUT=ROOT/"examples/source_bound_holdout/unfamiliar_tabletop_label_feeder_20261020.json"


def _scenario(name):
    return json.loads((EXAMPLES/name).read_text(encoding="utf-8"))


def _plan(s):
    return plan_engineering_project(
        s["intake"],engineering_sources=s.get("engineering_sources"),
        declared_conflicts=s.get("declared_conflicts"),skip_vision=True,
    )


@pytest.fixture(scope="module")
def quadruped_case():
    s=_scenario("conflicting_quadruped_reconstruction.json")
    p=_plan(s)
    return s,p,build_source_bound_candidate(s,plan=p)


@pytest.fixture(scope="module")
def repair_case():
    s=_scenario("donor_repair_rover.json")
    p=_plan(s)
    return s,p,build_source_bound_candidate(s,plan=p)


@pytest.fixture(scope="module")
def holdout_case():
    s=json.loads(HOLDOUT.read_text(encoding="utf-8"))
    p=_plan(s)
    return s,p,build_source_bound_candidate(s,plan=p)


def test_quadruped_source_claims_and_revision_conflicts_retained(quadruped_case):
    s,p,c=quadruped_case
    a=independently_audit_source_bound_candidate(s,p,c)
    assert a["passes_independent_evidence_integrity"]
    assert len(c["source_integrity"])==4
    assert len(c["source_conflicts"])==4
    assert all(x["blocking"] for x in c["source_conflicts"])
    assert len(c["decisions"])==2
    assert all(d["source_claims"] for d in c["decisions"])
    assert c["physical_fabrication_or_power_authorized"] is False


def test_fixture_measurement_label_does_not_prove_actual_donor(repair_case):
    s,p,c=repair_case
    measured=next(x for x in p["engineering_source_graph"]["sources"] if x["source_id"]=="motor_measurements")
    assert measured["authority_ceiling"]=="measured"  # What the *fixture* claims
    binding=next(x for x in c["source_integrity"] if x["source_id"]=="motor_measurements")
    assert binding["external_attestation_status"]=="UNMOUNTED_FIXTURE_REFERENCE_NOT_PHYSICAL_PROOF"
    assert binding["source_claims_physical_authority"] is False
    assert c["verified_usable_donor_count"]==0
    assert not c["repair_completed"]
    assert independently_audit_source_bound_candidate(s,p,c)["passes_independent_evidence_integrity"]


def test_unfamiliar_stationary_holdout_rejects_spurious_rover_plan(holdout_case):
    s,p,c=holdout_case
    a=independently_audit_source_bound_candidate(s,p,c)
    assert p["robot_topology"]["robot_genre"]=="rover"  # Reproduced bug in existing canonical planner
    assert c["archetype"]=="UNRESOLVED_STATIONARY_EQUIPMENT"
    assert c["architecture_consistency"]["mobile_topology_mismatch_detected"] is True
    assert not c["architecture_consistency"]["native_topology_usable"]
    assert a["passes_independent_evidence_integrity"]  # Source bookkeeping is still valid
    assert not a["passes_independent_architecture_relevance"]
    assert not a["conditional_candidate_accepted"]
    assert a["explicit_topology_rejection_was_honestly_recorded"]
    assert len(c["source_integrity"])==6
    assert sum(len(x["source_claims"]) for x in c["decisions"])>=6


def test_losing_source_identity_triggers_independent_failure(quadruped_case):
    s,p,c=copy.deepcopy(quadruped_case)
    c["source_integrity"].pop()
    check=independently_audit_source_bound_candidate(s,p,c)
    assert not check["passes_independent_evidence_integrity"]


def test_source_version_mismatch_fails_independent_attestation(quadruped_case):
    s,p,c=copy.deepcopy(quadruped_case)
    c["source_integrity"][0]["expected_version"]="v999"
    check=independently_audit_source_bound_candidate(s,p,c)
    assert not check["passes_independent_evidence_integrity"]
    assert any("source_provenance_tampered" in f for f in check["failures"])


def test_forged_source_claim_content_rejected(quadruped_case):
    s,p,c=copy.deepcopy(quadruped_case)
    c["decisions"][0]["source_claims"][0]["verbatim_claim"]="Invented measured pinout"
    check=independently_audit_source_bound_candidate(s,p,c)
    assert "source_claim_content_changed" in check["failures"]


def test_conflict_silencing_fails_even_if_topology_still_exists(quadruped_case):
    s,p,c=copy.deepcopy(quadruped_case)
    c["source_conflicts"][0]["blocking"]=False
    check=independently_audit_source_bound_candidate(s,p,c)
    assert not check["passes_independent_evidence_integrity"]
    assert any("conflict_silenced_or_mutated" in f for f in check["failures"])


def test_physical_authority_smuggling_is_rejected(repair_case):
    s,p,c=copy.deepcopy(repair_case)
    c["physical_fabrication_or_power_authorized"]=True
    c["verified_usable_donor_count"]=2
    check=independently_audit_source_bound_candidate(s,p,c)
    assert not check["passes_independent_evidence_integrity"]
    assert "unverified_donors_promoted" in check["failures"]


def test_fixture_evidence_uri_cannot_be_declared_authenticated(repair_case):
    s,p,c=copy.deepcopy(repair_case)
    binding=next(x for x in c["source_integrity"] if x["source_id"]=="motor_measurements")
    binding["external_attestation_status"]="INDEPENDENT_BENCH_VERIFIED"
    check=independently_audit_source_bound_candidate(s,p,c)
    assert any("fixture_evidence_falsely_authenticated" in f for f in check["failures"])


def test_forged_architecture_relevance_rejected(holdout_case):
    s,p,c=copy.deepcopy(holdout_case)
    c["architecture_consistency"]["mobile_topology_mismatch_detected"]=False
    c["architecture_consistency"]["native_topology_usable"]=True
    c["archetype"]="rover"
    check=independently_audit_source_bound_candidate(s,p,c)
    assert not check["passes_independent_evidence_integrity"]
    assert any("stationary_goal_mislabelled" in f for f in check["failures"])


def test_removed_design_evidence_link_cannot_be_silently_granted(holdout_case):
    s,p,c=copy.deepcopy(holdout_case)
    for d in c["decisions"]:
        d["source_claims"]=[]
    check=independently_audit_source_bound_candidate(s,p,c)
    assert "design_decisions_not_bound_to_any_source_claim" in check["failures"]


def test_invented_electrical_constraint_rejected(holdout_case):
    s,p,c=copy.deepcopy(holdout_case)
    c["decisions"][0]["original_input_constraints"]["known_safe_voltage_v"]=12
    check=independently_audit_source_bound_candidate(s,p,c)
    assert "invented_constraint:known_safe_voltage_v" in check["failures"]


def test_sdk_and_mcp_reject_irrelevant_topology_without_physical_authority(holdout_case):
    import asyncio
    from hardware_splicer import sdk, mcp_server
    scenario,_,_=holdout_case
    result=sdk.plan_source_bound_design(scenario=scenario)
    assert result["independent_evidence_audit"]["passes_independent_evidence_integrity"]
    assert result["conditional_architecture_accepted"] is False
    assert result["physical_build_authorized"] is False
    tools=asyncio.run(mcp_server.list_tools())
    assert any(tool.name=="hs_plan_source_bound_design" for tool in tools)
    response=asyncio.run(mcp_server.call_tool("hs_plan_source_bound_design",{"scenario":scenario}))
    body=json.loads(response[0].text)
    assert body["candidate"]["architecture_consistency"]["mobile_topology_mismatch_detected"]
    assert body["conditional_architecture_accepted"] is False
    assert body["physical_build_authorized"] is False

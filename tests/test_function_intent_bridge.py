"""Function-first intake lowers into existing HS MachineProject without false proofs."""
from __future__ import annotations
import copy
import hashlib
import json
from pathlib import Path

import pytest
from hardware_splicer.function_intent_bridge import canonical, parse_intent, package_intent

ROOT=Path(__file__).resolve().parents[1]
EXAMPLE=ROOT/"examples/functionality/water_filter_nonpotable_bench_001.json"


def water():
    return json.loads(EXAMPLE.read_text())


def test_water_filter_compiles_into_existing_machine_project_with_full_traceability(tmp_path):
    brief=water()
    project,gate=parse_intent(brief)
    assert len(project.requirements)==7
    assert len(project.verifications)==7
    assert len(project.functions)==6
    assert len(project.interfaces)==4
    assert len(project.subsystems)==5
    assert not [i for i in project.traceability_issues()
                if i.code.startswith("invalid_ref") or i.code=="duplicate_id"]
    assert gate["functional_traceability_pass"] is True
    assert gate["status"]=="FUNCTIONAL_CONCEPT_ONLY"
    assert gate["evidence_collected_count"]==0
    assert all(v.status.value=="planned" and not v.evidence_ids for v in project.verifications)
    assert all(not v for v in gate["physical_authority"].values())
    assert len(gate["machine_project_unresolved_interfaces"])==4
    assert any(s.metadata["engineering_specialty"]=="separation process and materials"
               for s in project.subsystems)
    receipt=package_intent(brief,tmp_path/"out")
    assert receipt["source_spec_sha256"]==hashlib.sha256(canonical(brief)).hexdigest()
    for filename,record in receipt["files"].items():
        payload=(tmp_path/"out"/filename).read_bytes()
        assert hashlib.sha256(payload).hexdigest()==record["sha256"]
        assert len(payload)==record["bytes"]
    with pytest.raises(ValueError,match="overwrite"):
        package_intent(brief,tmp_path/"out")


def test_missing_critical_performance_test_rejected():
    brief=water()
    del brief["requirements"][1]["verification"]["acceptance"]
    with pytest.raises(ValueError,match="observable acceptance"):
        parse_intent(brief)


def test_stale_or_unbound_function_rejected():
    brief=water()
    brief["functions"][0]["requirements"]=["REQ_DOES_NOT_EXIST"]
    with pytest.raises(ValueError,match="invalid requirements"):
        parse_intent(brief)
    brief=water()
    brief["functions"]=[fn for fn in brief["functions"] if fn["id"]!="FN_LABEL"]
    with pytest.raises(ValueError,match="every requirement"):
        parse_intent(brief)


def test_unqualified_drinking_claim_or_inflated_measured_status_rejected():
    brief=water()
    brief["intended_use"]="potable"
    with pytest.raises(ValueError,match="unqualified intended use"):
        parse_intent(brief)
    brief=water()
    brief["claims"]=["certified"]
    with pytest.raises(ValueError,match="health/safety"):
        parse_intent(brief)
    brief=water()
    brief["requirements"][0]["verification"]["evidence_status"]="passed"
    with pytest.raises(ValueError,match="cannot import measured"):
        parse_intent(brief)
    brief=water()
    brief["requirements"][0]["measured"]=True
    with pytest.raises(ValueError,match="promoted to measured"):
        parse_intent(brief)


def test_missing_physical_interface_unknowns_rejected():
    brief=water()
    brief["interfaces"][0]["unresolved"]=[]
    with pytest.raises(ValueError,match="unresolved parameters"):
        parse_intent(brief)


def test_unknown_or_duplicate_owners_cannot_bypass_machine_project_graph():
    brief=water()
    brief["subsystems"][0]["id"]=brief["subsystems"][1]["id"]
    with pytest.raises(ValueError,match="duplicate id"):
        parse_intent(brief)
    brief=water()
    brief["interfaces"][0]["to"]="NOT_A_REAL_SUBSYSTEM"
    with pytest.raises(ValueError,match="two distinct subsystems"):
        parse_intent(brief)


def test_second_non_water_device_uses_identical_bridge():
    brief={
      "schema_version":"hardware_splicer.function_intent.v1",
      "project_id":"temperature_alert_001",
      "purpose":"Detect a specified ambient temperature threshold and alert a user, prototype only",
      "intended_use":"general_device",
      "inputs":[{"id":"temperature","medium":"air"}],
      "outputs":[{"id":"notification","medium":"signal"}],
      "requirements":[{"id":"R_TEMP","kind":"functional",
         "statement":"Detect a chosen ambient threshold with a specified error tolerance",
         "verification":{"procedure":"Calibrated chamber sweep and independent thermometer comparison",
             "acceptance":{"max_error_c":2.0},"evidence_status":"not_collected"}}],
      "functions":[{"id":"F_SENSE","name":"Sense temperature",
         "requirements":["R_TEMP"],"subsystems":["S_SENSOR"]}],
      "subsystems":[
        {"id":"S_SENSOR","name":"Sensor","domain":"electrical",
         "purpose":"Obtain ambient measurement","requirements":["R_TEMP"]},
        {"id":"S_ALERT","name":"Alert","domain":"firmware",
         "purpose":"Produce a user signal","requirements":[]}],
      "interfaces":[{"id":"I_SAMPLE","name":"Sample to notifier",
         "from":"S_SENSOR","to":"S_ALERT","medium":"signal",
         "unresolved":["protocol","sample_rate_hz","voltage_levels"]}],
    }
    project,gate=parse_intent(brief)
    assert len(project.verifications)==1
    assert len(project.subsystems)==2
    assert gate["status"]=="FUNCTIONAL_CONCEPT_ONLY"
    assert gate["subsystem_disciplines"]["S_ALERT"]=="firmware"
    assert all(flag is False for flag in gate["physical_authority"].values())


def test_same_brief_same_digests_and_one_requirement_change_changes_digest(tmp_path):
    b=water()
    first=package_intent(b,tmp_path/"first")
    second=package_intent(copy.deepcopy(b),tmp_path/"second")
    assert first["files"]==second["files"]
    changed=copy.deepcopy(b)
    changed["requirements"][1]["verification"]["acceptance"]["minimum_turbidity_reduction_percent"]=80
    different=package_intent(changed,tmp_path/"third")
    assert different["source_spec_sha256"]!=first["source_spec_sha256"]
    assert different["files"]["MACHINE_PROJECT.json"]["sha256"]!=first["files"]["MACHINE_PROJECT.json"]["sha256"]

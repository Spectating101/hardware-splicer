"""Actual end-user repair triage artifacts: proposed tests without physical authority."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from hardware_splicer.repair_triage_cli import write_repair_triage_package


CORPUS=Path(__file__).resolve().parents[1]/"benchmarks/repair_corpus_v2_20261023/blind_observations.json"


def _case(identifier):
    cases=json.loads(CORPUS.read_text(encoding="utf-8"))["cases"]
    return next(case for case in cases if case["case_id"]==identifier)


def test_confounded_power_supply_case_generates_abstention_and_next_test(tmp_path):
    # Real user-reported PS5 symptom. Same physical path under two workloads.
    receipt=write_repair_triage_package(_case("R08"),tmp_path)
    report=json.loads((tmp_path/"REPAIR_TRIAGE.json").read_text(encoding="utf-8"))
    text=(tmp_path/"REPAIR_TRIAGE.md").read_text(encoding="utf-8")
    assert receipt["verdict"]=="insufficient_discriminating_evidence"
    assert report["repair_path_diagnostic"]["reason"]=="operating_condition_confounded"
    assert report["repair_path_diagnostic"]["candidates"]==[]
    assert "record_operating_condition_delta" in text
    assert "Physical repair verified: **NO**" in text
    assert receipt["power_on_authorized"] is False


def test_known_two_path_iPhone_case_reports_hypotheses_and_safe_observation(tmp_path):
    receipt=write_repair_triage_package(_case("R01"),tmp_path)
    diagnostic=json.loads((tmp_path/"REPAIR_TRIAGE.json").read_text(encoding="utf-8"))["repair_path_diagnostic"]
    text=(tmp_path/"REPAIR_TRIAGE.md").read_text(encoding="utf-8")
    assert receipt["verdict"]=="triage_hypothesis_only"
    assert diagnostic["candidates"]
    assert diagnostic["recommended_tests"]
    assert "Unverified component hypotheses" in text
    assert "Operator" in text or "operator" in text
    assert diagnostic["recommended_tests"][0]["physical_repair_verified"] is False


def test_plain_symptoms_never_create_a_component_recommendation(tmp_path):
    receipt=write_repair_triage_package(
        {"repair_intake":{"device_hint":"unknown low voltage item","symptoms":["does not start"]}},
        tmp_path,
    )
    assert receipt["verdict"]=="no_structured_diagnosis"
    data=json.loads((tmp_path/"REPAIR_TRIAGE.json").read_text(encoding="utf-8"))
    assert "repair_path_diagnostic" not in data
    assert "No component hypothesis" in (tmp_path/"REPAIR_TRIAGE.md").read_text()


def test_real_python_cli_entrypoint_writes_file_receipts(tmp_path):
    source=tmp_path/"input.json"
    source.write_text(json.dumps(_case("R08")),encoding="utf-8")
    output=tmp_path/"out"
    completed=subprocess.run(
        [sys.executable,"-m","hardware_splicer.repair_triage_cli",str(source),str(output)],
        text=True,capture_output=True,timeout=15,check=True,
    )
    status=json.loads(completed.stdout)
    assert status["verdict"]=="insufficient_discriminating_evidence"
    assert (output/"REPAIR_TRIAGE.json").is_file()
    assert (output/"REPAIR_TRIAGE.md").is_file()

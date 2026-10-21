"""Exploration must distinguish compiled-but-blocked from false release approval.

A blocked result is successful *harness coverage* only when production gates
and project authority consistently say the actual device is NOT authorized.
"""
from __future__ import annotations
import importlib.util
import json
import stat
import subprocess
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def harness(tmp_path_factory):
    out=tmp_path_factory.mktemp("exploration")
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("HARDWARE_SPLICER_EXPLORATION_OUT",str(out))
        spec=importlib.util.spec_from_file_location("exploration_under_test",ROOT/"scripts"/"exploration_test.py")
        module=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    return module


def _python(tmp_path, *, exit_code, stderr=""):
    script=tmp_path/"fake-python"
    script.write_text(f"#!/bin/sh\necho '{stderr}' >&2\nexit {exit_code}\n",encoding="utf-8")
    script.chmod(script.stat().st_mode|stat.S_IXUSR)
    return script


def _result(tmp_path, *, compile_ok=True, claimable=False,
            production_ready=False, gaps=None, blockers=None,
            passed=7, total=9, level=None, scenario_ok=None):
    path=tmp_path/"SCENARIO_RESULT.json"
    gaps=["mechanical_release","integrated_bench"] if gaps is None else gaps
    blockers=["Mechanical subsystem release not closed","Integrated bench not validated"] if blockers is None else blockers
    level=level or ("production_ready_project_package" if claimable else "simulation_bench_project_package")
    body={
        "schema_version":"hardware_splicer.scenario_result.v1",
        "compile_ok":compile_ok,
        "ok":claimable if scenario_ok is None else scenario_ok,
        "project_authority":{
            "schema_version":"hardware_splicer.project_authority.v1",
            "claimable":claimable,
            "project_authority_level":level,
            "production_release_metrics":{"production_ready":production_ready,
                "schema_version":"hardware_splicer.production_release_metrics.v1",
                "gates_passed":passed,"gates_total":total,"evidence_gap_ids":gaps},
        },
        "production_release_metrics":{
            "schema_version":"hardware_splicer.production_release_metrics.v1",
            "production_ready":production_ready,"gates_passed":passed,
            "gates_total":total,"evidence_gap_ids":gaps,
            "what_blocks_production":blockers,
        },
    }
    path.write_text(json.dumps(body),encoding="utf-8")
    return path


def _proc(code):
    return subprocess.CompletedProcess(args=[],returncode=code,stdout="",stderr="")


def test_compiled_release_blocked_is_valid_exploration_not_release(harness,tmp_path):
    ok,detail=harness._scenario_passes(Path('closed_pan_tilt_mechatronics_project.json'),
                                       _result(tmp_path),_proc(1))
    assert ok
    assert 'outcome=compiled_release_blocked' in detail
    assert 'gates=7/9' in detail
    assert 'mechanical_release,integrated_bench' in detail
    assert 'claimable=False' in detail


def test_negative_safety_scenario_never_gets_release(harness,tmp_path):
    ok,detail=harness._scenario_passes(Path('rover_bad_speed_project.json'),
                                       _result(tmp_path),_proc(1))
    assert ok and 'outcome=negative_safety_scenario' in detail
    ok,detail=harness._scenario_passes(Path('rover_bad_speed_project.json'),
      _result(tmp_path,claimable=True,production_ready=True,passed=9,total=9,gaps=[],blockers=[]),_proc(0))
    assert not ok


def test_approved_positive_scenario_still_passes(harness,tmp_path):
    ok,detail=harness._scenario_passes(Path('some_scenario.json'),
      _result(tmp_path,claimable=True,production_ready=True,passed=9,total=9,gaps=[],blockers=[]),_proc(0))
    assert ok
    assert 'outcome=production_authorized' in detail


@pytest.mark.parametrize('edits,exit_code',[
    ({'compile_ok':False},1),
    ({'ok':True},1),
    ({'project_authority':{'claimable':True,'project_authority_level':'production_ready_project_package',
                           'production_release_metrics':{'production_ready':False}}},1),
    ({'production_release_metrics':{'production_ready':True,'gates_passed':7,
           'gates_total':9,'evidence_gap_ids':['mechanical_release','integrated_bench'],
           'what_blocks_production':['Mechanical release incomplete']}},1),
    ({'production_release_metrics':{'production_ready':False,'gates_passed':9,
           'gates_total':9,'evidence_gap_ids':[],
           'what_blocks_production':['Mechanical release incomplete']}},1),
    ({'production_release_metrics':{'production_ready':False,'gates_passed':7,
           'gates_total':9,'evidence_gap_ids':[],
           'what_blocks_production':['Mechanical release incomplete']}},1),
    ({'production_release_metrics':{'production_ready':False,'gates_passed':7,
           'gates_total':9,'evidence_gap_ids':['mechanical_release','integrated_bench'],
           'what_blocks_production':[]}},1),
    ({},2),
])
def test_malformed_or_inconsistent_blocked_release_fails(harness,tmp_path,edits,exit_code):
    path=_result(tmp_path)
    body=json.loads(path.read_text())
    body.update(edits)
    path.write_text(json.dumps(body))
    ok,_=harness._scenario_passes(Path('rover_project.json'),path,_proc(exit_code))
    assert not ok


def test_missing_or_broken_scenario_result_fails(harness,tmp_path):
    missing=tmp_path/'does-not-exist.json'
    ok,_=harness._scenario_passes(Path('rover_project.json'),missing,_proc(1))
    assert not ok
    invalid=tmp_path/'SCENARIO_RESULT.json'
    invalid.write_text('{not json')
    ok,detail=harness._scenario_passes(Path('rover_project.json'),invalid,_proc(1))
    assert not ok and 'invalid' in detail


def test_unexpected_release_failure_names_broken_cadquery_import(harness,tmp_path,monkeypatch):
    monkeypatch.setenv('SPLICER3D_PYTHON',str(_python(tmp_path,exit_code=1,
        stderr='ImportError: libGL.so.1: cannot open shared object file')))
    path=_result(tmp_path,scenario_ok=True)
    ok,detail=harness._scenario_passes(Path('closed_pan_tilt_mechatronics_project.json'),path,_proc(1))
    assert not ok
    assert 'cannot import cadquery: ImportError: libGL.so.1: cannot open shared object file' in detail


def test_mirrored_project_authority_metrics_disagreement_cannot_pass(harness,tmp_path):
    path=_result(tmp_path)
    body=json.loads(path.read_text())
    body['project_authority']['production_release_metrics']['evidence_gap_ids']=['mechanical_release']
    path.write_text(json.dumps(body))
    ok,detail=harness._scenario_passes(Path('rover_project.json'),path,_proc(1))
    assert not ok
    assert 'inconsistent release evidence' in detail


def test_schema_mismatch_cannot_pass(harness,tmp_path):
    path=_result(tmp_path)
    body=json.loads(path.read_text())
    body['production_release_metrics']['schema_version']='untrusted.v0'
    path.write_text(json.dumps(body))
    ok,detail=harness._scenario_passes(Path('rover_project.json'),path,_proc(1))
    assert not ok
    assert 'schema' in detail

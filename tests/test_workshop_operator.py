"""Integration truth for registered HS work orders.

The actual reference verifier is only executed when the local KiCad 9/pcbnew
toolchain is available. All security/replay cases are deterministic and run
without hardware, SSH, models, or a remote GitHub Actions worker.
"""
from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
from types import SimpleNamespace

import pytest

from hardware_splicer import workshop_operator as op

ROOT=Path(__file__).resolve().parents[1]
NATIVE_KICAD=bool(shutil.which("kicad-cli") and importlib.util.find_spec("pcbnew"))


def _result(out:Path)->dict:
    assert (out/"ENGINEERING_HANDOFF.md").is_file()
    assert (out/"HS_OPERATOR_RESULT.json").is_file()
    return json.loads((out/"HS_OPERATOR_RESULT.json").read_text())


def test_registered_routes_are_vetted_existing_HS_components():
    rows=op.list_cases()
    assert {r["case_id"] for r in rows} == {op.SPI_ID,op.RC_ID}
    assert {r["route"] for r in rows} == {
        "reference_native_verifier","existing_splice_intake"}
    assert all((ROOT/r["source"]).exists() for r in rows)


@pytest.mark.parametrize("case",[op.SPI_ID,op.RC_ID])
def test_operator_preview_does_not_compile_or_call_electrical_tools(tmp_path,monkeypatch,case):
    monkeypatch.setattr(op,"_native_spi",lambda *a: pytest.fail("unexpected KiCad"))
    monkeypatch.setattr(op,"_repair",lambda *a: pytest.fail("unexpected repair tool"))
    result=op.run_workshop_operator(case,out_dir=tmp_path/"preview")
    assert result["status"]=="planned_not_executed"
    assert result["trace"][0]["state"]=="planned"
    assert not result["execute_requested"]
    assert not result["engineering_acceptance"]
    assert set(result[f] for f in (
       "physical_validation","fabrication_authorized",
       "power_on_authorized","real_repair_confirmed"))=={False}
    assert sorted(f.name for f in (tmp_path/"preview").iterdir())==[
        "ENGINEERING_HANDOFF.md","HS_OPERATOR_RESULT.json"
    ]


def test_unsupported_objective_never_falls_through_to_generic_compiler(tmp_path):
    with pytest.raises(ValueError,match="case not registered"):
        op.run_workshop_operator("please build a robot for me && rm -rf /",
                                 out_dir=tmp_path/"foo",execute=True)
    assert not (tmp_path/"foo").exists()


def test_symlink_and_parent_traversal_are_not_accepted(tmp_path):
    with pytest.raises(ValueError,match="unapproved source path"):
        op._source_path(ROOT,"../../etc/passwd")
    outside=tmp_path/"elsewhere";outside.write_text("secret")
    folder=tmp_path/"repo";folder.mkdir()
    (folder/"linked").symlink_to(outside)
    with pytest.raises(ValueError,match="escapes controlled repository"):
        op._source_path(folder,"linked")


def test_stale_output_cannot_overwrite_evidence(tmp_path):
    out=tmp_path/"job";out.mkdir()
    (out/"HS_OPERATOR_RESULT.json").write_text('{"status":"old_pass"}')
    with pytest.raises(ValueError,match="new/empty"):
        op.run_workshop_operator(op.SPI_ID,out_dir=out)
    assert 'old_pass' in (out/"HS_OPERATOR_RESULT.json").read_text()


def test_mock_verifier_cannot_inherit_old_committed_green_receipt(tmp_path,monkeypatch):
    monkeypatch.setattr(op.subprocess,"run",lambda *a,**k: SimpleNamespace(
        returncode=0,stdout="",stderr=""))
    output=op.run_workshop_operator(op.SPI_ID,out_dir=tmp_path/"fake",execute=True)
    assert output["status"]=="blocked_independent_verification"
    assert output["engineering_acceptance"] is False
    assert output["trace"][-1]["receipt_matches_all_sources"] is False
    # Source archive has prior verification.json, but staged copy must not.
    assert not (tmp_path/"fake/source_copy/verification.json").exists()
    assert all(not output[field] for field in (
        "physical_validation","fabrication_authorized","power_on_authorized"))


@pytest.mark.skipif(not NATIVE_KICAD, reason="requires native KiCad + pcbnew")
def test_verifier_nonzero_even_if_generating_green_receipt_is_refused(tmp_path,monkeypatch):
    old=subprocess.run
    def wrong_exit(args,**kwargs):
        # The existing script is trusted and really writes a valid receipt.
        result=old(args,**kwargs)
        assert result.returncode==0
        return SimpleNamespace(returncode=1,stdout=result.stdout,stderr="forced failure")
    monkeypatch.setattr(op.subprocess,"run",wrong_exit)
    output=op.run_workshop_operator(op.SPI_ID,out_dir=tmp_path/"fail",execute=True)
    assert output["engineering_acceptance"] is False
    assert output["status"]=="blocked_independent_verification"
    assert output["trace"][-1]["exit_code"]==1


@pytest.mark.skipif(not NATIVE_KICAD, reason="requires native KiCad + pcbnew")
def test_real_spi_reference_verification_replays_with_original_identity(tmp_path):
    try:
        import pcbnew  # noqa: F401
    except ImportError:
        pytest.skip("native pcbnew binding missing")
    source=ROOT/op.SPI_ROOT
    from hashlib import sha256
    before=sha256((source/"spi_flash_adapter_v1.kicad_pcb").read_bytes()).hexdigest()
    report=op.run_workshop_operator(op.SPI_ID,out_dir=tmp_path/"real",execute=True)
    assert report["status"]=="verified_design_only_physical_blocked",report
    assert report["engineering_acceptance"]
    assert report["trace"][-1]["receipt_matches_all_sources"]
    assert report["trace"][-1]["source_unchanged"]
    assert report["trace"][-1]["nonphysical_authority"]
    assert report["trace"][-1]["exit_code"]==0
    assert all(n==0 for n in report["trace"][-1]["checks"].values())
    assert len(report["artifacts_sha256"])==4
    assert (source/"spi_flash_adapter_v1.kicad_pcb").read_bytes()==(
        tmp_path/"real/source_copy/spi_flash_adapter_v1.kicad_pcb").read_bytes()
    after=sha256((source/"spi_flash_adapter_v1.kicad_pcb").read_bytes()).hexdigest()
    assert before==after
    assert report["canonical_machine_release"]["allowed"] is False
    assert report["canonical_machine_release"]["software_evidence_count"] == 1
    assert report["canonical_machine_release"]["physical_measurements_count"] == 0
    assert report["canonical_machine_release"]["verification_states"] == {
      "verify-software":"passed","verify-physical":"planned"}
    assert not report["physical_validation"]
    assert not report["fabrication_authorized"]
    assert not report["power_on_authorized"]
    assert not report["real_repair_confirmed"]
    assert "not physically" in (tmp_path/"real/ENGINEERING_HANDOFF.md").read_text().lower() or (
        "Real physical verification: **NO**" in (tmp_path/"real/ENGINEERING_HANDOFF.md").read_text()
    )


def test_unresolved_donor_planning_blocks_before_catalog_compile(tmp_path,monkeypatch):
    from hardware_splicer import project_intake, splice_manifest
    # With a model adapter present, the real intake may occasionally select
    # a grounded architecture. Force the precise unresolved state here.
    monkeypatch.setattr(project_intake,"plan_project_from_intake",lambda _:{
       "salvage_package":{"recommended_build_id":None,
                          "splice_plan":{"reusable_blocks":[]}},
       "donor_board_vision_report":{"applied_board_count":1},
       "evidence_extraction_report":{"accepted_count":0},
    })
    monkeypatch.setattr(splice_manifest,"run_splice_case",
                        lambda *a,**kw: pytest.fail("wrong generic CAD must not compile"))
    report=op.run_workshop_operator(op.RC_ID,out_dir=tmp_path/"rc",execute=True)
    assert report["status"]=="blocked_unresolved_donor_architecture"
    assert report["canonical_machine_release"]["allowed"] is False
    assert report["canonical_machine_release"]["software_evidence_count"] == 0
    assert not report["engineering_acceptance"]
    assert report["trace"][0]["stage"]=="intake"
    assert report["trace"][1]["stage"]=="planning"
    assert report["trace"][1]["state"]=="blocked"
    assert report["trace"][2]["stage"]=="execution"
    assert report["trace"][2]["state"]=="skipped"
    assert report["trace"][1]["donor_vision_applied"]>=1
    assert any("non-generic" in s for s in report["open_actions"])
    assert not (tmp_path/"rc/compiled").exists()
    assert not (tmp_path/"rc/SPLICE_PLAN.json").exists()
    assert "Do not energize" in (tmp_path/"rc/ENGINEERING_HANDOFF.md").read_text()


def test_compiled_case_drc_cannot_override_manufacturing_failure(tmp_path,monkeypatch):
    from hardware_splicer import project_intake,splice_manifest
    def good_plan(_):
        return {
            "salvage_package":{
                "recommended_build_id":"robot_drive_base",
                "splice_plan":{"reusable_blocks":[{"block_id":"donor_hbridge"}]},
            },
            "donor_board_vision_report":{"applied_board_count":1},
            "evidence_extraction_report":{"accepted_count":1},
        }
    def fake_compiler(case,*,out_dir,export_gerber):
        target=Path(out_dir);target.mkdir(parents=True,exist_ok=True)
        (target/"PROJECT_PACKAGE.json").write_text(json.dumps(
          {"manufacturing_reconciliation":{
            "status":"blocked","package_ready":False,
            "blockers":[{"code":"bom_mismatch","message":"BOM is missing donor driver"}]}
          }))
        (target/"SPLICE_BENCH_SESSION.json").write_text(json.dumps(
            {"power_on_authorized":False,"open_gate_count":3}))
        (target/"SPLICE_PLAN.json").write_text("{}")
        return {"build_id":"robot_drive_base","drc_pass":True}
    monkeypatch.setattr(project_intake,"plan_project_from_intake",good_plan)
    monkeypatch.setattr(splice_manifest,"run_splice_case",fake_compiler)
    monkeypatch.setattr(splice_manifest,"evaluate_splice_case",
                        lambda metrics,case:{"passed":True,"failures":[]})
    result=op.run_workshop_operator(op.RC_ID,out_dir=tmp_path/"fake_compile",
                                     execute=True)
    assert result["status"]=="blocked_compiled_case_or_manufacturing"
    assert not result["engineering_acceptance"]
    assert any("BOM is missing" in s for s in result["open_actions"])
    assert result["trace"][-1]["state"]=="failed"
    assert not result["power_on_authorized"]


def test_forged_bench_power_authority_is_independently_refused(tmp_path,monkeypatch):
    from hardware_splicer import project_intake,splice_manifest
    monkeypatch.setattr(project_intake,"plan_project_from_intake",lambda _:{
        "salvage_package":{"recommended_build_id":"robot_drive_base",
           "splice_plan":{"reusable_blocks":[{"block_id":"driver"}]}},
        "donor_board_vision_report":{"applied_board_count":1},
    })
    def create_case(case,*,out_dir,export_gerber):
        path=Path(out_dir);path.mkdir(parents=True,exist_ok=True)
        (path/"PROJECT_PACKAGE.json").write_text(json.dumps({
            "manufacturing_reconciliation":{"package_ready":True,"status":"ready","blockers":[]}}))
        (path/"SPLICE_BENCH_SESSION.json").write_text(json.dumps({
            "power_on_authorized":True,"open_gate_count":0}))
        (path/"SPLICE_PLAN.json").write_text("{}")
        return {"build_id":"robot_drive_base","drc_pass":True}
    monkeypatch.setattr(splice_manifest,"run_splice_case",create_case)
    monkeypatch.setattr(splice_manifest,"evaluate_splice_case",
                        lambda *args:{"passed":True,"failures":[]})
    report=op.run_workshop_operator(op.RC_ID,out_dir=tmp_path/"forged",
                                    execute=True)
    assert report["status"]=="blocked_unverified_bench_authority"
    assert not report["engineering_acceptance"]
    assert not report["power_on_authorized"]
    assert not report["physical_validation"]


def test_cli_preview_is_real_runnable_and_never_masquerades_as_execution(tmp_path):
    cmd=[sys.executable,str(ROOT/"scripts/hs_workshop_operator.py"),
         "--case",op.RC_ID,"--out",str(tmp_path/"cli")]
    r=subprocess.run(cmd,cwd=ROOT,text=True,capture_output=True,timeout=20)
    assert r.returncode==0,r.stderr
    data=json.loads(r.stdout)
    assert data["status"]=="planned_not_executed"
    assert data["fabrication_authorized"] is False
    assert _result(tmp_path/"cli")["engineering_acceptance"] is False


def test_real_pilot_receipts_stay_bound_to_exact_source_revision():
    import hashlib
    spi=json.loads((ROOT/"examples/workshop_operator/pilot/SPI_OPERATOR_RESULT.json").read_text())
    rc=json.loads((ROOT/"examples/workshop_operator/pilot/RC_OPERATOR_RESULT.json").read_text())
    assert spi["status"]=="verified_design_only_physical_blocked"
    assert spi["canonical_machine_release"]["allowed"] is False
    assert spi["canonical_machine_release"]["physical_measurements_count"]==0
    assert spi["trace"][-1]["receipt_matches_all_sources"] is True
    assert spi["trace"][-1]["source_unchanged"] is True
    assert all(n==0 for n in spi["trace"][-1]["checks"].values())
    assert rc["status"]=="blocked_unresolved_donor_architecture"
    assert rc["canonical_machine_release"]["allowed"] is False
    assert rc["engineering_acceptance"] is False
    assert rc["trace"][-1]["state"]=="skipped"
    src=ROOT/op.SPI_ROOT
    item_hashes={p.relative_to(src).as_posix():op._hash(p)
                 for p in sorted(src.rglob("*")) if p.is_file() and not p.is_symlink()
                 and "out" not in p.relative_to(src).parts and "__pycache__" not in p.parts}
    assert hashlib.sha256(json.dumps(item_hashes,sort_keys=True).encode()).hexdigest()==spi["source_sha256"]
    assert op._hash(ROOT/op.REGISTERED[op.RC_ID]["source"])==rc["source_sha256"]
    for row in (spi,rc):
        assert not row["fabrication_authorized"]
        assert not row["power_on_authorized"]
        assert not row["real_repair_confirmed"]

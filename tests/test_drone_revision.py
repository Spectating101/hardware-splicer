"""The same drone is repaired in CAD; metadata alone cannot pass acceptance."""
from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import shutil
from types import SimpleNamespace

import pytest

from hardware_splicer import workshop_operator as op

ROOT = Path(__file__).resolve().parents[1]
REV = ROOT / "examples/drone_proving_ground/revision_b"


def _module(name, file):
    spec = importlib.util.spec_from_file_location(name, REV / file)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod


build = _module("hs_drone_revision_tests", "build_package.py")


@pytest.fixture
def reference():
    return json.loads((REV / "reference/results.json").read_text())


def test_revision_preserves_function_and_rejects_the_first_clearance_candidate(reference):
    assert {"gps", "camera", "vtx", "receiver"} <= {p["id"] for p in reference["parts"]}
    assert reference["design_iterations"][0]["wheelbase_mm"] == 135
    assert "prop_radial_clearance" in reference["design_iterations"][0]["failed_checks"]
    assert reference["design_iterations"][-1]["wheelbase_mm"] == 137
    assert reference["design_iterations"][-1]["failed_checks"] == []
    assert reference["mass"]["auw_g"] <= 235
    assert reference["power"]["design_current_a"] <= 35
    assert reference["power"]["throttle_limit_relied_on"] is False
    assert reference["power"]["battery_continuous_a"] == 59.5


def test_original_small_connector_is_not_hidden_by_throttle_scaling(reference, monkeypatch):
    original = build.inputs
    def old_connector():
        base, cfg, parts, hw, frame, table = copy.deepcopy(original())
        cfg["power_path"]["rated_current_a"] = 15
        return base, cfg, parts, hw, frame, table
    monkeypatch.setattr(build, "inputs", old_connector)
    result = build.analyze(reference["measured"], frame_parameters=reference["frame_parameters"])
    assert result["checks"]["connector_at_design_current"] is False
    assert result["power"]["throttle_limit_relied_on"] is False


def test_cut_and_post_drill_processes_are_kept_distinct(reference):
    processes = reference["manufacturing"]
    assert processes["post_drilled_holes"] == 16
    assert all(not r["holes_below_rule"] and not r["webs_below_rule"] for r in processes["cutter_blank"].values())
    assert processes["finished_geometry_against_cutting_rules"]["bottom_plate"]["holes_below_rule"] == ["motor_bolt_hole"]
    assert not processes["cutter_acceptance_obtained"]
    assert not processes["shop_drilling_qualified"]


def test_operator_has_a_drone_preview_without_executing_tools(tmp_path, monkeypatch):
    monkeypatch.setattr(op, "_native_drone", lambda *a: pytest.fail("preview executed CAD"))
    result = op.run_workshop_operator(op.DRONE_ID, out_dir=tmp_path / "preview")
    assert result["status"] == "planned_not_executed"
    assert result["engineering_acceptance"] is False
    assert result["canonical_machine_release"]["allowed"] is False


def test_green_metadata_without_required_artifacts_is_refused(tmp_path, monkeypatch):
    source = ROOT / op.REGISTERED[op.DRONE_ID]["source"]
    monkeypatch.setattr(op, "_registered_source_files", lambda *a: [source / "hs3g_frame.py"])
    def fake(command, **kwargs):
        package = tmp_path / "forged/candidate"; package.mkdir(parents=True, exist_ok=True)
        receipt = {"engineering_acceptance": True, "checks": {k: True for k in [
            "native_solids", "cut_blank_dfm", "configured_frame_dimensions", "official_hex_records", "source_identity", "no_physical_authority"]},
            "artifact_sha256": {}, "purchase_ready": False, "fabrication_authorized": False, "power_on_authorized": False, "flight_authorized": False}
        (package / "verification.json").write_text(json.dumps(receipt))
        return SimpleNamespace(returncode=0, stdout="green claim", stderr="")
    monkeypatch.setattr(op.subprocess, "run", fake)
    result = op.run_workshop_operator(op.DRONE_ID, out_dir=tmp_path / "forged", execute=True)
    assert result["engineering_acceptance"] is False
    assert result["status"] == "blocked_drone_independent_verification"
    assert result["canonical_machine_release"]["allowed"] is False


@pytest.fixture(scope="module")
def native(tmp_path_factory):
    pytest.importorskip("cadquery")
    out = tmp_path_factory.mktemp("hs3g-revision")
    result = build.build(out, REV / "reference/firmware")
    verifier = _module("hs_drone_revision_verify_tests", "verify_package.py")
    receipt = verifier.verify(out)
    assert receipt["engineering_acceptance"], receipt["failed_checks"]
    return out, result, verifier


@pytest.mark.requires_cadquery
def test_native_iteration_and_independent_acceptance(native):
    out, result, verifier = native
    assert all(result["checks"].values())
    assert (out / "ASSEMBLY_ENVELOPES.step").stat().st_size > 1000
    assert (out / "POST_DRILL_1_TO_1.svg").is_file()
    receipt = json.loads((out / "verification.json").read_text())
    assert receipt["configuration_complete"] is False
    assert not any(receipt[k] for k in ["purchase_ready", "fabrication_authorized", "power_on_authorized", "flight_authorized"])


@pytest.mark.requires_cadquery
@pytest.mark.parametrize("tamper,failed_check", [("bom", "bom_csv_matches_model"), ("motor_holes", "cut_blank_dfm"), ("firmware", "official_hex_records")])
def test_native_verifier_rejects_changed_deliverables(native, tmp_path, tamper, failed_check):
    original, _, verifier = native
    out = tmp_path / "modified"; shutil.copytree(original, out)
    if tamper == "bom":
        p = out / "BOM.csv"; p.write_text(p.read_text().replace("KV2900", "KV3800"))
    elif tamper == "motor_holes":
        shutil.copyfile(out / "finished_geometry/hs3g_bottom_plate.step", out / "cutter_blanks/hs3g_bottom_plate.step")
    else:
        p = out / "firmware/inav_9.1.0_SPEEDYBEEF405MINI.hex"; text = p.read_text(); p.write_text(text[:11] + ("0" if text[11] != "0" else "1") + text[12:])
    receipt = verifier.verify(out)
    assert receipt["engineering_acceptance"] is False
    assert failed_check in receipt["failed_checks"]

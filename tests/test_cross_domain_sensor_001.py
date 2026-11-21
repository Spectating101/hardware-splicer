"""Actual HS firmware/device planner + Mecha Splicer cross-domain package tests.

Runs core existing code, not a mocked CAD/firmware generator. No hardware used.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from hardware_splicer.device_plan import DevicePlanError, build_device_plan

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/generate_cross_domain_sensor_001.py"
spec = importlib.util.spec_from_file_location("hs_cross_domain_sensor_001", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_real_components_produce_shared_spec_package(tmp_path):
    result = module.build_cross_domain_package(module.sensor_only_spec(), tmp_path / "demo")
    out = tmp_path / "demo"
    assert result["revision_consistent"] is True
    assert result["firmware_package_status"] == "HOST_TESTABLE_PROPOSAL"
    assert (out / "FIRMWARE_SOURCE.zip").stat().st_size > 2000
    assert (out / "enclosure.scad").read_text().count("module base()") == 1
    assert "usb_cable_access" in (out / "ENCLOSURE_INPUT.json").read_text()
    assert "module vented_lid()" in (out / "enclosure.scad").read_text()
    vents = json.loads((out / "VENTILATION_PLAN.json").read_text())
    assert vents["slot_count"] == 4
    assert vents["nominal_lid_material_removed_mm3"] == pytest.approx(76.8)
    assert vents["catalog_footprints_nonoverlapping"]
    assert not vents["sensor_airflow_validated"]
    plan = json.loads((out / "DEVICE_PLAN.json").read_text())
    enc = json.loads((out / "ENCLOSURE_INPUT.json").read_text())
    assert enc["inner_w_mm"] == plan["case"]["inner_mm"]["x"]
    assert enc["inner_d_mm"] == plan["case"]["inner_mm"]["z"]
    assert enc["inner_h_mm"] == plan["case"]["inner_mm"]["y"]
    assert result["native_eda_artifacts_verified"] is False
    assert not result["fabrication_authorized"]
    assert not result["flashing_authorized"]
    assert not result["power_on_authorized"]


def test_change_to_spec_changes_all_bound_artifact_receipts(tmp_path):
    src = module.sensor_only_spec()
    first = module.build_cross_domain_package(src, tmp_path / "a")
    edited = module.sensor_only_spec()
    edited["case"]["clearance_mm"] = 1.2
    second = module.build_cross_domain_package(edited, tmp_path / "b")
    assert first["source_spec_sha256"] != second["source_spec_sha256"]
    assert first["artifacts"]["DEVICE_PLAN.json"]["sha256"] != second["artifacts"]["DEVICE_PLAN.json"]["sha256"]
    assert first["artifacts"]["enclosure.scad"]["sha256"] != second["artifacts"]["enclosure.scad"]["sha256"]
    assert first["artifacts"]["FIRMWARE_SOURCE.zip"]["sha256"] != second["artifacts"]["FIRMWARE_SOURCE.zip"]["sha256"]


def test_output_cannot_overwrite_prior_candidate(tmp_path):
    dest = tmp_path / "a"
    module.build_cross_domain_package(module.sensor_only_spec(), dest)
    with pytest.raises(FileExistsError):
        module.build_cross_domain_package(module.sensor_only_spec(), dest)


def test_unsupported_device_refuses_both_firmware_and_case(tmp_path):
    source = module.sensor_only_spec()
    source["connections"] = [c for c in source["connections"] if c["to"] != "mcu.IO21"]
    with pytest.raises(DevicePlanError):
        module.build_cross_domain_package(source, tmp_path / "invalid")
    assert not (tmp_path / "invalid").exists()


def test_usb_cutout_boundary_conflict_refused_without_geometry(tmp_path):
    plan = build_device_plan(module.sensor_only_spec())
    plan["case"]["usb_cutout"]["z"] = 10_000.0
    with pytest.raises(ValueError, match="USB aperture"):
        module._enclosure_from_plan(plan)


def test_sensor_vents_refuse_bad_module_envelope():
    plan = build_device_plan(module.sensor_only_spec())
    envelope, source = module._enclosure_from_plan(plan)
    sensor = next(x for x in plan["modules"] if x["id"] == "sensor")
    # Simulate a catalog variant too small to support the requested ventilation pattern.
    sensor["box"]["x1"] = sensor["box"]["x0"] + 7
    with pytest.raises(ValueError, match="vent pattern"):
        module._add_sensor_ventilation(plan, envelope, source)


def test_sensor_vents_reject_cross_domain_board_overlap():
    plan = build_device_plan(module.sensor_only_spec())
    envelope, source = module._enclosure_from_plan(plan)
    boards = {x["id"]: x for x in plan["modules"]}
    boards["sensor"]["box"] = dict(boards["mcu"]["box"])
    with pytest.raises(ValueError, match="footprints overlap"):
        module._add_sensor_ventilation(plan, envelope, source)


def test_sensor_vents_do_not_authorize_manufacture(tmp_path):
    result = module.build_cross_domain_package(module.sensor_only_spec(), tmp_path / "proposal")
    assert result["sensor_ventilation_geometry_proposed"]
    assert not result["enclosure_mounted_and_ventilated"]
    assert not result["fabrication_authorized"]
    manifest = json.loads((tmp_path / "proposal/VENTILATION_PLAN.json").read_text())
    assert manifest["mechanical_mounting_validated"] is False
    assert manifest["physical_dimensions_measured"] is False

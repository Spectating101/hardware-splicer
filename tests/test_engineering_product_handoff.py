"""Synthetic-only graph mapping regressions; CI separately replays actual native inputs."""
from __future__ import annotations
import copy
import hashlib
import json
import pytest
from hardware_splicer.engineering_product_handoff import from_verified_sensor
from hardware_splicer.machine_project import MachineProject, ReleaseState


def canonical(x):
    return (json.dumps(x, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()


def fixture():
    sha = hashlib.sha256(b"source spec fixture only").hexdigest()
    keys = ("DEVICE_SPEC.json", "ELECTRICAL_PREFLIGHT.json", "firmware.bin",
            "firmware.elf", "enclosure_base.stl", "enclosure_lid.stl",
            "retained_base.stl", "retained_lid.stl")
    files = {name: {"sha256": hashlib.sha256(name.encode()).hexdigest(),
                    "verified": True, "bytes": 42} for name in keys}
    files["DEVICE_SPEC.json"]["sha256"] = sha
    report = {
        "schema_version": "hardware_splicer.engineering_acceptance.v1",
        "source_spec_sha256": sha,
        "cross_domain_consistency_pass": True,
        "release_readiness": "software_candidate_only",
        "artifact_hashes_verified": files,
        "verified_native_toolchains": ["OpenSCAD + trimesh", "PlatformIO 6.1.18"],
        "physical_authority": {"fabrication": False, "flashing": False,
                               "power_on": False, "physical_product": False},
    }
    atlas = {
        "schema_version": "hardware_splicer.external_capability.v1",
        "capability_id": "hs.esp32_sensor_001.cross_domain_software",
        "provenance": {
            "source_spec_sha256": sha,
            "report_sha256": hashlib.sha256(canonical(report)).hexdigest(),
        },
        "authorization": {"real_world_actuation": False, "fabrication": False},
    }
    spec = {"name": "Sensor 001", "modules": [{"id": "mcu"}, {"id": "sensor"}]}
    plan = {"modules": [{"id": "mcu", "module": "esp32-devkitc-v4"},
                        {"id": "sensor", "module": "adafruit-bme280-stemma-qt"}]}
    electrical = {
        "source_spec_sha256": sha,
        "software_source_pin_consistency": True,
        "symbolic_catalog_net_consistency": True,
        "i2c_gpios": {"sda": 21, "scl": 22},
        "native_kicad_erc_drc_executed": False,
    }
    return report, atlas, spec, plan, electrical


def test_second_product_is_canonical_and_physically_blocked():
    model, summary = from_verified_sensor(*fixture())
    assert isinstance(model, MachineProject)
    assert MachineProject.model_validate(model.model_dump(mode="json")) == model
    assert model.project_id == "esp32_bme280_sensor_001"
    assert len(model.requirements) == 5
    assert len(model.subsystems) == 3
    assert len(model.components) == 3
    assert len(model.interfaces) == 2
    assert [x.status.value for x in model.verifications].count("passed") == 3
    assert [x.status.value for x in model.verifications].count("planned") == 2
    assert all(e.simulated and e.metadata["nonphysical_digital_only"] for e in model.evidence)
    assert not model.assess_release(ReleaseState.OPERATIONALLY_AUTHORIZED).allowed
    assert "safety_not_closed" in summary["release_blockers"]
    assert not summary["manufacturing_authorized"]
    assert not summary["firmware_flashing_authorized"]
    assert not summary["product_specimen_complete_digitally"]


@pytest.mark.parametrize("case", [
    "different_source", "forged_acceptance", "forged_atlas",
    "missing_firmware", "missing_cad", "physical_authority",
    "unexpected_kicad", "different_sensor", "wrong_i2c",
])
def test_refuse_untrusted_or_stale_sensor_machine_handoff(case):
    p = list(copy.deepcopy(fixture()))
    if case == "different_source":
        p[0]["source_spec_sha256"] = "f" * 64
    elif case == "forged_acceptance":
        p[0]["cross_domain_consistency_pass"] = False
    elif case == "forged_atlas":
        p[1]["provenance"]["report_sha256"] = "0" * 64
    elif case == "missing_firmware":
        del p[0]["artifact_hashes_verified"]["firmware.bin"]
    elif case == "missing_cad":
        del p[0]["artifact_hashes_verified"]["retained_lid.stl"]
    elif case == "physical_authority":
        p[0]["physical_authority"]["power_on"] = True
    elif case == "unexpected_kicad":
        p[4]["native_kicad_erc_drc_executed"] = True
    elif case == "different_sensor":
        p[3]["modules"][1]["module"] = "different-part"
    elif case == "wrong_i2c":
        p[4]["i2c_gpios"]["sda"] = 23
    with pytest.raises(ValueError, match="handoff refused"):
        from_verified_sensor(*p)

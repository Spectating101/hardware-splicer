"""A pasted bench scan is compared with the plan; an acknowledge is never an identity."""

import copy
import json
import re

import pytest
from fastapi.testclient import TestClient

from hardware_splicer import device_plan
from hardware_splicer.device_observations import MAX_TRANSCRIPT_CHARS, check_device_observations
from hardware_splicer.device_plan import DevicePlanError, example_specs, module_library
from hardware_splicer.firmware_scaffold import generate_i2c_diagnostic_source
from hardware_splicer.product_api import create_product_app
from hardware_splicer.project_store import ProjectStore

SPEC = example_specs()["esp32_oled_bme280_usb"]


def _scan(*acks, errors=(), total=None, header=True):
    lines = []
    if header:
        lines += ["PROPOSAL ONLY: review wiring, supply and pull-ups before use.",
                  "Declared possible addresses, NOT observations: 0x3C 0x3D 0x76 0x77",
                  "No automatic scan. A serial 's' requests an address probe."]
    lines += [f"Observed ACK at 0x{a:02X}; identity and function unverified." for a in acks]
    lines += [f"Probe error {code} at 0x{a:02X}." for a, code in errors]
    lines.append(f"Observed acknowledgements: {len(acks) if total is None else total}. No sensor readings or physical validation.")
    return "\n".join(lines) + "\n"


def _status(result):
    return {m["id"]: m["status"] for m in result["modules"]}


def test_a_scan_with_each_module_answering_is_consistent_and_still_claims_nothing():
    result = check_device_observations(SPEC, _scan(0x3C, 0x77))
    assert _status(result) == {"display": "acknowledged", "sensor": "acknowledged"}
    assert result["summary"] == {"assessed": True, "consistent_with_declared_addresses": True,
                                 "statement": result["summary"]["statement"]}
    assert result["provenance"] == "operator_supplied_text"
    assert result["firmware_authorized"] is False and result["power_on_authorized"] is False
    assert result["physical_correctness"] == "UNPROVEN"
    assert "identify the chip" in result["claim_boundary"]
    assert result["declared_addresses_match_plan"] is True
    by_id = {m["id"]: m for m in result["modules"]}
    assert by_id["display"]["acknowledged_at"] == ["0x3C"] and by_id["sensor"]["acknowledged_at"] == ["0x77"]


def test_a_module_that_does_not_answer_is_reported_without_a_cause():
    result = check_device_observations(SPEC, _scan(0x3C))
    assert _status(result)["sensor"] == "no_acknowledge"
    assert result["summary"]["consistent_with_declared_addresses"] is False
    note = next(m for m in result["modules"] if m["id"] == "sensor")["note"]
    assert "cannot say why" in note


def test_a_scan_without_its_closing_total_is_not_assessed():
    text = "Observed ACK at 0x3C; identity and function unverified.\nObserved ACK at 0x77; identity and function unverified.\n"
    result = check_device_observations(SPEC, text)
    assert result["summary"]["assessed"] is False
    assert result["summary"]["consistent_with_declared_addresses"] is None
    assert set(_status(result).values()) == {"not_assessed"}
    assert "cut short" in result["scans"][0]["note"]


def test_a_total_that_disagrees_with_the_lines_is_not_assessed():
    result = check_device_observations(SPEC, _scan(0x3C, 0x77, total=3))
    assert result["summary"]["assessed"] is False
    assert "does not match" in result["scans"][0]["note"]


def test_a_failed_bus_start_gives_no_result():
    result = check_device_observations(SPEC, "I2C initialization failed; no scan result.\n")
    assert result["summary"]["assessed"] is False
    assert result["scans"][0]["complete"] is False


def test_both_alternatives_answering_is_ambiguous_not_chosen():
    result = check_device_observations(SPEC, _scan(0x3C, 0x76, 0x77))
    assert _status(result)["sensor"] == "ambiguous"
    assert result["summary"]["consistent_with_declared_addresses"] is False


def test_an_address_nobody_declares_is_reported_neutrally():
    result = check_device_observations(SPEC, _scan(0x3C, 0x77, 0x57))
    assert result["unexpected_acknowledgements"] == ["0x57"]
    assert result["summary"]["consistent_with_declared_addresses"] is True


def test_an_i2c_error_at_a_declared_address_is_not_a_confirmed_absence():
    result = check_device_observations(SPEC, _scan(0x3C, errors=[(0x77, 4)]))
    assert _status(result)["sensor"] == "bus_error"
    assert result["summary"]["consistent_with_declared_addresses"] is False


def test_the_latest_complete_scan_is_used_and_disagreement_is_reported():
    result = check_device_observations(SPEC, _scan(0x3C, 0x77) + _scan(0x3C, header=False))
    assert result["scan_used"] == 1
    assert result["scans_stable"] is False
    assert _status(result)["sensor"] == "no_acknowledge"
    steady = check_device_observations(SPEC, _scan(0x3C, 0x77) + _scan(0x3C, 0x77, header=False))
    assert steady["scans_stable"] is True


def test_a_transcript_from_a_different_plan_is_flagged():
    other = _scan(0x3C, 0x77).replace("0x3C 0x3D 0x76 0x77", "0x3C 0x3D")
    result = check_device_observations(SPEC, other)
    assert result["declared_addresses_match_plan"] is False


def test_serial_monitor_timestamps_and_crlf_are_accepted():
    stamped = "".join(f"12:03:{i:02d}.123 > {line}\r\n" for i, line in enumerate(_scan(0x3C, 0x77, header=False).splitlines()))
    assert _status(check_device_observations(SPEC, stamped)) == {"display": "acknowledged", "sensor": "acknowledged"}


def test_an_empty_transcript_is_not_an_error_and_concludes_nothing():
    result = check_device_observations(SPEC, "")
    assert result["summary"]["assessed"] is False and result["unrecognised_lines"] == 0


def test_unrelated_lines_are_counted_not_trusted():
    result = check_device_observations(SPEC, "hello\n" + _scan(0x3C, 0x77, header=False))
    assert result["unrecognised_lines"] == 1


def test_a_shared_address_cannot_be_attributed(tmp_path, monkeypatch):
    original = copy.deepcopy(module_library())
    original["modules"][2]["i2c"]["addresses"] = ["0x3C", "0x76"]
    path = tmp_path / "device_modules.json"
    path.write_text(json.dumps(original), encoding="utf-8")
    monkeypatch.setattr(device_plan, "LIBRARY_PATH", path)
    device_plan._library.cache_clear()
    try:
        result = check_device_observations(SPEC, _scan(0x3C))
        assert _status(result) == {"display": "shared_address", "sensor": "shared_address"}
        assert result["summary"]["consistent_with_declared_addresses"] is None
    finally:
        device_plan._library.cache_clear()


@pytest.mark.parametrize("bad", [None, 5, "\x1b[31mred", "a" * (MAX_TRANSCRIPT_CHARS + 1), "x" * 301])
def test_a_bad_transcript_is_refused(bad):
    with pytest.raises(DevicePlanError):
        check_device_observations(SPEC, bad)


def test_the_parser_matches_what_the_diagnostic_sketch_actually_prints():
    source = generate_i2c_diagnostic_source(sda=21, scl=22, declared_addresses=["0x3C", "0x77"])
    for fragment in ("Observed ACK at 0x%02X; identity and function unverified.",
                     "Probe error %u at 0x%02X.",
                     "Observed acknowledgements: %u. No sensor readings or physical validation.",
                     "I2C initialization failed; no scan result.",
                     "Declared possible addresses, NOT observations: 0x3C 0x77"):
        assert fragment in source


def test_the_check_recomputes_from_the_spec_and_refuses_an_invalid_one():
    with pytest.raises(DevicePlanError):
        check_device_observations({"modules": []}, _scan())
    bad = copy.deepcopy(SPEC)
    bad["modules"][0]["module"] = "nope"
    with pytest.raises(DevicePlanError):
        check_device_observations(bad, _scan())


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setenv("HARDWARE_SPLICER_OUTPUT_ROOT", str(tmp_path))
    return TestClient(create_product_app(ProjectStore(tmp_path / "store")))


def test_the_http_contract_is_stateless_and_strict(api, tmp_path):
    before = sorted(str(p) for p in tmp_path.rglob("*"))
    ok = api.post("/v1/devices/observations", json={"spec": SPEC, "transcript": _scan(0x3C, 0x77)})
    assert ok.status_code == 200
    assert ok.json()["observation"]["summary"]["consistent_with_declared_addresses"] is True
    assert api.post("/v1/devices/observations", json={"spec": SPEC}).status_code == 422
    assert api.post("/v1/devices/observations", json=[1]).status_code == 422
    assert api.post("/v1/devices/observations", content=b"not json").status_code == 422
    assert api.post("/v1/devices/observations", json={"spec": SPEC, "transcript": "\x00"}).status_code == 422
    assert sorted(str(p) for p in tmp_path.rglob("*")) == before


# --- the application's own serial output ------------------------------------------------------------------------------


def _app(*lines):
    return "\n".join(lines) + "\n"


READING = "T=0 STATE=OK TEMP_C=21.50 HUM_PCT=45.0 PRES_HPA=1013.3"


def test_the_applications_boot_line_is_chip_id_evidence_for_the_sensor_and_a_presence_check_for_the_display():
    result = check_device_observations(SPEC, _app("BOOT sensor=0x77 display=0x3C", READING))
    by_id = {m["id"]: m for m in result["modules"]}
    assert by_id["sensor"]["status"] == "acknowledged" and by_id["sensor"]["acknowledged_at"] == ["0x77"]
    assert by_id["sensor"]["evidence"] == "application_chip_id_match"
    assert "register 0xD0 read 0x60" in by_id["sensor"]["note"]
    assert by_id["display"]["status"] == "acknowledged" and by_id["display"]["evidence"] == "application_presence_check"
    assert "not a display identity" in by_id["display"]["note"]
    assert result["summary"]["assessed"] is True and result["summary"]["consistent_with_declared_addresses"] is True
    assert result["application"]["boot"] == {"sensor": "0x77", "display": "0x3C"}
    assert result["application"]["readings"] == 1
    assert result["provenance"] == "operator_supplied_text"
    assert result["firmware_authorized"] is False and result["physical_correctness"] == "UNPROVEN"


def test_a_missing_display_and_a_missing_sensor_are_reported_from_the_application_output():
    missing_display = check_device_observations(SPEC, _app("DISPLAY MISSING", "BOOT sensor=0x76 display=NONE", READING))
    by_id = {m["id"]: m for m in missing_display["modules"]}
    assert by_id["sensor"]["status"] == "acknowledged" and by_id["display"]["status"] == "no_acknowledge"
    assert missing_display["summary"]["consistent_with_declared_addresses"] is False

    missing_sensor = check_device_observations(SPEC, _app("T=0 STATE=FAULT_SENSOR_MISSING"))
    by_id = {m["id"]: m for m in missing_sensor["modules"]}
    assert by_id["sensor"]["status"] == "no_acknowledge"
    assert "cannot say why" in by_id["sensor"]["note"]
    assert by_id["display"]["status"] == "not_assessed"


def test_an_ambiguous_address_fault_is_not_resolved_by_the_text():
    result = check_device_observations(SPEC, _app("DISPLAY MISSING", "T=0 STATE=FAULT_AMBIGUOUS_ADDRESS"))
    assert {m["id"]: m["status"] for m in result["modules"]}["sensor"] == "ambiguous"


def test_the_latest_boot_line_counts():
    result = check_device_observations(SPEC, _app("BOOT sensor=0x77 display=0x3C", "BOOT sensor=0x76 display=0x3D"))
    by_id = {m["id"]: m for m in result["modules"]}
    assert by_id["sensor"]["acknowledged_at"] == ["0x76"] and by_id["display"]["acknowledged_at"] == ["0x3D"]


def test_a_scan_and_the_application_that_agree_or_disagree_are_both_reported():
    agree = check_device_observations(SPEC, _scan(0x3C, 0x77) + _app("BOOT sensor=0x77 display=0x3C"))
    assert all(m["application"]["agrees"] is True for m in agree["modules"])
    differ = check_device_observations(SPEC, _scan(0x3C, 0x77) + _app("BOOT sensor=0x76 display=0x3C"))
    sensor = next(m for m in differ["modules"] if m["id"] == "sensor")
    # Same status, different address: that is a disagreement, and the scan stays the primary text.
    assert sensor["status"] == "acknowledged" and sensor["acknowledged_at"] == ["0x77"]
    assert sensor["application"]["acknowledged_at"] == ["0x76"]
    assert sensor["application"]["agrees"] is False and "differs" in sensor["note"]
    broken = check_device_observations(SPEC, _scan(0x3C) + _app("BOOT sensor=0x77 display=0x3C"))
    sensor = next(m for m in broken["modules"] if m["id"] == "sensor")
    assert sensor["status"] == "no_acknowledge" and sensor["application"]["agrees"] is False
    assert "differs" in sensor["note"]


def test_application_lines_with_other_modules_say_nothing_about_them(tmp_path):
    spec = copy.deepcopy(SPEC)
    spec["modules"].append({"id": "light", "module": "adafruit-bh1750-stemma-qt"})
    spec["connections"] += [{"from": "light.VIN", "to": "mcu.3V3"}, {"from": "light.GND", "to": "mcu.GND"},
                            {"from": "light.SCL", "to": "mcu.IO22"}, {"from": "light.SDA", "to": "mcu.IO21"}]
    result = check_device_observations(spec, _app("BOOT sensor=0x77 display=0x3C"))
    assert {m["id"]: m["status"] for m in result["modules"]}["light"] == "not_assessed"
    assert result["summary"]["consistent_with_declared_addresses"] is None or result["summary"]["consistent_with_declared_addresses"] is False


def test_the_parser_matches_the_lines_the_application_actually_prints():
    from pathlib import Path

    core = (Path(__file__).resolve().parents[1] / "src/hardware_splicer/data/firmware_application/app_core.h").read_text()
    for fragment in ('"BOOT sensor=0x%02X display=0x%02X"', '"BOOT sensor=0x%02X display=NONE"', '"T=%u STATE=%s"',
                     '"T=%u STATE=OK TEMP_C=%.2f HUM_PCT=%.1f PRES_HPA=%.1f"', 'hal_.log("DISPLAY MISSING")',
                     'hal_.log("RECOVERED")'):
        assert fragment in core
    for state in ("OK", "STALE", "FAULT_SENSOR_MISSING", "FAULT_SENSOR_READ", "FAULT_AMBIGUOUS_ADDRESS"):
        assert f'return "{state}";' in core


def test_application_text_with_timestamps_is_accepted():
    stamped = "12:03:44.123 > BOOT sensor=0x77 display=0x3C\r\n"
    assert {m["id"]: m["status"] for m in check_device_observations(SPEC, stamped)["modules"]} == {
        "display": "acknowledged", "sensor": "acknowledged"}


@pytest.mark.parametrize("state,status", [
    ("FAULT_AMBIGUOUS_ADDRESS", "ambiguous"), ("FAULT_SENSOR_MISSING", "no_acknowledge"),
    ("FAULT_SENSOR_READ", "sensor_read_fault"), ("STALE", "stale"),
])
def test_a_later_fault_is_not_masked_by_boot_success(state, status):
    result = check_device_observations(SPEC, _app("BOOT sensor=0x77 display=0x3C", f"T=2000 STATE={state}"))
    assert _status(result)["sensor"] == status
    assert result["summary"]["consistent_with_declared_addresses"] is False
    assert result["physical_correctness"] == "UNPROVEN" and result["power_on_authorized"] is False


def test_recovery_and_reboot_replace_the_latest_fault_not_the_history():
    result = check_device_observations(SPEC, _app("BOOT sensor=0x77 display=0x3C", "T=2000 STATE=FAULT_SENSOR_READ",
                                                "RECOVERED", READING))
    assert _status(result)["sensor"] == "acknowledged"
    assert result["application"]["states"]["FAULT_SENSOR_READ"] == 1
    assert result["application"]["latest_state"] == "OK"
    reboot = check_device_observations(SPEC, _app("T=0 STATE=FAULT_AMBIGUOUS_ADDRESS", "BOOT sensor=0x76 display=0x3D"))
    assert _status(reboot)["sensor"] == "acknowledged"


def test_a_good_scan_does_not_resolve_a_later_application_fault():
    result = check_device_observations(SPEC, _scan(0x3C, 0x77) + _app("BOOT sensor=0x77 display=0x3C", "T=2000 STATE=FAULT_SENSOR_READ"))
    assert result["summary"]["consistent_with_declared_addresses"] is False
    assert next(m for m in result["modules"] if m["id"] == "sensor")["application"]["agrees"] is False


@pytest.mark.parametrize("line", ["T=0 STATE=OK", "T=0 STATE=FAULT_SENSOR_READ TEMP_C=21.50 HUM_PCT=45.0 PRES_HPA=1013.3"])
def test_invalid_application_state_shapes_are_not_readings(line):
    result = check_device_observations(SPEC, line)
    assert result["unrecognised_lines"] == 1 and result["application"] is None


def test_more_than_fifty_scans_keep_the_latest_not_the_first():
    result = check_device_observations(SPEC, _scan(0x3C, 0x77) * 50 + _scan(0x3C))
    assert len(result["scans"]) == 50
    assert _status(result)["sensor"] == "no_acknowledge"

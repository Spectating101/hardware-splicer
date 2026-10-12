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

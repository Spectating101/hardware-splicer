"""The compiled design must contain what the request listed, or say that it does not."""

from __future__ import annotations

from hardware_splicer.request_fidelity import assess_request_fidelity


def _graph(*module_ids: str) -> dict:
    return {"nodes": [{"id": f"n{i}", "moduleId": module_id} for i, module_id in enumerate(module_ids, 1)]}


PAN_TILT_REQUEST = [
    {"module_id": "esp32-devkit", "name": "ESP32 DevKit"},
    {"module_id": "sg90", "name": "SG90 pan servo"},
    {"module_id": "sg90", "name": "SG90 tilt servo"},
    {"module_id": "usb-power-5v", "name": "USB 5V power bank"},
]


def test_two_requested_servos_with_one_in_the_design_is_a_mismatch_naming_the_missing_servo() -> None:
    result = assess_request_fidelity(PAN_TILT_REQUEST, _graph("esp32-devkit", "sg90", "usb-power-5v"))

    assert result["status"] == "mismatch"
    [missing] = result["missing_parts"]
    assert missing["module_id"] == "sg90"
    assert (missing["requested"], missing["in_design"]) == (2, 1)
    assert missing["names"] == ["SG90 pan servo", "SG90 tilt servo"]


def test_every_requested_part_present_in_the_right_count_matches() -> None:
    result = assess_request_fidelity(
        PAN_TILT_REQUEST, _graph("esp32-devkit", "sg90", "sg90", "usb-power-5v")
    )

    assert result["status"] == "matches"
    assert result["missing_parts"] == []


def test_no_compiled_graph_means_not_assessable_never_a_match() -> None:
    assert assess_request_fidelity(PAN_TILT_REQUEST, None)["status"] == "not_assessable"


def test_an_empty_request_has_nothing_to_compare_so_it_is_not_assessable() -> None:
    assert assess_request_fidelity([], _graph("esp32-devkit"))["status"] == "not_assessable"


def test_a_compiled_design_with_no_parts_is_a_mismatch_not_unassessable() -> None:
    result = assess_request_fidelity(PAN_TILT_REQUEST, {"nodes": []})

    assert result["status"] == "mismatch"
    assert {row["module_id"] for row in result["missing_parts"]} == {"esp32-devkit", "sg90", "usb-power-5v"}


def test_a_requested_part_with_no_module_cannot_be_compared_and_blocks_a_match() -> None:
    request = [{"module_id": "esp32-devkit", "name": "ESP32 DevKit"}, {"name": "unidentified relay board"}]
    result = assess_request_fidelity(request, _graph("esp32-devkit"))

    assert result["status"] == "not_assessable"
    assert result["unmapped_requests"] == ["unidentified relay board"]


def test_a_mismatch_outranks_an_unmapped_part() -> None:
    request = [{"module_id": "sg90", "name": "pan servo"}, {"name": "unidentified relay board"}]

    assert assess_request_fidelity(request, _graph())["status"] == "mismatch"


def test_parts_the_design_added_beyond_the_request_are_listed_but_do_not_fail_it() -> None:
    result = assess_request_fidelity(
        [{"module_id": "esp32-devkit", "name": "ESP32 DevKit"}],
        _graph("esp32-devkit", "ldo-3v3", "ldo-3v3"),
    )

    assert result["status"] == "matches"
    assert result["unrequested_in_design"] == [{"module_id": "ldo-3v3", "count": 2}]


def test_the_result_states_what_it_does_not_check() -> None:
    result = assess_request_fidelity(PAN_TILT_REQUEST, _graph("esp32-devkit"))

    assert result["schema_version"] == "hardware_splicer.request_fidelity.v1"
    for limit in ("wiring", "firmware", "function"):
        assert limit in result["claim_boundary"]


def test_with_no_compiled_graph_no_part_is_reported_missing() -> None:
    result = assess_request_fidelity(PAN_TILT_REQUEST, None)

    assert result["status"] == "not_assessable"
    assert result["missing_parts"] == []

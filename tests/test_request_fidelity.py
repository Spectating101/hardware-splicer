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


def _unknown_row(module_id: str, name: str = "part") -> dict:
    result = assess_request_fidelity([{"module_id": module_id, "name": name}], _graph("esp32-devkit"))
    [row] = result["missing_parts"]
    return row


def test_an_id_hs_does_not_know_is_flagged_and_given_the_ids_it_was_probably_meant_to_be() -> None:
    for guess, expected in (
        ("usb-5v", "usb-power-5v"),
        ("usb-5v-supply", "usb-power-5v"),
        ("ds3231", "ds3231_rtc"),
        ("ds3231-module", "ds3231_rtc"),
        ("rtc-ds3231", "ds3231_rtc"),
        ("bme-280", "bme280"),
    ):
        row = _unknown_row(guess)

        assert row["unknown_module_id"] is True, guess
        assert expected in row["did_you_mean"], (guess, row["did_you_mean"])


def test_a_suggestion_is_never_a_part_that_only_shares_a_generic_word() -> None:
    assert "esp32-cam-module" not in _unknown_row("ds3231-module")["did_you_mean"]
    assert "ds1307_rtc" not in _unknown_row("ds3231-rtc")["did_you_mean"]
    assert "bmp280" not in _unknown_row("bme-280")["did_you_mean"]


def test_an_id_with_nothing_plausible_gets_no_suggestion_rather_than_a_wrong_one() -> None:
    row = _unknown_row("zzz-qq", "mystery part")

    assert row["unknown_module_id"] is True
    assert row["did_you_mean"] == []


def test_a_real_part_that_is_simply_missing_from_the_design_is_not_called_unknown() -> None:
    result = assess_request_fidelity([{"module_id": "sg90", "name": "servo"}], _graph("esp32-devkit"))
    [row] = result["missing_parts"]

    assert row["unknown_module_id"] is False
    assert row["did_you_mean"] == []

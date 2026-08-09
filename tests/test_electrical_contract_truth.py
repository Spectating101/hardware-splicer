from __future__ import annotations

import pytest

from hardware_splicer.electrical_contract_truth import (
    contract_snapshot,
    exact_output_voltage_v,
    is_bidirectional_motor_driver_interface,
    logic_input_min_v,
    max_output_current_a,
    output_voltage_range_v,
)


def test_power_module_ranges_and_currents_come_from_structured_fields() -> None:
    assert output_voltage_range_v("buck-lm2596") == pytest.approx((1.2, 30.0))
    assert max_output_current_a("buck-lm2596") == pytest.approx(2.0)

    assert output_voltage_range_v("buck-mp1584") == pytest.approx((0.8, 20.0))
    assert max_output_current_a("buck-mp1584") == pytest.approx(3.0)

    assert output_voltage_range_v("boost-mt3608") == pytest.approx((5.0, 28.0))
    assert max_output_current_a("boost-mt3608") == pytest.approx(2.0)

    assert output_voltage_range_v("ldo-ams1117-3v3") == pytest.approx((3.3, 3.3))
    assert exact_output_voltage_v("ldo-ams1117-3v3") == pytest.approx(3.3)
    assert max_output_current_a("ldo-ams1117-3v3") == pytest.approx(1.0)

    assert output_voltage_range_v("tp4056") == pytest.approx((3.0, 4.2))
    assert max_output_current_a("tp4056") == pytest.approx(1.0)


def test_fixed_source_voltage_does_not_invent_source_current() -> None:
    assert exact_output_voltage_v("usb-power-5v") == pytest.approx(5.0)
    assert max_output_current_a("usb-power-5v") is None
    assert exact_output_voltage_v("dc-barrel-12v") == pytest.approx(12.0)
    assert max_output_current_a("dc-barrel-12v") is None


def test_auxiliary_power_pin_is_not_motor_driver_current_truth() -> None:
    # L298N has a 100mA 5V auxiliary output pin. That must never become the
    # H-bridge motor-channel current rating.
    assert max_output_current_a("l298n") is None
    snapshot = contract_snapshot("l298n")
    assert snapshot["max_output_current_a"] is None


def test_human_summary_and_nominal_pin_voltage_do_not_become_guaranteed_thresholds() -> None:
    assert logic_input_min_v("l298n") is None
    assert logic_input_min_v("mosfet-irlz44n") is None
    assert logic_input_min_v("mosfet-irf520") is None
    assert max_output_current_a("drv8833-motor") is None
    assert max_output_current_a("l9110-motor") is None


def test_bidirectional_motor_driver_identity_is_structural_not_magic_id_table() -> None:
    assert is_bidirectional_motor_driver_interface("l298n") is True
    assert is_bidirectional_motor_driver_interface("drv8833-motor") is True
    assert is_bidirectional_motor_driver_interface("l9110-motor") is True
    assert is_bidirectional_motor_driver_interface("mosfet-irlz44n") is False
    assert is_bidirectional_motor_driver_interface("usb-power-5v") is False


def test_contract_snapshot_labels_fact_source_and_zero_authority_effect() -> None:
    snapshot = contract_snapshot("buck-lm2596")
    assert snapshot["source"] == "structured_catalog_fields_only"
    assert snapshot["authority_effect"] == "none"
    assert snapshot["output_voltage_range_v"] == pytest.approx([1.2, 30.0])
    assert snapshot["max_output_current_a"] == pytest.approx(2.0)

import math

import pytest

from hardware_splicer.spi_derived_rc_spice import (
    build_rc_spice_netlist,
    build_rc_sweep,
    analytical_rc_step,
)


def test_analytical_rc_matches_first_order_10_90_formula() -> None:
    result = analytical_rc_step(
        rail_v=1.8,
        source_resistance_ohm=50.0,
        series_resistance_ohm=22.0,
        load_capacitance_pf=25.0,
    )

    tau_ns = 72.0 * 25.0e-12 * 1e9
    expected_rise_ns = math.log(9.0) * tau_ns
    assert result["tau_ns"] == pytest.approx(tau_ns)
    assert result["rise_10_90_ns"] == pytest.approx(expected_rise_ns)
    assert result["evidence_class"] == "derived_surrogate_only"
    assert result["vendor_model_campaign_credit_eligible"] is False
    assert result["physical_correctness"] == "UNPROVEN"
    assert result["physical_authority_granted"] is False


def test_rc_sweep_is_frozen_36_case_grid() -> None:
    sweep = build_rc_sweep()

    assert sweep["case_count"] == 36
    assert len(sweep["rows"]) == 36
    assert {row["rail_v"] for row in sweep["rows"]} == {1.773, 1.8, 1.827}
    assert {row["series_resistance_ohm"] for row in sweep["rows"]} == {0.0, 22.0, 47.0}
    assert {row["load_capacitance_pf"] for row in sweep["rows"]} == {10.0, 25.0, 50.0, 100.0}
    assert sweep["vendor_model_campaign_credit_eligible"] is False


def test_larger_capacitance_and_resistance_monotonically_slow_edges() -> None:
    fast = analytical_rc_step(
        rail_v=1.8,
        source_resistance_ohm=50.0,
        series_resistance_ohm=0.0,
        load_capacitance_pf=10.0,
    )
    slow = analytical_rc_step(
        rail_v=1.8,
        source_resistance_ohm=50.0,
        series_resistance_ohm=47.0,
        load_capacitance_pf=100.0,
    )

    assert slow["rise_10_90_ns"] > fast["rise_10_90_ns"]


def test_spice_netlist_is_labeled_and_contains_measurements() -> None:
    analytic = analytical_rc_step(
        rail_v=1.8,
        source_resistance_ohm=50.0,
        series_resistance_ohm=22.0,
        load_capacitance_pf=25.0,
    )
    text = build_rc_spice_netlist(analytic)

    assert "NOT IBIS" in text
    assert ".meas tran T10" in text
    assert ".meas tran T90" in text
    assert ".meas tran TR1090" in text
    assert "CLOAD out 0 25p" in text


@pytest.mark.parametrize(
    "kwargs",
    [
        {"rail_v": 0.0, "source_resistance_ohm": 50.0, "series_resistance_ohm": 22.0, "load_capacitance_pf": 25.0},
        {"rail_v": 1.8, "source_resistance_ohm": 0.0, "series_resistance_ohm": 22.0, "load_capacitance_pf": 25.0},
        {"rail_v": 1.8, "source_resistance_ohm": 50.0, "series_resistance_ohm": -1.0, "load_capacitance_pf": 25.0},
        {"rail_v": 1.8, "source_resistance_ohm": 50.0, "series_resistance_ohm": 22.0, "load_capacitance_pf": 0.0},
    ],
)
def test_invalid_rc_domains_fail_closed(kwargs) -> None:
    with pytest.raises(ValueError):
        analytical_rc_step(**kwargs)

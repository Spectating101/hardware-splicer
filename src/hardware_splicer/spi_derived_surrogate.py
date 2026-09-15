"""Derived-surrogate SPI engineering model.

This layer is intentionally below manufacturer-model evidence. Every parameter must carry a
source/derivation identity, but outputs are never eligible for vendor-model campaign credit,
measured evidence, or physical authority.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

SCHEMA_VERSION = "hardware_splicer.spi_derived_surrogate.v1"


def build_default_surrogate() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "surrogate_id": "hs-spi-derived-surrogate-v1",
        "evidence_class": "derived_surrogate_only",
        "eligible_for_vendor_model_campaign_credit": False,
        "parameters": {
            "host_logic_v": {"value": 3.3, "source_ids": ["src-controller"]},
            "dut_vcc_v": {"value": 1.8, "source_ids": ["dut-operating-supply"]},
            "dut_vcc_min_v": {"value": 1.7, "source_ids": ["dut-operating-supply"]},
            "dut_vcc_max_v": {"value": 1.95, "source_ids": ["dut-operating-supply"]},
            "dut_pin_abs_max_offset_v": {"value": 0.4, "source_ids": ["dut-pin-absolute-maximum"]},
            "txu_a_to_b_tpd_ns": {"value": 19.0, "source_ids": ["txu-switching-characteristics"]},
            "txu_b_to_a_tpd_ns": {"value": 15.0, "source_ids": ["txu-switching-characteristics"]},
            "dut_tclqv_ns": {"value": 6.0, "source_ids": ["w25q128jw-tclqv"]},
            "host_setup_ns": {"value": 8.0, "derivation": "surrogate_assumption", "source_ids": []},
            "host_launch_ns": {"value": 8.0, "derivation": "surrogate_assumption", "source_ids": []},
            "clock_skew_ns": {"value": 4.0, "derivation": "surrogate_assumption", "source_ids": []},
            "load_cap_pf": {"value": 20.0, "derivation": "surrogate_assumption", "source_ids": []},
            "load_penalty_ns_per_10pf": {"value": 2.0, "derivation": "surrogate_assumption", "source_ids": []},
        },
        "authority": {
            "modeled_evidence_only": True,
            "measured_evidence_present": False,
            "physical_correctness": "UNPROVEN",
            "fabrication_ready": False,
            "power_on_ready": False,
            "physical_authority_granted": False,
            "authority_effect": "none",
        },
    }


def clone_default_surrogate() -> dict[str, Any]:
    return deepcopy(build_default_surrogate())


def _value(model: Mapping[str, Any], name: str) -> float:
    row = model.get("parameters", {}).get(name, {})
    value = row.get("value") if isinstance(row, Mapping) else None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"surrogate parameter {name!r} is not numeric")
    return float(value)


def evaluate_surrogate_case(
    model: Mapping[str, Any],
    *,
    spi_clock_hz: int,
    direct_drive: bool = False,
    miso_direction: str = "dut_to_host",
    translator_topology: str = "fixed_3_forward_1_reverse",
    oe_enabled: bool = True,
    dut_rail_present: bool = True,
    dut_vcc_v: float | None = None,
    load_cap_pf: float | None = None,
) -> dict[str, Any]:
    """Evaluate one bounded software-only SPI case with explicit assumptions."""

    if spi_clock_hz <= 0:
        raise ValueError("spi_clock_hz must be positive")

    vcc = float(dut_vcc_v if dut_vcc_v is not None else _value(model, "dut_vcc_v"))
    load_pf = float(load_cap_pf if load_cap_pf is not None else _value(model, "load_cap_pf"))
    half_period_ns = 1e9 / float(spi_clock_hz) / 2.0
    abs_max_v = vcc + _value(model, "dut_pin_abs_max_offset_v")
    load_penalty_ns = max(load_pf, 0.0) / 10.0 * _value(model, "load_penalty_ns_per_10pf")

    forward_total_ns = (
        _value(model, "host_launch_ns")
        + _value(model, "txu_a_to_b_tpd_ns")
        + _value(model, "clock_skew_ns")
        + load_penalty_ns
    )
    return_total_ns = (
        _value(model, "dut_tclqv_ns")
        + _value(model, "txu_b_to_a_tpd_ns")
        + _value(model, "host_setup_ns")
        + _value(model, "clock_skew_ns")
        + load_penalty_ns
    )

    checks = {
        "dut_rail_in_range": _value(model, "dut_vcc_min_v") <= vcc <= _value(model, "dut_vcc_max_v"),
        "no_unsafe_direct_drive": not direct_drive or _value(model, "host_logic_v") <= abs_max_v,
        "miso_direction_correct": miso_direction == "dut_to_host",
        "translator_topology_correct": translator_topology == "fixed_3_forward_1_reverse",
        "oe_safe_with_rail_state": not (oe_enabled and not dut_rail_present),
        "forward_halfcycle_margin_positive": forward_total_ns < half_period_ns,
        "return_halfcycle_margin_positive": return_total_ns < half_period_ns,
    }

    failed = sorted(name for name, passed in checks.items() if not passed)
    status = "pass_surrogate" if not failed else "fail_surrogate"
    return {
        "schema_version": "hardware_splicer.spi_derived_surrogate_result.v1",
        "surrogate_id": model.get("surrogate_id"),
        "evidence_class": "derived_surrogate_only",
        "eligible_for_vendor_model_campaign_credit": False,
        "status": status,
        "checks": checks,
        "failed_checks": failed,
        "metrics": {
            "spi_clock_hz": int(spi_clock_hz),
            "half_period_ns": round(half_period_ns, 6),
            "dut_vcc_v": vcc,
            "dut_abs_max_v": round(abs_max_v, 6),
            "load_cap_pf": load_pf,
            "load_penalty_ns": round(load_penalty_ns, 6),
            "forward_total_ns": round(forward_total_ns, 6),
            "forward_margin_ns": round(half_period_ns - forward_total_ns, 6),
            "return_total_ns": round(return_total_ns, 6),
            "return_margin_ns": round(half_period_ns - return_total_ns, 6),
        },
        "assumptions": sorted(
            name
            for name, row in model.get("parameters", {}).items()
            if isinstance(row, Mapping) and row.get("derivation") == "surrogate_assumption"
        ),
        **dict(model.get("authority", {})),
    }

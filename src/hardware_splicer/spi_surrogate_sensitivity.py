"""Sensitivity sweeps for the derived SPI virtual-lab surrogate."""

from __future__ import annotations

from copy import deepcopy
from itertools import product
from typing import Any

from .spi_derived_surrogate import build_default_surrogate, evaluate_surrogate_case

SCHEMA_VERSION = "hardware_splicer.spi_surrogate_sensitivity.v1"


def run_sensitivity_sweep() -> dict[str, Any]:
    """Sweep development assumptions to expose which terms dominate timing closure."""

    rows: list[dict[str, Any]] = []
    for clock_hz, load_pf, skew_ns, setup_ns, launch_ns in product(
        (1_000_000, 5_000_000, 10_000_000, 15_000_000, 20_000_000, 25_000_000),
        (5.0, 10.0, 20.0, 40.0, 80.0),
        (0.0, 2.0, 4.0, 8.0),
        (2.0, 4.0, 8.0, 12.0),
        (2.0, 4.0, 8.0, 12.0),
    ):
        model = deepcopy(build_default_surrogate())
        model["parameters"]["clock_skew_ns"]["value"] = skew_ns
        model["parameters"]["host_setup_ns"]["value"] = setup_ns
        model["parameters"]["host_launch_ns"]["value"] = launch_ns
        result = evaluate_surrogate_case(model, spi_clock_hz=clock_hz, load_cap_pf=load_pf)
        rows.append({
            "clock_hz": clock_hz,
            "load_cap_pf": load_pf,
            "clock_skew_ns": skew_ns,
            "host_setup_ns": setup_ns,
            "host_launch_ns": launch_ns,
            "status": result["status"],
            "forward_margin_ns": result["metrics"]["forward_margin_ns"],
            "return_margin_ns": result["metrics"]["return_margin_ns"],
        })

    passed = sum(row["status"] == "pass_surrogate" for row in rows)
    by_clock: dict[str, dict[str, int]] = {}
    for row in rows:
        key = str(row["clock_hz"])
        bucket = by_clock.setdefault(key, {"pass": 0, "fail": 0})
        bucket["pass" if row["status"] == "pass_surrogate" else "fail"] += 1

    return {
        "schema_version": SCHEMA_VERSION,
        "sweep_id": "hs-spi-derived-sensitivity-v1",
        "case_count": len(rows),
        "pass_count": passed,
        "fail_count": len(rows) - passed,
        "by_clock_hz": by_clock,
        "rows": rows,
        "evidence_class": "derived_surrogate_only",
        "eligible_for_vendor_model_campaign_credit": False,
        "interpretation_boundary": (
            "Sensitivity identifies dependence on development assumptions; it does not convert those assumptions into evidence."
        ),
        "measured_evidence_present": False,
        "physical_correctness": "UNPROVEN",
        "physical_authority_granted": False,
        "authority_effect": "none",
    }

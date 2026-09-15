"""Generate and score a deterministic SPI surrogate benchmark corpus."""

from __future__ import annotations

from itertools import product
from typing import Any, Iterable, Mapping

from .spi_derived_surrogate import build_default_surrogate, evaluate_surrogate_case

SCHEMA_VERSION = "hardware_splicer.spi_virtual_lab_benchmark.v1"


def _expected_unsafe(case: Mapping[str, Any]) -> bool:
    """Preregister the expected label without consulting verifier output.

    The v1 surrogate assumptions make 25 MHz unsafe because the known bounded propagation/
    launch/setup/skew/load terms exceed the 20 ns half-cycle for both preregistered loads.
    """

    return bool(
        case["direct_drive"]
        or case["miso_direction"] != "dut_to_host"
        or case["translator_topology"] != "fixed_3_forward_1_reverse"
        or (case["oe_enabled"] and not case["dut_rail_present"])
        or not (1.7 <= float(case["dut_vcc_v"]) <= 1.95)
        or int(case["spi_clock_hz"]) >= 25_000_000
    )


def generate_benchmark_cases() -> list[dict[str, Any]]:
    """Return 576 deterministic cases spanning logical, voltage, load, and clock faults."""

    cases: list[dict[str, Any]] = []
    index = 0
    for (
        clock_hz,
        direct_drive,
        miso_direction,
        topology,
        oe_enabled,
        rail_present,
        dut_vcc_v,
        load_pf,
    ) in product(
        (1_000_000, 5_000_000, 25_000_000),
        (False, True),
        ("dut_to_host", "host_to_dut"),
        ("fixed_3_forward_1_reverse", "grouped_2_plus_2"),
        (False, True),
        (False, True),
        (1.65, 1.8, 1.98),
        (10.0, 40.0),
    ):
        case = {
            "case_id": f"spi-surrogate-{index:04d}",
            "spi_clock_hz": clock_hz,
            "direct_drive": direct_drive,
            "miso_direction": miso_direction,
            "translator_topology": topology,
            "oe_enabled": oe_enabled,
            "dut_rail_present": rail_present,
            "dut_vcc_v": dut_vcc_v,
            "load_cap_pf": load_pf,
        }
        case["expected_unsafe"] = _expected_unsafe(case)
        cases.append(case)
        index += 1
    return cases


def run_benchmark(cases: Iterable[Mapping[str, Any]] | None = None) -> dict[str, Any]:
    model = build_default_surrogate()
    rows = []
    tp = fp = tn = fn = 0
    for case in list(cases) if cases is not None else generate_benchmark_cases():
        result = evaluate_surrogate_case(
            model,
            spi_clock_hz=int(case["spi_clock_hz"]),
            direct_drive=bool(case["direct_drive"]),
            miso_direction=str(case["miso_direction"]),
            translator_topology=str(case["translator_topology"]),
            oe_enabled=bool(case["oe_enabled"]),
            dut_rail_present=bool(case["dut_rail_present"]),
            dut_vcc_v=float(case["dut_vcc_v"]),
            load_cap_pf=float(case["load_cap_pf"]),
        )
        predicted_unsafe = result["status"] == "fail_surrogate"
        expected_unsafe = bool(case["expected_unsafe"])
        if expected_unsafe and predicted_unsafe:
            tp += 1
        elif expected_unsafe and not predicted_unsafe:
            fn += 1
        elif not expected_unsafe and predicted_unsafe:
            fp += 1
        else:
            tn += 1
        rows.append({
            "case_id": case["case_id"],
            "expected_unsafe": expected_unsafe,
            "predicted_unsafe": predicted_unsafe,
            "failed_checks": result["failed_checks"],
            "metrics": result["metrics"],
        })

    count = len(rows)
    recall = tp / (tp + fn) if tp + fn else 1.0
    specificity = tn / (tn + fp) if tn + fp else 1.0
    return {
        "schema_version": SCHEMA_VERSION,
        "benchmark_id": "hs-spi-derived-virtual-lab-v1",
        "case_count": count,
        "confusion": {"true_positive": tp, "false_positive": fp, "true_negative": tn, "false_negative": fn},
        "unsafe_detection_recall": round(recall, 6),
        "safe_case_specificity": round(specificity, 6),
        "rows": rows,
        "evidence_class": "derived_surrogate_only",
        "eligible_for_vendor_model_campaign_credit": False,
        "measured_evidence_present": False,
        "physical_correctness": "UNPROVEN",
        "physical_authority_granted": False,
        "authority_effect": "none",
    }

#!/usr/bin/env python3
"""Independently audit Derived Virtual Lab v1 cases and per-case results.

This auditor intentionally does not import ``spi_derived_virtual_lab``.  It recomputes the gold
classification from the serialized case fields with a separate implementation, then compares
that gold label with both the frozen case label and the evaluator result.  This reduces the
risk of a self-confirming benchmark where the generator and scorer share one bug.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

SCHEMA_VERSION = "hardware_splicer.spi_derived_virtual_lab_independent_audit.v1"
_REQUIRED_PROVENANCE = {
    "host_logic_high_v",
    "dut_vcc_range",
    "dut_pin_abs_max_rule",
    "spi_directions",
    "translator_topology",
}
_EXPECTED_SIGNALS = {
    "SCLK": "host_to_dut",
    "MOSI": "host_to_dut",
    "CS#": "host_to_dut",
    "MISO": "dut_to_host",
}


def _sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _translator_topology_safe(case: Mapping[str, Any]) -> bool:
    if case.get("direct_connection") is True:
        return True
    translator = case.get("translator")
    if not isinstance(translator, Mapping):
        return False
    topology = translator.get("topology")
    if topology == "fixed_direction":
        forward = translator.get("forward_channels")
        reverse = translator.get("reverse_channels")
        return (
            isinstance(forward, int)
            and not isinstance(forward, bool)
            and isinstance(reverse, int)
            and not isinstance(reverse, bool)
            and forward >= 3
            and reverse >= 1
        )
    if topology == "shared_direction_groups":
        groups = translator.get("direction_groups")
        # For this frozen 4-channel campaign, whole direction-sharing groups must be capable
        # of a simultaneous 3-forward/1-reverse split.  A 2+2 device therefore fails.
        if not isinstance(groups, list) or not groups:
            return False
        total = sum(v for v in groups if isinstance(v, int) and not isinstance(v, bool))
        possible_forward = {0}
        for group in groups:
            if not isinstance(group, int) or isinstance(group, bool) or group <= 0:
                return False
            possible_forward |= {value + group for value in list(possible_forward)}
        return total == 4 and any(value >= 3 and total - value >= 1 for value in possible_forward)
    return False


def independent_gold(case: Mapping[str, Any]) -> str:
    """Classify one serialized case without using the benchmark implementation."""

    vcc = float(case["dut_vcc_v"])
    vcc_min = float(case["dut_vcc_min_v"])
    vcc_max = float(case["dut_vcc_max_v"])
    pin_max = vcc + float(case["dut_pin_abs_max_offset_v"])

    unsafe = not (vcc_min <= vcc <= vcc_max)

    if case.get("direct_connection") is True:
        unsafe = unsafe or float(case["host_logic_high_v"]) > pin_max

    signals = case.get("signals") if isinstance(case.get("signals"), Mapping) else {}
    unsafe = unsafe or any(signals.get(name) != direction for name, direction in _EXPECTED_SIGNALS.items())
    unsafe = unsafe or not _translator_topology_safe(case)

    translator = case.get("translator")
    if isinstance(translator, Mapping):
        out_max = translator.get("dut_side_output_max_v")
        if out_max is None:
            unsafe = True
        else:
            unsafe = unsafe or float(out_max) > pin_max

    if not bool(case.get("dut_rail_present")) and bool(case.get("oe_enabled")):
        unsafe = True

    clock_hz = float(case["spi_clock_hz"])
    half_cycle_ns = 0.5e9 / clock_hz
    forward_ns = float(case["txu_forward_delay_ns"]) + float(case["derived_load_delay_ns"])
    return_ns = (
        float(case["txu_reverse_delay_ns"])
        + float(case["dut_clock_to_output_ns"])
        + float(case["derived_load_delay_ns"])
        + float(case["host_setup_allowance_ns"])
    )
    unsafe = unsafe or forward_ns > half_cycle_ns or return_ns > half_cycle_ns
    unsafe = unsafe or float(case["estimated_load_a"]) > float(case["regulator_capacity_a"])

    if unsafe:
        return "unsafe"

    refs = case.get("source_claim_ids") if isinstance(case.get("source_claim_ids"), Mapping) else {}
    missing = [key for key in _REQUIRED_PROVENANCE if not isinstance(refs.get(key), list) or not refs.get(key)]
    if missing:
        return "blocked"
    return "safe"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", required=True, type=Path)
    parser.add_argument("--results", required=True, type=Path)
    parser.add_argument("--benchmark-report", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()

    corpus = _load(args.corpus)
    results_payload = _load(args.results)
    report = _load(args.benchmark_report)
    if not isinstance(corpus, list):
        raise SystemExit("corpus must be a JSON array")
    if not isinstance(results_payload, Mapping) or not isinstance(results_payload.get("rows"), list):
        raise SystemExit("results must contain a rows array")

    result_by_id = {
        str(row.get("case_id")): row
        for row in results_payload["rows"]
        if isinstance(row, Mapping) and row.get("case_id")
    }

    frozen_label_mismatches: list[str] = []
    evaluator_mismatches: list[str] = []
    missing_results: list[str] = []
    duplicate_case_ids: list[str] = []
    seen: set[str] = set()
    independent_matrix = {
        expected: {predicted: 0 for predicted in ("safe", "blocked", "unsafe")}
        for expected in ("safe", "blocked", "unsafe")
    }

    for case in corpus:
        if not isinstance(case, Mapping):
            raise SystemExit("corpus contains a non-object row")
        case_id = str(case.get("case_id") or "")
        if not case_id:
            raise SystemExit("corpus row is missing case_id")
        if case_id in seen:
            duplicate_case_ids.append(case_id)
        seen.add(case_id)

        gold = independent_gold(case)
        if case.get("expected_outcome") != gold:
            frozen_label_mismatches.append(case_id)

        row = result_by_id.get(case_id)
        if not isinstance(row, Mapping):
            missing_results.append(case_id)
            continue
        predicted = str(row.get("predicted_outcome") or "")
        if predicted not in {"safe", "blocked", "unsafe"}:
            evaluator_mismatches.append(case_id)
            continue
        independent_matrix[gold][predicted] += 1
        if predicted != gold:
            evaluator_mismatches.append(case_id)
        if row.get("case_hash") != case.get("case_hash"):
            evaluator_mismatches.append(case_id)
        if (
            row.get("vendor_model_campaign_credit_eligible") is not False
            or row.get("physical_correctness") != "UNPROVEN"
            or row.get("physical_authority_granted") is not False
        ):
            evaluator_mismatches.append(case_id)

    extra_results = sorted(set(result_by_id) - seen)
    report_matrix_matches = report.get("outcome_matrix") == independent_matrix
    checks = {
        "exact_case_count_512": len(corpus) == 512,
        "unique_case_ids": not duplicate_case_ids and len(seen) == len(corpus),
        "exact_result_coverage": not missing_results and not extra_results and len(result_by_id) == len(corpus),
        "frozen_labels_match_independent_gold": not frozen_label_mismatches,
        "evaluator_matches_independent_gold": not evaluator_mismatches,
        "aggregate_matrix_matches_independent_recompute": report_matrix_matches,
        "benchmark_report_claims_pass": report.get("benchmark_pass") is True,
        "benchmark_report_authority_closed": (
            report.get("vendor_model_campaign_credit_eligible") is False
            and report.get("physical_correctness") == "UNPROVEN"
            and report.get("physical_authority_granted") is False
        ),
    }
    audit_pass = all(checks.values())
    payload = {
        "schema_version": SCHEMA_VERSION,
        "status": "passed_independent_derived_audit" if audit_pass else "failed_independent_derived_audit",
        "audit_pass": audit_pass,
        "checks": checks,
        "independent_outcome_matrix": independent_matrix,
        "frozen_label_mismatch_case_ids": sorted(set(frozen_label_mismatches)),
        "evaluator_mismatch_case_ids": sorted(set(evaluator_mismatches)),
        "missing_result_case_ids": sorted(set(missing_results)),
        "extra_result_case_ids": extra_results,
        "duplicate_case_ids": sorted(set(duplicate_case_ids)),
        "input_hashes": {
            "corpus_sha256": _sha256(args.corpus),
            "results_sha256": _sha256(args.results),
            "benchmark_report_sha256": _sha256(args.benchmark_report),
        },
        "evidence_class": "derived_surrogate_only",
        "vendor_model_campaign_credit_eligible": False,
        "physical_correctness": "UNPROVEN",
        "physical_authority_granted": False,
        "authority_effect": "none",
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"audit_pass": audit_pass, "status": payload["status"]}, sort_keys=True))
    return 0 if audit_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())

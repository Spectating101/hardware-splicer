"""Assess whether an HS station design can support a Policy Lab experiment order.

Planning-only: a design's theoretical sensing points do not establish wiring,
calibration, timebase, equipment custody, assembly or authorization to energize.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from .dc_measurement_station import SCHEMA as STATION_SCHEMA

ORDER_SCHEMA = "hardware_splicer.experiment_work_order.v1"
RESULT_SCHEMA = "hardware_splicer.experiment_feasibility.v1"
SUPPORTED_PAIRS = {
    ("J2_LOAD", "VOLTAGE_V"): "INA228 VBUS and independent reference load voltage (interfaces only)",
    ("J2_LOAD", "CURRENT_A"): "INA228 Kelvin shunt and independent reference shunt (interfaces only)",
    ("J2_LOAD", "ENERGY_WH"): "Integrated sampled J2 load energy; no physical energy counter",
}
KNOWN_PAIRS = SUPPORTED_PAIRS.keys() | {
    ("CONVERTER_INPUT", "VOLTAGE_V"),
    ("CONVERTER_INPUT", "CURRENT_A"),
    ("CONVERTER_INPUT", "ENERGY_WH"),
    ("J2_REFERENCE", "CALIBRATION_RECORD"),
    ("CLOCK_REFERENCE", "UTC_TIMEBASE_CHECK"),
}


def _require(ok: bool, message: str) -> None:
    if not ok:
        raise ValueError("HS_EXPERIMENT_REJECTED: " + message)


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _strict_record(value: Any, keys: set[str], name: str) -> None:
    _require(isinstance(value, dict) and set(value) == keys, name + " must have exact fields")


def assess_order(order_bytes: bytes, design_bytes: bytes) -> dict[str, Any]:
    """Validate exact source bindings; classify coverage without asserting build readiness."""
    _require(0 < len(order_bytes) <= 65536 and 0 < len(design_bytes) <= 1048576,
             "work order / station design size is invalid")
    order = json.loads(order_bytes)
    design = json.loads(design_bytes)
    _strict_record(order, {"schema", "case_id", "question_type", "source_binding",
                          "requested_observations", "purpose", "execution_authorized"}, "work order")
    _require(order["schema"] == ORDER_SCHEMA, "unsupported work order schema")
    _require(isinstance(order["case_id"], str) and 1 <= len(order["case_id"]) <= 96,
             "invalid case_id")
    _require(order["question_type"] in ("LOAD_ENERGY_BUDGET", "CONVERTER_EFFICIENCY"),
             "unsupported question type")
    _require(isinstance(order["purpose"], str) and 1 <= len(order["purpose"]) <= 500,
             "invalid purpose")
    _require(order["execution_authorized"] is False,
             "external request cannot authorize physical execution")
    _strict_record(order["source_binding"],
                   {"capture_evidence_root_sha256", "station_design_sha256", "capture_kind"},
                   "source binding")
    _require(order["source_binding"]["station_design_sha256"] == _sha256(design_bytes),
             "station design bytes do not match exact pinned hash")
    _require(isinstance(order["source_binding"]["capture_evidence_root_sha256"], str)
             and len(order["source_binding"]["capture_evidence_root_sha256"]) == 64
             and all(c in "0123456789abcdef" for c in
                     order["source_binding"]["capture_evidence_root_sha256"]),
             "invalid capture evidence root")
    _require(order["source_binding"]["capture_kind"] in ("TEST_FIXTURE", "DECLARED_BENCH_CAPTURE"),
             "unsupported source kind")
    _require(design.get("schema_version") == STATION_SCHEMA, "wrong station design schema")
    _require(isinstance(design.get("design_checks_passed"), bool),
             "station numerical check result missing")
    _require(design.get("physical_status") == "UNBUILT_UNVERIFIED",
             "only the original unbuilt candidate station may be assessed; a changed readiness label is not proof")
    _require(design.get("measurement_boundary", "").startswith("Both voltage channels measure at J2"),
             "station design is not a verified compatible J2 measurement layout")
    _require(isinstance(order["requested_observations"], list)
             and 1 <= len(order["requested_observations"]) <= 12,
             "request 1 to 12 typed observations")
    seen = set()
    coverage = []
    for observation in order["requested_observations"]:
        _strict_record(observation, {"point", "quantity"}, "observation")
        pair = (observation["point"], observation["quantity"])
        _require(pair in KNOWN_PAIRS, "unknown point / quantity pair")
        _require(pair not in seen, "duplicate observation")
        seen.add(pair)
        supported = pair in SUPPORTED_PAIRS
        coverage.append({"point": pair[0], "quantity": pair[1],
                         "designed_interface_present": supported,
                         "method_or_blocker": SUPPORTED_PAIRS.get(pair, "No modeled and proven interface at this physical point")})
    required = []
    if not design["design_checks_passed"]:
        required.append("Resolve failing station numerical design checks before building")
    required.append("Select exact parts, review isolation/protection and assemble/commission station")
    if order["source_binding"]["capture_kind"] == "TEST_FIXTURE":
        required.append("Replace software fixture with real, independently retained instrument observations")
    else:
        required.append("Externally verify instrument identity, clocks, calibration and custody")
    if any(not row["designed_interface_present"] for row in coverage):
        required.append("Engineer and independently validate the missing physical measurement interfaces")
    required.append("Obtain separate operator approval before any electrical experiment")
    covered = all(row["designed_interface_present"] for row in coverage)
    if not design["design_checks_passed"]:
        status = "DESIGN_CHECKS_FAILED"
    elif not covered:
        status = "ADDITIONAL_INSTRUMENTATION_REQUIRED"
    else:
        status = "DESIGN_COVERS_POINTS_UNBUILT_OR_UNVERIFIED"
    return {
        "schema": RESULT_SCHEMA,
        "case_id": order["case_id"],
        "question_type": order["question_type"],
        "source_binding": order["source_binding"],
        "exact_order_sha256": _sha256(order_bytes),
        "exact_station_design_sha256": _sha256(design_bytes),
        "status": status,
        "designed_coverage_complete": covered,
        "observations": coverage,
        "next_engineering_actions": required,
        "physical_measurements_performed": 0,
        "physical_evidence_verified": False,
        "energization_authorized": False,
        "calibration_verified": False,
    }


def run(argv: list[str] | None = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--order", required=True, type=Path)
    parser.add_argument("--station-design", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        result = assess_order(args.order.read_bytes(), args.station_design.read_bytes())
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("x", encoding="utf-8") as stream:
            json.dump(result, stream, indent=2, sort_keys=True, allow_nan=False)
            stream.write("\n")
        print(json.dumps({"status": result["status"], "output": str(args.out),
                          "coverage": result["designed_coverage_complete"],
                          "energization_authorized": False}))
        return 0 if result["designed_coverage_complete"] else 2
    except (OSError, json.JSONDecodeError, ValueError, TypeError) as error:
        parser.exit(1, str(error) + "\n")


if __name__ == "__main__":
    raise SystemExit(run())

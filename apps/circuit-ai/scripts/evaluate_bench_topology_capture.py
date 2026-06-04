#!/usr/bin/env python3
"""Evaluate bench topology capture against real public pinout examples.

The public sources seed realistic pinouts. The production-authorized case uses a
synthetic operator bench capture shaped from that public pinout; it is not a
claim that this machine physically measured the board.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Sequence


ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from src.intelligence.bench_topology_capture import build_bench_capture_template  # noqa: E402
from src.intelligence.hardware_plan import HardwarePlanOrchestrator  # noqa: E402


SPARKFUN_CH340C_REFERENCE = {
    "schema_version": "topology_evidence.v1",
    "source_type": "public_reference_topology",
    "reference_uri": "https://www.sparkfun.com/sparkfun-serial-basic-breakout-ch340c-and-usb-c.html",
    "connectors": [
        {
            "ref": "J1",
            "label": "SparkFun CH340C FTDI-style header",
            "pins": [
                {"pin": "1", "net": "DTR", "role": "dtr"},
                {"pin": "2", "net": "RXI", "role": "rxi", "logic_voltage": 3.3},
                {"pin": "3", "net": "TXO", "role": "txo", "logic_voltage": 3.3},
                {"pin": "4", "net": "VCC", "role": "vcc", "voltage": 3.3},
                {"pin": "5", "net": "CTS", "role": "cts"},
                {"pin": "6", "net": "GND", "role": "gnd"},
            ],
        }
    ],
}


def release_manifest(resource_ids: Sequence[str]) -> Dict[str, Any]:
    return {
        "release_id": "BENCH-CAPTURE-CH340C-001",
        "selected_resource_ids": list(resource_ids),
        "released_by": "operator-1",
        "released_at": "2026-05-26T05:00:00Z",
        "scope_statement": "Release is limited to the measured CH340C header capture and recorded UART validation outcome.",
        "artifact_uris": ["session://bench/ch340c/release-report", "session://bench/ch340c/photo-set"],
        "acceptance_reviewed": True,
        "repeatability_count": 1,
    }


def bench_capture(*, include_artifacts: bool = True) -> Dict[str, Any]:
    return {
        "schema_version": "bench_topology_capture.v1",
        "capture_id": "bench-ch340c-001",
        "operator_id": "operator-1",
        "recorded_at": "2026-05-26T04:00:00Z",
        "instruments": [
            {"instrument_id": "bench_dmm_01", "instrument_type": "calibrated_dmm", "calibration_status": "valid"},
            {"instrument_id": "bench_supply_01", "instrument_type": "current_limited_supply", "calibration_status": "valid"},
            {"instrument_id": "thermal_probe_01", "instrument_type": "thermal_probe", "calibration_status": "valid"},
        ],
        "artifacts": [
            {"kind": "photo", "uri": "session://bench/ch340c/pinout-photo"},
            {"kind": "measurement_log", "uri": "session://bench/ch340c/measurement-log"},
        ]
        if include_artifacts
        else [],
        "connectors": [
            {
                "ref": "J1",
                "label": "bench verified CH340C UART header",
                "pins": [
                    {"pin": "1", "net": "DTR", "role": "dtr", "status": "verified"},
                    {"pin": "2", "net": "RXI", "role": "rxi", "logic_voltage": 3.3, "status": "verified"},
                    {"pin": "3", "net": "TXO", "role": "txo", "logic_voltage": 3.3, "status": "verified"},
                    {"pin": "4", "net": "VCC", "role": "vcc", "voltage": 3.3, "status": "verified"},
                    {"pin": "5", "net": "CTS", "role": "cts", "status": "verified"},
                    {"pin": "6", "net": "GND", "role": "gnd", "status": "verified"},
                ],
            }
        ],
        "measurements": [
            {
                "kind": "resistance",
                "target": "power to ground no-short",
                "value": "pass",
                "status": "pass",
                "notes": "unpowered resistance between VCC and GND is no-short",
            },
            {
                "kind": "continuity",
                "target": "connector ground to exposed ground",
                "value": "pass",
                "status": "pass",
            },
            {
                "kind": "current",
                "target": "current draw under current-limited supply",
                "value": "pass",
                "status": "pass",
                "instrument_id": "bench_supply_01",
            },
            {
                "kind": "thermal",
                "target": "thermal behavior after first power",
                "value": "normal",
                "status": "pass",
                "instrument_id": "thermal_probe_01",
            },
        ],
    }


def base_payload() -> Dict[str, Any]:
    return {
        "goal": "reuse a SparkFun CH340C serial board as a low-voltage UART harness",
        "target_authority_level": "production_repair",
        "strategy_mode": "constrained",
        "required_capabilities": ["usb_serial", "connector"],
        "outcome_history": [
            {
                "decision": "built",
                "selected_resource_ids_used": ["topology_j1"],
                "measurements_recorded": True,
                "cash_spent_usd": 0,
                "value_recovered_usd": 10,
                "time_spent_minutes": 18,
                "deviations_from_plan": [],
                "failure_or_stop_reason": "",
                "output_function_verified": True,
                "first_power_result": "pass",
                "thermal_result": "normal",
                "evidence_uri": "session://outcomes/topology-j1-built",
            }
        ],
        "production_release": release_manifest(["topology_j1"]),
        "repair_authority": {
            "status": "authoritative_low_risk",
            "score": 0.94,
            "required_measurements": [],
            "blocked_decisions": [],
        },
        "use_reference_catalog": False,
    }


BENCH_CASES: List[Dict[str, Any]] = [
    {
        "case_id": "sparkfun_reference_template_only",
        "title": "Public CH340C pinout creates a capture template, not measured authority",
        "payload": {
            "goal": "reuse CH340C from official pinout only",
            "strategy_mode": "constrained",
            "required_capabilities": ["usb_serial", "connector"],
            "bench_topology_capture": build_bench_capture_template(reference_topology=SPARKFUN_CH340C_REFERENCE),
            "use_reference_catalog": False,
        },
        "expected": {
            "status": "blocked_missing_resources",
            "can_power_or_splice": False,
            "production_authorized": False,
            "actionable_capture": False,
        },
    },
    {
        "case_id": "sparkfun_measured_bench_capture_authorized",
        "title": "CH340C bench capture reaches narrow production authority after outcome and release",
        "payload": {**base_payload(), "bench_topology_capture": bench_capture(include_artifacts=True)},
        "expected": {
            "status": "ready_for_build_plan",
            "can_power_or_splice": True,
            "production_authorized": True,
            "selected_contains": ["topology_j1"],
            "missing_artifacts": [],
            "actionable_capture": True,
        },
    },
    {
        "case_id": "sparkfun_bench_capture_missing_artifacts",
        "title": "Measured CH340C capture without audit artifacts remains blocked for production",
        "payload": {**base_payload(), "bench_topology_capture": bench_capture(include_artifacts=False)},
        "expected": {
            "status": "ready_for_build_plan",
            "can_power_or_splice": True,
            "production_authorized": False,
            "selected_contains": ["topology_j1"],
            "actionable_capture": True,
            "missing_artifacts_nonempty": True,
        },
    },
]


def selected_ids(plan: Dict[str, Any]) -> List[str]:
    strategy = plan.get("resource_strategy") if isinstance(plan.get("resource_strategy"), dict) else {}
    return [str(resource.get("resource_id")) for resource in strategy.get("selected_resources") or []]


def check_case(case: Dict[str, Any], plan: Dict[str, Any]) -> List[Dict[str, Any]]:
    expected = case["expected"]
    integrated = plan.get("integrated_plan") if isinstance(plan.get("integrated_plan"), dict) else {}
    assurance = integrated.get("assurance") if isinstance(integrated.get("assurance"), dict) else {}
    production = integrated.get("production_repair_authority") if isinstance(integrated.get("production_repair_authority"), dict) else {}
    analysis = plan.get("analysis") if isinstance(plan.get("analysis"), dict) else {}
    capture = analysis.get("bench_topology_capture") if isinstance(analysis.get("bench_topology_capture"), dict) else {}
    provenance = production.get("measurement_provenance") if isinstance(production.get("measurement_provenance"), dict) else {}

    checks: List[Dict[str, Any]] = []

    def add(name: str, passed: bool, actual: Any = None, expected_value: Any = None) -> None:
        checks.append({"name": name, "passed": bool(passed), "actual": actual, "expected": expected_value})

    add("status", integrated.get("status") == expected["status"], integrated.get("status"), expected["status"])
    add(
        "can_power_or_splice",
        assurance.get("can_power_or_splice") is expected["can_power_or_splice"],
        assurance.get("can_power_or_splice"),
        expected["can_power_or_splice"],
    )
    add(
        "production_authorized",
        production.get("authorized") is expected["production_authorized"],
        production.get("authorized"),
        expected["production_authorized"],
    )
    add(
        "actionable_capture",
        capture.get("actionable_topology") is expected["actionable_capture"],
        capture.get("actionable_topology"),
        expected["actionable_capture"],
    )
    if "selected_contains" in expected:
        add(
            "selected_contains",
            set(expected["selected_contains"]).issubset(set(selected_ids(plan))),
            selected_ids(plan),
            expected["selected_contains"],
        )
    if "missing_artifacts" in expected:
        add(
            "missing_artifacts",
            provenance.get("missing_artifact_categories") == expected["missing_artifacts"],
            provenance.get("missing_artifact_categories"),
            expected["missing_artifacts"],
        )
    if expected.get("missing_artifacts_nonempty"):
        add(
            "missing_artifacts_nonempty",
            bool(provenance.get("missing_artifact_categories")),
            provenance.get("missing_artifact_categories"),
            "nonempty",
        )
    return checks


def evaluate_cases() -> Dict[str, Any]:
    planner = HardwarePlanOrchestrator()
    rows = []
    for case in BENCH_CASES:
        plan = planner.plan(case["payload"])
        checks = check_case(case, plan)
        passed = len([check for check in checks if check["passed"]])
        integrated = plan.get("integrated_plan") if isinstance(plan.get("integrated_plan"), dict) else {}
        production = integrated.get("production_repair_authority") if isinstance(integrated.get("production_repair_authority"), dict) else {}
        rows.append(
            {
                "case_id": case["case_id"],
                "title": case["title"],
                "score": round(passed / max(len(checks), 1), 3),
                "all_passed": passed == len(checks),
                "status": integrated.get("status"),
                "production_authorized": bool(production.get("authorized")),
                "selected_resources": selected_ids(plan),
                "checks": checks,
            }
        )
    summary = {
        "case_count": len(rows),
        "pass_rate": round(len([row for row in rows if row["all_passed"]]) / max(len(rows), 1), 3),
        "production_authorized_count": len([row for row in rows if row["production_authorized"]]),
        "weak_cases": [row["case_id"] for row in rows if not row["all_passed"]],
    }
    return {
        "mode": "bench_topology_capture_eval",
        "schema_version": "bench_topology_capture_eval.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_boundary": "Public pinout references seed templates; only synthetic operator measurement packets are evaluated as bench evidence.",
        "summary": summary,
        "cases": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("eval/bench_topology_capture"))
    args = parser.parse_args()

    report = evaluate_cases()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "latest.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    summary = report["summary"]
    print(f"wrote {args.output_dir}")
    print(
        "cases={case_count} pass_rate={pass_rate} production_authorized={production_authorized_count} weak={weak_cases}".format(
            **summary
        )
    )
    for row in report["cases"]:
        print(
            f"{row['case_id']}: score={row['score']} status={row['status']} "
            f"production_authorized={row['production_authorized']} selected={row['selected_resources']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

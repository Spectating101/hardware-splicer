#!/usr/bin/env python3
"""Regression harness for production repair authority and release casefiles."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from src.intelligence.hardware_plan import HardwarePlanOrchestrator  # noqa: E402


def trusted_measurement(measurement_type: str, target: str, value: Any, notes: str, *, unit: str = "") -> Dict[str, Any]:
    return {
        "type": measurement_type,
        "target": target,
        "value": value,
        "unit": unit,
        "notes": notes,
        "instrument_id": "bench_dmm_01" if measurement_type != "thermal" else "thermal_probe_01",
        "instrument_type": "calibrated_dmm" if measurement_type != "thermal" else "thermal_probe",
        "calibration_status": "valid",
        "recorded_at": "2026-05-26T02:00:00Z",
        "operator_id": "operator-1",
        "evidence_uri": f"session://measurements/{measurement_type}/{target}",
    }


def untrusted_measurement(measurement_type: str, target: str, value: Any, notes: str) -> Dict[str, Any]:
    return {"type": measurement_type, "target": target, "value": value, "notes": notes}


def measurements(*, trusted: bool = True) -> List[Dict[str, Any]]:
    fn = trusted_measurement if trusted else untrusted_measurement
    return [
        fn("resistance", "power to ground no-short", "pass", "unpowered resistance between power and ground is no-short"),
        fn("continuity", "connector ground to exposed ground", "pass", "connector ground continuity ok"),
        fn("voltage", "UART logic high voltage", 3.31, "UART TX/RX idle high at 3.3V"),
        fn("continuity", "shared ground continuity", "pass", "shared ground continuity pass"),
        fn("logic_level", "serial UART idle state", "pass", "serial idle high and stable before connecting target board"),
        fn("current", "current draw under current-limited supply", "pass", "current draw under current-limited supply within limit"),
        fn("thermal", "thermal behavior after first power", "normal", "temperature stable and no abnormal heat"),
    ]


def outcome(resource_id: str = "known_ch340") -> List[Dict[str, Any]]:
    return [
        {
            "decision": "built",
            "selected_resource_ids_used": [resource_id],
            "measurements_recorded": True,
            "cash_spent_usd": 0,
            "value_recovered_usd": 9,
            "time_spent_minutes": 20,
            "deviations_from_plan": [],
            "failure_or_stop_reason": "",
            "output_function_verified": True,
            "first_power_result": "pass",
            "thermal_result": "normal",
            "current_limit_used": True,
            "operator_id": "operator-1",
            "recorded_at": "2026-05-26T03:00:00Z",
            "evidence_uri": "session://outcomes/terminal-uart-loopback",
        }
    ]


def release_manifest(resource_ids: List[str]) -> Dict[str, Any]:
    return {
        "release_id": "REL-REG-001",
        "selected_resource_ids": resource_ids,
        "released_by": "operator-1",
        "released_at": "2026-05-26T03:30:00Z",
        "scope_statement": "Release is limited to measured low-voltage UART adapter evidence and terminal outcome.",
        "artifact_uris": ["session://release/test-report", "session://release/photos"],
        "acceptance_reviewed": True,
        "repeatability_count": 1,
    }


def base_release_payload() -> Dict[str, Any]:
    return {
        "goal": "release a measured low-voltage UART debug adapter repair",
        "target_authority_level": "production_repair",
        "strategy_mode": "hybrid",
        "required_capabilities": ["usb_serial", "connector"],
        "available_resources": [
            {
                "resource_id": "known_ch340",
                "name": "known CH340 adapter",
                "resource_kind": "owned",
                "capabilities": ["usb_serial", "connector"],
                "confidence": 0.92,
                "evidence_status": "verified",
            }
        ],
        "measurements": measurements(trusted=True),
        "outcome_history": outcome("known_ch340"),
        "production_release": release_manifest(["known_ch340"]),
        "repair_authority": {
            "status": "authoritative_low_risk",
            "score": 0.94,
            "required_measurements": [],
            "blocked_decisions": [],
        },
        "use_reference_catalog": False,
    }


def hazard_visual_payload() -> Dict[str, Any]:
    payload = base_release_payload()
    payload.pop("available_resources", None)
    payload.pop("measurements", None)
    payload.pop("outcome_history", None)
    payload.pop("production_release", None)
    payload["required_capabilities"] = ["battery", "power"]
    payload["board_evidence"] = {
        "schema_version": "board_evidence.v1",
        "components": [{"id": "bat1", "label": "swollen lithium battery pack", "kind": "battery_pack", "confidence": 0.82}],
        "damage": [{"id": "d1", "label": "swollen lithium pouch cell", "severity": "critical", "confidence": 0.78}],
    }
    payload["repair_authority"] = {"status": "authoritative_low_risk", "score": 0.94}
    return payload


CASES = [
    {
        "case_id": "complete_low_voltage_release_authorizes",
        "payload": base_release_payload(),
        "expected": {"authorized": True, "decision": "authorized_low_voltage_repair_release", "casefile_status": "release_ready", "blocked_claim_count": 0},
    },
    {
        "case_id": "missing_release_manifest_blocks",
        "payload": {key: value for key, value in base_release_payload().items() if key != "production_release"},
        "expected": {"authorized": False, "decision": "not_authorized_evidence_required", "casefile_status": "evidence_required", "must_blocker": "Production release manifest is incomplete."},
    },
    {
        "case_id": "resource_mismatch_manifest_blocks",
        "payload": {**base_release_payload(), "production_release": release_manifest(["wrong_resource"])},
        "expected": {"authorized": False, "decision": "not_authorized_evidence_required", "casefile_status": "evidence_required", "must_requirement": "Release manifest selected_resource_ids must exactly match selected production resources."},
    },
    {
        "case_id": "untrusted_measurements_block",
        "payload": {**base_release_payload(), "measurements": measurements(trusted=False)},
        "expected": {"authorized": False, "decision": "not_authorized_evidence_required", "casefile_status": "evidence_required", "must_blocker": "Required production measurements lack trusted provenance."},
    },
    {
        "case_id": "vision_battery_hazard_blocks",
        "payload": hazard_visual_payload(),
        "expected": {"authorized": False, "decision": "blocked_by_hazard_scope", "casefile_status": "evidence_required", "must_blocker": "The hazard profile is outside production repair authority scope."},
    },
]


def evaluate_case(planner: HardwarePlanOrchestrator, case: Dict[str, Any]) -> Dict[str, Any]:
    plan = planner.plan(case["payload"])
    production = plan["integrated_plan"]["production_repair_authority"]
    casefile = production.get("authority_casefile") or {}
    actual = {
        "authorized": production.get("authorized"),
        "decision": production.get("decision"),
        "casefile_status": casefile.get("status"),
        "blocked_claim_count": casefile.get("blocked_claim_count"),
        "blockers": production.get("blockers") or [],
        "requirements": production.get("requirements") or [],
    }
    expected = case["expected"]
    checks = {
        "authorized": actual["authorized"] == expected.get("authorized"),
        "decision": actual["decision"] == expected.get("decision"),
        "casefile_status": actual["casefile_status"] == expected.get("casefile_status"),
    }
    if "blocked_claim_count" in expected:
        checks["blocked_claim_count"] = actual["blocked_claim_count"] == expected["blocked_claim_count"]
    if expected.get("must_blocker"):
        checks["must_blocker"] = expected["must_blocker"] in actual["blockers"]
    if expected.get("must_requirement"):
        checks["must_requirement"] = expected["must_requirement"] in actual["requirements"]
    return {
        "case_id": case["case_id"],
        "passed": all(checks.values()),
        "checks": checks,
        "actual": actual,
        "expected": expected,
    }


def main() -> int:
    planner = HardwarePlanOrchestrator()
    rows = [evaluate_case(planner, case) for case in CASES]
    out_dir = ROOT / "eval" / "production_authority_regression"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "latest.json").write_text(json.dumps(rows, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    passed = sum(1 for row in rows if row["passed"])
    print(f"cases={len(rows)} passed={passed} pass_rate={passed / max(len(rows), 1):.3f}")
    for row in rows:
        print(f"{row['case_id']}: passed={row['passed']} actual={row['actual']}")
    return 0 if passed == len(rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())


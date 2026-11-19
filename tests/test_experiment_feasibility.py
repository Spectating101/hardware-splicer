"""Synthetic feasibility checks; none demonstrate actual equipment availability."""
from __future__ import annotations

import hashlib
import json
import unittest

from hardware_splicer.dc_measurement_station import design_station
from hardware_splicer.experiment_feasibility import assess_order


def to_bytes(value):
    return (json.dumps(value, sort_keys=True) + "\n").encode()


class ExperimentFeasibilityTests(unittest.TestCase):
    def setUp(self):
        self.design = design_station()
        self.design_bytes = to_bytes(self.design)
        self.order = {
            "schema": "hardware_splicer.experiment_work_order.v1",
            "case_id": "synthetic_load_budget",
            "question_type": "LOAD_ENERGY_BUDGET",
            "source_binding": {
                "capture_evidence_root_sha256": "0" * 64,
                "station_design_sha256": hashlib.sha256(self.design_bytes).hexdigest(),
                "capture_kind": "TEST_FIXTURE",
            },
            "requested_observations": [
                {"point": "J2_LOAD", "quantity": "VOLTAGE_V"},
                {"point": "J2_LOAD", "quantity": "CURRENT_A"},
                {"point": "J2_LOAD", "quantity": "ENERGY_WH"},
            ],
            "purpose": "Test planning with software fixture only",
            "execution_authorized": False,
        }

    def assess(self):
        return assess_order(to_bytes(self.order), self.design_bytes)

    def test_existing_station_covers_j2_but_not_physical(self):
        result = self.assess()
        self.assertEqual(result["status"], "DESIGN_COVERS_POINTS_UNBUILT_OR_UNVERIFIED")
        self.assertTrue(result["designed_coverage_complete"])
        self.assertEqual(result["physical_measurements_performed"], 0)
        self.assertFalse(result["energization_authorized"])
        self.assertFalse(result["calibration_verified"])
        self.assertTrue(any("commission" in a for a in result["next_engineering_actions"]))

    def test_converter_needs_genuinely_distinct_input_boundary(self):
        self.order["question_type"] = "CONVERTER_EFFICIENCY"
        self.order["requested_observations"].append(
            {"point": "CONVERTER_INPUT", "quantity": "ENERGY_WH"})
        result = self.assess()
        self.assertEqual(result["status"], "ADDITIONAL_INSTRUMENTATION_REQUIRED")
        self.assertFalse(result["designed_coverage_complete"])
        self.assertFalse(result["observations"][-1]["designed_interface_present"])

    def test_invalid_or_duplicate_observation_rejects(self):
        self.order["requested_observations"].append(
            {"point": "J2_LOAD", "quantity": "ENERGY_WH"})
        with self.assertRaisesRegex(ValueError, "duplicate"):
            self.assess()
        self.order["requested_observations"][-1]["point"] = "IMPOSSIBLE_BUS"
        with self.assertRaisesRegex(ValueError, "unknown"):
            self.assess()

    def test_work_order_cannot_energize(self):
        self.order["execution_authorized"] = True
        with self.assertRaisesRegex(ValueError, "authorize"):
            self.assess()

    def test_exact_station_bytes_and_unknown_capture_kind(self):
        self.order["source_binding"]["station_design_sha256"] = "a" * 64
        with self.assertRaisesRegex(ValueError, "pinned hash"):
            self.assess()
        self.order["source_binding"]["station_design_sha256"] = hashlib.sha256(self.design_bytes).hexdigest()
        self.order["source_binding"]["capture_kind"] = "REAL_CALIBRATED"
        with self.assertRaisesRegex(ValueError, "unsupported source kind"):
            self.assess()

    def test_forged_station_build_status_rejected_even_with_new_sha(self):
        self.design["physical_status"] = "PHYSICALLY_COMMISSIONED"
        self.design_bytes = to_bytes(self.design)
        self.order["source_binding"]["station_design_sha256"] = hashlib.sha256(self.design_bytes).hexdigest()
        with self.assertRaisesRegex(ValueError, "readiness label"):
            self.assess()

    def test_numerically_failed_station_cannot_pass_feasibility(self):
        self.design["design_checks_passed"] = False
        self.design_bytes = to_bytes(self.design)
        self.order["source_binding"]["station_design_sha256"] = hashlib.sha256(self.design_bytes).hexdigest()
        self.assertEqual(self.assess()["status"], "DESIGN_CHECKS_FAILED")


if __name__ == "__main__":
    unittest.main()

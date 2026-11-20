"""Independent decision-level guardrails for existing HS/Policy Lab fixture handoff."""
import copy
import unittest

from assessment import Hold
from review_g3 import review

ROOT = "9a" * 32


def synthetic_controls():
    native = {
        "schema": "hardware_splicer.5v_witness_design_replay.v1",
        "status": "SOFTWARE_DESIGN_VALIDATED_ONLY",
        "native_erc": "ZERO_VIOLATIONS",
        "native_drc": "ZERO_VIOLATIONS_ZERO_UNCONNECTED_ZERO_PARITY_ERRORS",
        "pl_intake_decision": "TEST_FIXTURE_STRUCTURALLY_INGESTED_NO_PHYSICAL_CLAIMS",
        "fabrication_released": False, "hardware_powered": False,
        "calibration_verified": False, "physical_equipment_built": False,
        "primary_samples_fixture": 183, "pl_intake_evidence_root": ROOT,
    }
    pl = {
        "schema": "policylab.plrs6_offline_intake_receipt.v1",
        "decision": native["pl_intake_decision"], "capture_kind": "TEST_FIXTURE",
        "normalized_capture_hashes_verified": 2, "supporting_file_hashes_verified": 6,
        "evidence_root_sha256": ROOT,
        "physical_ready": False, "grid_export_eligible": False, "spk_issuance_allowed": False,
        "calibration_documents_content_verified": False, "independent_device_custody_verified": False,
        "physical_channel_identity_verified": False, "circuit_safety_review_verified": False,
        "timebase_verified_against_external_clock": False,
    }
    screen = {
        "schema": "hardware_splicer.witness_fixture_discrimination.v1",
        "decision": "PASS_FIXTURE_DISCRIMINATION_ONLY",
        "physical_ready": False, "metrological_agreement_proven": False,
        "fabrication_allowed": False, "reference_independence_verified": False,
        "reference_calibration_verified": False, "external_timebase_verified": False,
        "fixture_only": True, "primary_receipt_verified": True, "samples_paired": 183,
    }
    capture = {"capture_kind": "TEST_FIXTURE", "source_kind": "register_fixture",
               "status": "COMPLETE", "completed_samples": 183}
    return native, pl, screen, capture


class G3Tests(unittest.TestCase):
    def test_fixture_consistent_returns_no_physical_claims(self):
        r = review(*synthetic_controls())
        self.assertEqual(r["software_structural_replay"], "PASS")
        self.assertEqual(r["source_authenticity"], "NOT_ESTABLISHED")
        self.assertFalse(r["physical_operation_authorized"])
        self.assertFalse(r["token_issuance_authorized"])

    def test_unpinned_root_explicitly_not_authenticated(self):
        r = review(*synthetic_controls())
        self.assertEqual(r["source_authenticity"], "NOT_ESTABLISHED")
        with self.assertRaisesRegex(Hold, "independently pinned"):
            review(*synthetic_controls(), expected_evidence_root="aa" * 32)

    def test_wrong_hs_or_policy_lab_status_fails(self):
        for idx, key, value in [(0, "status", "PHYSICALLY_VALIDATED"),
                                (0, "hardware_powered", True),
                                (1, "decision", "ADMIT"),
                                (1, "capture_kind", "MEASURED"),
                                (2, "decision", "PASS_PHYSICAL")]:
            with self.subTest(idx=idx,key=key):
                data=list(synthetic_controls())
                data[idx][key]=value
                with self.assertRaises(Hold):
                    review(*data)

    def test_any_physical_claim_in_replay_fails(self):
        for idx, key in [(0, "fabrication_released"), (0, "calibration_verified"),
                         (1, "physical_ready"), (1, "spk_issuance_allowed"),
                         (1, "independent_device_custody_verified"),
                         (2, "fabrication_allowed"), (2, "metrological_agreement_proven")]:
            with self.subTest(idx=idx,key=key):
                data=list(synthetic_controls())
                data[idx][key]=True
                with self.assertRaises(Hold):
                    review(*data)

    def test_changed_evidence_root_or_missing_hash_receipt_rejected(self):
        for idx, key, value in [(0, "pl_intake_evidence_root", "ff" * 32),
                                (1, "normalized_capture_hashes_verified", False),
                                (1, "normalized_capture_hashes_verified", True),
                                (1, "normalized_capture_hashes_verified", 1),
                                (1, "supporting_file_hashes_verified", False),
                                (1, "supporting_file_hashes_verified", True)]:
            data=list(synthetic_controls())
            data[idx][key]=value
            with self.assertRaises(Hold):
                review(*data)

    def test_unequal_sample_counts_or_bad_capture_class_rejected(self):
        for idx, key, value in [(3, "completed_samples", 182), (2, "samples_paired", 182),
                                (0, "primary_samples_fixture", 0), (3, "source_kind", "hardware")]:
            data=list(synthetic_controls())
            data[idx][key]=value
            with self.assertRaises(Hold):
                review(*data)


if __name__ == "__main__":
    unittest.main()

"""Consolidated review driver contract; verifies release-hold semantics."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import review_witness as driver

HERE = Path(__file__).resolve().parent


class UnifiedReviewContractTests(unittest.TestCase):
    def test_all_declared_module_tests_exist(self):
        self.assertEqual(len(driver.TEST_FILES), len(set(driver.TEST_FILES)))
        self.assertIn("test_g1_stream_binding.py", driver.TEST_FILES)
        for name in driver.TEST_FILES:
            with self.subTest(file=name):
                self.assertTrue((HERE / name).is_file())

    def test_original_policy_lab_receiver_pinned_by_commit(self):
        self.assertEqual(len(driver.EXPECTED_POLICY_LAB_COMMIT), 40)
        self.assertTrue(all(c in "0123456789abcdef"
                            for c in driver.EXPECTED_POLICY_LAB_COMMIT))

    def test_physical_release_flag_missing_or_true_is_rejected(self):
        with tempfile.TemporaryDirectory(prefix="hs-review-hold-") as temp:
            p = Path(temp) / "proof.json"
            for data in ({"physical_ready": True},
                         {"physical_ready": False}):
                p.write_text(json.dumps(data))
                with self.assertRaises(AssertionError):
                    driver.must_hold(p, ("physical_ready", "fabrication_allowed"))

    def test_complete_false_claims_pass_only_the_flag_check(self):
        with tempfile.TemporaryDirectory(prefix="hs-review-false-") as temp:
            p = Path(temp) / "proof.json"
            evidence = {"physical_ready": False,
                        "fabrication_allowed": False,
                        "energization_authorized": False}
            p.write_text(json.dumps(evidence))
            self.assertEqual(driver.must_hold(p, (
                "physical_ready", "fabrication_allowed", "energization_authorized"
            )), evidence)

    def test_review_never_overwrites_existing_directory(self):
        with tempfile.TemporaryDirectory(prefix="hs-review-existing-") as temp:
            p = Path(temp)
            result = subprocess.run([
                sys.executable, str(HERE/"review_witness.py"),
                "--pl-root", str(p), "--out", str(p)
            ], text=True, capture_output=True, timeout=12)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("must not already exist", result.stderr)


if __name__ == "__main__":
    unittest.main()

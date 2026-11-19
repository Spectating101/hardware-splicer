"""Unit tests for engine verdicts, parsing, fail-closed behavior."""
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

MODULE = Path(__file__).resolve().parents[2] / "src/hardware_splicer/integrations/external_eda_verification.py"
spec = importlib.util.spec_from_file_location("external_eda_verification", MODULE)
assert spec and spec.loader
eda = importlib.util.module_from_spec(spec)
spec.loader.exec_module(eda)


class ExternalEdaVerificationTests(unittest.TestCase):
    def setUp(self):
        self.good = {"mode": "sch-pcb", "equivalent": True}
        self.zero = {"violations": 0, "unconnected_pads": 0,
                     "footprint_errors": 0}

    def test_valid_requires_all_three_authorities(self):
        r = eda.verdict(0, self.good, self.zero, 0)
        self.assertTrue(r["digital_review_pass"])
        self.assertFalse(r["physical_test_performed"])

    def test_structural_parse_never_overrides_short(self):
        r = eda.verdict(0, self.good, {**self.zero, "violations": 5}, 0)
        self.assertFalse(r["digital_review_pass"])

    def test_wrong_net_causes_rejection(self):
        r = eda.verdict(0, {"mode": "sch-pcb", "equivalent": False},
                        self.zero, 0)
        self.assertFalse(r["digital_review_pass"])

    def test_missing_drc_or_native_exit_fails_closed(self):
        self.assertFalse(eda.verdict(0, self.good, None, 0)["digital_review_pass"])
        self.assertFalse(eda.verdict(0, self.good, self.zero, 1)["digital_review_pass"])

    def test_kx_parser_error_causes_rejection(self):
        self.assertFalse(eda.verdict(1, self.good, self.zero, 0)["digital_review_pass"])

    def test_parse_drc_uses_counts_not_just_process_status(self):
        t = ("** Found 4 DRC violations **\n"
             "** Found 1 unconnected pads **\n"
             "** Found 0 Footprint errors **\n")
        self.assertEqual(eda.parse_native_drc(t), {
            "violations": 4, "unconnected_pads": 1, "footprint_errors": 0})
        self.assertIsNone(eda.parse_native_drc("command exited 0"))

    def test_unexpected_akcli_mode_not_accepted(self):
        self.assertFalse(eda.verdict(0, {"mode": "sch-sch",
                                        "equivalent": True}, self.zero, 0)["digital_review_pass"])


if __name__ == "__main__":
    unittest.main()

"""Source contract and metrology math tests; no physical proof is claimed."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("audit_readiness", HERE/"audit_readiness.py")
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class MetrologyAuditTests(unittest.TestCase):
    def test_nominal_does_not_exceed_design_declared_power_limit(self):
        b=audit.corner_arithmetic(5,10)
        self.assertAlmostEqual(b["load_power_w"],2.462918,places=5)
        self.assertFalse(b["declared_load_power_limit_exceeded"])

    def test_maximum_declared_bus_exceeds_stated_power_budget(self):
        b=audit.corner_arithmetic(5.25,10)
        self.assertTrue(b["declared_load_power_limit_exceeded"])
        self.assertGreater(b["load_power_w"],2.7)
        self.assertFalse(b["source_limit_engaged_in_ideal_model"])

    def test_lower_resistance_at_high_voltage_is_worse(self):
        high=audit.corner_arithmetic(5.25,9.5)
        self.assertTrue(high["declared_load_power_limit_exceeded"])
        self.assertGreater(high["load_power_w"],2.85)

    def test_10mohm_shunt_5mV_and_candidate_dmm_accuracy(self):
        d=audit.dmm_shunt_uncertainty_example()
        self.assertAlmostEqual(d["nominal_reference_current_a"], .5)
        self.assertAlmostEqual(d["manufacturer_dmm_voltage_error_uV"],8.75)
        self.assertAlmostEqual(d["dmm_error_pct_of_5mV"],.175)
        self.assertGreater(d["simple_worst_case_pct_at_nominal"],1.17)

    def test_current_limited_source_not_fuse_assurance(self):
        self.assertLess(audit.SOURCE_CURRENT_LIMIT_A,audit.FUSE_CANDIDATE_A)

    def test_spice_corners_agree_with_independent_series_circuit_oracle(self):
        for v,load in ((5,10),(5.25,10),(5.25,9.5)):
            a=audit.corner_arithmetic(v,load)
            s=audit.corner_spice(v,load)
            self.assertAlmostEqual(a["current_a"],s["current_a"],places=6)
            self.assertAlmostEqual(a["load_power_w"],s["load_power_w"],places=5)


if __name__=="__main__":
    unittest.main()

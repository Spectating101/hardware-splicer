"""Bounded source/operating-envelope controls. No hardware tests."""
import importlib.util
from pathlib import Path
import json
import math
import unittest

ROOT=Path(__file__).parent
FILE=ROOT/"optimize.py"
mod=importlib.util.spec_from_file_location("witness_optimize",FILE)
opti=importlib.util.module_from_spec(mod)
mod.loader.exec_module(opti)


class OperatingEnvelopeTests(unittest.TestCase):
    def test_frozen_original_station_is_pinned(self):
        plan=json.loads((ROOT/"experiment-20261120.json").read_text())
        self.assertEqual(opti.sha(ROOT.parent/"station-spec-5v.json"),plan["design_identity"]["source_station_spec_sha256"])
        self.assertEqual(opti.sha(ROOT.parent/"spice_low_voltage_witness.cir"),plan["design_identity"]["source_spice_sha256"])
        self.assertEqual(plan["candidate_load_resistances_ohm"],[10,11,12,13,15,18])

    def test_nominal_spice_passes_but_maximum_supply_is_exceeded(self):
        nominal=opti.spice(5,10,.075)
        corner=opti.spice(5.25,9.5,0)
        self.assertAlmostEqual(nominal["load_power_w"],2.462918,places=5)
        self.assertGreater(corner["load_power_w"],2.5)
        self.assertLess(nominal["load_power_w"],2.5)

    def test_13_ohm_passes_trial_reserve_but_12_does_not(self):
        volts=5.25
        conservative=lambda resistance:volts**2/(resistance*.95)
        self.assertLess(conservative(13),2.5*.9)
        self.assertGreater(conservative(12),2.5*.9)
        self.assertGreater(4.75/(13*1.05+.15),.34)
        self.assertLess(4.75/(15*1.05+.15),.34)

    def test_proposal_not_robust_without_prospective_resistor_tolerance(self):
        conservative_13_at_10_percent=5.25**2/(13*.9)
        self.assertGreater(conservative_13_at_10_percent,2.25)
        self.assertLess(conservative_13_at_10_percent,2.5)

    def test_zero_series_circuit_is_grounded_and_spice_agrees(self):
        c=opti.circuit(5.25,9.5,0)
        self.assertIn("V_SRC load 0 DC 5.25",c)
        self.assertIn("R_LOAD load 0 9.5",c)
        a=opti.spice(5.25,9.5,0)
        self.assertTrue(math.isclose(a["current_a"],5.25/9.5,rel_tol=2e-6))


if __name__=="__main__":
    unittest.main()

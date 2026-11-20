"""Native CAD and bounded fixture test, without energizing or acquiring any hardware."""
from __future__ import annotations

import csv
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
NAME = "low_voltage_witness_fixture_v0"
HS = HERE.parents[2]
CAD = shutil.which("kicad-cli") is not None and shutil.which("ngspice") is not None
try:
    import pcbnew
except ImportError:
    CAD = False


@unittest.skipUnless(CAD, "requires KiCad9 pcbnew, kicad-cli, and ngspice")
class LowVoltageWitnessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="hs-witness-unit-")
        cls.out = Path(cls.temp.name) / "replay"
        result = subprocess.run(
            [os.environ.get("PYTHON", "python3"), str(HERE / "verify_and_replay.py"),
             "--out", str(cls.out)],
            cwd=HERE, capture_output=True, text=True, timeout=65,
        )
        if result.returncode:
            raise AssertionError(f"CAD/decoder fixture failed:\n{result.stdout}\n{result.stderr}")
        cls.report = json.loads((cls.out / "verification.json").read_text())

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_native_erc_drc_and_footprint_parity(self):
        self.assertEqual(self.report["native_erc"], "ZERO_VIOLATIONS")
        self.assertEqual(self.report["native_drc"],
                         "ZERO_VIOLATIONS_ZERO_UNCONNECTED_ZERO_PARITY_ERRORS")
        self.assertEqual(self.report["expected_net_pads"], 22)

    def test_spice_steady_load_is_analytically_consistent(self):
        self.assertAlmostEqual(self.report["spice_current_a"], 5 / 10.075, places=6)
        self.assertAlmostEqual(self.report["spice_load_voltage_v"],
                               self.report["spice_current_a"] * 10, places=5)
        self.assertAlmostEqual(self.report["spice_3min_load_energy_wh"],
                               self.report["spice_load_power_w"] * 0.05, places=9)

    def test_fixture_has_no_authority(self):
        self.assertEqual(self.report["status"], "SOFTWARE_DESIGN_VALIDATED_ONLY")
        for key in ["physical_equipment_built", "hardware_powered",
                    "calibration_verified", "fabrication_released"]:
            self.assertIs(self.report[key], False)
        self.assertEqual(self.report["primary_samples_fixture"], 183)
        self.assertEqual(self.report["pl_intake_decision"], "NOT_RUN")

    def test_station_specific_shunts_and_5v_envelope(self):
        spec = json.loads((HERE / "station-spec-5v.json").read_text())
        self.assertEqual(spec["nominal_voltage_v"], 5)
        self.assertEqual(spec["maximum_power_w"], 2.5)
        self.assertEqual(spec["shunt_ohm"], 0.015)
        self.assertEqual(spec["reference_shunt_ohm"], 0.01)
        self.assertEqual(self.report["station_design_checks_passed"], True)

    def test_bom_complete_and_not_procured(self):
        with (HERE / "BOM_candidate.csv").open(newline="") as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual(len(rows), 14)
        self.assertEqual({v["Ref"] for v in rows} & {"F1", "R1", "EXT_INA228"},
                         {"F1", "R1", "EXT_INA228"})
        self.assertTrue(all(v["Status"] not in ("PROCURED", "ASSEMBLED", "VALIDATED") for v in rows))
        self.assertTrue((HERE / "BUILD_HOLD.md").is_file())

    def test_separate_kelvin_and_carrier_current_pins(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("witness_gen",
                                                     HERE / "generate_schematic.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        nets = module.NETS
        self.assertNotEqual(nets["J3"]["1"], nets["J3"]["2"])
        self.assertEqual(nets["J3"]["2"], nets["R1"]["1"])
        self.assertEqual(nets["R1"]["4"], nets["J2"]["1"])
        self.assertEqual(nets["R1"]["2"], nets["J5"]["1"])
        self.assertEqual(nets["R1"]["3"], nets["J5"]["2"])
        self.assertEqual(nets["J4"]["1"], nets["J2"]["1"])
        self.assertEqual(nets["J6"]["1"], nets["J2"]["1"])


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations
import tempfile
import unittest
from pathlib import Path
from hardware_splicer.open_repair_candidates import summarize_repairs

HEADER = "id,product_category,repair_status,problem,repair_barrier_if_end_of_life\n"
ROWS = ("r-1,Printer,Fixed,No power,\n"
        "r-2,Printer,End of life,Jam,Spare parts not available\n"
        "r-3,Phone,Fixed,No power,\n")

class OraTest(unittest.TestCase):
    def test_bounded_category_observations_not_diagnosis(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "open-repair.csv"
            p.write_text(HEADER + ROWS, encoding="utf-8")
            data = summarize_repairs(p, category="Printer")
            self.assertEqual(data["rows_scanned"], 3)
            self.assertEqual(data["matching_rows"], 2)
            self.assertEqual(data["repair_status_counts"]["Fixed"], 1)
            self.assertFalse(data["device_identity_verified"])
            self.assertFalse(data["mission_success"])
            self.assertFalse(data["scan_truncated"])
            partial = summarize_repairs(p, category="Printer", max_rows=1)
            self.assertTrue(partial["scan_truncated"])

    def test_lfs_pointer_not_accepted(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "pointer.csv"
            p.write_text("version https://git-lfs.github.com/spec/v1\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                summarize_repairs(p, category="Printer")

if __name__ == "__main__":
    unittest.main()

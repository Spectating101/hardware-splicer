"""HS-BUS-A's JLCPCB files cover every BOM part with an LCSC number and a placement."""
import csv
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "projects" / "hs-bus-a"


def test_every_bom_part_has_an_lcsc_number_and_a_placement():
    out = subprocess.run([sys.executable, str(ROOT / "jlc_order_files.py")], capture_output=True, text=True, check=True)
    assert '"without_lcsc": []' in out.stdout and '"in_bom_not_in_cpl": []' in out.stdout
    with open(ROOT / "fab" / "jlc" / "hs_bus_a_bom_jlc.csv", newline="") as f:
        bom = list(csv.DictReader(f))
    with open(ROOT / "fab" / "jlc" / "hs_bus_a_cpl_jlc.csv", newline="") as f:
        cpl = {r["Designator"] for r in csv.DictReader(f)}
    refs = {r for row in bom for r in row["Designator"].split(",")}
    assert refs <= cpl and all(row["LCSC Part #"].startswith("C") for row in bom)

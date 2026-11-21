"""Challenge 001 generation must disclose copied topology and incomplete output."""
import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/generate_hs_build_candidate_001.py"
spec = importlib.util.spec_from_file_location("hs_build_candidate_001", SCRIPT)
candidate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(candidate)


def test_first_candidate_contains_real_pin_nets_and_is_not_fabrication_ready(tmp_path):
    candidate.generate_candidate(tmp_path)
    import json
    design = json.loads((tmp_path / "design_candidate.json").read_text())
    assert design["components"][0]["mpn"] == "LM2596S-5.0/NOPB"
    assert design["reference_design_reused"] is True
    assert "U1.4" in design["nets"]["VOUT"]
    assert "U1.5" in design["nets"]["GND"]
    assert "D1.K" in design["nets"]["SW"]
    assert not design["fabrication_authorized"]
    assert any(row["mpn"] is None for row in design["components"])
    assert not (tmp_path / "design.kicad_pcb").exists()

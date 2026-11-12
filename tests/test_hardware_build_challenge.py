"""Safety: no incomplete/supplied circuit can be reported as a built device."""
import json

from hardware_splicer.hardware_build_challenge import evaluate_build_submission


def test_empty_submission_rejected(tmp_path):
    result = evaluate_build_submission(tmp_path)
    assert not result["automated_submission_checks_pass"]
    assert "missing_or_empty:design.kicad_sch" in result["errors"]
    assert not result["physical_prototype_built"]
    assert not result["fabrication_authorized"]


def test_reference_design_cannot_masquerade_as_generated(tmp_path):
    for filename in ("design.kicad_sch", "design.kicad_pcb", "simulation.cir"):
        (tmp_path / filename).write_text("placeholder")
    (tmp_path / "bom.csv").write_text("reference,manufacturer_part_number,quantity\nU1,EXAMPLE,1\n")
    (tmp_path / "design_origin.json").write_text(json.dumps({
        "origin": "reference_import",
        "reference_design_reused": True,
        "generator_run_id": "test",
    }))
    result = evaluate_build_submission(tmp_path)
    assert "design_not_declared_hs_generated" in result["errors"]
    assert "reference_reuse_unresolved" in result["errors"]
    assert not result["automated_submission_checks_pass"]


def test_undeclared_components_block_gate(tmp_path):
    (tmp_path / "bom.csv").write_text(
        "reference,manufacturer_part_number,quantity\nU1,,1\n"
    )
    result = evaluate_build_submission(tmp_path)
    assert "unresolved_manufacturer_part_number" in result["errors"]
    assert not result["performance_validated"]
    assert not result["schematic_pcb_parity_verified"]

from __future__ import annotations

from types import SimpleNamespace

from hardware_splicer.capability_policy import product_capability_report


def _run(command, **kwargs):
    return SimpleNamespace(returncode=0, stdout="9.0.9\n", stderr="")


def _missing_kicad_happy():
    return {
        "available": False,
        "root": None,
        "revision": None,
        "capabilities": [],
        "missing_capabilities": ["schematic", "pcb", "gerber"],
    }


def test_missing_optional_cadquery_does_not_fail_base_product_readiness() -> None:
    report = product_capability_report(
        environ={},
        which=lambda name: "/usr/bin/kicad-cli" if name == "kicad-cli" else None,
        run=_run,
        kicad_happy_discover=_missing_kicad_happy,
    )

    cadquery = next(
        row for row in report["capabilities"] if row["id"] == "cadquery-isolated"
    )
    assert cadquery["required"] is False
    assert cadquery["product_scope"] == [
        "generated_mechanical_output",
        "exact_step_brep_pair_interference",
        "exact_step_brep_minimum_clearance",
        "bounded_placed_step_tessellation",
        "exact_step_brep_surface_anchor",
        "exact_step_brep_anchor_mating_geometry",
        "bounded_sampled_step_brep_mating_path",
        "adaptive_step_brep_transition_refinement",
    ]
    assert "sampled mating-path clearance" in cadquery["authority_boundary"]
    assert "adaptively refined predicate brackets" in cadquery["authority_boundary"]
    assert "unique transition pose" in cadquery["authority_boundary"]
    assert "continuous-path clearance" in cadquery["authority_boundary"]
    assert "whole-assembly validity" in cadquery["authority_boundary"]
    assert "connector mating" in cadquery["authority_boundary"]
    assert "protocol/pin compatibility" in cadquery["authority_boundary"]
    assert "fabrication" in cadquery["authority_boundary"]
    if cadquery["runtime"]["discovered"] is False:
        assert cadquery["readiness"] == "missing_optional"
        assert "exact STEP/BREP geometry work" in cadquery["next_action"]
        assert "cadquery-isolated" not in report["required_missing"]
    assert report["policy"] == {
        "schema_version": "hardware_splicer.capability_policy.v1",
        "optional_specialists": ["cadquery-isolated"],
        "statement": (
            "Optional specialist engines are required only by projects that select "
            "their workflow; their absence does not fail the base product installation."
        ),
    }

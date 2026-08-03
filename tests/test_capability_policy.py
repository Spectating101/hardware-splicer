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
    if cadquery["runtime"]["discovered"] is False:
        assert cadquery["readiness"] == "missing_optional"
        assert "cadquery-isolated" not in report["required_missing"]
    assert report["policy"] == {
        "schema_version": "hardware_splicer.capability_policy.v1",
        "optional_specialists": ["cadquery-isolated"],
        "statement": (
            "Optional specialist engines are required only by projects that select "
            "their workflow; their absence does not fail the base product installation."
        ),
    }

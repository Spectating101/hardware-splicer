"""A footprint nobody checked against the real part withholds fabrication, never build_ready."""

from __future__ import annotations

import json
from pathlib import Path

from hardware_splicer.build_compiler import compile_catalog_build
from hardware_splicer.design_quality import build_design_quality_gate
from hardware_splicer.fabrication_inspection import inspect_fabrication_package
from hardware_splicer.netlist.quality_flags import finalize_launch_quality
from hardware_splicer.pcb.fit_report import UNVERIFIED_FIT_BLOCKER_PREFIX, module_fit_report
from hardware_splicer.pcb.module_registry import resolve_module_fit


def test_a_module_with_no_registered_footprint_is_never_verified() -> None:
    fit = resolve_module_fit("boost-mt3608")
    assert fit["status"] == "unverified_variant"
    assert "placeholder" in fit["reason"]


def test_fit_report_lists_unverified_modules_once_and_sorted() -> None:
    report = module_fit_report(["usb-power-5v", "boost-mt3608", "usb-power-5v", "a4988-stepper"])
    assert [r["module_id"] for r in report["module_fit"]] == ["usb-power-5v", "boost-mt3608", "a4988-stepper"]
    assert report["unverified_fit_modules"] == sorted(report["unverified_fit_modules"])
    assert "boost-mt3608" in report["unverified_fit_modules"]
    assert report["fabrication_blocker"].startswith(UNVERIFIED_FIT_BLOCKER_PREFIX)
    assert "boost-mt3608" in report["fabrication_blocker"]


def test_a_board_of_only_verified_modules_has_no_fit_blocker(monkeypatch) -> None:
    monkeypatch.setattr(
        "hardware_splicer.pcb.fit_report.resolve_module_fit",
        lambda module_id: {"status": "verified_against", "verified_against": "test source"},
    )
    report = module_fit_report(["a4988-stepper", "arduino-nano"])
    assert report["unverified_fit_modules"] == []
    assert report["fabrication_blocker"] is None


def _clean_launch_quality(**extra: object) -> dict:
    return {
        "build_ready": True,
        "kicad_drc_pass": True,
        "kicad_drc_errors": 0,
        "kicad_erc_pass": True,
        "kicad_erc_errors": 0,
        "freerouting_ok": True,
        "freerouting_track_count": 10,
        "gerber_ready": True,
        "board_outline": {"trace_segments": 10},
        **extra,
    }


def test_unverified_fit_clears_fabrication_ready_but_not_build_ready() -> None:
    clean = finalize_launch_quality(_clean_launch_quality())
    assert clean["build_ready"] is True and clean["fabrication_ready"] is True

    flagged = finalize_launch_quality(
        _clean_launch_quality(unverified_fit_modules=["tp4056"], module_fit=[{"module_id": "tp4056"}])
    )
    assert flagged["build_ready"] is True
    assert flagged["fabrication_ready"] is False
    assert any(b.startswith(UNVERIFIED_FIT_BLOCKER_PREFIX) and "tp4056" in b for b in flagged["fabrication_blockers"])


def test_design_quality_gate_names_the_unverified_modules_as_a_fabrication_blocker_only() -> None:
    body = {
        "build_graph_compiled": True,
        "electrical_safety_pass": True,
        "drc_pass": True,
        "gerber_ready": True,
        "bom_ready": True,
        "build_ready": True,
        "fabrication_ready": True,
        "unverified_fit_modules": ["mosfet-irlz44n", "tp4056"],
        "module_fit": [{"module_id": "mosfet-irlz44n"}, {"module_id": "tp4056"}, {"module_id": "a4988-stepper"}],
    }
    gate = build_design_quality_gate(body)
    assert gate["build_ready"] is True
    assert gate["fabrication_ready"] is False
    assert gate["blockers"] == []
    assert any("mosfet-irlz44n, tp4056" in b for b in gate["fabrication_blockers"])
    assert gate["unverified_fit_modules"] == ["mosfet-irlz44n", "tp4056"]

    body["unverified_fit_modules"] = []
    assert build_design_quality_gate(body)["fabrication_ready"] is True


def test_fabrication_inspection_is_not_honest_ready_while_a_fit_is_unverified(tmp_path: Path) -> None:
    result = inspect_fabrication_package(
        build_compilation={"design_quality": {"unverified_fit_modules": ["tp4056"], "module_fit": [{}, {}]}}
    )
    assert result["honest_fabrication_ready"] is False
    assert any("tp4056" in b for b in result["blockers"])
    assert result["unverified_fit_modules"] == ["tp4056"]


def test_compiled_catalog_build_reports_its_unverified_modules(tmp_path: Path) -> None:
    result = compile_catalog_build("usb_uart_debug_adapter", tmp_path, export_gerber=False)
    quality = result.design_quality
    fit_by_id = {row["module_id"]: row for row in quality["module_fit"]}
    assert set(fit_by_id) == {"usb-power-5v", "ch340-usb-ttl"} or len(fit_by_id) == quality["module_count"]
    assert quality["unverified_fit_modules"] == sorted(
        mid for mid, row in fit_by_id.items() if row["status"] != "verified_against"
    )
    assert quality["unverified_fit_modules"], "this build uses variant-dependent modules"
    assert quality["fabrication_ready"] is False
    assert any(b.startswith(UNVERIFIED_FIT_BLOCKER_PREFIX) for b in quality["fabrication_blockers"])
    on_disk = json.loads(Path(quality["design_quality_file"]).read_text(encoding="utf-8"))
    assert on_disk["unverified_fit_modules"] == quality["unverified_fit_modules"]
    # Fit never changes the ERC/DRC/connectivity verdict.
    gate = build_design_quality_gate(quality)
    assert gate["build_ready"] == (not gate["blockers"] and bool(quality.get("build_ready")))


# ---- fit is computed from the footprint geometry that is actually emitted ----------------------------


def _quality_for_graph(tmp_path: Path, module_ids: list) -> dict:
    from hardware_splicer.pcb.geometry_compile import compile_graph_to_artifacts

    nodes = [{"id": f"n{i + 1}", "moduleId": mid} for i, mid in enumerate(module_ids)]
    wires = [
        {"id": "w1", "from": {"nodeId": "n1", "pinId": "GND"}, "to": {"nodeId": "n2", "pinId": "GND"}},
    ]
    return compile_graph_to_artifacts("custom", tmp_path, {"nodes": nodes, "wires": wires})["quality"]


def test_a_module_id_that_only_matches_after_trimming_gets_a_synthetic_footprint_and_no_verification(
    tmp_path: Path,
) -> None:
    # Geometry looks the id up exactly, so "arduino-nano " gets the synthetic placeholder, and the
    # fit report must say so instead of certifying the real Nano.
    report = module_fit_report(["arduino-nano "])
    assert report["unverified_fit_modules"] == ["arduino-nano "]
    quality = _quality_for_graph(tmp_path, ["arduino-nano ", "usb-power-5v"])
    assert "arduino-nano " in quality["unverified_fit_modules"]
    assert quality["fabrication_ready"] is False


def test_an_empty_module_id_has_an_unverified_fit_record(tmp_path: Path) -> None:
    report = module_fit_report(["", "arduino-nano"])
    by_id = {row["module_id"]: row for row in report["module_fit"]}
    assert by_id[""]["status"] == "unverified_variant"
    assert "" in report["unverified_fit_modules"]
    quality = _quality_for_graph(tmp_path, ["", "arduino-nano"])
    assert quality["fabrication_ready"] is False and "" in quality["unverified_fit_modules"]


def test_resolve_module_fit_does_not_normalise_the_id() -> None:
    assert resolve_module_fit("arduino-nano")["status"] == "verified_against"
    for raw in ("arduino-nano ", " arduino-nano", "ARDUINO-NANO", "", None):
        assert resolve_module_fit(raw)["status"] == "unverified_variant", repr(raw)

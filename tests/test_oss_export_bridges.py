"""Skip-safe OSS export bridges — tools absent must not fail."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from hardware_splicer.integrations.esphome_export import build_esphome_stub, write_esphome_stub
from hardware_splicer.integrations.ibom_bridge import run_ibom
from hardware_splicer.integrations.kikit_bridge import run_kikit_fab
from hardware_splicer.integrations.oss_export_bundle import attach_oss_mech_refs, run_oss_export_bundle
from hardware_splicer.integrations.pcbdraw_bridge import run_pcbdraw
from hardware_splicer.integrations.easyeda2kicad_bridge import fetch_lcsc_to_kicad
from hardware_splicer.integrations.tscircuit_autorouter_bridge import run_tscircuit_autorouter
from hardware_splicer.project_package import write_project_package_artifacts


def test_ibom_skips_without_cli(tmp_path: Path) -> None:
    pcb = tmp_path / "board.kicad_pcb"
    pcb.write_text("(kicad_pcb (version 20241229))\n", encoding="utf-8")
    with patch("hardware_splicer.integrations.ibom_bridge._resolve_ibom_cli", return_value=None):
        with patch("hardware_splicer.integrations.ibom_bridge.subprocess.run") as run:
            run.return_value.returncode = 1
            run.return_value.stderr = "No module named 'InteractiveHtmlBom'"
            run.return_value.stdout = ""
            report = run_ibom(pcb, out_dir=tmp_path / "out")
    assert report["skipped"] is True
    assert report["id"] == "ibom"


def test_pcbdraw_skips_without_cli(tmp_path: Path) -> None:
    pcb = tmp_path / "board.kicad_pcb"
    pcb.write_text("(kicad_pcb (version 20241229))\n", encoding="utf-8")
    with patch("hardware_splicer.integrations.pcbdraw_bridge._resolve_pcbdraw", return_value=None):
        report = run_pcbdraw(pcb, out_dir=tmp_path / "out")
    assert report["skipped"] is True
    assert report["id"] == "pcbdraw"


def test_kikit_skips_without_cli(tmp_path: Path) -> None:
    pcb = tmp_path / "board.kicad_pcb"
    pcb.write_text("(kicad_pcb (version 20241229))\n", encoding="utf-8")
    with patch("hardware_splicer.integrations.kikit_bridge._resolve_kikit", return_value=None):
        report = run_kikit_fab(pcb, out_dir=tmp_path / "kikit")
    assert report["skipped"] is True


def test_easyeda2kicad_invalid_id() -> None:
    report = fetch_lcsc_to_kicad("not-an-id", out_dir="/tmp/hs_lcsc_test")
    assert report["ok"] is False
    assert report["reason"] == "invalid_lcsc_id"


def test_esphome_stub_from_pins(tmp_path: Path) -> None:
    payload = build_esphome_stub(
        build_id="inspection_motion_fixture",
        pins={"sourced_from_graph": True, "servo_pan": 18, "servo_tilt": 16},
        project_name="pan_tilt",
    )
    assert "GPIO18" in payload["source"]
    assert "GPIO16" in payload["source"]
    assert payload["pin_count"] == 2
    written = write_esphome_stub(
        build_id="inspection_motion_fixture",
        out_dir=tmp_path,
        pins={"sourced_from_graph": True, "servo_pan": 18, "servo_tilt": 16},
    )
    assert written["ok"] is True
    assert (tmp_path / "firmware" / "esphome_stub.yaml").is_file()


def test_oss_export_bundle_never_raises(tmp_path: Path) -> None:
    comp = tmp_path / "build_compilation"
    comp.mkdir()
    (comp / "board.kicad_pcb").write_text("(kicad_pcb (version 20241229))\n", encoding="utf-8")
    (comp / "build_graph.json").write_text(
        json.dumps(
            {
                "nodes": [{"id": "n1", "moduleId": "esp32-devkit"}, {"id": "n2", "moduleId": "sg90"}],
                "wires": [{"from": {"nodeId": "n1", "pinId": "GPIO18"}, "to": {"nodeId": "n2", "pinId": "SIG"}}],
            }
        ),
        encoding="utf-8",
    )
    with patch("hardware_splicer.integrations.ibom_bridge._resolve_ibom_cli", return_value=None):
        with patch("hardware_splicer.integrations.pcbdraw_bridge._resolve_pcbdraw", return_value=None):
            with patch(
                "hardware_splicer.integrations.ibom_bridge.subprocess.run",
                side_effect=FileNotFoundError("no"),
            ):
                report = run_oss_export_bundle(tmp_path, build_id="demo", enforce_roots=False)
    assert report["ok"] is True
    assert (tmp_path / "build_compilation" / "exports" / "OSS_EXPORTS.json").is_file()
    # ESPHome should still write from graph
    assert (tmp_path / "firmware" / "esphome_stub.yaml").is_file()


def test_attach_oss_mech_refs() -> None:
    pack = attach_oss_mech_refs({"status": "degraded"})
    ids = {r["id"] for r in pack["oss_mech_refs"]}
    assert "nopscadlib" in ids
    assert "build123d" in ids


def test_package_write_includes_oss_exports(tmp_path: Path) -> None:
    comp = tmp_path / "build_compilation"
    comp.mkdir()
    (comp / "board.kicad_pcb").write_text("(kicad_pcb (version 20241229))\n", encoding="utf-8")
    with patch("hardware_splicer.integrations.ibom_bridge._resolve_ibom_cli", return_value=None):
        with patch("hardware_splicer.integrations.pcbdraw_bridge._resolve_pcbdraw", return_value=None):
            with patch(
                "hardware_splicer.integrations.ibom_bridge.subprocess.run",
                side_effect=FileNotFoundError("no"),
            ):
                result = write_project_package_artifacts(
                    tmp_path,
                    result={"ok": True, "build_id": "demo", "project_name": "demo"},
                    source="test",
                )
    assert "oss_exports" in result
    package = json.loads((tmp_path / "PROJECT_PACKAGE.json").read_text(encoding="utf-8"))
    assert "oss_exports" in package


def test_tscircuit_autoroute_skips_without_circuit_json(tmp_path: Path) -> None:
    (tmp_path / "build_compilation").mkdir()
    report = run_tscircuit_autorouter(tmp_path)
    assert report["skipped"] is True
    assert report["engine"] == "tscircuit"

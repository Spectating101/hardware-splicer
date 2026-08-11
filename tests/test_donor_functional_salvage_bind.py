"""Donor functional salvage must preserve donor capability without catalog stand-ins."""

from __future__ import annotations

from pathlib import Path

from hardware_splicer.project_intake import load_project_intake, splice_and_build_from_intake
from hardware_splicer.salvage_bridge import build_intake_salvage_package

ROOT = Path(__file__).resolve().parents[1]


def test_robot_drive_keeps_unknown_donor_hbridge_and_motor_identity_unresolved(monkeypatch) -> None:
    # This is an identity-boundary test, so do not let the suite-wide offline compatibility
    # environment silently re-enable the historical representative-module resolver.
    # QWEN_DISABLED itself means "force offline compatibility" in the central policy, so it
    # must also be cleared; with no provider credentials, model-first identity remains
    # unresolved rather than falling back to heuristics.
    monkeypatch.setenv("HARDWARE_SPLICER_OFFLINE_SALVAGE", "0")
    monkeypatch.setenv("QWEN_DISABLED", "0")
    monkeypatch.setenv("HARDWARE_SPLICER_QWEN_DISABLED", "0")
    monkeypatch.setenv("HARDWARE_SPLICER_QWEN_SALVAGE", "1")
    monkeypatch.delenv("QWEN_API_KEY", raising=False)
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)

    intake = load_project_intake(ROOT / "examples" / "intakes" / "splice_robot_drive_brief.json")
    package = build_intake_salvage_package(
        goal=str(intake.get("goal") or ""),
        parts=list(intake.get("available_parts") or []),
        constraints=dict(intake.get("constraints") or {}),
        project_name=str(intake.get("project_name") or "robot"),
        donor_context={
            "circuit": intake.get("circuit"),
            "functional_salvage": intake.get("functional_salvage"),
        },
    )
    resolved = list(package.get("resolved_modules") or [])

    # An unknown donor H-bridge is useful capability evidence, but it is not an L298N.
    assert not any(row.get("module_id") == "l298n" for row in resolved), resolved
    donor_drv = [
        row
        for row in resolved
        if str(row.get("source") or "").startswith("donor_functional_salvage")
        and row.get("role") == "drv"
    ]
    assert donor_drv, resolved
    assert donor_drv[0].get("module_id") is None
    assert donor_drv[0].get("external_capability_only") is True
    assert "J_MOTOR_L" in (donor_drv[0].get("connector_refs") or [])
    assert "J_MOTOR_R" in (donor_drv[0].get("connector_refs") or [])

    # The two physical motors must remain two inventory instances even though neither generic
    # name is sufficient evidence for a particular catalog motor identity.
    by_name = {str(row.get("part_name") or ""): row for row in resolved}
    for name in ("left 6V DC gear motor", "right 6V DC gear motor"):
        assert name in by_name, resolved
        assert by_name[name].get("module_id") is None
        assert by_name[name].get("identity_status") == "unresolved"

    # A strict identity-only package may not have enough concrete module identity to compile a
    # hardware-specific bring-up card. Connector truth therefore lives on the donor capability
    # row until a later architecture/identity decision; the package must not invent L298N text.
    bringup = (package.get("bringup_card") or {}).get("markdown") or ""
    assert "L298N" not in bringup

    # Voltage numbers or familiar connector names are not exact source identity.
    assert package.get("power_topology") == "unresolved"
    bound = package.get("salvage_resolution", {}).get("functional_salvage_bound", {})
    assert bound.get("driver_capability_present") is True
    assert bound.get("catalog_standin_required") is False


def test_enabot_lite_intake_keeps_donor_drive(tmp_path: Path) -> None:
    intake = load_project_intake(ROOT / "examples" / "intakes" / "splice_vibe_enabot_lite_brief.json")
    result = splice_and_build_from_intake(
        intake,
        out_dir=tmp_path / "enabot_lite",
        export_gerber=False,
        request_id="enabot_lite",
    )
    assert result.get("ok") is True
    package = result.get("salvage_package") or {}
    resolved = list(package.get("resolved_modules") or [])
    assert not any(r.get("source") == "gap_fill" and r.get("module_id") == "l298n" for r in resolved)
    assert any(r.get("source") == "donor_functional_salvage" and r.get("role") == "drv" for r in resolved)
    assert any(r.get("module_id") == "esp32-cam-module" for r in resolved)
    assert (package.get("module_overrides") or {}).get("mcu") == "esp32-cam-module"

    bringup = (package.get("bringup_card") or {}).get("markdown") or ""
    assert "J_MOTOR_L" in bringup
    assert "J_MOTOR_R" in bringup

    gpio = (package.get("bringup_card") or {}).get("gpio_assignments") or []
    in_pins = {str(row.get("to_pin") or "").upper() for row in gpio}
    assert {"IN1", "IN2", "IN3", "IN4"}.issubset(in_pins), in_pins

    shopping = {
        str(r.get("module_id") or "")
        for r in ((package.get("gap_analysis") or {}).get("shopping_list") or [])
    }
    assert "l298n" not in shopping
    assert "usb-power-5v" not in shopping

    fw_meta = tmp_path / "enabot_lite" / "firmware" / "FIRMWARE_SCAFFOLD.json"
    assert fw_meta.is_file()
    import json

    fw = json.loads(fw_meta.read_text(encoding="utf-8"))
    assert all(fw.get("pins", {}).get(k) is not None for k in ("in1", "in2", "in3", "in4"))
    assert "const int IN3" in str(fw.get("source") or "")

    assert (tmp_path / "enabot_lite" / "PROJECT_PACKAGE.json").is_file()

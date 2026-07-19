#!/usr/bin/env python3
"""Endgame acceptance: junk bin → Enabot-lite cousin (offline, no Qwen)."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

# Prefer offline — do not burn cloud quota during acceptance.
os.environ.setdefault("HARDWARE_SPLICER_OFFLINE_LLM", "1")
os.environ.setdefault("HARDWARE_SPLICER_OFFLINE_VISION", "1")
os.environ.setdefault("HARDWARE_SPLICER_OFFLINE_SALVAGE", "1")
os.environ.setdefault("QWEN_DISABLED", "1")

from hardware_splicer.project_intake import load_project_intake, splice_and_build_from_intake


def _fail(msg: str, failures: list[str]) -> None:
    failures.append(msg)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--intake",
        type=Path,
        default=ROOT / "examples" / "intakes" / "splice_vibe_enabot_lite_brief.json",
    )
    parser.add_argument("--out", type=Path, default=Path("/tmp/hs_vibe_enabot_endgame"))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    failures: list[str] = []
    out_dir = args.out.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    intake = load_project_intake(args.intake)
    result = splice_and_build_from_intake(
        intake,
        out_dir=out_dir,
        export_gerber=False,
        request_id="vibe_enabot_endgame",
    )
    package = dict(result.get("salvage_package") or {})
    resolved = list(package.get("resolved_modules") or [])
    bringup_md = str((package.get("bringup_card") or {}).get("markdown") or "")
    gpio = list((package.get("bringup_card") or {}).get("gpio_assignments") or [])
    shopping = list((package.get("gap_analysis") or {}).get("shopping_list") or [])
    still_missing = list((package.get("gap_analysis") or {}).get("still_missing") or [])
    overrides = dict(package.get("module_overrides") or {})

    if result.get("ok") is not True:
        _fail(f"splice_and_build ok!=True: {result.get('error') or result.get('errors')}", failures)

    if not any(
        r.get("source") == "donor_functional_salvage" and r.get("role") == "drv" for r in resolved
    ):
        _fail("donor H-bridge not bound as drv", failures)

    if any(r.get("source") == "gap_fill" and r.get("module_id") == "l298n" for r in resolved):
        _fail("catalog L298N was gap-filled (should reuse donor)", failures)

    motors = [r for r in resolved if r.get("module_id") == "dc_motor_3v_6v"]
    if len(motors) < 2:
        _fail(f"expected 2 motors, got {len(motors)}", failures)

    if overrides.get("mcu") != "esp32-cam-module" and not any(
        r.get("module_id") == "esp32-cam-module" for r in resolved
    ):
        _fail(f"ESP32-CAM not selected (overrides={overrides})", failures)

    if "J_MOTOR_L" not in bringup_md or "J_MOTOR_R" not in bringup_md:
        _fail("bring-up missing donor harness labels J_MOTOR_L/R", failures)

    in_pins = {
        str(row.get("to_pin") or "").upper()
        for row in gpio
        if str(row.get("to_pin") or "").upper().startswith("IN")
    }
    if not {"IN1", "IN2", "IN3", "IN4"}.issubset(in_pins):
        _fail(f"bring-up missing dual-channel IN1–IN4 (got {sorted(in_pins)})", failures)

    if package.get("power_topology") != "hybrid":
        _fail(f"power_topology expected hybrid, got {package.get('power_topology')}", failures)

    shop_ids = {str(r.get("module_id") or "") for r in shopping}
    if "l298n" in shop_ids:
        _fail("shopping list still asks for L298N", failures)
    if "usb-power-5v" in shop_ids:
        _fail("shopping list asks for USB PSU despite junk-bin battery", failures)

    blocking_driver = [
        r for r in still_missing if str(r.get("module_id") or "") == "l298n"
    ]
    if blocking_driver:
        _fail("still_missing blocks on L298N", failures)

    pkg_path = out_dir / "PROJECT_PACKAGE.json"
    if not pkg_path.is_file():
        _fail("PROJECT_PACKAGE.json missing", failures)

    fw_meta = out_dir / "firmware" / "FIRMWARE_SCAFFOLD.json"
    if not fw_meta.is_file():
        _fail("firmware scaffold missing", failures)
    else:
        fw = json.loads(fw_meta.read_text(encoding="utf-8"))
        pins = dict(fw.get("pins") or {})
        src = str(fw.get("source") or "")
        for key in ("in1", "in2", "in3", "in4"):
            if pins.get(key) is None:
                _fail(f"firmware pins missing {key}", failures)
        if "const int IN3" not in src or "const int IN4" not in src:
            _fail("firmware sketch is not dual-channel", failures)

    # Power-on must stay gated until bench evidence — package should not claim authorized.
    project = dict(result.get("project") or result.get("project_package") or {})
    if project.get("power_on_authorized") is True:
        _fail("power_on_authorized true without bench evidence", failures)

    report = {
        "ok": not failures,
        "intake": str(args.intake),
        "out_dir": str(out_dir),
        "build_id": (result.get("project") or {}).get("build_id") or result.get("build_id"),
        "mcu_override": overrides.get("mcu"),
        "power_topology": package.get("power_topology"),
        "shopping": sorted(shop_ids),
        "failures": failures,
    }
    report_path = out_dir / "ENABOT_ENDGAME_REPORT.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        status = "PASS" if report["ok"] else "FAIL"
        print(f"Vibe Enabot endgame: {status}")
        print(f"report: {report_path}")
        for row in failures:
            print(f"  - {row}")

    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

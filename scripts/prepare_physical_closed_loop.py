#!/usr/bin/env python3
"""Build the flagship physical closed-loop pack (pan-tilt) + human bench runbook."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

os.environ.setdefault("HARDWARE_SPLICER_OFFLINE_LLM", "1")
os.environ.setdefault("HARDWARE_SPLICER_OFFLINE_VISION", "1")
os.environ.setdefault("HARDWARE_SPLICER_OFFLINE_SALVAGE", "1")
os.environ.setdefault("QWEN_DISABLED", "1")
os.environ.setdefault("HARDWARE_SPLICER_SKIP_VISION_LIVE", "1")
os.environ.setdefault("HARDWARE_SPLICER_AUTOROUTE", "0")
os.environ.setdefault("HARDWARE_SPLICER_DRC_FIX_LOOP", "1")

from hardware_splicer.project_intake import load_project_intake, splice_and_build_from_intake  # noqa: E402


def _audit_path(out_dir: Path) -> Dict[str, Any]:
    import importlib.util

    audit_file = ROOT / "scripts" / "audit_mechatronics_confidence.py"
    spec = importlib.util.spec_from_file_location("hs_audit_mechatronics_confidence", audit_file)
    if spec is None or spec.loader is None:
        return {"passed": False, "failures": ["audit module load failed"]}
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.audit_path(out_dir)


def _runbook(*, out_dir: Path, fw: Dict[str, Any], mech: Dict[str, Any], pins: Dict[str, Any]) -> str:
    pan = pins.get("servo_pan", "?")
    tilt = pins.get("servo_tilt", "?")
    scad = ", ".join(str(x) for x in (mech.get("outputs") or [])[:8])
    return f"""# Physical closed loop — pan-tilt

**Claim boundary:** Starter pack only. Not production release. You own wiring and power-on.

**Build folder:** `{out_dir}`

## What you need on the bench

- ESP32 DevKit
- 2× SG90 (or equivalent) servos
- USB 5V supply / power bank (≥1A preferred when both servos move)
- Common breadboard / Dupont wires
- Optional: print the OpenSCAD parts in `mecha_bundle/` ({scad})

## 1. Print (optional but recommended)

1. Open `mecha_bundle/PRINT_PLAN.md` and `MECH_CHECK.md`.
2. Print `pt_base.scad`, `pt_bracket.scad`, `pt_platform.scad` (and enclosure if you want the controller box).
3. Dry-fit servos in the mounts **before** power.

## 2. Wire (must match compiled graph)

| From | To | Purpose |
|------|-----|---------|
| USB 5V V+ | ESP32 VIN | MCU power |
| USB 5V GND | ESP32 GND | common ground |
| USB 5V V+ | both servo VCC | servo power (not 3V3) |
| USB / ESP32 GND | both servo GND | common ground |
| ESP32 **GPIO{pan}** | pan servo SIG | yaw |
| ESP32 **GPIO{tilt}** | tilt servo SIG | pitch |

Also see `BRINGUP_CARD.md` in this folder.

## 3. Flash

1. Sketch: `firmware/{fw.get("filename") or "inspection_motion_fixture.ino"}`
2. Confirm constants: `PAN_PIN = {pan}`, `TILT_PIN = {tilt}`
3. Board: ESP32 Dev Module, upload via USB
4. Open serial at 115200 — you should see pan/tilt pin printf and slow sweeps

## 4. Bench gates (before continuous power)

- [ ] Common ground confirmed with meter
- [ ] USB rail ≈5V at servo VCC under no-load
- [ ] Servos move on serial sweep without brownout
- [ ] No hot spots on ESP32 / wiring after 30s
- [ ] `power_on_authorized` stays false until you close gates in the UI Bench stage with **physical** captures

## 5. Capture evidence (closes the loop)

Fill `PHYSICAL_BENCH_EVIDENCE.json` (template in this folder) with:

- photo of wiring
- serial log snippet
- voltage reading at servo rail
- pass/fail on motion sweep

Then run Bench stage in splice-ui against this `build_dir`, or keep the JSON as the partner proof packet.

## Honesty

- Offline pack ready ≠ café-validated product
- Invites stay paused until this checklist is done with real hardware
"""


def _evidence_template(pins: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "schema_version": "hardware_splicer.physical_bench_evidence.v1",
        "path_id": "pan_tilt",
        "status": "pending_operator",
        "pins_expected": {
            "servo_pan": pins.get("servo_pan"),
            "servo_tilt": pins.get("servo_tilt"),
        },
        "checks": [
            {"id": "common_ground", "status": "open", "note": ""},
            {"id": "servo_rail_5v", "status": "open", "measured_v": None, "note": ""},
            {"id": "serial_sweep_ok", "status": "open", "note": ""},
            {"id": "no_thermal_hotspot", "status": "open", "note": ""},
            {"id": "photo_wiring_uri", "status": "open", "uri": ""},
            {"id": "serial_log_uri", "status": "open", "uri": ""},
        ],
        "operator": "",
        "completed_at": None,
        "claim_boundary": "Physical evidence required — simulated checks do not close this loop.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=ROOT / "examples" / "physical_loop" / "manifest.json",
    )
    parser.add_argument("--out", type=Path, default=Path("/tmp/hs_physical_closed_loop"))
    parser.add_argument("--path", default="pan_tilt")
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    specs = [p for p in manifest.get("paths") or [] if p.get("path_id") == args.path]
    if not specs:
        print(f"path {args.path!r} not in manifest", file=sys.stderr)
        return 2
    spec = specs[0]

    out_dir = args.out.resolve() / str(spec["path_id"])
    out_dir.mkdir(parents=True, exist_ok=True)

    intake = load_project_intake(ROOT / spec["intake"])
    print(f"→ building physical pack {spec['path_id']} …", flush=True)
    result = splice_and_build_from_intake(
        intake,
        out_dir=out_dir,
        export_gerber=False,
        request_id=f"physical_{spec['path_id']}",
    )

    fw_meta = out_dir / "firmware" / "FIRMWARE_SCAFFOLD.json"
    fw = json.loads(fw_meta.read_text(encoding="utf-8")) if fw_meta.is_file() else {}
    pins = {
        k: v
        for k, v in dict(fw.get("pins") or {}).items()
        if type(v) is int  # bool is a subclass of int — exclude flags
    }
    mech = {}
    mech_path = out_dir / "MECHANISM_PACK.json"
    if mech_path.is_file():
        mech = json.loads(mech_path.read_text(encoding="utf-8"))

    runbook = _runbook(out_dir=out_dir, fw=fw, mech=mech, pins=pins)
    (out_dir / "PHYSICAL_BENCH_RUNBOOK.md").write_text(runbook, encoding="utf-8")
    (out_dir / "PHYSICAL_BENCH_EVIDENCE.json").write_text(
        json.dumps(_evidence_template(pins), indent=2), encoding="utf-8"
    )

    confidence = _audit_path(out_dir)
    summary = {
        "schema_version": "hardware_splicer.physical_closed_loop_pack.v1",
        "path_id": spec["path_id"],
        "title": spec.get("title"),
        "out_dir": str(out_dir),
        "compile_ok": bool(result.get("ok")),
        "build_id": result.get("build_id"),
        "firmware_pins": pins,
        "mechanism_kind": mech.get("kind"),
        "mechanism_status": mech.get("status"),
        "confidence_passed": confidence.get("passed"),
        "confidence_failures": confidence.get("failures") or [],
        "runbook": str(out_dir / "PHYSICAL_BENCH_RUNBOOK.md"),
        "evidence_template": str(out_dir / "PHYSICAL_BENCH_EVIDENCE.json"),
        "claim_boundary": "Pack is software-ready for a human bench; physical evidence still open.",
        "next_human_action": "Follow PHYSICAL_BENCH_RUNBOOK.md, then fill PHYSICAL_BENCH_EVIDENCE.json",
    }
    (out_dir / "PHYSICAL_CLOSED_LOOP_PACK.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (args.out.resolve() / "PHYSICAL_CLOSED_LOOP_SUMMARY.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )

    print(json.dumps(summary, indent=2))
    print(f"\nRunbook: {out_dir / 'PHYSICAL_BENCH_RUNBOOK.md'}")
    return 0 if summary["compile_ok"] and summary["confidence_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

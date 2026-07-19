#!/usr/bin/env python3
"""Closed pan-tilt golden: dual-servo FW + pan_tilt mech pack + authority."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

os.environ.setdefault("HARDWARE_SPLICER_OFFLINE_LLM", "1")
os.environ.setdefault("HARDWARE_SPLICER_OFFLINE_VISION", "1")
os.environ.setdefault("HARDWARE_SPLICER_OFFLINE_SALVAGE", "1")
os.environ.setdefault("QWEN_DISABLED", "1")
os.environ.setdefault("HARDWARE_SPLICER_SKIP_VISION_LIVE", "1")
os.environ.setdefault("HARDWARE_SPLICER_AUTOROUTE", "0")
os.environ.setdefault("HARDWARE_SPLICER_DRC_FIX_LOOP", "1")

from verify_mechatronics_paths import _eval_mechatronics  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("/tmp/hs_mechatronics_golden"))
    args = parser.parse_args()

    spec = {
        "path_id": "pan_tilt",
        "title": "Pan-tilt closed golden",
        "intake": "examples/intakes/money_pan_tilt_brief.json",
        "expected_build_ids": ["inspection_motion_fixture"],
        "require_roles": ["mcu"],
        "require_module_ids_any": ["sg90"],
        "min_servos": 2,
        "forbid_shopping": ["esp32-devkit", "sg90"],
        "require_compile": True,
        "require_firmware": True,
        "require_mechanism": True,
        "require_authority": True,
        "mechanism_kinds_any": ["pan_tilt"],
        "require_firmware_tokens": ["PAN_PIN", "TILT_PIN"],
        "min_firmware_pins": 1,
    }

    out_root = args.out.resolve()
    out_root.mkdir(parents=True, exist_ok=True)
    print("→ pan_tilt golden …", flush=True)
    row = _eval_mechatronics(spec, out_root)

    # Extra golden assertions on bundle primitives
    out_dir = Path(str(row["out_dir"]))
    bundle = out_dir / "mecha_bundle"
    failures = list(row.get("failures") or [])
    if bundle.is_dir():
        scads = list(bundle.glob("*.scad")) + list(bundle.glob("**/*.scad"))
        names = " ".join(p.name for p in scads)
        if "pt_" not in names and "pan" not in names.lower() and "tilt" not in names.lower():
            # Accept any pan_tilt-related outputs listed in MECHANISM_PACK
            mech = json.loads((out_dir / "MECHANISM_PACK.json").read_text(encoding="utf-8"))
            outs = " ".join(str(x) for x in (mech.get("outputs") or []))
            if "pan" not in outs.lower() and "tilt" not in outs.lower() and "pt_" not in outs:
                failures.append(f"no pan_tilt SCAD primitives in bundle (have {names or outs})")
    else:
        failures.append("mecha_bundle missing")

    fw = json.loads((out_dir / "firmware" / "FIRMWARE_SCAFFOLD.json").read_text(encoding="utf-8"))
    pins = dict(fw.get("pins") or {})
    if pins.get("servo_pan") is None and "PAN_PIN" not in str(fw.get("source") or ""):
        failures.append("dual-servo pan pin not evidenced")

    row["failures"] = failures
    row["passed"] = not failures
    report = {
        "schema_version": "hardware_splicer.mechatronics_golden.v1",
        "golden": "pan_tilt",
        "passed": row["passed"],
        "result": row,
    }
    report_path = out_root / "MECHATRONICS_GOLDEN_REPORT.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    status = "PASS" if row["passed"] else "FAIL"
    print(f"Mechatronics golden pan_tilt: {status}")
    print(f"report: {report_path}")
    for f in failures:
        print(f"  - {f}")
    return 0 if row["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

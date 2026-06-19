#!/usr/bin/env python3
"""Donor board vision smoke: dry-run always; live Qwen when keyed."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import importlib.util

_gen_spec = importlib.util.spec_from_file_location(
    "generate_donor_test_image",
    ROOT / "scripts" / "generate_donor_test_image.py",
)
_gen_mod = importlib.util.module_from_spec(_gen_spec)
assert _gen_spec.loader is not None
_gen_spec.loader.exec_module(_gen_mod)
write_synthetic_board_png = _gen_mod.write_synthetic_board_png

from hardware_splicer.board_vision_salvage import _analyze_board_image_path
from hardware_splicer.repair_intake import extract_repair_context

DEFAULT_IMAGE = ROOT / "tests" / "data" / "donor_rc_board_sample.png"


def main() -> int:
    parser = argparse.ArgumentParser(description="Donor board vision smoke test")
    parser.add_argument("--image", type=Path, default=DEFAULT_IMAGE)
    parser.add_argument("--live", action="store_true", help="Call live Qwen (needs API key)")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    image_path = args.image
    if not image_path.is_file():
        image_path = write_synthetic_board_png(image_path)

    repair = extract_repair_context(
        {
            "repair_intake": {
                "device_hint": "RC toy dual H-bridge motor board",
                "symptoms": ["motors do not spin", "board smells burnt near driver"],
                "when_it_fails": "immediately on battery connect",
            }
        }
    )

    live = bool(args.live or os.getenv("HARDWARE_SPLICER_RUN_VISION_LIVE", "").strip().lower() in {"1", "true", "yes", "on"})
    result = _analyze_board_image_path(
        image_path,
        goal="salvage motor driver for robot drive base",
        live=live,
        device_hint=repair.get("device_hint") or "",
        symptoms=repair.get("symptoms") or [],
    )

    summary = {
        "image": str(image_path),
        "live": live,
        "mode": result.get("mode") or ("analyzed" if result.get("board_evidence") else "dry_run"),
        "ok": bool(result.get("board_evidence")) if live else result.get("mode") in {"dry_run", "analyzed"},
        "image_sha256": (result.get("preflight") or {}).get("image_sha256"),
        "component_count": len((result.get("board_evidence") or {}).get("components") or []),
        "symptoms_passed": repair.get("symptoms"),
    }

    if args.json:
        print(json.dumps({**summary, "result": result}, indent=2))
    else:
        print(f"Donor vision smoke: mode={summary['mode']} live={live} image={image_path.name}")
        if live and summary["component_count"]:
            print(f"  board_evidence components: {summary['component_count']}")
        elif not live:
            print("  dry-run OK (set --live or HARDWARE_SPLICER_RUN_VISION_LIVE=1 for Qwen)")

    if live and not os.getenv("QWEN_API_KEY") and not os.getenv("DASHSCOPE_API_KEY"):
        print("WARN: live requested but no QWEN_API_KEY / DASHSCOPE_API_KEY", file=sys.stderr)
        return 2
    return 0 if summary["ok"] or (not live and summary["mode"] == "dry_run") else 1


if __name__ == "__main__":
    raise SystemExit(main())

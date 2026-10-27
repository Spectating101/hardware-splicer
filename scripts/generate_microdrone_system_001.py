#!/usr/bin/env python3
"""Build offline and inspectable HS Crazyflie system design proposal."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from hardware_splicer.system_example_microdrone import generate_package


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--design", type=Path, default=ROOT / "examples/system_examples/microdrone_sensor_deck_001.json")
    parser.add_argument("--guidance", type=Path, default=ROOT / "examples/robotics_guidance/crazyflie_custom_sensor_deck.json")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.design.stat().st_size > 64 * 1024 or args.guidance.stat().st_size > 64 * 1024:
        parser.error("Source design or guidance exceeds 64 KiB")
    design, scenario = json.loads(args.design.read_text()), json.loads(args.guidance.read_text())
    receipt = generate_package(design, scenario, args.output)
    print(json.dumps(receipt, indent=2, sort_keys=True))
    print("Review-only drone architecture created; no physical actions, simulator or EDA were executed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

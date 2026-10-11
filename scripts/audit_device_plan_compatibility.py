"""Compare existing OLED wiring checks with a saved repository revision.

Run with PYTHONPATH=src. The revision's planner and library are loaded in memory;
neither the worktree nor the original files are changed.
"""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import subprocess
import sys
import types

ROOT = Path(__file__).resolve().parents[1]
# The sibling scripts/hardware_splicer.py otherwise shadows the package when
# this file is executed directly, even with PYTHONPATH=src.
sys.path.insert(0, str(ROOT / "src"))

from hardware_splicer import device_plan


def saved_file(revision: str, path: str) -> str:
    return subprocess.check_output(["git", "show", f"{revision}:{path}"], cwd=ROOT, text=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", default="bfeb992b")
    args = parser.parse_args()
    revision = subprocess.check_output(["git", "rev-parse", "--verify", f"{args.baseline}^{{commit}}"], cwd=ROOT, text=True).strip()
    previous = types.ModuleType("hardware_splicer._previous_device_plan")
    previous.__file__ = str(ROOT / "src/hardware_splicer/device_plan.py")
    previous.__package__ = "hardware_splicer"
    exec(compile(saved_file(revision, "src/hardware_splicer/device_plan.py"), previous.__file__, "exec"), previous.__dict__)
    library = json.loads(saved_file(revision, "src/hardware_splicer/data/device_modules.json"))
    previous._library = lambda: copy.deepcopy(library)
    example = previous.example_specs()["esp32_oled_usb"]
    modules = {module["id"]: module for module in library["modules"]}
    mismatches = []
    cases = 0
    for mcu_pin in modules["esp32-devkitc-v4"]["pins"]:
        for oled_pin in modules["ssd1306-096-i2c"]["pins"]:
            for reverse in (False, True):
                spec = copy.deepcopy(example)
                ends = [f"mcu.{mcu_pin['id']}", f"display.{oled_pin['id']}"]
                if reverse:
                    ends.reverse()
                spec["connections"] = [{"from": ends[0], "to": ends[1]}]
                before = previous.build_device_plan(spec)
                after = device_plan.build_device_plan(spec)
                cases += 1
                findings = lambda plan: [row for row in plan["findings"] if row["severity"] in {"error", "warning"}]
                if findings(before) != findings(after):
                    mismatches.append({"from": ends[0], "to": ends[1], "before": findings(before), "after": findings(after)})
    before_default = previous.build_device_plan(example)
    after_default = device_plan.build_device_plan(example)
    report = {
        "baseline": revision,
        "cases": cases,
        "mismatches": mismatches,
        "default_spec_unchanged": example == device_plan.example_specs()["esp32_oled_usb"],
        "authority_unchanged": previous.AUTHORITY_STATEMENT == device_plan.AUTHORITY_STATEMENT,
        "default_plan_identical": before_default == after_default,
    }
    report["pass"] = not mismatches and report["default_spec_unchanged"] and report["authority_unchanged"]
    print(json.dumps(report, indent=2))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Source and requirement inputs shared by the Fielddeck 5 native stages."""
import importlib.util
import math
from pathlib import Path
import sys

from build import read, require

ROOT = Path(__file__).resolve().parent
PACKAGE = ROOT.parents[2]
BASELINE = ROOT.parent / "digital_v1"
REVISION = PACKAGE / "revision"
CASE_ID = "fielddeck-5"
REQUIREMENTS = {
    "minimum_work_runtime_h": (2.5, .1, 24),
    "minimum_supply_margin_a": (.3, 0, 2),
    "pi_work_current_a": (1., .4, 2.5),
    "keyboard_current_a": (.1, .02, .5),
}


def requirements():
    values = read(PACKAGE / "requirements.json")
    require(set(values) == set(REQUIREMENTS), "Unexpected Fielddeck 5 requirement fields.")
    for name, (_, low, high) in REQUIREMENTS.items():
        value = values[name]
        require(type(value) in (int, float) and low <= value <= high and math.isfinite(value),
                f"Invalid Fielddeck 5 requirement: {name}")
    return values


def evaluator():
    # Use the exact retained evaluator even when the runtime has a different
    # installed version of Hardware Splicer.
    path = PACKAGE / "src/hardware_splicer/part_substitution.py"
    spec = importlib.util.spec_from_file_location("retained_substitution_evaluator", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.evaluate_substitution


def engineering_result(power, selected):
    cases = {row["scenario"]: row["variant_5inch"] for row in power["scenarios"]}
    work = cases["work_published_panel_power"]
    stress = cases["stress_design_allocation"]
    sensitivity = cases["high_keyboard_demand"]
    normal_margin = min(work["source_margin_a"], stress["source_margin_a"])
    minimums = [
        ("work_runtime", work["runtime_h"][0], selected["minimum_work_runtime_h"], "h"),
        ("ordinary_source_margin", normal_margin, selected["minimum_supply_margin_a"], "A"),
        ("high_keyboard_supply_limit", sensitivity["source_margin_a"], 0, "A"),
    ]
    checks = [{"id": name, "actual": actual, "limit": limit, "unit": unit, "passed": actual >= limit}
              for name, actual, limit, unit in minimums]
    return {"case_id": CASE_ID, "requirements": selected, "constraints": checks,
            "requirements_met": all(item["passed"] for item in checks),
            "metrics": {"work_system_power_w": work["system_w"], "work_runtime_lower_h": work["runtime_h"][0],
                        "work_runtime_upper_h": work["runtime_h"][1], "ordinary_source_margin_a": normal_margin,
                        "high_keyboard_source_margin_a": sensitivity["source_margin_a"]},
            "power_scope": "Steady-state scenarios with declared loads and usable battery energy.",
            "physical_validation_performed": False}

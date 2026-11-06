#!/usr/bin/env python3
"""Write the Build 1 test 1 report: the chosen parts, what is sourced, typical, conflicting or unconfirmed, HS's sizing
and the quote check. The report describes sources, not a robot: nothing in it has been bought or measured.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

_spec = importlib.util.spec_from_file_location("mapping_robot_sizing", HERE / "sizing.py")
sizing = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sizing)

from hardware_splicer.robot_parts import verify_quotes  # noqa: E402

CAPTURES = ROOT / ".cache" / "hardware-splicer" / "robot_part_sources"


def _value(fact: dict) -> str:
    if "alternatives" in fact:
        return " or ".join(f"{a['value']}" for a in fact["alternatives"]) + f" {fact['unit']} (conflicting)"
    value = fact["value"]
    if isinstance(value, list):
        value = " to ".join(str(v) for v in value) if len(value) == 2 else " x ".join(str(v) for v in value)
    return f"{value} {fact['unit']}" if fact["unit"] != "text" else str(value)


def render_report(parts: list[dict], sizing_result: dict, quote_check: dict) -> str:
    out = ["# Mapping robot v0, Build 1 test 1: parts sourced and understood", "",
           "**Status: sourced, not measured.** Every part below is a real, current listing, and each fact names its source. "
           "Nothing has been bought, contacted or measured; a number here is what a document says, not what a part does.", ""]

    out += ["## Chosen parts", "", "| Kind | Part | Listing | Variant | Facts: published / typical / conflicting / unconfirmed |",
            "|---|---|---|---|---|"]
    for p in parts:
        facts = p.get("facts", {})
        published = sum(1 for f in facts.values() if f.get("basis") == "published" and "alternatives" not in f)
        typical = sum(1 for f in facts.values() if f.get("basis") == "typical")
        conflicting = sum(1 for f in facts.values() if "alternatives" in f)
        listing = p.get("listing", {})
        out.append(f"| {p['kind']} | {p.get('name', p['id'])} | [{listing.get('url')}]({listing.get('url')}) "
                   f"NT${listing.get('price_twd')} ({listing.get('marketplace')}) | {listing.get('variant')} | "
                   f"{published} / {typical} / {conflicting} / {len(p.get('unconfirmed', []))} |")

    out += ["", "## Open questions: measure these on the bench", ""]
    for p in parts:
        rows = [f"- **{name}** {_value(f)}: {f.get('note', '')}".rstrip(": ")
                for name, f in p.get("facts", {}).items() if "alternatives" in f]
        rows += [f"- **{name}** {_value(f)} (typical): {f.get('note', '')}"
                 for name, f in p.get("facts", {}).items() if f.get("basis") == "typical"]
        rows += [f"- **{u['fact']}** unconfirmed: {u['reason']}" for u in p.get("unconfirmed", [])]
        if rows:
            out += [f"{p.get('name', p['id'])}:", *rows, ""]

    s = sizing_result
    verdict = ("meets the targets" if s["passed"] else "does not meet the targets: " + "; ".join(s["reasons"]))
    out += ["## Sizing through HS robotics simulation", "",
            f"The design {verdict}.", "",
            "| Quantity | Value | Target |", "|---|---|---|",
            f"| Runtime, continuous mapping | {s['runtime_min']} min | ≥ {s['targets']['runtime_min']} min |",
            f"| Speed margin at {s['targets']['speed_mps']} m/s | {s['speed_margin']} | ≥ {s['targets']['min_speed_margin']} |",
            f"| Wheel speed needed | {s['required_wheel_rpm']} rpm | motor gives {round(s['effective']['motor_free_speed_rpm'], 1)} rpm at pack voltage |",
            f"| Force margin (acceleration and rolling only) | {s['force_margin']} | ≥ 1 |",
            f"| Pack peak current (motors at their limit, electronics at peak, minimum voltage) | "
            f"{round(s['pack_peak_current_a'], 2)} A | ≤ {s['pack_max_discharge_a']} A |",
            f"| 5 V converter peak | {round(s['converter_peak_current_a'], 2)} A | ≤ {s['converter_rating_a']} A |",
            f"| Door threshold torque per motor | {round(s['step_torque_available_nm'], 3)} N·m available | "
            f"≥ {round(s['step_torque_required_nm'], 3)} N·m |",
            f"| Robot mass | {round(s['mass_kg'], 3)} kg | |",
            f"| Average power | {s['average_power_w']} W | |", ""]
    if s.get("warnings"):
        out += ["Warnings:", "", *[f"- {w}" for w in s["warnings"]], ""]
    out += ["Assumptions (not part facts):", ""]
    out += [f"- `{name}` = {a['value']} ({a['basis']}): {a['note']}" for name, a in s["assumptions"].items()]
    out += ["", "## Handed to later stages", "",
            "- The microcontroller is not a bought module here: it is soldered on the HS board as a module from the "
            "LCSC/JLCPCB catalogue, chosen in the board plan; its power is the `mcu_power_w` assumption above.",
            *[f"- `{name}` = {a['value']}: {a['note']}" for name, a in s["assumptions"].items() if a.get("basis") == "design"],
            "- Dimensions given only as drawings (LiDAR, Raspberry Pi) are read from those drawings by the chassis plan."]

    q = quote_check
    out += ["", "## Quote check", "",
            f"{q['quotes_checked']} quotes checked against captured copies of their sources"
            f"{' on ' + q['checked_on'] if q.get('checked_on') else ''}: "
            + ("all found." if q["pass"] else f"{len(q['failed'])} not found."), ""]
    out += [f"- {f['part']} `{f['claim']}` ({f['source']}): {f['reason']}" for f in q.get("failed", [])]
    out += ["", "Gaps in HS met on the way are in `GAP_LOG.md`; why each part was chosen is in `selection/`.", ""]
    return "\n".join(out)


def main() -> int:
    selection = json.loads((HERE / "selection.json").read_text(encoding="utf-8"))
    chosen = sizing.load_selection(HERE / "selection.json")
    roles = {role: part for role, part in chosen.items() if role in sizing.ROLES}
    assumptions = json.loads((HERE / "assumptions.json").read_text(encoding="utf-8"))
    result = sizing.run_sizing(roles, assumptions)
    quotes = verify_quotes(list({p["id"]: p for p in chosen.values()}.values()), CAPTURES)
    parts = [chosen[role] for role in selection]
    (HERE / "BUILD1_TEST1.md").write_text(render_report(parts, result, quotes), encoding="utf-8")
    print(f"sizing passed={result['passed']} quotes pass={quotes['pass']} ({quotes['quotes_checked']})")
    return 0 if result["passed"] and quotes["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

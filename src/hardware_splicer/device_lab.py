"""A lab pack: one folder a person can follow from parts on the desk to a device that runs, with honest status.

It gathers what the device planner already produces (plan, engineering review, case files, firmware with host tests) into
LAB.md and a status ladder in lab.json. HS can tick only the first rungs (planned, and host-tested when the generated
firmware's host tests ran). Built, flashed, observed and measured belong to the person at the bench: ``observe`` compares
pasted serial output with the plan, and ``record`` stores measurements beside HS's estimates. Neither proves anything
physical, and nothing here changes any authority flag.

    PYTHONPATH=src python -m hardware_splicer.device_lab build spec.json out/lab [--host-test]
    PYTHONPATH=src python -m hardware_splicer.device_lab observe out/lab serial.txt
    PYTHONPATH=src python -m hardware_splicer.device_lab record out/lab --usb-current-ma 140 --case-fit loose --minutes 45
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import sys
import zipfile
from pathlib import Path
from typing import Any

from .device_application import build_device_application
from .device_case import build_device_case
from .device_engineering import build_engineering_review
from .device_observations import check_device_observations
from .device_plan import DevicePlanError, build_device_plan, module_library

SCHEMA = "hardware_splicer.device_lab.v1"
BOUNDARY = ("A lab pack gathers HS's proposals for one device. HS ticks only 'planned' and 'host-tested'. Every other rung is "
            "what a person did and wrote down; HS records it as operator-supplied and does not verify it.")
RUNGS = (
    ("planned", "HS", "The plan has no wiring errors or warnings."),
    ("host_tested", "HS", "The generated firmware's host tests passed off-hardware. Not silicon, not real sensors."),
    ("built", "you", "Parts wired as the table says, checked for shorts before power."),
    ("flashed", "you", "The firmware uploaded and the serial monitor shows a BOOT line."),
    ("observed", "you", "Your pasted serial output agrees with the plan's declared addresses."),
    ("measured", "you", "USB current, case fit and time spent recorded."),
)


class DeviceLabError(ValueError):
    pass


def _json(value: Any) -> str:
    return json.dumps(value, indent=2, ensure_ascii=False) + "\n"


def _unzip(archive: bytes, into: Path) -> list[str]:
    names = []
    with zipfile.ZipFile(io.BytesIO(archive)) as zf:
        for info in zf.infolist():
            target = (into / info.filename).resolve()
            if not str(target).startswith(str(into.resolve()) + os.sep) or info.is_dir():
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(zf.read(info))
            names.append(info.filename)
    return names


def _sustained_ma(review: dict[str, Any]) -> float | None:
    for domain in review["domains"]:
        for check in domain["checks"]:
            if check["id"] == "supply_current":
                return check["quantities"].get("sourced_sustained_ma_sum")
    return None


def _lab_md(spec: dict[str, Any], plan: dict[str, Any], review: dict[str, Any], firmware: dict[str, Any], case: dict[str, Any]) -> str:
    name = plan.get("name") or spec.get("name", "Device")
    lines = [f"# {name}", "", BOUNDARY, "", "## Status", "", "| Rung | Who | Done |", "|---|---|---|"]
    for rung, who, _ in RUNGS:
        done = rung == "planned" or (rung == "host_tested" and firmware.get("host_tested"))
        lines.append(f"| {rung.replace('_', ' ')} | {who} | {'yes' if done else 'not yet'} |")
    lines += ["", "## What you need", ""]
    lines += [f"- {row['quantity']} x {row['item']}" + (f" ({row['note']})" if row.get("note") else "") for row in plan["shopping"]]
    lines += ["- To measure: a USB inline power meter (optional, for the current check below)", "", "## Wire it", "",
              "Unplug USB before wiring. Connect by the printed pin names, not by position in a picture.", "",
              "| From | To |", "|---|---|"]
    lines += [f"| {w['from']['module']}: {w['from']['label']} | {w['to']['module']}: {w['to']['label']} |" for w in plan["wires"]]
    notes = [f for f in plan["findings"] if f["severity"] == "info" and f["rule"] in {"oled_supply_note", "module_supply_note", "i2c_pullups_note", "power_bank"}]
    if notes:
        lines += ["", "Before power, read these:", ""] + [f"- {f['message']}" for f in notes]
    lines += ["", "Check for a short between 3V3 and GND with a multimeter before plugging in.", "", "## Flash it", ""]
    if firmware.get("folder"):
        lines += ["The firmware is a PlatformIO project in `firmware/`. With PlatformIO installed:", "", "```",
                  "cd firmware", "pio run -t upload -t monitor", "```", ""]
        lines += ["## What you should see", "", "On the serial monitor at 115200 baud, a boot line and then readings, for example:", "", "```",
                  f"BOOT sensor={firmware['sensor_addresses'][0]} display={firmware['display_addresses'][0] if firmware.get('display_addresses') else 'NONE'}",
                  "T=... STATE=OK ...", "```", "",
                  "The sensor and display addresses can be any of: " + ", ".join(firmware["sensor_addresses"] + firmware.get("display_addresses", [])) + ".",
                  "If you see `DISPLAY MISSING` or a FAULT state, unplug and check the wiring table.", "",
                  "Save what the monitor printed to a file and let HS compare it with the plan:", "", "```",
                  "python -m hardware_splicer.device_lab observe <this folder> serial.txt", "```"]
    else:
        lines += [f"No application firmware for this combination: {firmware.get('reason')}. The I2C diagnostic export (POST /v1/devices/firmware) still works."]
    sustained = _sustained_ma(review)
    lines += ["", "## Measure", "",
              "- **USB current** with the inline meter while it shows readings. "
              + (f"HS's sum of the published sustained currents is {sustained:.0f} mA; the USB bridge, regulator and unsourced parts add to that."
                 if sustained else "No module publishes a sustained current, so HS has no estimate to compare."),
              "- **Case fit**: print `case/case_base.stl` and `case/case_lid.stl`, then note whether the boards seat, the USB plug reaches "
              "and the window lines up with the screen (good, tight, loose, or does not fit).",
              "- **Time**: minutes from parts on the desk to readings on the screen.", "", "Record them:", "", "```",
              "python -m hardware_splicer.device_lab record <this folder> --usb-current-ma 140 --case-fit good --minutes 45", "```", "",
              "## Case", "", f"Outer size {case['outer_mm']['x']} x {case['outer_mm']['z']} x {case['outer_mm']['y']} mm. "
              "Files in `case/`; the case has not been printed or test-fitted.", "",
              "## Engineering review", "", "From `engineering.json`. No check says the design works.", ""]
    for domain in review["domains"]:
        for check in domain["checks"]:
            lines.append(f"- **{check['title']}** ({check['status'].replace('_', ' ')}): {check['summary']}")
    lines += ["", "Not assessed at all:", ""] + [f"- {row['domain']}: {row['why']}" for row in review["not_assessed"]]
    return "\n".join(lines) + "\n"


def build_lab(spec: Any, out: Path, *, host_test: bool = False) -> dict[str, Any]:
    plan = build_device_plan(spec)
    blockers = sorted({f["rule"] for f in plan["findings"] if f["severity"] in {"error", "warning"}})
    if blockers:
        raise DeviceLabError("Resolve the plan's errors and warnings before making a lab: " + ", ".join(blockers))
    review = build_engineering_review(spec)
    out.mkdir(parents=True, exist_ok=True)
    case_meta, case_zip = build_device_case(spec)
    _unzip(case_zip, out / "case")
    firmware: dict[str, Any] = {}
    try:
        app_meta, app_zip = build_device_application(spec)
    except DevicePlanError as exc:
        firmware = {"folder": None, "reason": str(exc)}
    else:
        _unzip(app_zip, out / "firmware")
        # The export refuses a descriptor whose addresses disagree with the library, so the library's addresses are the firmware's.
        lib = {m["id"]: m for m in module_library()["modules"]}
        display_mod = next((m["module"] for m in plan["modules"] if m["kind"] == "display"), None)
        sensor_mod = next(m["module"] for m in plan["modules"] if m["kind"] == "i2c_breakout")
        firmware = {"folder": "firmware", "status": app_meta.get("status"), "sensor_addresses": lib[sensor_mod]["i2c"]["addresses"],
                    "display_addresses": lib[display_mod]["i2c"]["addresses"] if display_mod else []}
        if host_test:
            from .device_application_runtime import run_device_application

            run = run_device_application(spec)
            (out / "host_run.json").write_text(_json(run))
            firmware["host_tested"] = run.get("host", {}).get("status") == "PASSED"
    (out / "spec.json").write_text(_json(spec))
    (out / "plan.json").write_text(_json(plan))
    (out / "engineering.json").write_text(_json(review))
    (out / "LAB.md").write_text(_lab_md(spec, plan, review, firmware, plan["case"]))
    status = {rung: {"done": rung == "planned" or (rung == "host_tested" and bool(firmware.get("host_tested"))), "by": who, "means": means}
              for rung, who, means in RUNGS}
    lab = {"schema_version": SCHEMA, "claim_boundary": BOUNDARY, "physical_correctness": "UNPROVEN", "firmware_authorized": False,
           "power_on_authorized": False, "spec_sha256": hashlib.sha256(_json(spec).encode()).hexdigest(), "status": status,
           "firmware": firmware, "case": {"outer_mm": plan["case"]["outer_mm"], "files": sorted(case_meta.get("files", {}))},
           "estimates": {"sourced_sustained_ma": _sustained_ma(review)}, "records": []}
    (out / "lab.json").write_text(_json(lab))
    return lab


def what_can_i_build(have: list[str]) -> dict[str, Any]:
    """From the parts on your bench: every controller + display + sensor combination that plans with no errors or warnings,
    split into ready to build, one part away, and further. A combination counts once whatever order the parts were named in."""

    from .device_draft import draft_device_spec

    lib = {m["id"]: m for m in module_library()["modules"]}
    unknown = sorted(set(have) - set(lib))
    if unknown:
        raise DeviceLabError(f"not in the module library: {', '.join(unknown)}")
    controllers = [i for i, m in lib.items() if m["kind"] == "mcu_board"]
    displays = [None] + [i for i, m in lib.items() if m["kind"] == "display"]
    sensors = [None] + [i for i, m in lib.items() if m["kind"] == "i2c_breakout"]
    owned = set(have)
    ready, one_away, further = [], [], 0
    for controller in controllers:
        for display in displays:
            for sensor in sensors:
                parts = [p for p in (display, sensor) if p]
                if not parts:
                    continue
                try:
                    plan = build_device_plan(draft_device_spec({"controller": controller, "parts": parts})["spec"])
                except DevicePlanError:
                    continue
                if plan["counts"]["errors"] or plan["counts"]["warnings"]:
                    continue
                missing = [p for p in (controller, *parts) if p not in owned]
                row = {"controller": controller, "parts": parts, "missing": missing}
                if not missing:
                    ready.append(row)
                elif len(missing) == 1:
                    one_away.append(row)
                else:
                    further += 1
    adds: dict[str, int] = {}
    for row in one_away:
        adds[row["missing"][0]] = adds.get(row["missing"][0], 0) + 1
    return {"have": sorted(owned), "ready": ready, "one_part_away": one_away, "needs_two_or_more": further,
            "best_single_addition": sorted(adds.items(), key=lambda kv: (-kv[1], kv[0]))[:5],
            "note": "Planned without errors or warnings; nothing here has been built."}


def _load(lab_dir: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        return json.loads((lab_dir / "lab.json").read_text()), json.loads((lab_dir / "spec.json").read_text())
    except (OSError, ValueError) as exc:
        raise DeviceLabError(f"{lab_dir} is not a lab folder: {exc}") from exc


def observe(lab_dir: Path, transcript: str) -> dict[str, Any]:
    lab, spec = _load(lab_dir)
    result = check_device_observations(spec, transcript)
    (lab_dir / "observations.json").write_text(_json(result))
    consistent = result["summary"].get("consistent_with_declared_addresses") is True
    if isinstance(result.get("application"), dict) and result["application"].get("boot"):
        # A boot line means the board was wired and flashed; both stay operator-supplied claims.
        for rung in ("built", "flashed"):
            lab["status"][rung].update(done=True, provenance="operator_supplied_text")
    lab["status"]["observed"].update(done=consistent, provenance="operator_supplied_text",
                                     detail={m["id"]: m["status"] for m in result["modules"]})
    (lab_dir / "lab.json").write_text(_json(lab))
    return lab


def record(lab_dir: Path, *, usb_current_ma: float | None, case_fit: str | None, minutes: float | None, note: str = "") -> dict[str, Any]:
    lab, _spec = _load(lab_dir)
    if case_fit is not None and case_fit not in {"good", "tight", "loose", "does_not_fit"}:
        raise DeviceLabError("case fit must be good, tight, loose or does_not_fit")
    for label, value, high in (("usb current", usb_current_ma, 5000), ("minutes", minutes, 10000)):
        if value is not None and not 0 < value <= high:
            raise DeviceLabError(f"{label} must be above 0 and at most {high}")
    entry: dict[str, Any] = {"provenance": "operator_supplied", "usb_current_ma": usb_current_ma, "case_fit": case_fit, "minutes": minutes, "note": note[:500]}
    estimate = lab["estimates"].get("sourced_sustained_ma")
    if usb_current_ma is not None and estimate:
        entry["current_vs_sourced_sum"] = round(usb_current_ma / estimate, 2)
    lab["records"].append(entry)
    if usb_current_ma is not None and case_fit is not None and minutes is not None:
        lab["status"]["built"].update(done=True, provenance="operator_supplied")
        lab["status"]["measured"].update(done=True, provenance="operator_supplied")
    (lab_dir / "lab.json").write_text(_json(lab))
    return lab


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="command", required=True)
    b = sub.add_parser("build")
    b.add_argument("spec", type=Path)
    b.add_argument("out", type=Path)
    b.add_argument("--host-test", action="store_true", help="run the firmware's host tests (needs HS_DEVICE_RUNTIME_ENABLED=1 and a C++ compiler)")
    o = sub.add_parser("observe")
    o.add_argument("lab", type=Path)
    o.add_argument("serial", type=Path)
    r = sub.add_parser("record")
    r.add_argument("lab", type=Path)
    r.add_argument("--usb-current-ma", type=float)
    r.add_argument("--case-fit")
    r.add_argument("--minutes", type=float)
    r.add_argument("--note", default="")
    w = sub.add_parser("bench", help="what you can build from the parts you have")
    w.add_argument("have", nargs="+", help="module library ids")
    args = ap.parse_args(argv)
    if args.command == "bench":
        try:
            print(json.dumps(what_can_i_build(args.have), indent=2))
        except DeviceLabError as exc:
            print(json.dumps({"error": str(exc)}), file=sys.stderr)
            return 2
        return 0
    try:
        if args.command == "build":
            lab = build_lab(json.loads(args.spec.read_text(encoding="utf-8")), args.out, host_test=args.host_test)
        elif args.command == "observe":
            lab = observe(args.lab, args.serial.read_text(encoding="utf-8", errors="replace"))
        else:
            lab = record(args.lab, usb_current_ma=args.usb_current_ma, case_fit=args.case_fit, minutes=args.minutes, note=args.note)
    except (DeviceLabError, DevicePlanError, OSError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 2
    print(json.dumps({rung: row["done"] for rung, row in lab["status"].items()}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

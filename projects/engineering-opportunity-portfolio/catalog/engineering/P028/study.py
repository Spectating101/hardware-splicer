"""Build switch coupons, inspect the exported cuts, and exercise the trace reader."""

import argparse
import csv
import json
import math
import random
from collections import Counter
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from xml.etree import ElementTree as ET

from geometry import SWITCHES, cutfile, generate
from replay import CYCLE_MS, Sample, adjudicate, replay


HERE = Path(__file__).resolve().parent
NS = {"s": "http://www.w3.org/2000/svg"}


def cuts(svg):
    doc = ET.fromstring(svg)
    assert (doc.get("width"), doc.get("height"), doc.get("viewBox")) == ("30mm", "24mm", "0 0 30 24")
    outline = doc.find(".//s:rect", NS)
    assert [float(outline.get(name)) for name in ("x", "y", "width", "height")] == [0, 0, 30, 24]
    slot = doc.find(".//s:rect[@id='datum-slot']", NS)
    assert [float(slot.get(n)) for n in ("x", "y", "width", "height", "rx", "ry")] == [
        23.65, 3.975, 2.7, 2.05, 1.025, 1.025]
    return {c.get("id"): tuple(float(c.get(v)) for v in ("cx", "cy", "r"))
            for c in doc.findall(".//s:circle", NS)}


def inspect(small, carrier, keeper, per_axis_error=0.18):
    """Verify exported top views against an independent transcription of the drawing."""
    mount = {"mount-1": (4, 12, 1.6), "mount-2": (26, 12, 1.6), "datum": (5, 5, 1.025)}
    xy = [(11.75, 9.75), (18.25, 9.75), (11.75, 14.25), (18.25, 14.25)] if small else [
        (8.75, 9.5), (21.25, 9.5), (8.75, 14.5), (21.25, 14.5)]
    terminals = ("terminal-top-left", "terminal-top-right", "terminal-bottom-left", "terminal-bottom-right")
    expected = {**mount, **{pin: (*point, 0.5 if small else 0.6) for pin, point in zip(terminals, xy)}}
    if not small:
        expected.update({"boss-1": (15, 7.5, 0.9), "boss-2": (15, 16.5, 0.9)})
    assert carrier == expected, "Carrier drawing differs from independent drill map"
    assert set(keeper) == {*mount, "button"} and all(keeper[n] == mount[n] for n in mount)
    x, y, radius = keeper["button"]
    assert (x, y) == (15, 12)
    body, envelope = (6, 3.5) if small else (12, 7.1)
    # Body tolerance ±0.2 mm. Use ±0.4 mm for the un-toleranced round envelope.
    # Trial allowances: aperture diameter ±0.10 mm and registration as specified.
    # Use the radial bound, not a single-axis bound, for passage of a round moving part.
    radial_offset = math.hypot(per_axis_error, per_axis_error)
    movement_clearance = radius - 0.05 - (envelope + 0.4) / 2 - radial_offset
    retaining_land = (body - 0.2) / 2 - (radius + 0.05) - per_axis_error
    washer_gap = 11 - 3.5 - (body + 0.2) / 2 - per_axis_error
    webs = []
    for holes in [carrier, keeper]:
        circles = list(holes.values())
        for i, (cx, cy, r) in enumerate(circles):
            webs.append(min(cx, 30-cx, cy, 24-cy) - r)
            slot_center_x = min(25.325, max(24.675, cx))
            webs.append(math.hypot(cx-slot_center_x, cy-5) - r - 1.025)
            for x2, y2, r2 in circles[:i]:
                webs.append(math.hypot(cx-x2, cy-y2) - r-r2)
    return {"terminal_holes": 4, "locating_boss_holes": 0 if small else 2,
            "button_aperture_mm": round(2*radius, 2),
            "worst_radial_gap_mm": round(movement_clearance, 3),
            "worst_retaining_land_mm": round(retaining_land, 3),
            "washer_to_body_gap_mm": round(washer_gap, 3), "minimum_nominal_web_mm": round(min(webs), 3),
            "passes_envelope": movement_clearance >= 0.15 and retaining_land >= 0.2
            and washer_gap > 0 and min(webs) >= 1.5}


def synthetic(seed, kind):
    """Construct raw samples independently of the adjudicator's window logic."""
    rng = random.Random(seed)
    close_at = 40 + rng.randint(8, 70)
    open_at = 160 + rng.randint(8, 70)
    record = []
    for tick in range(280):
        command = "home" if tick < 40 else "press" if tick < 160 else "release"
        closed = close_at <= tick < open_at
        if 0 <= tick-close_at < 5 or 0 <= tick-open_at < 5:
            closed = bool(rng.getrandbits(1))
        if kind == "stuck-open":
            closed = False
        elif kind == "welded":
            closed = True
        elif kind == "latches" and tick >= open_at:
            closed = True
        elif kind == "intermittent" and 140 <= tick < 150:
            closed = False
        elif kind == "late-press" and tick < 155:
            closed = False
        elif kind == "three-ms-spike" and 140 <= tick < 143:
            closed = False
        record.append(Sample(tick, "a", command, closed))
    if kind == "gap":
        del record[rng.randrange(280)]
    elif kind == "truncated":
        record.pop()
    elif kind == "duplicate-in-place":
        record[141] = record[140]
    elif kind == "misordered":
        record[140], record[141] = record[141], record[140]
    elif kind == "reset" or kind == "reset-with-contact-fault":
        at = rng.randrange(1, 280) if kind == "reset" else 265
        record = [replace(s, boot="b" if s.tick >= at else "a",
                          closed=False if kind == "reset-with-contact-fault" else s.closed)
                  for s in record]
    elif kind == "lost-command":
        record[80] = replace(record[80], command="home")
    return record


CASES = {"bouncing": "pass", "stuck-open": "missed_close", "welded": "closed_at_home",
         "latches": "missed_open", "intermittent": "missed_close", "late-press": "missed_close",
         "three-ms-spike": "pass", "gap": "inconclusive_length", "truncated": "inconclusive_length",
         "duplicate-in-place": "inconclusive_sequence", "misordered": "inconclusive_sequence",
         "reset": "inconclusive_reset", "reset-with-contact-fault": "inconclusive_reset",
         "lost-command": "inconclusive_command"}


def exercise(folder):
    # Test the normal CSV ingestion entry point with entirely absent, trailing and restarted cycles.
    trace = folder / "simulated-trace.csv"
    with trace.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["cycle", "tick_ms", "boot", "command", "closed"])
        for cycle, kind in [(1, "bouncing"), (2, "reset"), (4, "stuck-open"), (5, "bouncing")]:
            for s in synthetic(318, kind):
                writer.writerow([cycle, s.tick, s.boot if cycle < 4 else "b", s.command, int(s.closed)])
    expected = ["pass", "inconclusive_reset", "inconclusive_length", "missed_close", "pass", "inconclusive_length"]
    assert list(replay(trace, 6)) == list(enumerate(expected, 1))
    counts = Counter()
    for seed in range(32):
        for kind, expected_outcome in CASES.items():
            actual = adjudicate(synthetic(seed, kind), "a")
            assert actual == expected_outcome, (seed, kind, expected_outcome, actual)
            counts[actual] += 1
    return {"seeds_per_case": 32, "case_expectations": CASES, "classifications": dict(sorted(counts.items())),
            "commanded_cycles_per_trace": 1, "duration_ms_per_cycle": CYCLE_MS,
            "independent_replay_sequence": expected}


def run(folder):
    generate(folder)
    profiles = {}
    for name, switch in SWITCHES.items():
        carrier = cuts((folder / f"{name}-carrier.svg").read_text())
        keeper = cuts((folder / f"{name}-keeper.svg").read_text())
        result = inspect(name == "B3F-1000", carrier, keeper)
        assert result["passes_envelope"], (name, result)
        undersized = cuts(cutfile(switch, keeper=True, aperture_allowance=1.2))
        rejected = inspect(name == "B3F-1000", carrier, undersized, per_axis_error=0.30)
        assert not rejected["passes_envelope"]
        result["rejected_initial_gap_mm"] = rejected["worst_radial_gap_mm"]
        profiles[name] = result
    summary = {"holders": profiles, "controller": exercise(folder)}
    (folder / "results.json").write_text(json.dumps(summary, indent=2, sort_keys=True)+"\n", encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true", help="regenerate in a temporary directory and compare outputs")
    args = parser.parse_args()
    if args.verify:
        with TemporaryDirectory() as tmp:
            folder = Path(tmp)
            run(folder)
            for f in folder.iterdir():
                if f.read_bytes() != (HERE / f.name).read_bytes():
                    raise SystemExit(f"Stale output: {f.name}")
            print("P028 exported profiles and controller replay verified")
    else:
        run(HERE)

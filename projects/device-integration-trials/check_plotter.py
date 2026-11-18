"""Replay the baseline and candidate in the HS simulator and compare drawn segments."""

import argparse
from collections import Counter
import hashlib
import json
from math import dist, isclose
from pathlib import Path
import sys
from zipfile import ZipFile

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ender3-penplotter-digital" / "scripts"))
from simulate import replay


def measure(code, lift):
    steps = replay(code, lift)
    ink = Counter()
    travel = drawing = 0.0
    for step in steps:
        a, b = [(step["x" + i], step["y" + i]) for i in ("0", "1")]
        if step["drawing"]:
            ink[a, b] += 1
            drawing += dist(a, b)
        elif a != b:
            if (step["z0"], step["z1"]) != (lift, lift):
                raise ValueError("Travel recorded before lifting pen")
            travel += dist(a, b)
    return steps, ink, {"pen_down_mm": drawing, "pen_up_mm": travel,
                        "ideal_feed_time_s": sum(step["duration_s"] for step in steps)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("study", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("preview", type=Path)
    args = parser.parse_args()
    with ZipFile(args.study) as archive:
        source = archive.read("simulation/example.gcode").decode()
        req = json.loads(archive.read("requirements.json"))
        reference = json.loads(archive.read("reports/simulation.json"))["metrics"]
    before, drawn, original = measure(source, req["pen_lift_mm"])
    after, repeated, optimized = measure(args.candidate.read_text(), req["pen_lift_mm"])
    if (not isclose(original["pen_up_mm"], reference["travel_length_mm"])
            or drawn != repeated or optimized["pen_up_mm"] >= original["pen_up_mm"]):
        raise ValueError("Route changed the drawing, reference result, or failed to improve travel")
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.6), sharex=True, sharey=True)
    for ax, rows, metrics, title in zip(axes, [before, after], [original, optimized],
                                        ["Original stroke order", "vpype stroke order"]):
        for row in rows:
            xy = [[row[axis + i] for i in ("0","1")] for axis in ("x","y")]
            ax.plot(*xy, color="#17425c" if row["drawing"] else "#c76a2d",
                    linestyle="-" if row["drawing"] else "--", linewidth=1.25)
        ax.set_aspect("equal")
        ax.set_title(f"{title}\n{metrics['pen_up_mm']:.1f} mm pen-up travel")
        ax.set_xlabel("Controller X (mm)")
    axes[0].set_ylabel("Controller Y (mm)")
    fig.suptitle("Ender-3 digital replay · solid drawing strokes, dashed pen-up moves")
    fig.tight_layout()
    fig.savefig(args.preview, dpi=150)
    print(json.dumps({"requirements": req, "original": original, "optimized": optimized,
                      "identical_directed_drawing_segments": drawn.total(),
                      "strokes": reference["stroke_count"],
                      "candidate_sha256": hashlib.sha256(args.candidate.read_bytes()).hexdigest(),
                      "study_sha256": hashlib.sha256(args.study.read_bytes()).hexdigest()}, indent=2))

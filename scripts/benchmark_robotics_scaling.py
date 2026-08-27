#!/usr/bin/env python3
"""Run the open-reference robotics scaling benchmark suite."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = Path(__file__).resolve().parent
sys.path = [str(SRC)] + [value for value in sys.path if Path(value).resolve() != SCRIPTS]

from hardware_splicer.robotics_benchmark import (  # noqa: E402
    evaluate_robotics_suite,
    load_robotics_benchmark,
)


def _markdown(report: dict) -> str:
    lines = [
        "# Robotics scaling benchmark",
        "",
        "Public repositories, documentation, and video discovery links are reference material only. "
        "They do not raise project authority above proposed/observed status.",
        "",
        "| Benchmark | Genre | Pressure | Stack coverage | Verdict | Detected archetype | Main gaps |",
        "|---|---|---:|---:|---|---|---|",
    ]
    for row in report["rows"]:
        gaps = ", ".join(row["gaps"][:5]) or "none"
        lines.append(
            f"| {row['benchmark_id']} | {row['robot_genre']} | {row['pressure_index']:.1f} | "
            f"{row['stack_coverage_score']:.1f} | {row['verdict']} | "
            f"{row['detected_archetype']} | {gaps} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- `pressure_index` estimates multidisciplinary robot complexity; it is not a safety rating.",
            "- `stack_coverage_score` measures structural representation in the current intake plan, not physical correctness.",
            "- `native_archetype_missing` means the robot was forced into a different or generic product family.",
            "- Video sources require timestamped observations and identity mapping before they can become governed evidence.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--fixtures",
        default=str(ROOT / "examples" / "robotics_benchmarks"),
        help="Directory containing benchmark JSON files.",
    )
    parser.add_argument(
        "--out",
        default=str(ROOT / ".cache" / "hardware-splicer" / "robotics_scaling"),
        help="Output directory.",
    )
    args = parser.parse_args()

    os.environ.setdefault("HARDWARE_SPLICER_OFFLINE_SALVAGE", "1")
    os.environ.setdefault("HARDWARE_SPLICER_OFFLINE_COMPOSE", "1")
    os.environ.setdefault("HARDWARE_SPLICER_SKIP_VISION_LIVE", "1")
    os.environ.setdefault("HARDWARE_SPLICER_QWEN_SALVAGE", "0")

    fixture_dir = Path(args.fixtures)
    fixtures = [load_robotics_benchmark(path) for path in sorted(fixture_dir.glob("*.json"))]
    if not fixtures:
        raise SystemExit(f"no robotics benchmark fixtures found in {fixture_dir}")

    report = evaluate_robotics_suite(fixtures)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "ROBOTICS_SCALING_REPORT.json"
    md_path = out_dir / "ROBOTICS_SCALING_REPORT.md"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    md_path.write_text(_markdown(report), encoding="utf-8")

    print(json.dumps(report, indent=2))
    print(f"json_report={json_path}")
    print(f"markdown_report={md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
